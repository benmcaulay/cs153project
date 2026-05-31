# Verbatim

**A privacy-preserving, self-hosted legal template assistant.** (CS 153)

Verbatim transcribes facts from a legal matter's case file into the blank fields
of a firm-authored template. **All computation — parsing, retrieval, and
language-model inference — runs on hardware controlled by the firm.** The only
network endpoint Verbatim ever touches is an [Ollama](https://ollama.com)
runtime bound to the local host. No privileged information, work product, or PHI
leaves the machine.

This repository implements the prototype described in `SPEC.md`. The web UI
reuses the visual identity (steel-blue legal theme, logos, shadcn/ui component
library) of the firm's existing front-end.

---

## What it does

- **Grounded template filling.** For a `(matter, template, model)` triple, each
  `{{blank}}` is filled with a value extracted from the case file — and every
  value carries a verbatim supporting quote and its source document (provenance).
- **Refuses to guess.** Any blank that cannot be grounded in the case file is
  returned as `NEEDS_REVIEW` and visibly distinguished. Verbatim never
  fabricates a value. A grounding check downgrades any "filled" value whose
  supporting quote is not actually present in the retrieved source.
- **Two surfaces:**
  - **Attorney Workspace** — three selections and one button. Filled document
    with substitutions highlighted in place, summary metrics, provenance panel,
    and `.docx` export.
  - **Developer Console** — enumerate installed local models, assign a *style*
    to each template, flag each filled field correct/incorrect, and read a
    per-`(model, style)` accuracy / needs-review / latency report.
- **Degrades gracefully.** Runs with only a chat model installed (lexical TF-IDF
  retrieval fallback) and shows a clear status — never crashes — when the model
  runtime is unreachable.

---

## Architecture

```
case files (.pdf/.docx/.txt/.md)  ─┐
                                    ├─ ingest + chunk ─ retrieve (dense | lexical)
template ({{blanks}} / [[blanks]]) ─┘                          │
                                                               ▼
                          grounded JSON  ◄──  local LLM (Ollama, temp 0, JSON mode)
                                                               │
                       template filler + in-place highlight ◄──┘
                                                               ▼
            filled .docx  +  per-field provenance  +  needs-review flags  +  run record
```

### Backend (`app/`, Python + FastAPI)

| Module | Responsibility | SRS |
|--------|----------------|-----|
| `models.py` | Pydantic data model (`CaseInfo`, `TemplateInfo`, `FieldSpec`, `FilledField`, `FillResult`, …) | §11 |
| `prompts.py` | The grounding system prompt — the primary artifact governing model behavior | §9 |
| `ingest.py` | Read pdf/docx/txt/md, overlapping chunking | FR-1, FR-2 |
| `retrieval.py` | Dense (Ollama embeddings) retrieval with pure-Python TF-IDF fallback | FR-3 |
| `templates.py` | Detect `{{key}}` / `[[key]]` / `{{key \| instruction}}`, labels, fill | FR-4, FR-5 |
| `ollama_client.py` | Local-only runtime client; model list, JSON-mode generation, graceful degradation | FR-11, NFR-1/2/3 |
| `filler.py` | Orchestrate fill, provenance validation, anti-hallucination | FR-6/7/8 |
| `export.py` | `.docx` export with provenance appendix + review notice | FR-10 |
| `store.py` | Local JSON run records, style assignments, field flags | FR-12/13/16/17 |
| `reporting.py` | Per-`(model, style)` accuracy aggregation | FR-14 |
| `catalog.py` | Enumerate matters and templates from the local store | — |
| `main.py` | FastAPI HTTP API + serves the built UI | — |

### Frontend (`frontend/`, React + Vite + Tailwind + shadcn/ui)

Reuses the existing steel-blue theme, firm logo, and component library. Key
files: `src/pages/Index.tsx` (surface toggle), `src/components/AttorneyWorkspace.tsx`,
`src/components/DeveloperConsole.tsx`, `src/components/FilledDocument.tsx`
(in-place highlighting), `src/api/client.ts` (typed backend client).

---

## Running it

### 1. Backend

```bash
pip install -r requirements.txt
./run.sh                      # uvicorn app.main:app on http://127.0.0.1:8000
```

The API is now serving. With a built frontend present (step 3) it also serves
the UI at the same origin.

### 2. Local model (for real fills)

Install [Ollama](https://ollama.com) and pull a demo-sized model:

```bash
ollama pull llama3.1:8b          # or mistral:7b, qwen2.5:7b / qwen2.5:14b
ollama pull nomic-embed-text     # optional: enables dense retrieval
```

Verbatim talks only to `http://localhost:11434` (override with `OLLAMA_HOST`).
Without Ollama running, the app still works end-to-end — every field returns as
`NEEDS_REVIEW` with a clear "runtime offline" status.

### 3. Frontend

For development (hot reload, proxies `/api` to the backend on :8000):

```bash
cd frontend
npm install
npm run dev                   # http://localhost:8080
```

For a single-origin deployment, build it and let the backend serve it:

```bash
cd frontend && npm run build  # emits frontend/dist/
# then start ./run.sh and open http://127.0.0.1:8000
```

### Data layout

```
data/
  matters/<Matter_Name>/...    # per-matter case files (sample matters included)
  templates/*.{md,txt,docx}    # firm templates with {{blanks}} (samples included)
  runs/*.json                  # immutable run records (generated)
  config.json                  # template→style assignments (generated)
```

Two sample matters (*Smith v. Johnson*, *Estate of Williams*) and three
templates ship with the repo so you can run a fill immediately.

---

## Privacy & professional responsibility

- **Local-only inference** is enforced architecturally: the only outbound call is
  to the local Ollama host. There is no telemetry.
- Output is explicitly a **draft requiring attorney review**. Verbatim does not
  provide legal advice or exercise legal judgment.
- The prototype intentionally omits authentication/RBAC and encryption-at-rest;
  these are required for production and must not be exposed beyond a trusted
  local host as-is (see `SPEC.md` §13).
