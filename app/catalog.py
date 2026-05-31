"""
Matter and template enumeration from the local data store.

Today the storage layer is folder-based (one folder per matter, one file per
template). It is intentionally abstracted so a DMS adapter (§12) can later
substitute the source without changing the rest of the system.
"""
from __future__ import annotations

import hashlib
import os
from typing import List, Optional

from .ingest import SUPPORTED_EXTS, ingest_folder, total_chars
from .models import CaseInfo, TemplateInfo
from .store import MATTERS_DIR, TEMPLATES_DIR, get_template_style
from .templates import detect_fields, read_template_text

TEMPLATE_EXTS = {".docx", ".txt", ".md"}


def _stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


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
    tid = _stable_id(filename)
    name = os.path.splitext(filename)[0].replace("_", " ").title()
    return TemplateInfo(
        id=tid,
        name=name,
        filename=filename,
        kind=kind,
        fields=detect_fields(text),
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
