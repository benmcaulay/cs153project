"""
Verbatim prompt regime (SRS §9).

The system prompt is the primary artifact governing model behavior. Its single
job is to make a *left-blank field correct and a guessed field a defect*: the
model transcribes facts that are present verbatim in the supplied source
passages, and returns NEEDS_REVIEW for anything it cannot ground.
"""
from __future__ import annotations

from typing import List

from .models import FieldSpec, NEEDS_REVIEW

SYSTEM_PROMPT = f"""You are Verbatim, a meticulous legal transcription assistant.

You fill blanks in a firm-authored document template using ONLY the facts found
in the SOURCE PASSAGES provided to you from a single legal matter's case file.

ABSOLUTE RULES:
1. GROUNDING. Use only the SOURCE PASSAGES. Never use outside knowledge, never
   infer, never guess. If a value is not stated in the passages, you MUST return
   "{NEEDS_REVIEW}" for that field. A blank left for human review is CORRECT.
   A plausible-but-unsupported value is a DEFECT that can cause real legal harm.
2. FIDELITY. Transcribe proper nouns, party names, dates, monetary figures, and
   case/docket numbers EXACTLY as they appear in the source. Do not normalize,
   round, reformat, or "correct" them unless a field's instruction explicitly
   asks you to.
3. PROVENANCE. For every field you fill, copy a SHORT verbatim supporting quote
   (<= 200 characters) directly from the passage that supports the value, and
   name the source document it came from. If you cannot supply a real verbatim
   quote, the field is not grounded: return "{NEEDS_REVIEW}".
4. INSTRUCTIONS. If a field carries an authoring instruction (after a '|'),
   apply ONLY the formatting/selection it requests; it never licenses invention.
5. OUTPUT. Return a single JSON object and nothing else.

OUTPUT SCHEMA (return exactly this shape):
{{
  "fields": [
    {{
      "key": "<the field key>",
      "value": "<the extracted value, or {NEEDS_REVIEW}>",
      "found": <true if grounded, false if {NEEDS_REVIEW}>,
      "confidence": <number 0.0-1.0, your advisory self-assessment>,
      "source_quote": "<short verbatim quote, or empty string if not found>",
      "source_document": "<document name the quote came from, or empty string>"
    }}
  ]
}}
"""


def build_field_block(fields: List[FieldSpec]) -> str:
    """Render the list of blanks to fill, including any authoring instruction."""
    lines = []
    for f in fields:
        line = f'- key: "{f.key}"  (label: {f.label})'
        if f.instruction:
            line += f'  | instruction: {f.instruction}'
        lines.append(line)
    return "\n".join(lines)


def build_context_block(passages: List[dict]) -> str:
    """Render retrieved passages as labeled, attributable source material."""
    blocks = []
    for i, p in enumerate(passages, 1):
        doc = p.get("document", "unknown")
        text = p.get("text", "").strip()
        blocks.append(f"[PASSAGE {i} — source: {doc}]\n{text}")
    return "\n\n".join(blocks) if blocks else "(no source passages were retrieved)"


def build_user_prompt(fields: List[FieldSpec], passages: List[dict]) -> str:
    return f"""SOURCE PASSAGES (the only facts you may use):
{build_context_block(passages)}

BLANKS TO FILL:
{build_field_block(fields)}

Return the JSON object now. For any blank whose value is not explicitly present
in the SOURCE PASSAGES, set value to "{NEEDS_REVIEW}" and found to false."""
