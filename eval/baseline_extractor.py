"""
A transparent, rule-based extractor used as a *reproducible baseline* engine for
the evaluation harness.

This is deliberately NOT a language model. It is a label-anchored extractor: it
reads the retrieved passages, finds ``Label: value`` lines, and matches each
template blank to the best-overlapping label. It exists so the evaluation
instrument (eval/run_eval.py) and the grounding/anti-hallucination contract can
be exercised and measured **without a live Ollama model**, deterministically, in
CI. A real local LLM is plug-compatible: it implements the same extractor
signature and is selected with ``--engine ollama:<model>``.

Crucially, the baseline honors the same rule the system asks of the LLM: it only
emits a value it can quote verbatim from a source passage, and returns
NEEDS_REVIEW otherwise. That makes its fabrication rate 0 by construction —
which is precisely the property the eval is designed to verify is preserved
end-to-end (retrieval -> extraction -> grounding validation).
"""
from __future__ import annotations

import re
import time
from typing import List, Tuple

from app.models import FieldSpec, NEEDS_REVIEW

_STOP = {
    "the", "a", "an", "of", "at", "in", "on", "to", "for", "and", "or", "by",
    "is", "was", "no", "our", "client", "matter", "date", "name",
}
# A "Label: value" or "Label - value" line.
_LABELED = re.compile(r"^\s*(?P<label>[A-Za-z][A-Za-z0-9 .,'#/()-]{1,48}?)\s*[:\-]\s*(?P<value>\S.*\S|\S)\s*$")


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOP and len(t) > 1}


def _clean_value(value: str) -> str:
    # Drop a trailing parenthetical role like "(Defendant)" and surrounding noise.
    value = re.sub(r"\s*\((?:defendant|plaintiff|client)\)\s*$", "", value, flags=re.I)
    return value.strip().strip(".").strip()


def extract(
    model: str, fields: List[FieldSpec], passages: List[dict], temperature: float
) -> Tuple[dict, float]:
    """Match the ``Extractor`` signature used by ``app.filler.fill``."""
    start = time.perf_counter()

    # Collect every labeled line across passages, with its source document.
    labeled: List[dict] = []
    for p in passages:
        doc = p.get("document", "unknown")
        for line in p.get("text", "").split("\n"):
            m = _LABELED.match(line)
            if not m:
                continue
            value = _clean_value(m.group("value"))
            if not value:
                continue
            labeled.append(
                {
                    "label_tokens": _tokens(m.group("label")),
                    "value": value,
                    "quote": line.strip(),
                    "document": doc,
                }
            )

    out_fields = []
    for f in fields:
        ftoks = _tokens(f.key.replace("_", " ")) | _tokens(f.label)
        best = None
        best_score = 0
        for cand in labeled:
            score = len(ftoks & cand["label_tokens"])
            if score > best_score:
                best_score, best = score, cand
        if best is not None and best_score >= 1:
            out_fields.append(
                {
                    "key": f.key,
                    "value": best["value"],
                    "found": True,
                    "confidence": round(min(0.5 + 0.2 * best_score, 0.95), 2),
                    "source_quote": best["quote"],
                    "source_document": best["document"],
                }
            )
        else:
            # The baseline refuses to guess — the system's core thesis.
            out_fields.append(
                {
                    "key": f.key,
                    "value": NEEDS_REVIEW,
                    "found": False,
                    "confidence": 0.0,
                    "source_quote": "",
                    "source_document": "",
                }
            )

    elapsed = time.perf_counter() - start
    return {"fields": out_fields}, elapsed
