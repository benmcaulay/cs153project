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
        '{"fields": [...]}',
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


def _run_with(tmp_path, monkeypatch, fake):
    monkeypatch.setattr(ollama_client, "has_embeddings_model", lambda: None)
    monkeypatch.setattr(ollama_client, "generate_json", fake)
    folder = os.path.join(tmp_path, "Roe")
    os.makedirs(folder)
    with open(os.path.join(folder, "intake.txt"), "w") as fh:
        fh.write(_DOC)
    template = TemplateInfo(id="t1", name="Test", filename="t.md", kind="md",
                            fields=templates.detect_fields(_TEMPLATE))
    return filler.fill(folder, "m1", "Roe", template, _TEMPLATE, "fake:latest")


def test_flat_dict_response_shape_is_grounded_by_value(tmp_path, monkeypatch):
    # Models often return {key: value} with no quote. The value itself ("Jane
    # Roe") appears in the source, so it should be grounded and filled.
    def fake(model, system, prompt, temperature=0.0):
        return ({"client_name": "Jane Roe"}, 0.5, '{"client_name": "Jane Roe"}')
    run = _run_with(tmp_path, monkeypatch, fake)
    cn = next(f for f in run.fields if f.key == "client_name")
    assert cn.found and cn.value == "Jane Roe"
    assert cn.source_document  # provenance located from the source


def test_value_not_in_sources_is_dropped(tmp_path, monkeypatch):
    # A value the model invented (not present in the case file) must NOT fill.
    def fake(model, system, prompt, temperature=0.0):
        return ({"client_name": "Nonexistent Person"}, 0.5, "{}")
    run = _run_with(tmp_path, monkeypatch, fake)
    cn = next(f for f in run.fields if f.key == "client_name")
    assert not cn.found
    assert cn.review_reason == "ungrounded"


def test_label_keyed_response_is_matched(tmp_path, monkeypatch):
    # Model keyed by label ("Client Name") with a grounded quote -> should fill.
    def fake(model, system, prompt, temperature=0.0):
        return (
            {"fields": [{"key": "Client Name", "value": "Jane Roe", "found": True,
                         "source_quote": "Our client is Jane Roe", "source_document": "intake.txt"}]},
            0.5, "ok",
        )
    run = _run_with(tmp_path, monkeypatch, fake)
    cn = next(f for f in run.fields if f.key == "client_name")
    assert cn.found and cn.value == "Jane Roe"


def test_unparseable_response_surfaces_raw_snippet(tmp_path, monkeypatch):
    def fake(model, system, prompt, temperature=0.0):
        return ({"fields": []}, 0.5, "the model rambled and produced no usable JSON here")
    run = _run_with(tmp_path, monkeypatch, fake)
    assert run.blanks_filled == 0
    assert "Raw model output" in (run.message or "")
    assert run.raw_model_output


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


def test_stub_response_explains_context_window_not_just_raw(tmp_path, monkeypatch):
    """A near-empty JSON stub ('{') is the signature of a truncated/overflowed
    prompt — the diagnostic should say so, not just print the bare '{'."""
    def fake(model, system, prompt, temperature=0.0):
        return ({"fields": []}, 0.5, "{")

    run = _run_with(tmp_path, monkeypatch, fake)
    assert run.blanks_filled == 0
    msg = run.message or ""
    assert "context" in msg.lower()
    assert "VERBATIM_NUM_CTX" in msg
    # it must NOT degrade to the cryptic raw-snippet branch for a stub
    assert "Raw model output (first 240 chars): {" not in msg


def test_rambling_response_still_shows_raw_snippet(tmp_path, monkeypatch):
    """A substantive but off-schema response keeps the raw-snippet diagnostic
    (this is the non-overflow case and must not be misclassified)."""
    def fake(model, system, prompt, temperature=0.0):
        return ({"fields": []}, 0.5, "the model rambled and produced no usable JSON here")

    run = _run_with(tmp_path, monkeypatch, fake)
    assert "Raw model output" in (run.message or "")


def test_adaptive_num_ctx_scales_and_clamps(monkeypatch):
    # Floor for a small prompt; powers-of-two up; clamped to the configured max.
    monkeypatch.setattr(ollama_client, "NUM_CTX", 8192)
    monkeypatch.setattr(ollama_client, "NUM_CTX_MAX", 32768)
    assert ollama_client.adaptive_num_ctx("sys", "tiny") == 8192
    big = "x" * (40000 * 4)  # ~40k tokens of prompt
    assert ollama_client.adaptive_num_ctx("sys", big) == 32768  # clamped to max
    mid = "x" * (10000 * 4)  # ~10k tokens -> next step up from 8192
    assert ollama_client.adaptive_num_ctx("sys", mid) == 16384
