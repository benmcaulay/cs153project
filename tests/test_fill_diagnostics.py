"""
Integration tests for fill diagnostics + hardening (the "0/N, why?" problem).

Drives app.filler.fill end-to-end over a real temp matter folder with a fake
local model (no Ollama required), asserting that every needs-review blank is
classified with a precise reason and that grounding tolerates near-verbatim
quotes while still rejecting fabrications.
"""
from __future__ import annotations

import os

from app import filler, ollama_client, templates
from app.models import TemplateInfo


_DOC = (
    "INTAKE MEMO.\n"
    "Our client is Jane Roe. The incident occurred on March 3, 2024 in Oakland.\n"
)

_TEMPLATE = (
    "To {{client_name}}: the incident on {{incident_date}} at "
    "{{incident_location}}. Caption: {{matter_caption}}. Pending in {{court}}. "
    "Demand: {{demand_amount}}."
)


def _fake_generate_json(model, system, prompt, temperature=0.0):
    # client_name + incident_date are grounded; the rest exercise each reason.
    return (
        {
            "fields": [
                {"key": "client_name", "value": "Jane Roe", "found": True,
                 "source_quote": "Our client is Jane Roe", "source_document": "intake.txt"},
                {"key": "incident_date", "value": "March 3, 2024", "found": True,
                 # paraphrased quote (word order differs) -> fuzzy grounding should accept
                 "source_quote": "the incident occurred on March 3 2024 in Oakland",
                 "source_document": "intake.txt"},
                {"key": "incident_location", "value": "NEEDS_REVIEW", "found": False,
                 "source_quote": ""},
                {"key": "matter_caption", "value": "NEEDS_REVIEW", "found": False},
                # "court" deliberately omitted -> missing_key
                {"key": "demand_amount", "value": "$100,000", "found": True,
                 "source_quote": "we hereby demand one hundred thousand dollars in full",
                 "source_document": "nowhere.txt"},
            ]
        },
        1.23,
    )


def _run(tmp_path, monkeypatch):
    monkeypatch.setattr(ollama_client, "has_embeddings_model", lambda: None)
    monkeypatch.setattr(ollama_client, "generate_json", _fake_generate_json)

    folder = os.path.join(tmp_path, "Roe_v_City")
    os.makedirs(folder)
    with open(os.path.join(folder, "intake.txt"), "w") as fh:
        fh.write(_DOC)

    template = TemplateInfo(
        id="t1", name="Test", filename="t.md", kind="md",
        fields=templates.detect_fields(_TEMPLATE),
    )
    return filler.fill(folder, "m1", "Roe v City", template, _TEMPLATE, "fake:latest")


def test_reasons_are_classified(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch)
    reasons = {f.key: f.review_reason for f in run.fields}

    assert reasons["client_name"] == "filled"
    assert reasons["incident_date"] == "filled"      # fuzzy grounding accepted paraphrase
    assert reasons["incident_location"] == "model_blanked"  # had context, model blanked it
    assert reasons["matter_caption"] == "no_context"        # nothing retrieved
    assert reasons["court"] == "missing_key"                # model omitted it
    assert reasons["demand_amount"] == "ungrounded"         # value given, quote not in sources


def test_counts_and_message(tmp_path, monkeypatch):
    run = _run(tmp_path, monkeypatch)
    assert run.blanks_filled == 2
    assert run.blanks_total == 6
    assert run.status == "ok"
    # the diagnostic message explains the 4 needs-review blanks
    assert "Needs-review breakdown" in (run.message or "")
    assert "embedding model" in (run.message or "")  # lexical + no_context hint


def test_empty_documents_are_flagged(tmp_path, monkeypatch):
    monkeypatch.setattr(ollama_client, "has_embeddings_model", lambda: None)
    monkeypatch.setattr(ollama_client, "generate_json", _fake_generate_json)
    folder = os.path.join(tmp_path, "Scanned")
    os.makedirs(folder)
    with open(os.path.join(folder, "scan.txt"), "w") as fh:
        fh.write("   ")  # extracts to nothing, like a scanned PDF
    template = TemplateInfo(id="t", name="T", filename="t.md", kind="md",
                            fields=templates.detect_fields(_TEMPLATE))
    run = filler.fill(folder, "m", "Scanned", template, _TEMPLATE, "fake:latest")
    assert run.status == "error"
    assert "no readable text" in (run.message or "")
    assert all(f.review_reason == "no_documents" for f in run.fields)
