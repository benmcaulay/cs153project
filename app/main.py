"""
Verbatim HTTP API (FastAPI).

Binds the local-only pipeline to two interface surfaces:
  - Attorney Workspace  : matters, templates, models, fill, export
  - Developer Console    : model enumeration, style assignment, runs, flagging, report

The only outbound network call anywhere in this app is to the Ollama runtime on
the local host (NFR-1). There is no telemetry.
"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import catalog, ollama_client, reporting
from .export import export_docx
from .filler import fill as run_fill
from .models import CaseInfo, FillResult, ModelStyleStats, TemplateInfo
from .store import flag_field, list_runs, load_run, set_template_style
from .templates import read_template_text

app = FastAPI(title="Verbatim", description="Privacy-preserving local legal template assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prototype runs on a trusted local host only (§15)
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Health / runtime status (NFR-3)
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    available = ollama_client.is_available()
    return {
        "ok": True,
        "ollama_available": available,
        "ollama_host": ollama_client.OLLAMA_HOST,
    }


# --------------------------------------------------------------------------- #
# Attorney Workspace
# --------------------------------------------------------------------------- #
@app.get("/api/matters", response_model=List[CaseInfo])
def get_matters():
    return catalog.list_matters(light=True)


@app.get("/api/templates", response_model=List[TemplateInfo])
def get_templates():
    return catalog.list_templates()


@app.get("/api/models")
def get_models():
    """Enumerate installed local models (FR-11), degrading gracefully (NFR-3)."""
    try:
        return {"available": True, "models": ollama_client.list_models()}
    except ollama_client.OllamaUnavailable as exc:
        return {"available": False, "models": [], "message": str(exc)}


class FillRequest(BaseModel):
    matter_id: str
    template_id: str
    model: str


@app.post("/api/fill", response_model=FillResult)
def post_fill(req: FillRequest):
    matter = catalog.get_matter(req.matter_id)
    folder = catalog.matter_folder(req.matter_id)
    template = catalog.get_template(req.template_id)
    if matter is None or folder is None:
        raise HTTPException(404, "Matter not found")
    if template is None:
        raise HTTPException(404, "Template not found")

    path = catalog.template_path(req.template_id)
    _kind, template_text = read_template_text(path)

    result = run_fill(
        matter_folder=folder,
        matter_id=matter.id,
        matter_name=matter.name,
        template=template,
        template_text=template_text,
        model=req.model,
    )
    # Persist as an immutable run record (FR-16, FR-17)
    from .store import save_run

    save_run(result)
    return result


@app.post("/api/export/{run_id}")
def export_run(run_id: str):
    result = load_run(run_id)
    if result is None:
        raise HTTPException(404, "Run not found")
    data = export_docx(result.template_name, result.filled_text, result.fields)
    filename = f"{result.template_name.replace(' ', '_')}_filled.docx"
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --------------------------------------------------------------------------- #
# Developer Console
# --------------------------------------------------------------------------- #
@app.get("/api/runs", response_model=List[FillResult])
def get_runs():
    return list_runs()


@app.get("/api/runs/{run_id}", response_model=FillResult)
def get_run(run_id: str):
    result = load_run(run_id)
    if result is None:
        raise HTTPException(404, "Run not found")
    return result


class FlagRequest(BaseModel):
    field_key: str
    flag: Optional[str] = None  # "correct" | "incorrect" | None


@app.post("/api/runs/{run_id}/flag", response_model=FillResult)
def post_flag(run_id: str, req: FlagRequest):
    if req.flag not in (None, "correct", "incorrect"):
        raise HTTPException(400, "flag must be 'correct', 'incorrect', or null")
    result = flag_field(run_id, req.field_key, req.flag)
    if result is None:
        raise HTTPException(404, "Run not found")
    return result


class StyleRequest(BaseModel):
    style: str


@app.post("/api/templates/{template_id}/style", response_model=TemplateInfo)
def post_style(template_id: str, req: StyleRequest):
    template = catalog.get_template(template_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    set_template_style(template_id, req.style)
    template.style = req.style
    return template


@app.get("/api/report", response_model=List[ModelStyleStats])
def get_report():
    return reporting.model_style_report()


# --------------------------------------------------------------------------- #
# Library: upload case documents and firm templates (FR-1, FR-4)
# --------------------------------------------------------------------------- #
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per file


class CreateMatterRequest(BaseModel):
    name: str


@app.post("/api/matters", response_model=CaseInfo)
def create_matter(req: CreateMatterRequest):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "Matter name is required")
    return catalog.create_matter(name)


@app.post("/api/matters/{matter_id}/documents", response_model=CaseInfo)
async def upload_documents(matter_id: str, files: List[UploadFile] = File(...)):
    info = None
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename} exceeds the 25 MB upload limit")
        try:
            info = catalog.add_document(matter_id, f.filename or "file", data)
        except catalog.CatalogError as exc:
            raise HTTPException(400, str(exc))
    if info is None:
        raise HTTPException(400, "No files were uploaded")
    return info


@app.delete("/api/matters/{matter_id}/documents/{filename}", response_model=CaseInfo)
def remove_document(matter_id: str, filename: str):
    try:
        return catalog.delete_document(matter_id, filename)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))


@app.delete("/api/matters/{matter_id}")
def remove_matter(matter_id: str):
    try:
        catalog.delete_matter(matter_id)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True}


@app.post("/api/templates", response_model=TemplateInfo)
async def upload_template(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Template exceeds the 25 MB upload limit")
    try:
        return catalog.add_template(file.filename or "template.md", data)
    except catalog.CatalogError as exc:
        raise HTTPException(400, str(exc))


@app.delete("/api/templates/{template_id}")
def remove_template(template_id: str):
    try:
        catalog.delete_template(template_id)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Serve the built frontend (the visual surfaces) if present
# --------------------------------------------------------------------------- #
_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
