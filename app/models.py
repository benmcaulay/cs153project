"""
Verbatim data model (SRS §11).

These schemas are the canonical data structures that flow through the
ingest -> retrieve -> fill -> provenance pipeline and are persisted as
human-readable run records (FR-16, FR-17).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Dict

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Matter (case file) and template descriptors
# --------------------------------------------------------------------------- #
class CaseInfo(BaseModel):
    """A legal matter: a per-matter folder of source documents (FR-1)."""

    id: str
    name: str
    documents: List[str] = Field(default_factory=list)
    char_count: int = 0


class FieldSpec(BaseModel):
    """A single detected blank in a template (FR-4, FR-5)."""

    key: str
    label: str
    instruction: Optional[str] = None
    placeholder: str  # the literal token as it appears in the template, e.g. "{{key}}"


class TemplateInfo(BaseModel):
    """A firm-authored document template with detected blanks (FR-4, FR-12)."""

    id: str
    name: str
    filename: str
    kind: str  # docx | txt | md
    fields: List[FieldSpec] = Field(default_factory=list)
    style: Optional[str] = None  # admin-assigned category (litigation, transactional, ...)

    @property
    def blank_count(self) -> int:
        return len(self.fields)


# --------------------------------------------------------------------------- #
# Fill results and provenance
# --------------------------------------------------------------------------- #
NEEDS_REVIEW = "NEEDS_REVIEW"


class FilledField(BaseModel):
    """One filled (or flagged) blank, carrying its provenance (FR-7, FR-8)."""

    key: str
    label: str
    value: str  # the extracted value, or the NEEDS_REVIEW sentinel
    found: bool  # False => could not be grounded => needs review
    confidence: Optional[float] = None  # advisory model self-report (§15)
    source_quote: Optional[str] = None  # short verbatim supporting quote
    source_document: Optional[str] = None  # originating document name
    source_page: Optional[int] = None  # 1-based page in the source document (PDFs)

    # Why a blank was left for review, when it was (diagnostic, surfaced in UI):
    # "filled" | "no_context" | "model_blanked" | "ungrounded" | "missing_key"
    # | "model_unreachable" | "no_documents"
    review_reason: Optional[str] = None

    # Administrator evaluation flag (FR-13): "correct" | "incorrect" | None
    admin_flag: Optional[str] = None


class FillResult(BaseModel):
    """An immutable run record (FR-16): the complete record of one fill."""

    run_id: str
    timestamp: str = Field(default_factory=_now_iso)
    matter_id: str
    matter_name: str
    template_id: str
    template_name: str
    style: Optional[str] = None
    model: str

    fields: List[FilledField] = Field(default_factory=list)

    original_text: str = ""
    filled_text: str = ""

    # timing + counts
    inference_seconds: float = 0.0
    blanks_total: int = 0
    blanks_filled: int = 0
    blanks_needs_review: int = 0

    # pipeline status / degradation notes (NFR-3)
    retrieval_mode: str = "lexical"  # "dense" | "lexical"
    status: str = "ok"  # "ok" | "model_unreachable" | "error"
    message: Optional[str] = None

    # Truncated raw model response, kept for diagnosis when output doesn't parse
    # or doesn't match the expected schema (local-only, like the rest of the run).
    raw_model_output: Optional[str] = None

    def recount(self) -> "FillResult":
        self.blanks_total = len(self.fields)
        self.blanks_filled = sum(1 for f in self.fields if f.found)
        self.blanks_needs_review = sum(1 for f in self.fields if not f.found)
        return self


# --------------------------------------------------------------------------- #
# Developer Console: aggregated evaluation (FR-14)
# --------------------------------------------------------------------------- #
class ModelStyleStats(BaseModel):
    model: str
    style: str
    runs: int = 0
    fields_flagged: int = 0
    fields_correct: int = 0
    fields_incorrect: int = 0
    needs_review_fields: int = 0
    total_fields: int = 0
    avg_inference_seconds: float = 0.0

    @property
    def accuracy(self) -> Optional[float]:
        if self.fields_flagged == 0:
            return None
        return self.fields_correct / self.fields_flagged

    @property
    def needs_review_rate(self) -> Optional[float]:
        if self.total_fields == 0:
            return None
        return self.needs_review_fields / self.total_fields
