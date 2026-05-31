"""
Local persistence (FR-16, FR-17).

Run records are stored locally in human-readable JSON. Template-style
assignments (FR-12) and admin field flags (FR-13) are persisted in a small
local config / the run records themselves. Nothing leaves the host (NFR-1).
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from .models import FillResult

DATA_DIR = os.environ.get(
    "VERBATIM_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)
MATTERS_DIR = os.path.join(DATA_DIR, "matters")
TEMPLATES_DIR = os.path.join(DATA_DIR, "templates")
RUNS_DIR = os.path.join(DATA_DIR, "runs")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")


def _ensure_dirs() -> None:
    for d in (DATA_DIR, MATTERS_DIR, TEMPLATES_DIR, RUNS_DIR):
        os.makedirs(d, exist_ok=True)


# --------------------------------------------------------------------------- #
# Config: template -> style mapping (FR-12)
# --------------------------------------------------------------------------- #
def load_config() -> dict:
    _ensure_dirs()
    if not os.path.exists(CONFIG_PATH):
        return {"template_styles": {}}
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError:
            return {"template_styles": {}}


def save_config(cfg: dict) -> None:
    _ensure_dirs()
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)


def get_template_style(template_id: str) -> Optional[str]:
    return load_config().get("template_styles", {}).get(template_id)


def set_template_style(template_id: str, style: str) -> None:
    cfg = load_config()
    cfg.setdefault("template_styles", {})[template_id] = style
    save_config(cfg)


# --------------------------------------------------------------------------- #
# Run records (FR-16, FR-17)
# --------------------------------------------------------------------------- #
def save_run(result: FillResult) -> None:
    _ensure_dirs()
    path = os.path.join(RUNS_DIR, f"{result.run_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(result.model_dump(), fh, indent=2)


def load_run(run_id: str) -> Optional[FillResult]:
    path = os.path.join(RUNS_DIR, f"{run_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return FillResult(**json.load(fh))


def list_runs() -> List[FillResult]:
    _ensure_dirs()
    runs: List[FillResult] = []
    for name in os.listdir(RUNS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(RUNS_DIR, name), "r", encoding="utf-8") as fh:
                runs.append(FillResult(**json.load(fh)))
        except Exception:
            continue
    runs.sort(key=lambda r: r.timestamp, reverse=True)
    return runs


def flag_field(run_id: str, field_key: str, flag: Optional[str]) -> Optional[FillResult]:
    """Flag a single filled field correct/incorrect (FR-13). flag in {correct, incorrect, None}."""
    result = load_run(run_id)
    if result is None:
        return None
    for f in result.fields:
        if f.key == field_key:
            f.admin_flag = flag
            break
    save_run(result)
    return result
