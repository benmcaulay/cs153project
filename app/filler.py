"""
Template filling orchestration (FR-6, FR-7, FR-8, NFR-2, NFR-3).

For a (matter, template, model) triple: ingest -> retrieve grounded passages ->
ask the local model to transcribe each blank with provenance -> validate
grounding -> assemble an immutable run record. Anything that cannot be grounded
in the case file is returned as NEEDS_REVIEW; the system never fabricates.
"""
from __future__ import annotations

import uuid
from typing import List

from . import ollama_client, prompts
from .ingest import IngestedDoc, ingest_folder, total_chars
from .models import FieldSpec, FilledField, FillResult, NEEDS_REVIEW, TemplateInfo
from .retrieval import auto_retriever


def _retrieval_query(field: FieldSpec) -> str:
    parts = [field.key, field.label]
    if field.instruction:
        parts.append(field.instruction)
    return " ".join(parts)


def _validate_grounding(field: FilledField, passages_by_doc: dict) -> FilledField:
    """
    Enforce the anti-hallucination contract (FR-8): a value only counts as
    grounded if its supporting quote actually appears in the retrieved source.
    Otherwise it is downgraded to NEEDS_REVIEW.
    """
    if not field.found or field.value.strip().upper() == NEEDS_REVIEW or not field.value.strip():
        field.found = False
        field.value = NEEDS_REVIEW
        field.source_quote = None
        field.source_document = None
        return field

    quote = (field.source_quote or "").strip()
    if not quote:
        field.found = False
        field.value = NEEDS_REVIEW
        field.source_document = None
        return field

    # The quote must be present (case-insensitively) in some retrieved passage.
    needle = " ".join(quote.lower().split())
    grounded = any(needle in " ".join(p.lower().split()) for p in passages_by_doc.values())
    if not grounded:
        field.found = False
        field.value = NEEDS_REVIEW
        field.source_quote = None
        field.source_document = None
    return field


def fill(
    matter_folder: str,
    matter_id: str,
    matter_name: str,
    template: TemplateInfo,
    template_text: str,
    model: str,
) -> FillResult:
    run = FillResult(
        run_id=uuid.uuid4().hex[:12],
        matter_id=matter_id,
        matter_name=matter_name,
        template_id=template.id,
        template_name=template.name,
        style=template.style,
        model=model,
        original_text=template_text,
    )

    if not template.fields:
        run.filled_text = template_text
        run.message = "Template has no detected blanks."
        return run.recount()

    # --- ingest + retrieve (FR-2, FR-3) -----------------------------------
    docs: List[IngestedDoc] = ingest_folder(matter_folder)
    all_chunks = [c for d in docs for c in d.chunks]
    if not all_chunks:
        run.status = "error"
        run.message = "No readable case documents found in the matter folder."
        run.fields = [
            FilledField(key=f.key, label=f.label, value=NEEDS_REVIEW, found=False)
            for f in template.fields
        ]
        run.filled_text = _assemble(template_text, run.fields, template.fields)
        return run.recount()

    retriever = auto_retriever(all_chunks)
    run.retrieval_mode = retriever.mode

    passages: List[dict] = []
    seen = set()
    for f in template.fields:
        for r in retriever.retrieve(_retrieval_query(f), k=4):
            key = (r.document, r.text[:80])
            if key in seen:
                continue
            seen.add(key)
            passages.append({"document": r.document, "text": r.text})
    passages = passages[:14]  # cap context for smaller models
    passages_by_doc = {f"{i}": p["text"] for i, p in enumerate(passages)}

    # --- model inference (FR-6, FR-7, NFR-2) -----------------------------
    system = prompts.SYSTEM_PROMPT
    user = prompts.build_user_prompt(template.fields, passages)
    try:
        parsed, elapsed = ollama_client.generate_json(model, system, user, temperature=0.0)
        run.inference_seconds = round(elapsed, 3)
    except ollama_client.OllamaUnavailable as exc:
        # Degrade gracefully (NFR-3): mark everything for review, never crash.
        run.status = "model_unreachable"
        run.message = f"Local model runtime unreachable: {exc}"
        run.fields = [
            FilledField(key=f.key, label=f.label, value=NEEDS_REVIEW, found=False)
            for f in template.fields
        ]
        run.filled_text = _assemble(template_text, run.fields, template.fields)
        return run.recount()

    # --- assemble + validate provenance (FR-7, FR-8) ----------------------
    by_key = {item.get("key"): item for item in parsed.get("fields", []) if isinstance(item, dict)}
    filled: List[FilledField] = []
    for spec in template.fields:
        item = by_key.get(spec.key, {})
        ff = FilledField(
            key=spec.key,
            label=spec.label,
            value=str(item.get("value", NEEDS_REVIEW)),
            found=bool(item.get("found", False)),
            confidence=_as_float(item.get("confidence")),
            source_quote=(item.get("source_quote") or None),
            source_document=(item.get("source_document") or None),
        )
        filled.append(_validate_grounding(ff, passages_by_doc))

    run.fields = filled
    run.filled_text = _assemble(template_text, filled, template.fields)
    return run.recount()


def _assemble(template_text: str, filled: List[FilledField], specs: List[FieldSpec]) -> str:
    from .templates import fill_text

    values = {f.key: (f.value if f.found else None) for f in filled}
    return fill_text(template_text, values)


def _as_float(v) -> float | None:
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None
