"""
The grounding / anti-hallucination contract (FR-6, FR-7, FR-8, NFR-3).

These are the tests that matter most: the system must keep grounded values,
downgrade ungrounded ones, and never fabricate — including when the model
runtime is unreachable. We inject fake extractors so this is exercised offline
and deterministically (no live model required).
"""
import pytest

from app import catalog, ollama_client
from app.filler import fill
from app.models import NEEDS_REVIEW
from app.templates import prepare_template, read_template_text


def _probate_setup():
    template = next(t for t in catalog.list_templates() if t.filename == "probate_petition.txt")
    matter = next(m for m in catalog.list_matters() if m.name == "Estate of Williams")
    folder = catalog.matter_folder(matter.id)
    _k, raw = read_template_text(catalog.template_path(template.id))
    canonical, _f = prepare_template(raw)
    return folder, matter, template, canonical


def _extractor_grounded(model, fields, passages, temperature):
    """Return, for every field, a value whose quote is genuinely in a passage."""
    out = []
    for i, f in enumerate(fields):
        passage = passages[i % len(passages)]
        quote = passage["text"].split("\n")[0][:80]
        out.append({
            "key": f.key, "value": "Harold E. Williams", "found": True,
            "confidence": 0.9, "source_quote": quote,
            "source_document": passage["document"],
        })
    return {"fields": out}, 0.01


def _extractor_hallucinated(model, fields, passages, temperature):
    """Claim a value with a quote that appears in NO source passage."""
    return {
        "fields": [
            {"key": f.key, "value": "TOTALLY MADE UP", "found": True,
             "confidence": 0.99, "source_quote": "this exact text is not in any source document anywhere",
             "source_document": "phantom.txt"}
            for f in fields
        ]
    }, 0.01


def test_grounded_values_are_kept():
    folder, matter, template, canonical = _probate_setup()
    r = fill(folder, matter.id, matter.name, template, canonical, "fake", extractor=_extractor_grounded)
    assert r.status == "ok"
    assert r.blanks_filled > 0
    for f in r.fields:
        if f.found:
            assert f.source_quote and f.source_document


def test_ungrounded_values_are_downgraded_not_trusted():
    folder, matter, template, canonical = _probate_setup()
    r = fill(folder, matter.id, matter.name, template, canonical, "fake", extractor=_extractor_hallucinated)
    # Every hallucinated field must be downgraded to NEEDS_REVIEW — never filled.
    assert r.blanks_filled == 0
    assert r.blanks_needs_review == r.blanks_total
    assert all(f.value == NEEDS_REVIEW and not f.found for f in r.fields)
    assert "TOTALLY MADE UP" not in r.filled_text


def test_unreachable_runtime_degrades_gracefully():
    folder, matter, template, canonical = _probate_setup()

    def _down(model, fields, passages, temperature):
        raise ollama_client.OllamaUnavailable("down", kind="connection")

    r = fill(folder, matter.id, matter.name, template, canonical, "fake", extractor=_down)
    assert r.status == "model_unreachable"
    assert r.blanks_filled == 0
    assert r.blanks_needs_review == r.blanks_total
    assert "NEEDS REVIEW" in r.filled_text


def test_timeout_is_distinguished_from_unreachable():
    folder, matter, template, canonical = _probate_setup()

    def _slow(model, fields, passages, temperature):
        raise ollama_client.OllamaUnavailable("slow", kind="timeout")

    r = fill(folder, matter.id, matter.name, template, canonical, "fake", extractor=_slow)
    assert r.status == "model_timeout"
