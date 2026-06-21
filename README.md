# Verbatim

**A privacy-preserving, self-hosted legal template assistant.** (CS 153)

Verbatim transcribes facts from a legal matter's case file into the blank fields
of a firm-authored template. **All computation — parsing, retrieval, and
language-model inference — runs on hardware controlled by the firm.** The only
network endpoint Verbatim ever touches is an [Ollama](https://ollama.com)
runtime bound to the local host. No privileged information, work product, or PHI
leaves the machine.

---

## What it does

- **Grounded template filling.** For a `(matter, template, model)` triple, each
  `{{blank}}` is filled with a value extracted from the case file — and every
  value carries a verbatim supporting quote and its source document (provenance).
- **Refuses to guess.** Any blank that cannot be grounded in the case file is
  returned as `NEEDS_REVIEW` and visibly distinguished. Verbatim never
  fabricates a value. A grounding check downgrades any "filled" value whose
  supporting quote is not actually present in the retrieved source. This is
  measured, not just asserted — see **Evaluation** below.
- **Detects real firm blanks, not just `{{markup}}`.** Lawyers mark blanks with
  underscores, `[ ]` checkboxes, `Label :` pairs, and ALL-CAPS sentinels
  (`NAME`, `XXX`) — never mustache syntax. A Tier-2 deterministic detector
  (`app/blank_detect.py`) normalizes those conventions to canonical markup at
  import, so a real firm template that used to detect **zero** blanks now detects
  them (the shipped `affidavit_of_heirs.txt` goes from 0 → 19). Design and
  taxonomy: `docs/blank-detection.md`.
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
case files (.pdf/.docx/.txt/.md/.eml/.xlsx) ─┐
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
| `ingest.py` | Read pdf/docx/txt/md/eml/xlsx, overlapping chunking | FR-1, FR-2 |
| `retrieval.py` | Dense (Ollama embeddings) retrieval with pure-Python TF-IDF fallback | FR-3 |
| `templates.py` | Detect `{{key}}` / `[[key]]` / `{{key \| instruction}}`, labels, fill; `prepare_template` normalization | FR-4, FR-5 |
| `blank_detect.py` | Tier-2 deterministic detection of real-world blank conventions (underscores, brackets, checkboxes, `XXX`, `label :`, highlighted runs, empty table grids) → normalize to canonical markup | FR-5.1, FR-5.2, FR-5.3 |
| `ollama_client.py` | Local-only runtime client; model list, JSON-mode generation, graceful degradation | FR-11, NFR-1/2/3 |
| `filler.py` | Orchestrate fill, provenance validation, anti-hallucination | FR-6/7/8 |
| `export.py` | `.docx` export with provenance appendix + review notice | FR-10 |
| `store.py` | Local JSON run records, style assignments, field flags | FR-12/13/16/17 |
| `reporting.py` | Per-`(model, style)` accuracy aggregation | FR-14 |
| `catalog.py` | Enumerate matters and templates from the local store | — |
| `security.py` | Local accounts (scrypt), sessions, role-based access control | §13 |
| `crypto.py` | Encryption at rest for run records (Fernet) | §13 |
| `audit.py` | Append-only, hash-chained audit log | §13 |
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

**Scanned PDFs (optional OCR).** Image-only PDFs have no text layer. Verbatim
will OCR them automatically if Tesseract + poppler are installed:

```bash
# macOS:   brew install tesseract poppler
# Ubuntu:  sudo apt-get install tesseract-ocr poppler-utils
# Windows: install Tesseract (UB-Mannheim) + poppler, add both to PATH
```

Without them, scanned documents extract no text and the fill diagnostic flags
them. Disable OCR entirely with `VERBATIM_OCR=0`.

If you'd rather not edit PATH (handy on Windows), point Verbatim straight at the
binaries — the poppler bin is the nested `Library\bin` folder of the release:

```powershell
$env:VERBATIM_TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:VERBATIM_POPPLER_PATH  = "C:\poppler-24.08.0\Library\bin"
./run.sh
```

### 2. Local model (for real fills)

Install [Ollama](https://ollama.com) and pull a demo-sized model:

```bash
ollama pull llama3.1:8b          # or mistral:7b, qwen2.5:7b / qwen2.5:14b
ollama pull nomic-embed-text     # optional: enables dense retrieval
```

Verbatim talks only to `http://localhost:11434` (override with `OLLAMA_HOST`).
Without Ollama running, the app still works end-to-end — every field returns as
`NEEDS_REVIEW` with a clear "runtime offline" status.

**Large matters:** a multi-document matter can exceed Ollama's default context
window, after which the model returns nothing and every field reads as review.
Verbatim **auto-sizes** the window per fill from the estimated prompt size,
scaling from `VERBATIM_NUM_CTX` (floor, default 8192) up to
`VERBATIM_NUM_CTX_MAX` (ceiling, default 32768) — so big matters just work
without tuning, and small ones don't waste memory. Lower the ceiling on a
RAM-constrained machine; raise it for very large matters. If a matter is too big
even at the ceiling, the fill diagnostic says so explicitly (with the estimated
token count) rather than failing silently.

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
  runs/*.json                  # immutable run records, encrypted at rest (generated)
  config.json                  # template→style assignments (generated)
  users.json                   # local accounts, scrypt-hashed (generated; never commit)
  audit.log                    # hash-chained audit trail (generated; never commit)
  .keys/data.key               # encryption key, 0600 (generated; never commit)
```

Two sample matters (*Smith v. Johnson*, *Estate of Williams*) and three
templates ship with the repo so you can run a fill immediately.

---

## Evaluation

The whole point of Verbatim is that it **refuses to guess**, so the evaluation
measures exactly that. `eval/` runs each `(matter, template)` gold fixture
through the real pipeline and scores every field as `correct`,
`correct_abstention`, **`fabrication`** (a guess on a fact that isn't in the
file — the critical failure), `wrong_value`, or `miss`. It runs against
pluggable engines so the safety contract is testable **without a live model**:

```bash
python -m eval.run_eval --engine baseline           # reproducible rule-based floor (no LLM)
python -m eval.run_eval --engine offline            # simulate runtime down (NFR-3)
python -m eval.run_eval --engine ollama:llama3.1:8b # a real local model
```

Results on the shipped gold set (32 labeled fields) and a full write-up,
including a real failure the harness caught, are in **`eval/README.md`**.
Headline: with the runtime down, the pipeline fabricated **0** values and
abstained correctly **100%** of the time; the naive baseline exposed a genuine
label-ambiguity bug (it grabbed the *intake* attorney as the *responsible*
attorney). No live 7B–70B run is included here — this machine has no GPU — and
that limitation is stated plainly.

## Testing

```bash
pip install -r requirements.txt pytest
pytest -q          # 53 tests
```

Coverage includes the anti-hallucination contract (ungrounded values are
downgraded, never trusted), graceful degradation when the runtime is
unreachable/slow, Tier-2 blank detection (0 → N on a firm-style template),
lexical retrieval fallback, `.docx` export, reporting aggregation, the eval
harness itself, and the security contract (auth on by default, role
enforcement over the live API, run records unreadable on disk, audit-chain
tamper detection).

## AI usage, sources & attribution

Honest disclosure is in **`docs/ai-and-attribution.md`** and `LICENSE` (MIT). In
short: the system design is original; the `frontend/` is a cited
[Lovable](https://lovable.dev) + [shadcn/ui](https://ui.shadcn.com) scaffold with
the application screens built on top; the backend, tests, eval, and docs were
written with AI assistance under the author's direction; and the evaluation
numbers are reproduced by running the harness, not manufactured. A shot-by-shot
demo-video script is in `docs/demo-script.md`.

## Privacy & professional responsibility

- **Local-only inference** is enforced architecturally: the only outbound call is
  to the local Ollama host. There is no telemetry.
- Output is explicitly a **draft requiring attorney review**. Verbatim does not
  provide legal advice or exercise legal judgment.

## Security

Verbatim handles privileged case material, so access control is on by default
(full model, deployment guidance, and roadmap: **`docs/security.md`**):

- **Authentication** — local accounts with scrypt-hashed passwords
  (`data/users.json`), HttpOnly session cookies, and a brute-force lockout.
  First start bootstraps an `admin` account (password from
  `VERBATIM_ADMIN_PASSWORD`, or generated and printed once). Manage users from
  the Developer Console → *Access* tab or `python -m app.security adduser …`.
  Disable for local demos with `VERBATIM_AUTH=0`.
- **Role-based access control** — *attorneys* get the Workspace and Library;
  *admins* additionally get the Developer Console (runs, flags, reports, user
  management). Enforced server-side per endpoint, not just hidden in the UI.
- **Encryption at rest** — run records (extracted facts, quotes, the filled
  document) are Fernet-encrypted on disk; the key lives in `data/.keys/` (0600)
  or `VERBATIM_DATA_KEY`. Case files stay in the firm's filesystem, where
  full-disk encryption is the right control — `docs/security.md` explains the
  boundary.
- **Tamper-evident audit log** — every login, fill, export, upload, and admin
  action is appended to a SHA-256 hash chain (`data/audit.log`). Verify with
  `python -m app.audit verify`; admins can inspect it in the Access tab.
- No authentication/identity provider is contacted: like inference, **auth is
  local-only**. SSO (OIDC/SAML), per-matter access walls, and the rest of the
  production path are laid out in `docs/security.md`.
