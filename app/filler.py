"""
Template filling orchestration (FR-6, FR-7, FR-8, NFR-2, NFR-3).

For a (matter, template, model) triple: ingest -> retrieve grounded passages ->
ask the local model to transcribe each blank with provenance -> validate
grounding -> assemble an immutable run record. Anything that cannot be grounded
in the case file is returned as NEEDS_REVIEW; the system never fabricates.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Dict, List

from . import ollama_client, prompts
from .ingest import IngestedDoc, ingest_folder, total_chars
from .models import FieldSpec, FilledField, FillResult, NEEDS_REVIEW, TemplateInfo
from .retrieval import auto_retriever

# Documents that extract to fewer than this many characters are almost certainly
# unreadable (scanned/image PDFs needing OCR) rather than genuinely empty.
_MIN_DOC_CHARS = 40

# Human-readable explanation for each needs-review reason (surfaced in the UI).
REASON_LABELS = {
    "no_context": "no matching passage retrieved",
    "model_blanked": "model found nothing to ground in the sources",
    "ungrounded": "value dropped — quote not found in sources",
    "missing_key": "model omitted this field",
    "model_unreachable": "model runtime unavailable",
    "no_documents": "no readable case text",
}


def _retrieval_query(field: FieldSpec) -> str:
    parts = [field.key, field.label]
    if field.instruction:
        parts.append(field.instruction)
    return " ".join(parts)


def _select_passages(fields, per_field: Dict[str, list], budget: int) -> List[dict]:
    """Interleave each field's top hits by rank so no field is starved of context.

    The previous strategy filled a single global pool field-by-field and then
    truncated it, which let the first few fields consume every slot and left the
    rest with no relevant passages at all. Round-robin by rank guarantees each
    field contributes its best passages before any field contributes its second.
    """
    seen = set()
    out: List[dict] = []
    rank = 0
    max_rank = max((len(v) for v in per_field.values()), default=0)
    while rank < max_rank and len(out) < budget:
        for f in fields:
            hits = per_field.get(f.key, [])
            if rank < len(hits):
                r = hits[rank]
                dedup = (r.document, r.text[:80])
                if dedup not in seen:
                    seen.add(dedup)
                    out.append({"document": r.document, "text": r.text})
                    if len(out) >= budget:
                        break
        rank += 1
    return out


def _is_grounded(quote: str, passages: List[str]) -> bool:
    """Anti-hallucination check (FR-8), tolerant of minor model paraphrase.

    A value is grounded if its supporting quote appears in a passage as a
    normalized substring, OR (for a quote of several content words) if at least
    three-quarters of its content tokens co-occur in a single passage. The
    fuzzy arm keeps near-verbatim quotes from being wrongly discarded while
    still rejecting fabricated values that don't track the source.
    """
    needle = " ".join(quote.lower().split())
    if not needle:
        return False
    hay = [" ".join(p.lower().split()) for p in passages]
    if any(needle in h for h in hay):
        return True
    q_tokens = [t for t in re.findall(r"[a-z0-9]+", needle) if len(t) > 2]
    if len(q_tokens) < 3:  # too short to fuzzy-match without risking a false positive
        return False
    q_set = set(q_tokens)
    for h in hay:
        h_set = set(re.findall(r"[a-z0-9]+", h))
        if len(q_set & h_set) / len(q_set) >= 0.75:
            return True
    return False


def _normalize_key(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _index_response(parsed, specs) -> dict:
    """Map each template field to the model's answer, tolerant of output shape.

    Models don't always return the agreed `{"fields":[{"key":...}]}`: some emit a
    flat `{key: value}` object, a bare list, or key each item by its label rather
    than its key. We collect items from any of these shapes and resolve each
    field by key first, then by label — so a well-meaning but off-schema response
    fills blanks instead of being silently dropped as "model omitted this field".
    """
    items: List[dict] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("fields"), list):
        items = [it for it in parsed["fields"] if isinstance(it, dict)]
    elif isinstance(parsed, list):
        items = [it for it in parsed if isinstance(it, dict)]
    elif isinstance(parsed, dict):
        for k, v in parsed.items():
            if k == "fields":
                continue
            if isinstance(v, dict):
                it = dict(v)
                it.setdefault("key", k)
                items.append(it)
            elif isinstance(v, (str, int, float)):
                items.append({"key": k, "value": v, "found": True})

    lookup: dict = {}
    for it in items:
        for alias in (it.get("key"), it.get("field"), it.get("name"), it.get("label")):
            if alias:
                lookup.setdefault(_normalize_key(alias), it)

    resolved: dict = {}
    for spec in specs:
        for cand in (spec.key, spec.label):
            it = lookup.get(_normalize_key(cand))
            if it is not None:
                resolved[spec.key] = it
                break
    return resolved


def _diagnostic_message(filled: List[FilledField], empty_docs: List[str], mode: str) -> str:
    """Explain *why* blanks were left for review, so 0/N is never a mystery."""
    parts: List[str] = []
    if empty_docs:
        shown = ", ".join(empty_docs[:5]) + ("…" if len(empty_docs) > 5 else "")
        parts.append(
            f"{len(empty_docs)} document(s) extracted no readable text "
            f"(likely scanned PDFs needing OCR): {shown}."
        )
    counts = Counter(f.review_reason for f in filled if not f.found and f.review_reason)
    if counts:
        breakdown = "; ".join(f"{REASON_LABELS.get(r, r)}: {n}" for r, n in counts.most_common())
        parts.append(f"Needs-review breakdown — {breakdown}.")
    if counts.get("no_context") and mode == "lexical":
        parts.append(
            "Retrieval is lexical; installing an embedding model "
            "(e.g. `ollama pull nomic-embed-text`) enables semantic matching."
        )
    return " ".join(parts)


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
    empty_docs = [d.filename for d in docs if len(d.text.strip()) < _MIN_DOC_CHARS]
    all_chunks = [c for d in docs for c in d.chunks]
    if not all_chunks:
        run.status = "error"
        hint = ""
        if empty_docs:
            hint = (
                f" {len(empty_docs)} file(s) extracted no readable text "
                f"(likely scanned PDFs needing OCR): {', '.join(empty_docs[:5])}."
            )
        run.message = "No readable case text found in the matter folder." + hint
        run.fields = [
            FilledField(key=f.key, label=f.label, value=NEEDS_REVIEW, found=False,
                        review_reason="no_documents")
            for f in template.fields
        ]
        run.filled_text = _assemble(template_text, run.fields, template.fields)
        return run.recount()

    retriever = auto_retriever(all_chunks)
    run.retrieval_mode = retriever.mode

    # Retrieve per field, then interleave by rank so every field gets context
    # (a single global pool let early fields starve the rest — a prime cause of
    # an all-needs-review result). Budget scales with the number of blanks.
    per_field = {f.key: retriever.retrieve(_retrieval_query(f), k=4) for f in template.fields}
    fields_with_context = {k for k, hits in per_field.items() if hits}
    budget = min(max(16, len(template.fields) * 2), 30)
    passages = _select_passages(template.fields, per_field, budget)
    passages_by_doc = {f"{i}": p["text"] for i, p in enumerate(passages)}

    # --- model inference (FR-6, FR-7, NFR-2) -----------------------------
    system = prompts.SYSTEM_PROMPT
    user = prompts.build_user_prompt(template.fields, passages)
    try:
        parsed, elapsed, raw = ollama_client.generate_json(model, system, user, temperature=0.0)
        run.inference_seconds = round(elapsed, 3)
        run.raw_model_output = (raw or "")[:4000] or None
    except ollama_client.OllamaUnavailable as exc:
        # Degrade gracefully (NFR-3): mark everything for review, never crash.
        kind = getattr(exc, "kind", "error")
        run.status = "model_timeout" if kind == "timeout" else "model_unreachable"
        run.message = str(exc)
        print(f"[fill] inference failed (kind={kind}) model={model}: {exc}")
        run.fields = [
            FilledField(key=f.key, label=f.label, value=NEEDS_REVIEW, found=False,
                        review_reason="model_unreachable")
            for f in template.fields
        ]
        run.filled_text = _assemble(template_text, run.fields, template.fields)
        return run.recount()

    # --- assemble + validate provenance (FR-7, FR-8) ----------------------
    # Classify every blank's outcome so an all-needs-review result is explained:
    # the field can be filled, or left for review because the model omitted it,
    # blanked it, had no retrieved context, or gave a value we couldn't ground.
    resolved = _index_response(parsed, template.fields)
    haystack = list(passages_by_doc.values())
    filled: List[FilledField] = []
    for spec in template.fields:
        item = resolved.get(spec.key)
        if item is None:
            filled.append(FilledField(key=spec.key, label=spec.label, value=NEEDS_REVIEW,
                                      found=False, review_reason="missing_key"))
            continue

        value = str(item.get("value", NEEDS_REVIEW)).strip()
        model_filled = (
            bool(item.get("found", False)) and value and value.upper() != NEEDS_REVIEW
        )
        if not model_filled:
            reason = "no_context" if spec.key not in fields_with_context else "model_blanked"
            filled.append(FilledField(key=spec.key, label=spec.label, value=NEEDS_REVIEW,
                                      found=False, review_reason=reason))
            continue

        quote = (item.get("source_quote") or "").strip()
        if quote and _is_grounded(quote, haystack):
            filled.append(FilledField(
                key=spec.key, label=spec.label, value=value, found=True,
                confidence=_as_float(item.get("confidence")),
                source_quote=quote,
                source_document=(item.get("source_document") or None),
                review_reason="filled",
            ))
        else:
            filled.append(FilledField(key=spec.key, label=spec.label, value=NEEDS_REVIEW,
                                      found=False, review_reason="ungrounded"))

    run.fields = filled
    run.message = _diagnostic_message(filled, empty_docs, run.retrieval_mode) or None
    # If the model produced output but we couldn't use any of it, show a snippet
    # so the mismatch is visible rather than a silent 0/N.
    if not any(f.found for f in filled) and run.raw_model_output:
        snippet = re.sub(r"\s+", " ", run.raw_model_output).strip()[:240]
        run.message = (run.message or "") + f" Raw model output (first 240 chars): {snippet}"
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
