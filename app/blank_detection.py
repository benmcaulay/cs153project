"""
Tier-2 deterministic blank detection (FR-5.1, FR-5.3).

Real firm templates do not use ``{{key}}`` mustache markup. They mark blanks the
way lawyers have marked them on paper for decades: underscore runs, bracketed
spaces, ``[ ]`` checkboxes, ``Label :`` pairs, and ALL-CAPS sentinel tokens
(``NAME``, ``XXX``). The design rationale and the full convention taxonomy are in
``docs/blank-detection.md``.

This module implements the *deterministic* tier of that design: it scans plain
template text for the unambiguous physical conventions and **normalizes** them
into the canonical ``{{key}}`` markup the rest of the pipeline already
understands. Detection runs once, at template import; the canonical text it
produces is what gets filled. Semantic tiers (LLM inference over highlight runs
and prose instructions, OOXML-level docx parsing) remain future work and are
documented but intentionally not implemented here.

The bias is toward precision over recall: it is better to miss a blank a human
can add than to flag boilerplate as a blank. Every detected blank carries the
``source`` signal that produced it so an import-review screen can explain itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .models import FieldSpec

# --------------------------------------------------------------------------- #
# Convention patterns (the physical "fill me" signals, in priority order)
# --------------------------------------------------------------------------- #
# A run of 3+ underscores: "residing at ____", "20____", signature lines.
_UNDERSCORES = re.compile(r"_{3,}")
# A bracketed span of 2+ spaces: caption "[          ]", "DATED:[      ]".
_BRACKET_SPAN = re.compile(r"\[\s{2,}\]")
# A checkbox: "[ ]", "[]", "[X]" — a single optional X/x inside short brackets.
_CHECKBOX = re.compile(r"\[\s?[Xx]?\s?\]")
# ALL-CAPS sentinel tokens lawyers use as "type the real value here" placeholders.
_SENTINEL = re.compile(r"(?<![A-Za-z])(NAME|XXXX?|XX)(?![A-Za-z])")
# "Label :" at the start of a line with nothing (or only a blank) after it.
_LABEL_COLON = re.compile(r"^(?P<indent>\s*)(?P<label>[A-Z][A-Za-z0-9 ./'#-]{1,38}?)\s*:\s*$")

# Filler words we don't want as the head of a derived key.
_STOPWORDS = {
    "the", "a", "an", "of", "at", "in", "on", "to", "for", "and", "or", "by",
    "is", "was", "that", "this", "with", "as", "be", "being", "are", "his",
    "her", "their", "our", "your", "my",
}


@dataclass
class BlankCandidate:
    """One detected blank, ready for an import-review screen."""

    key: str
    label: str
    source: str                 # underscore | bracket | checkbox | sentinel | label
    instruction: Optional[str] = None
    example: Optional[str] = None  # text the template already had (a naming hint)


def _slug(text: str, max_words: int = 4) -> str:
    """Turn a context phrase into a snake_case key fragment.

    Drops stopwords and bare list ordinals (``1.``, ``2``) so an enumerated
    clause like ``2. That ____`` keys on its real subject, not the item number.
    """
    words = re.findall(r"[A-Za-z][A-Za-z0-9]*", text.lower())
    words = [w for w in words if w not in _STOPWORDS]
    return "_".join(words[-max_words:]) if words else ""


def _label_from_key(key: str) -> str:
    return re.sub(r"[_\s]+", " ", key).strip().title() or key


class _KeyAllocator:
    """Hands out unique snake_case keys, falling back to field_N."""

    def __init__(self) -> None:
        self._used: set[str] = set()
        self._n = 0

    def take(self, hint: str) -> str:
        base = _slug(hint) or self._next_generic()
        key = base
        i = 2
        while key in self._used:
            key = f"{base}_{i}"
            i += 1
        self._used.add(key)
        return key

    def _next_generic(self) -> str:
        self._n += 1
        return f"field_{self._n}"


def _preceding_phrase(line: str, start: int) -> str:
    """The few words immediately before position ``start`` on a line."""
    return line[:start].rstrip(" :=.-")


def _following_phrase(line: str, end: int) -> str:
    return line[end:].lstrip(" :=.-")


# --------------------------------------------------------------------------- #
# Per-line normalization
# --------------------------------------------------------------------------- #
def _normalize_line(line: str, alloc: _KeyAllocator) -> Tuple[str, List[BlankCandidate]]:
    found: List[BlankCandidate] = []

    # 1) Whole-line "Label :" pairs (e.g. "Claim No. :", "Date of Loss :").
    m = _LABEL_COLON.match(line)
    if m:
        label = m.group("label").strip()
        key = alloc.take(label)
        found.append(BlankCandidate(key=key, label=_label_from_key(key), source="label"))
        return f"{m.group('indent')}{label} : {{{{{key}}}}}", found

    # 2) In-line conventions. Replace left-to-right, naming from local context.
    #    Checkboxes first (most specific), then bracket spans, underscores,
    #    then ALL-CAPS sentinels.
    def repl_checkbox(mm: re.Match) -> str:
        choice = _following_phrase(line, mm.end()).split("  ")[0]
        key = alloc.take(f"{choice}_selected" if choice else "checkbox")
        found.append(
            BlankCandidate(
                key=key,
                label=_label_from_key(key),
                source="checkbox",
                instruction="select yes/no",
            )
        )
        return f"{{{{{key} | yes or no}}}}"

    def repl_named(source: str, instruction: Optional[str] = None):
        def _inner(mm: re.Match) -> str:
            token = mm.group(0).strip()
            # An alphabetic sentinel (NAME) names itself; opaque ones (XXX) and
            # underscore/bracket spans take their name from local context.
            if source == "sentinel" and token.isalpha() and token != "XX":
                hint = token
            else:
                hint = _preceding_phrase(line, mm.start())
                if not _slug(hint):
                    hint = _following_phrase(line, mm.end())
            key = alloc.take(hint)
            found.append(
                BlankCandidate(
                    key=key,
                    label=_label_from_key(key),
                    source=source,
                    instruction=instruction,
                    example=mm.group(0).strip() if source == "sentinel" else None,
                )
            )
            return f"{{{{{key}}}}}"

        return _inner

    out = _CHECKBOX.sub(repl_checkbox, line)
    out = _BRACKET_SPAN.sub(repl_named("bracket"), out)
    out = _UNDERSCORES.sub(repl_named("underscore"), out)
    out = _SENTINEL.sub(repl_named("sentinel"), out)
    return out, found


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def normalize(text: str) -> Tuple[str, List[FieldSpec], List[BlankCandidate]]:
    """
    Convert heterogeneous firm markup into canonical ``{{key}}`` text.

    Returns ``(canonical_text, fields, candidates)``:
      - ``canonical_text`` — the template rewritten so every detected blank is a
        ``{{key}}`` (or ``{{key | instruction}}``) token the filler understands.
      - ``fields`` — the de-duplicated ``FieldSpec`` list (what the UI counts).
      - ``candidates`` — the per-blank detection record (source signal, example)
        for an import-review screen.
    """
    alloc = _KeyAllocator()
    out_lines: List[str] = []
    candidates: List[BlankCandidate] = []
    for line in text.split("\n"):
        new_line, line_blanks = _normalize_line(line, alloc)
        out_lines.append(new_line)
        candidates.extend(line_blanks)

    fields: List[FieldSpec] = []
    for c in candidates:
        fields.append(
            FieldSpec(
                key=c.key,
                label=c.label,
                instruction=c.instruction,
                placeholder=f"{{{{{c.key}}}}}",
            )
        )
    return "\n".join(out_lines), fields, candidates
