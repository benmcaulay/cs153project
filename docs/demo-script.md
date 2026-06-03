# Demo Video Script & Storyboard (~3–4 min)

A shot-by-shot script for the submission video. It is written so the rubric's
five dimensions are *visibly demonstrated* on screen. Record at 1080p; show the
terminal and the browser side by side where noted.

> Setup before recording: `pip install -r requirements.txt`, optionally
> `ollama pull llama3.1:8b` and `ollama pull nomic-embed-text`, then
> `cd frontend && npm install && npm run build`, then `./run.sh` and open
> http://127.0.0.1:8000.

---

### 0:00 — Problem & insight (talking head + title card)
> "Law firms re-type the same case facts — names, dates, injuries, case numbers —
> into template after template. The obvious fix is an LLM, but the most sensitive
> matters contain PHI and privileged work product that **cannot** go to a cloud
> API. Verbatim does the whole thing locally: nothing leaves the machine."

Show the README title and the one-line architecture diagram.

### 0:30 — The privacy guarantee is architectural (terminal)
- `grep -rn "OLLAMA_HOST" app/` → show the only network endpoint is localhost.
- Hit `GET /api/health` → `ollama_available` and `ollama_host: localhost`.
> "The only outbound call anywhere in the app is to a local model runtime. There
> is no telemetry."

### 0:50 — Attorney Workspace: a real fill (browser)
- Pick matter **Smith v. Johnson**, template **Demand Letter**, model
  **llama3.1:8b**, click **Fill**.
- Show the filled letter with substitutions **highlighted in place**.
- Open the **provenance panel**: for each filled field, the value + the verbatim
  source quote + the document it came from.
> "Every value is grounded — it carries the exact quote and source it came from."

### 1:30 — It refuses to guess (the core safety claim)
- Point to fields rendered as **NEEDS REVIEW**: the letter *date*, the *demand
  amount*, the *responsible attorney* — facts not in the case file.
> "These aren't failures. The demand amount isn't in the file — it's the
> attorney's call. Verbatim leaves it blank instead of inventing it. A blank is
> correct; a confident wrong value could get filed."
- Click **Export .docx**, open it, show the DRAFT — ATTORNEY REVIEW REQUIRED
  notice and the provenance appendix.

### 2:00 — Real firm templates (the hard part)
- In the Library, open **Affidavit of Heirs** (uses underscores, `[ ]`
  checkboxes, `Label :` pairs, `NAME` sentinels — no `{{ }}` markup).
> "Lawyers don't write templates in our markup. This one uses underscores,
> checkboxes, and ALL-CAPS placeholders. The old detector found **zero** blanks."
- Show it now detects **19** blanks (Tier-2 deterministic detection normalizing
  the firm's conventions to canonical markup). Reference `docs/blank-detection.md`.

### 2:30 — Developer Console: evidence (browser + terminal)
- Show the Developer Console: installed models, per-template style, per-(model,
  style) accuracy / needs-review / latency table, per-field flagging.
- Cut to terminal: `python -m eval.run_eval --engine offline` then
  `--engine baseline`.
> "The evaluation harness scores produced fields against hand-labeled gold. The
> metric that matters is **fabrications — guesses on facts that aren't there.**"
- Highlight the two results from `eval/README.md`:
  - **offline (runtime down):** 0 fabrications, 100% correct abstention — the
    safety guarantee holds even on failure.
  - **baseline:** caught a real failure — it grabbed the *intake* attorney as the
    *responsible* attorney. Good evaluation surfaces real bugs.

### 3:00 — Testing & integrity (terminal)
- `pytest -q` → **21 passing tests**, including the anti-hallucination tests.
> "Ungrounded values are downgraded, not trusted; the runtime going down never
> crashes and never fabricates — both are tested."
- Show `docs/ai-and-attribution.md`: the frontend is a cited Lovable + shadcn/ui
  scaffold; the backend, tests, and eval were AI-assisted and author-directed;
  eval numbers are reproduced by running the harness, not fabricated.

### 3:30 — Close
> "Verbatim: local-only, grounded, and honest about what it doesn't know —
> because in legal work, a blank you can trust beats a guess you can't."

Show: public repo URL, commit history, `SPEC.md`, `eval/README.md`.
