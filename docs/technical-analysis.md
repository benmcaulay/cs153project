# Verbatim — Technical Architecture Analysis

*A ~2-minute read mapped to the rubric's five dimensions.*

## 1. Problem & insight
Law firms re-enter the same facts — parties, dates, case numbers, injuries,
damages — into template after template. An LLM is the obvious automation, but the
most sensitive matters carry PHI and privileged work product that **cannot** leave
the building. Verbatim resolves the tension by running the *entire* pipeline
locally: the only outbound network call anywhere in the app is to an Ollama
runtime bound to `localhost`. Privacy is therefore an **architectural property,
not a policy** — there is no telemetry and no cloud call to disable.

## 2. Architecture (local RAG + a grounding contract)
1. **Ingest** (`ingest.py`) reads `.pdf/.docx/.txt/.md` per matter and chunks
   them. Scanned/encrypted PDFs fall back to Tesseract OCR (attempting
   `cryptography`-assisted empty-password decrypt first), degrading gracefully
   when those binaries are absent (NFR-3/5).
2. **Template normalization** (`templates.py` + `blank_detect.py`). Real firm
   templates don't use `{{markup}}` — they use underscores, `[ ]` checkboxes,
   `Label:` pairs, ALL-CAPS sentinels, and yellow-highlighted runs. A Tier-2
   deterministic pass reads `.docx` at the **OOXML level** (preserving the
   highlight signal) and rewrites every convention to canonical `{{key}}` at
   import — turning templates that detected *zero* blanks into ones that detect
   them.
3. **Retrieval** (`retrieval.py`) gathers passages per field: dense (cached
   Ollama embeddings) when an embedder is installed, pure-Python TF-IDF
   otherwise. Round-robin-by-rank selection ensures no field is starved of
   context, and `num_ctx` is raised so multi-document prompts aren't silently
   truncated.
4. **Extraction** (`filler.py`) issues a grounded JSON-mode prompt at
   temperature 0. The model call is an **injectable extractor**, so an offline
   baseline can exercise the full path in CI with no GPU.
5. **Grounding & assembly.** Every value is validated against the source text; a
   value not present in a retrieved passage is downgraded to `NEEDS_REVIEW`, with
   verbatim quote + source document attached to those that survive. Each blank is
   classified with a precise reason (`no_context`, `ungrounded`, `missing_key`,
   …) surfaced in the UI.

## 3. The core thesis — refuse to guess
The design treats a left-blank field as **correct** and a confident wrong value
as a **defect**, because an invented case number can be filed in court. Output is
explicitly a draft requiring attorney review; the system supports competence and
supervision rather than replacing them.

## 4. Evaluation
`eval/run_eval.py` scores produced fields against hand-labeled gold, optimizing
for one metric: **fabrications**. The offline engine (runtime down) yields **0
fabrications and 100% correct abstention** — the safety guarantee holds even on
failure — and the naive baseline surfaces real bugs (it grabbed the *intake*
attorney as the *responsible* attorney). Numbers are reproduced by running the
harness, not asserted.

## 5. Engineering & integrity
38 tests cover detection, grounding, diagnostics, OCR fallback, and graceful
degradation; CI runs them plus both offline eval engines on every push. Two UI
surfaces separate concerns — a one-action **Attorney Workspace** and a
**Developer Console** for model/eval instrumentation, plus a source inspector
showing exactly what the model reads. The frontend scaffold (Lovable +
shadcn/ui) is cited in `docs/ai-and-attribution.md`; the architecture, grounding
contract, and evaluation methodology are original.

**Limitations (disclosed):** Tier-3 LLM detection of ambiguous placeholders and
an import-time human-review screen are designed but unbuilt; auth/RBAC and
encryption-at-rest are out of prototype scope; the ~70B privacy thesis is
demonstrated on 7B–14B, with a model-agnostic architecture as the bridge to
scale.
