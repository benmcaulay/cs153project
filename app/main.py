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

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import audit, catalog, ollama_client, reporting, security
from .export import export_docx
from .filler import fill as run_fill
from .models import CaseInfo, FillResult, ModelStyleStats, TemplateInfo
from .security import User, require_admin, require_attorney
from .store import flag_field, list_runs, load_run, set_template_style
from .templates import prepare_template, read_template_text

app = FastAPI(title="Verbatim", description="Privacy-preserving local legal template assistant")

# Session cookies require explicit origins; in production the backend serves
# the built UI from the same origin, so this only matters for `npm run dev`.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _bootstrap_auth() -> None:
    generated = security.bootstrap_admin()
    if generated:
        import sys

        print(
            "\n[verbatim] First run: created user 'admin' with password "
            f"{generated!r}\n[verbatim] Change it now:  python -m app.security passwd admin\n",
            file=sys.stderr,
        )


# --------------------------------------------------------------------------- #
# Authentication (see app/security.py; full model in docs/security.md)
# --------------------------------------------------------------------------- #
class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, response: Response):
    user = security.authenticate(req.username, req.password)
    audit.log(req.username, "auth.login", ok=user is not None)
    if user is None:
        raise HTTPException(401, "Invalid credentials (or account temporarily locked)")
    token = security.create_session(user)
    response.set_cookie(
        security.SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=security.SESSION_TTL_SECONDS,
    )
    return {"username": user.username, "role": user.role}


@app.post("/api/auth/logout")
def auth_logout(request: Request, response: Response):
    token = request.cookies.get(security.SESSION_COOKIE)
    user = security.get_session_user(token)
    security.destroy_session(token)
    response.delete_cookie(security.SESSION_COOKIE)
    if user:
        audit.log(user.username, "auth.logout")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(request: Request):
    """Session probe for the UI. Always 200 so the login screen can render."""
    if not security.auth_enabled():
        return {"authenticated": True, "auth_enabled": False, "username": "local", "role": "admin"}
    user = security.get_session_user(request.cookies.get(security.SESSION_COOKIE))
    if user is None:
        return {"authenticated": False, "auth_enabled": True}
    return {"authenticated": True, "auth_enabled": True, "username": user.username, "role": user.role}


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = security.ROLE_ATTORNEY


@app.get("/api/auth/users")
def get_users(user: User = Depends(require_admin)):
    return security.list_users()


@app.post("/api/auth/users")
def post_user(req: CreateUserRequest, user: User = Depends(require_admin)):
    try:
        created = security.create_user(req.username, req.password, req.role)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    audit.log(user.username, "auth.user_created", resource=f"{req.username} ({req.role})")
    return created


class SetUserStateRequest(BaseModel):
    disabled: bool


@app.post("/api/auth/users/{username}/state")
def post_user_state(username: str, req: SetUserStateRequest, user: User = Depends(require_admin)):
    if username == user.username and req.disabled:
        raise HTTPException(400, "You cannot disable your own account")
    try:
        security.set_disabled(username, req.disabled)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    audit.log(user.username, "auth.user_disabled" if req.disabled else "auth.user_enabled", resource=username)
    return {"ok": True}


@app.get("/api/audit")
def get_audit(user: User = Depends(require_admin)):
    """Recent audit records plus chain-integrity status (admin only)."""
    broken = audit.verify()
    return {"intact": broken is None, "broken_at_line": broken, "records": audit.read(limit=200)}


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
def get_matters(user: User = Depends(require_attorney)):
    return catalog.list_matters(light=True)


@app.get("/api/templates", response_model=List[TemplateInfo])
def get_templates(user: User = Depends(require_attorney)):
    return catalog.list_templates()


@app.get("/api/matters/{matter_id}/text")
def get_matter_text(matter_id: str, user: User = Depends(require_attorney)):
    """Extracted text of each case document — what the model actually sees.

    Lets an attorney inspect ingestion (e.g. confirm a scanned/encrypted PDF was
    read, or spot an empty one) right from the workspace."""
    from .ingest import ingest_folder

    folder = catalog.matter_folder(matter_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    docs = ingest_folder(folder)
    return [
        {"filename": d.filename, "chars": len(d.text.strip()), "text": d.text[:20000]}
        for d in docs
    ]


@app.get("/api/templates/{template_id}/text")
def get_template_text(template_id: str, user: User = Depends(require_attorney)):
    """The normalized template text (with detected {{blanks}}) for preview."""
    path = catalog.template_path(template_id)
    if path is None:
        raise HTTPException(status_code=404, detail="Template not found")
    _, text = read_template_text(path)
    return {"text": text}


@app.get("/api/models")
def get_models(user: User = Depends(require_attorney)):
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
def post_fill(req: FillRequest, user: User = Depends(require_attorney)):
    matter = catalog.get_matter(req.matter_id)
    folder = catalog.matter_folder(req.matter_id)
    template = catalog.get_template(req.template_id)
    if matter is None or folder is None:
        raise HTTPException(404, "Matter not found")
    if template is None:
        raise HTTPException(404, "Template not found")

    path = catalog.template_path(req.template_id)
    _kind, raw_text = read_template_text(path)
    # Fill the canonical (normalized) text so Tier-2-detected blanks in real
    # firm templates are actually substituted, not just counted.
    canonical_text, _fields = prepare_template(raw_text)

    result = run_fill(
        matter_folder=folder,
        matter_id=matter.id,
        matter_name=matter.name,
        template=template,
        template_text=canonical_text,
        model=req.model,
    )
    # Persist as an immutable run record (FR-16, FR-17)
    from .store import save_run

    save_run(result)
    audit.log(user.username, "fill.run", resource=f"{matter.name} × {template.name} × {req.model}")
    return result


@app.post("/api/export/{run_id}")
def export_run(run_id: str, user: User = Depends(require_attorney)):
    result = load_run(run_id)
    if result is None:
        raise HTTPException(404, "Run not found")
    data = export_docx(result.template_name, result.filled_text, result.fields)
    audit.log(user.username, "run.export", resource=run_id)
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
def get_runs(user: User = Depends(require_admin)):
    return list_runs()


@app.get("/api/runs/{run_id}", response_model=FillResult)
def get_run(run_id: str, user: User = Depends(require_admin)):
    result = load_run(run_id)
    if result is None:
        raise HTTPException(404, "Run not found")
    return result


class FlagRequest(BaseModel):
    field_key: str
    flag: Optional[str] = None  # "correct" | "incorrect" | None


@app.post("/api/runs/{run_id}/flag", response_model=FillResult)
def post_flag(run_id: str, req: FlagRequest, user: User = Depends(require_admin)):
    if req.flag not in (None, "correct", "incorrect"):
        raise HTTPException(400, "flag must be 'correct', 'incorrect', or null")
    result = flag_field(run_id, req.field_key, req.flag)
    if result is None:
        raise HTTPException(404, "Run not found")
    audit.log(user.username, "field.flag", resource=f"{run_id}/{req.field_key}={req.flag}")
    return result


class StyleRequest(BaseModel):
    style: str


@app.post("/api/templates/{template_id}/style", response_model=TemplateInfo)
def post_style(template_id: str, req: StyleRequest, user: User = Depends(require_admin)):
    template = catalog.get_template(template_id)
    if template is None:
        raise HTTPException(404, "Template not found")
    set_template_style(template_id, req.style)
    template.style = req.style
    audit.log(user.username, "template.style", resource=f"{template_id}={req.style}")
    return template


@app.get("/api/report", response_model=List[ModelStyleStats])
def get_report(user: User = Depends(require_admin)):
    return reporting.model_style_report()


# --------------------------------------------------------------------------- #
# Library: upload case documents and firm templates (FR-1, FR-4)
# --------------------------------------------------------------------------- #
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per file


class CreateMatterRequest(BaseModel):
    name: str


@app.post("/api/matters", response_model=CaseInfo)
def create_matter(req: CreateMatterRequest, user: User = Depends(require_attorney)):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(400, "Matter name is required")
    info = catalog.create_matter(name)
    audit.log(user.username, "matter.create", resource=info.name)
    return info


@app.post("/api/matters/{matter_id}/documents", response_model=CaseInfo)
async def upload_documents(
    matter_id: str,
    files: List[UploadFile] = File(...),
    user: User = Depends(require_attorney),
):
    info = None
    for f in files:
        data = await f.read()
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename} exceeds the 25 MB upload limit")
        try:
            info = catalog.add_document(matter_id, f.filename or "file", data)
        except catalog.CatalogError as exc:
            raise HTTPException(400, str(exc))
        audit.log(user.username, "document.upload", resource=f"{matter_id}/{f.filename}")
    if info is None:
        raise HTTPException(400, "No files were uploaded")
    return info


@app.delete("/api/matters/{matter_id}/documents/{filename}", response_model=CaseInfo)
def remove_document(matter_id: str, filename: str, user: User = Depends(require_attorney)):
    try:
        info = catalog.delete_document(matter_id, filename)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))
    audit.log(user.username, "document.delete", resource=f"{matter_id}/{filename}")
    return info


@app.delete("/api/matters/{matter_id}")
def remove_matter(matter_id: str, user: User = Depends(require_attorney)):
    try:
        catalog.delete_matter(matter_id)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))
    audit.log(user.username, "matter.delete", resource=matter_id)
    return {"ok": True}


@app.post("/api/templates", response_model=TemplateInfo)
async def upload_template(file: UploadFile = File(...), user: User = Depends(require_attorney)):
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Template exceeds the 25 MB upload limit")
    try:
        info = catalog.add_template(file.filename or "template.md", data)
    except catalog.CatalogError as exc:
        raise HTTPException(400, str(exc))
    audit.log(user.username, "template.upload", resource=info.name)
    return info


@app.delete("/api/templates/{template_id}")
def remove_template(template_id: str, user: User = Depends(require_attorney)):
    try:
        catalog.delete_template(template_id)
    except catalog.CatalogError as exc:
        raise HTTPException(404, str(exc))
    audit.log(user.username, "template.delete", resource=template_id)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Serve the built frontend (the visual surfaces) if present
# --------------------------------------------------------------------------- #
_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
