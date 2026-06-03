"""
Matter and template enumeration from the local data store.

Today the storage layer is folder-based (one folder per matter, one file per
template). It is intentionally abstracted so a DMS adapter (§12) can later
substitute the source without changing the rest of the system.
"""
from __future__ import annotations

import hashlib
import os
import re
from typing import List, Optional

from .ingest import SUPPORTED_EXTS, ingest_folder, total_chars
from .models import CaseInfo, TemplateInfo
from .store import MATTERS_DIR, TEMPLATES_DIR, get_template_style
from .templates import prepare_template, read_template_text

TEMPLATE_EXTS = {".docx", ".txt", ".md"}


def _stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


# --------------------------------------------------------------------------- #
# Filename / folder sanitization (no path traversal, predictable names)
# --------------------------------------------------------------------------- #
def safe_filename(name: str) -> str:
    """Reduce an uploaded filename to a safe basename."""
    name = os.path.basename(name or "").strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "", name)
    name = name.lstrip(".") or "file"
    return name


def safe_matter_folder(name: str) -> str:
    """Derive a safe matter folder name from a display name."""
    name = (name or "").strip()
    name = re.sub(r"[^A-Za-z0-9._ -]", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    return name or "Untitled_Matter"


# --------------------------------------------------------------------------- #
# Matters
# --------------------------------------------------------------------------- #
def matter_folder(matter_id: str) -> Optional[str]:
    for name in os.listdir(MATTERS_DIR) if os.path.isdir(MATTERS_DIR) else []:
        folder = os.path.join(MATTERS_DIR, name)
        if os.path.isdir(folder) and _stable_id(name) == matter_id:
            return folder
    return None


def list_matters(light: bool = True) -> List[CaseInfo]:
    matters: List[CaseInfo] = []
    if not os.path.isdir(MATTERS_DIR):
        return matters
    for name in sorted(os.listdir(MATTERS_DIR)):
        folder = os.path.join(MATTERS_DIR, name)
        if not os.path.isdir(folder):
            continue
        files = [
            f
            for f in sorted(os.listdir(folder))
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
        ]
        info = CaseInfo(id=_stable_id(name), name=name.replace("_", " "), documents=files)
        if not light:
            docs = ingest_folder(folder)
            info.char_count = total_chars(docs)
        matters.append(info)
    return matters


def get_matter(matter_id: str) -> Optional[CaseInfo]:
    for m in list_matters(light=False):
        if m.id == matter_id:
            return m
    return None


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
def template_path(template_id: str) -> Optional[str]:
    if not os.path.isdir(TEMPLATES_DIR):
        return None
    for name in os.listdir(TEMPLATES_DIR):
        if os.path.splitext(name)[1].lower() not in TEMPLATE_EXTS:
            continue
        if _stable_id(name) == template_id:
            return os.path.join(TEMPLATES_DIR, name)
    return None


def _build_template_info(filename: str) -> TemplateInfo:
    path = os.path.join(TEMPLATES_DIR, filename)
    kind, text = read_template_text(path)
    _canonical, fields = prepare_template(text)
    tid = _stable_id(filename)
    name = os.path.splitext(filename)[0].replace("_", " ").title()
    return TemplateInfo(
        id=tid,
        name=name,
        filename=filename,
        kind=kind,
        fields=fields,
        style=get_template_style(tid),
    )


def list_templates() -> List[TemplateInfo]:
    templates: List[TemplateInfo] = []
    if not os.path.isdir(TEMPLATES_DIR):
        return templates
    for name in sorted(os.listdir(TEMPLATES_DIR)):
        if os.path.splitext(name)[1].lower() not in TEMPLATE_EXTS:
            continue
        try:
            templates.append(_build_template_info(name))
        except Exception as exc:
            print(f"[catalog] could not parse template {name}: {exc}")
    return templates


def get_template(template_id: str) -> Optional[TemplateInfo]:
    path = template_path(template_id)
    if not path:
        return None
    return _build_template_info(os.path.basename(path))


# --------------------------------------------------------------------------- #
# Write operations: create matters, upload case documents and templates (FR-1)
# --------------------------------------------------------------------------- #
class CatalogError(ValueError):
    """Raised on an invalid upload (unsupported type, name clash, etc.)."""


def create_matter(name: str) -> CaseInfo:
    """Create a new (empty) matter folder. Idempotent on an existing name."""
    folder_name = safe_matter_folder(name)
    folder = os.path.join(MATTERS_DIR, folder_name)
    os.makedirs(folder, exist_ok=True)
    return CaseInfo(id=_stable_id(folder_name), name=folder_name.replace("_", " "), documents=[])


def add_document(matter_id: str, filename: str, data: bytes) -> CaseInfo:
    """Save an uploaded case document into a matter folder (FR-1)."""
    folder = matter_folder(matter_id)
    if folder is None:
        raise CatalogError("Matter not found")
    fname = safe_filename(filename)
    if os.path.splitext(fname)[1].lower() not in SUPPORTED_EXTS:
        raise CatalogError(
            f"Unsupported document type. Allowed: {', '.join(sorted(SUPPORTED_EXTS))}"
        )
    with open(os.path.join(folder, fname), "wb") as fh:
        fh.write(data)
    return get_matter(matter_id)  # refreshed, with char count


def delete_document(matter_id: str, filename: str) -> CaseInfo:
    folder = matter_folder(matter_id)
    if folder is None:
        raise CatalogError("Matter not found")
    path = os.path.join(folder, safe_filename(filename))
    if os.path.isfile(path):
        os.remove(path)
    return get_matter(matter_id)


def delete_matter(matter_id: str) -> None:
    import shutil

    folder = matter_folder(matter_id)
    if folder is None:
        raise CatalogError("Matter not found")
    shutil.rmtree(folder, ignore_errors=True)


def add_template(filename: str, data: bytes) -> TemplateInfo:
    """Save an uploaded firm template (FR-4 parsing happens on read)."""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    fname = safe_filename(filename)
    if os.path.splitext(fname)[1].lower() not in TEMPLATE_EXTS:
        raise CatalogError(
            f"Unsupported template type. Allowed: {', '.join(sorted(TEMPLATE_EXTS))}"
        )
    with open(os.path.join(TEMPLATES_DIR, fname), "wb") as fh:
        fh.write(data)
    return _build_template_info(fname)


def delete_template(template_id: str) -> None:
    path = template_path(template_id)
    if path is None:
        raise CatalogError("Template not found")
    if os.path.isfile(path):
        os.remove(path)
