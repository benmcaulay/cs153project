# Verbatim — Software Requirements & Design Specification

**Project:** Verbatim — A Privacy-Preserving, Self-Hosted Legal Template Assistant
**Course:** CS 153
**Document status:** Draft v0.2 (living document — `main` now integrates the
Verbatim app and the blank-detection design notes in `docs/blank-detection.md`)
**Classification:** Internal / academic prototype

---

## 1. Executive Summary

Verbatim is a self-hosted software system that assists licensed attorneys and
paralegals by automatically transcribing facts from a legal matter's case file
into the blank fields of a firm-authored document template. All computation —
document parsing, retrieval, and language-model inference — executes on
hardware physically controlled by the firm. No privileged information,
attorney work product, or protected health information (PHI) is transmitted to
any third party.

The system pairs a local large language model (served by Ollama) with a
retrieval-augmented generation (RAG) pipeline and a strict, grounding-oriented
prompt regime. It exposes two interface surfaces: a deliberately simple
**Attorney Workspace** for legal professionals, and a separate **Developer
Console** for system administrators who tune model selection and measure
output quality.

---

## 2. Problem Statement and Thesis

A large fraction of an attorney's document production is repetitive. Across the
many filings a single matter generates, the same underlying facts — party
names, dates, case numbers, jurisdictions, injury descriptions, damages
figures — are re-entered by hand into successive templates. This work is
time-consuming, error-prone, and largely mechanical.

Two forces have, until recently, prevented automation of this task:

1. **Capability.** Reliable extraction of structured facts from heterogeneous
   legal prose required models that were not locally deployable.
2. **Privacy.** The most sensitive matters (e.g., personal-injury cases
   containing PHI) cannot lawfully or ethically be sent to external cloud
   services without significant risk and overhead.

**Thesis.** Open-weight models have advanced sufficiently that a model
deployable on a single internal device — an internal server, a high-memory
workstation, or an Apple-silicon Mac running a quantized ~70B model — can fill
template blanks at the quality a paralegal or attorney expects, *without
sacrificing the privacy of the underlying personal, medical, and legal data*.
Verbatim is the prototype intended to demonstrate this claim.

---

## 3. Goals and Non-Goals

### 3.1 Goals
- **G-1.** Demonstrate end-to-end local template filling: case file in, filled
  document out, with zero external network calls for inference.
- **G-2.** Make the system trustworthy for legal use by grounding every filled
  value in the source record and surfacing that provenance to the attorney.
- **G-3.** Refuse to guess: when a value cannot be grounded, mark it for human
  review rather than fabricate it.
- **G-4.** Provide a UI a non-technical attorney can operate without training.
- **G-5.** Provide administrators the means to switch between locally installed
  models and to measure which model performs best on which class of document.
- **G-6.** Be architected for later integration with firm document-management
  systems (NetDocuments, Centerbase, LexisNexis, iManage, etc.).

### 3.2 Non-Goals
- **NG-1.** Verbatim does **not** provide legal advice and does not exercise
  legal judgment. It is a drafting aid; a licensed attorney remains responsible
  for every output.
- **NG-2.** It is not a court e-filing system.
- **NG-3.** It does not train or fine-tune models in this prototype phase
  (model *selection* and *evaluation* are in scope; *training* is future work).
- **NG-4.** It does not implement authentication/RBAC in the prototype; this is
  identified as required future work for production (§13).

---

## 4. Stakeholders and User Roles

| Role | Description | Primary surface |
|------|-------------|-----------------|
| Attorney / Paralegal | Selects a matter and a template, runs a fill, reviews and exports the result. Non-technical. | Attorney Workspace |
| System Administrator | Installs models, assigns template styles, evaluates output accuracy, tunes model-to-style mapping. Technical. | Developer Console |
| Firm IT / Security | Owns the host machine, network isolation, and backups. | Deployment / ops |

The separation of surfaces is a deliberate requirement: attorneys must not be
burdened with model-management or performance instrumentation, which belongs
exclusively to the administrator.

---

## 5. System Overview

```
   ┌──────────────┐   ┌───────────┐   ┌──────────────────┐   ┌───────────────┐
   │ Case file    │ → │ Ingestion │ → │ Retrieval (RAG)  │ → │ Local LLM     │
   │ (.pdf/.docx/ │   │ + chunk   │   │ dense | lexical  │   │ (Ollama)      │
   │  .txt/.md)   │   └───────────┘   └──────────────────┘   └───────┬───────┘
   └──────────────┘                                                  │
   ┌──────────────┐                              grounded JSON       ▼
   │ Template     │ → detect blanks ───────────────────────→ ┌──────────────────┐
   │ {{blanks}}   │                                           │ Template filler  │
   └──────────────┘                                           │ + diff/highlight │
                                                              └────────┬─────────┘
                                                                       ▼
                                            Filled document + per-field provenance
                                            + needs-review flags + run record
```

The entire data path is local. The only network endpoint is the Ollama HTTP
API bound to `localhost`.

---

## 6. Functional Requirements

### 6.1 Ingestion and Retrieval
- **FR-1.** The system shall read case documents in `.pdf`, `.docx`, `.txt`,
  and `.md` formats from a per-matter folder.
- **FR-2.** The system shall split documents into overlapping text chunks
  suitable for retrieval.
- **FR-3.** The system shall retrieve the chunks most relevant to a template's
  fields. It shall use dense (embedding-based) retrieval when an embedding
  model is installed, and shall transparently fall back to lexical (TF-IDF)
  retrieval otherwise, with no change to the user experience.

### 6.2 Template Handling
- **FR-4.** The system shall parse templates and detect blanks expressed as
  `{{key}}` or `[[key]]`, optionally with an authoring instruction:
  `{{key | instruction}}`.
- **FR-5.** The system shall derive a human-readable label for each blank and
  shall present each template's blank count to the attorney before a fill.

FR-4 and FR-5 are **implemented** today (`app/templates.py`). However, the four
real firm templates evaluated to date (Allstate/Depo SUR letters, Affidavit of
Heirs, Caption) use **none** of this markup and therefore detect as zero blanks.
Real templates mark blanks with underscore runs, yellow highlighting, bracketed
spans, `[  ]` checkboxes, ALL-CAPS sentinels (`NAME`, `XXX`), `label :` pairs,
empty table cells, and inline instructions. The following requirements close
that gap; the full taxonomy, evidence, and proposed schema are in
`docs/blank-detection.md`.

- **FR-5.1 (Multi-convention detection — designed, not implemented).** Verbatim
  shall additionally detect the blank conventions real templates use, via a
  three-tier strategy: (i) deterministic heuristics for unambiguous physical
  signals (underscores, brackets, checkboxes, highlight runs, `label :`, empty
  table cells); (ii) LLM inference for semantic cases (sentinels, inline
  instructions, choice prompts); (iii) canonical `{{key}}` as the stored format.
- **FR-5.2 (OOXML-level docx parsing — designed, not implemented).** `.docx`
  templates shall be parsed at the OOXML run level so formatting signals —
  notably `w:highlight`, the firm's strongest intentional "fill me" marker — are
  preserved for detection. The current `read_template_text` flattens docx to
  plain text and discards them.
- **FR-5.3 (Normalize-at-import review — designed, not implemented).** Detection
  shall run **once at template import**, producing a canonical `{{key}}` template
  that a human reviews and approves before use. This converts heterogeneous
  source markup into one stored format and reduces the bar from "model must be
  perfect" to "model must produce a good, auditable first draft."

### 6.3 Filling
- **FR-6.** For a selected (matter, template, model) triple, the system shall
  produce a filled document in which each blank is replaced by a value
  extracted from the case file.
- **FR-7.** Every filled value shall carry provenance: a short supporting quote
  copied verbatim from the source and the originating document name.
- **FR-8.** Any blank that cannot be grounded in the case file shall be returned
  as **NEEDS_REVIEW** and visibly distinguished from filled values; the system
  shall never fabricate a value to fill a blank.
- **FR-9.** The system shall display the filled document with each substituted
  value highlighted in place, so the attorney can see exactly what changed.
- **FR-10.** The system shall allow export of the filled document as `.docx`.

### 6.4 Model Management (Administrator)
- **FR-11.** The system shall enumerate all models installed in the local
  Ollama runtime and allow selection of any of them for a fill.
- **FR-12.** The Developer Console shall allow an administrator to assign a
  **style** (category) to each template (e.g., *litigation*, *transactional*,
  *family-law*).
- **FR-13.** The administrator shall be able to flag each filled field of a run
  as **correct** or **incorrect**.
- **FR-14.** The system shall aggregate flags into a per-(model, style) accuracy
  report, including the rate of needs-review fields and average inference time,
  so an administrator can fit the best model to each document class.
- **FR-15.** All instrumentation in FR-11–FR-14 shall be confined to the
  Developer Console and shall not appear in the Attorney Workspace.

### 6.5 Persistence and Audit
- **FR-16.** Each fill shall be recorded as an immutable run record containing
  inputs, outputs, provenance, timing, and any subsequent admin flags.
- **FR-17.** Run records shall be stored locally in human-readable form (JSON).

---

## 7. Non-Functional Requirements

- **NFR-1 (Privacy).** No case content shall traverse any network other than to
  a model runtime bound to the local host. There shall be no telemetry.
- **NFR-2 (Determinism).** Extraction shall run at temperature 0 to maximize
  faithful, reproducible transcription over creative variation.
- **NFR-3 (Robustness).** The prototype shall run with only a chat model
  installed (lexical-retrieval fallback) and shall degrade gracefully when the
  model runtime is unreachable (clear status, no crash).
- **NFR-4 (Usability).** The Attorney Workspace shall require no configuration:
  three selections and one button produce a result.
- **NFR-5 (Portability).** The system shall run on Windows, macOS, and Linux
  with a single Python environment and an Ollama install.
- **NFR-6 (Auditability).** Every output shall be traceable to its source
  material and the model that produced it.

---

## 8. Hardware and Model Sizing

The thesis concerns models in the ~70B class on appropriate internal hardware.
The demonstration machine for this project is a workstation with 32 GB system
RAM and an NVIDIA GTX 1660 Ti (6 GB VRAM). This distinction must be stated
plainly:

- A 70B model **cannot** be served on a 6 GB GPU, and a 4-bit-quantized 70B
  requires on the order of 40 GB of memory — exceeding this machine's 32 GB
  RAM. It is therefore **not feasible on the demo PC**.
- Models in the **7B–14B** range, 4-bit quantized, fit comfortably (≈4–9 GB)
  and run at interactive speed. Recommended demo models: `llama3.1:8b`,
  `mistral:7b`, `qwen2.5:7b` / `qwen2.5:14b`.

Because Verbatim is **model-agnostic** (FR-11), the same software substantiates
the full thesis when deployed on hardware sized for a 70B model — an internal
GPU server, or an Apple-silicon machine with 64 GB+ unified memory capable of
running a quantized 70B locally. The demonstration is conducted on an 8B–14B
model; the architecture's portability is the bridge to the thesis at scale, and
the Developer Console's accuracy instrumentation (§6.4) is the means by which a
firm would empirically choose the smallest model that meets its quality bar for
each document style.

---

## 9. Extraction Methodology and Anti-Hallucination Design

The dominant risk in legal automation is a *confident wrong answer*: an
invented case number or misattributed party can cause real harm if filed.
Verbatim's design treats a left-blank field as correct and a guessed field as a
defect. The methodology:

1. **Grounded context.** Only retrieved passages from the matter's own
   documents are supplied to the model as source material.
2. **Constrained role.** The system prompt forbids outside knowledge and
   requires that any ungroundable field be returned as `NEEDS_REVIEW`.
3. **Structured output.** The model returns JSON (enforced via the runtime's
   JSON mode), reducing parse failures on smaller models.
4. **Per-field provenance.** Each value must be accompanied by a short verbatim
   supporting quote and its source document, enabling instant human
   verification.
5. **Fidelity rule.** Proper nouns, dates, figures, and case numbers are
   transcribed exactly; only formatting explicitly requested by a field's
   authoring instruction is applied.
6. **Deterministic decoding.** Temperature 0 (NFR-2).

The complete system prompt is implemented in `app/prompts.py` and is the
primary artifact governing model behavior.

---

## 10. User Interface Specification

### 10.1 Visual identity
A restrained, professional aesthetic appropriate to a legal-technology product:
a slate-gray and deep-blue palette, an editorial serif (Fraunces) for headings
paired with a technical sans (IBM Plex Sans) for body and a monospace (IBM Plex
Mono) for the administrator's technical surfaces. The palette is centralized in
CSS variables and is intended to be aligned to a firm's brand reference.

### 10.2 Attorney Workspace
- Select **matter**, **template**, and **model**; one **Fill** action.
- Result view: filled document with substituted values highlighted in place;
  ungrounded blanks rendered distinctly as review markers.
- Summary metrics: blanks filled, blanks needing review, inference time, model.
- Provenance panel: per field, the value, model confidence (advisory), and the
  verbatim source quote with its originating document.
- Export to `.docx`.

### 10.3 Developer Console (administrator only)
- Enumeration of installed local models.
- Template-to-style assignment.
- Per-(model, style) performance table: accuracy from admin flags,
  needs-review rate, average inference time.
- Run list and a per-run audit panel for flagging each field correct/incorrect.

---

## 11. Data Model (summary)

- **CaseInfo** — id, name, document list, character count.
- **TemplateInfo** — id, name, filename, kind, detected fields, style.
- **FieldSpec** — key, label, authoring instruction, literal placeholder.
- **FilledField** — key, label, value, found flag, confidence, source quote,
  source document.
- **FillResult** — run id, timestamp, matter, template, style, model, fields,
  original and filled text, timing, counts, admin flags.

Full schemas are defined in `app/models.py`.

---

## 12. Integration Roadmap (Document-Management Systems)

Verbatim is designed to slot into a firm's existing document infrastructure
rather than replace it. The integration surface is an adapter layer that maps
Verbatim's matter/template/run concepts onto a target system's API:

- **Inbound (case material):** pull matter documents from the DMS instead of a
  local folder (e.g., NetDocuments REST API, iManage Work API, Centerbase
  records, LexisNexis content) via firm-scoped credentials, preserving the
  local-only inference guarantee.
- **Outbound (filled documents):** write the filled `.docx` and its run record
  back to the matter in the DMS, with provenance metadata attached.

These integrations are out of scope for the prototype but the storage layer is
intentionally abstracted (folder-based today) to make adapter substitution
straightforward.

---

## 13. Security, Privacy, and Professional Responsibility

- **Local-only inference (NFR-1).** The privacy guarantee is the project's
  reason for existing and is enforced architecturally: the only network calls
  are to `localhost`.
- **PHI handling.** Matters may contain protected health information; it is
  processed in memory and persisted only to the local store. A production
  deployment must add encryption at rest and access controls.
- **Required for production (not in prototype):** user authentication and
  role-based access control (attorney vs. administrator), audit logging of who
  ran/exported what, encryption at rest, and matter-level access scoping.
- **Professional responsibility.** Output is explicitly a draft requiring
  attorney review (NG-1). UI and exports carry this notice. The system supports,
  but does not replace, the attorney's duty of competence and supervision.

---

## 14. Evaluation Plan

The Developer Console's flagging mechanism (FR-13/14) is the evaluation
instrument. The intended protocol:

1. Assemble a held-out set of matters with known-correct template fills.
2. Run each matter/template under several candidate local models.
3. Flag each field correct/incorrect.
4. Read per-(model, style) accuracy, needs-review rate, and latency.
5. Select, per document style, the smallest model meeting the firm's accuracy
   threshold.

This operationalizes the thesis: it produces evidence about *which* local model
size is sufficient for *which* class of legal document.

---

## 15. Limitations and Risks

- Small models may mis-extract on long or unusually formatted case files;
  provenance and needs-review surfacing are the mitigations, not a guarantee.
- Document parsing quality depends on source fidelity (scanned PDFs may require
  OCR, identified as future work).
- Confidence scores are model self-reports and are advisory only.
- The prototype lacks authentication and must not be exposed beyond a trusted
  local host as-is.
- Blank detection currently recognizes only `{{}}`/`[[]]` markup, which real
  firm templates do not use; templates lacking explicit markup detect zero
  blanks until the multi-convention detector (FR-5.1–5.3,
  `docs/blank-detection.md`) is implemented.

---

## 16. Milestones

| # | Milestone | Status |
|---|-----------|--------|
| M1 | Local pipeline: ingest → retrieve → fill → provenance | Implemented (prototype) |
| M2 | Attorney Workspace + Developer Console | Implemented (prototype) |
| M3 | `.docx` export | Implemented (prototype) |
| M3.5 | Multi-convention blank detection + import normalization (FR-5.1–5.3) | Designed (`docs/blank-detection.md`), not yet implemented |
| M4 | Evaluation run across multiple models on demo hardware | Pending models + data |
| M5 | Authentication / RBAC, encryption at rest | Future work |
| M6 | DMS integration adapter (one target) | Future work |

---

## 17. Glossary

- **RAG** — Retrieval-Augmented Generation: supplying a model with retrieved
  source passages so its output is grounded in those sources.
- **Grounding** — Restricting model output to facts present in supplied source
  material.
- **PHI** — Protected Health Information.
- **Ollama** — A local runtime for serving open-weight language models on the
  user's own hardware.
- **Style** — An administrator-assigned category for a template, used to map
  document classes to best-performing models.
