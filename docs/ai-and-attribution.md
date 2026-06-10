# AI Usage, Sources & Attribution

Verbatim originated as a Stanford CS 153 project. In the spirit of integrity and
disclosure expectations, this document states plainly what was AI-assisted, what
base code was borrowed, and where the substantial original work is. Please read
it alongside the commit history, which shows the work progressing over time.

## Summary

Verbatim is an **original system design** (the problem framing, the local-only
RAG + grounding architecture, the anti-hallucination/provenance contract, the
two-surface UX, the blank-detection strategy, and the evaluation methodology) by
the author. AI coding assistants and a UI scaffolding tool were used to
accelerate implementation. Nothing here is presented as if it were written
unassisted.

## Borrowed / generated base code (cited)

- **Frontend scaffold — [Lovable](https://lovable.dev) + [shadcn/ui](https://ui.shadcn.com).**
  The `frontend/` app was bootstrapped with Lovable's `vite_react_shadcn_ts`
  template. This is directly observable in the repo: `frontend/vite.config.ts`
  imports `lovable-tagger`, `frontend/public/lovable-uploads/` holds the
  generated brand assets, and `frontend/src/components/ui/*` are the standard
  **shadcn/ui** primitives (Radix UI + Tailwind), used under their respective
  MIT licenses. The Lovable project's stock README is preserved at
  `frontend/README.md`.
  - **What is original on top of the scaffold:** every application screen and the
    product itself — `AttorneyWorkspace.tsx`, `DeveloperConsole.tsx`,
    `FilledDocument.tsx` (in-place substitution highlighting), `Library.tsx`,
    the typed backend client `src/api/client.ts`, and the surface-toggle in
    `pages/Index.tsx`. The shadcn primitives are unmodified building blocks; the
    legal-assistant application logic and layout are the author's.

- **Runtime / libraries (standard dependencies, not vendored code).** Backend:
  FastAPI, Pydantic, python-docx, pypdf, Requests (see `requirements.txt`).
  Model serving: [Ollama](https://ollama.com) (external runtime; Verbatim only
  calls its local HTTP API). These are used as published libraries.

## AI assistance

- **Backend (`app/`), tests (`tests/`), evaluation harness (`eval/`), and
  documentation (`README.md`, `SPEC.md`, `docs/`)** were written with the help of
  AI coding assistants (Anthropic Claude, used via Claude Code), with the author
  directing the design, reviewing, integrating, and testing the output. The
  grounding system prompt in `app/prompts.py`, the design taxonomy in
  `docs/blank-detection.md`, and the evaluation design in `eval/` reflect the
  author's decisions about how the system should behave.
- AI assistance was used for: implementation drafting, refactoring, test
  scaffolding, and prose editing. It was **not** used to manufacture evaluation
  results — the numbers in `eval/results/` are produced by running the harness
  (`python -m eval.run_eval`) on this code, and are reproducible.

## Major decisions and limitations (disclosed elsewhere, indexed here)

- The privacy thesis and its hardware caveat (a 70B model is **not** runnable on
  the demo PC; the demo uses 7B–14B): `SPEC.md` §8.
- The blank-detection gap on real firm templates and the Tier-2 detector that
  closes the deterministic part of it: `docs/blank-detection.md`, `SPEC.md`
  §6.2, `app/blank_detect.py`.
- What the evaluation does and does **not** establish (no live 7B–70B run is
  included; the baseline is intentionally naive): `eval/README.md`.
- Production gaps intentionally out of scope for the prototype (auth/RBAC,
  encryption at rest): `SPEC.md` §13.

## How to verify the claims here

```bash
git log --oneline                 # development history
pytest -q                         # 21 tests across the pipeline
python -m eval.run_eval --engine baseline   # reproduces eval/results/baseline.json
grep -r lovable-tagger frontend/  # the cited scaffold origin
```
