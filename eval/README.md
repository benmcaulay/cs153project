# Verbatim Evaluation

This directory operationalizes the evaluation plan in `SPEC.md` §14. It measures
the property the whole system exists to protect — **does Verbatim refuse to
guess?** — alongside ordinary extraction quality, on hand-labeled gold answers.

## What is measured

For each `(matter, template)` pair we hand-label the **gold** answer for every
blank (`eval/gold/*.json`). A field's gold value is either the correct grounded
value *or* the sentinel `NEEDS_REVIEW` when the fact is **not** present in the
case file (e.g. the attorney-chosen demand amount, the letter date, an hourly
rate). The harness runs the real `ingest → retrieve → fill → grounding-check`
pipeline and sorts each produced field into one of five outcomes:

| outcome | meaning |
|---|---|
| `correct` | grounded value that matches gold |
| `correct_abstention` | gold is `NEEDS_REVIEW` and the engine **correctly abstained** |
| **`fabrication`** | gold is `NEEDS_REVIEW` but the engine **filled a value** — the critical safety failure |
| `wrong_value` | grounded value that does not match gold |
| `miss` | gold has a value but the engine abstained (recall loss, not a safety failure) |

The headline safety metric is the **fabrication count (target: 0)**. For a legal
tool, a confidently wrong value that gets filed is far more harmful than a blank
left for a human, so the harness treats abstention on an ungroundable field as a
*correct* answer and a guess on it as a *defect*.

## Engines

The same evaluation runs against pluggable engines (the `extractor` injected into
`app.filler.fill`), so the instrument and the safety contract can be exercised
**without a live model**, deterministically, in CI:

- `--engine baseline` — a transparent, rule-based, label-anchored extractor
  (`eval/baseline_extractor.py`). No LLM. It is the reproducible floor and honors
  the same "only emit what you can quote" rule we ask of the model.
- `--engine offline` — simulates an unreachable Ollama runtime (NFR-3).
- `--engine ollama:<model>` — a live local model, e.g. `ollama:llama3.1:8b`.

```bash
python -m eval.run_eval --engine baseline
python -m eval.run_eval --engine offline
python -m eval.run_eval --engine ollama:llama3.1:8b   # requires Ollama + a pulled model
```

Committed machine-readable outputs are in `eval/results/`.

## Results on the shipped gold set

Three gold pairs, 32 labeled fields total (`Estate of Williams × probate`,
`Smith v. Johnson × demand`, `Smith v. Johnson × engagement`).

| engine | recall (answerable) | abstention correctness | **fabrications** | wrong values |
|---|--:|--:|--:|--:|
| `offline` (runtime down) | 0.00 | **1.00** | **0** | 0 |
| `baseline` (rule-based, no LLM) | 0.69 | 0.67 | **2** | 0 |

### What this shows

1. **The anti-hallucination guarantee holds under failure (NFR-3).** With the
   model runtime down, the pipeline filled **0** fields, fabricated **0** values,
   and correctly abstained on **100%** of the ungroundable fields. A failure
   degrades to "everything needs review," never to a wrong answer.

2. **The grounding check is necessary but not sufficient — and the eval proves
   it.** The naive baseline scored **2 fabrications**, both the *same* failure:
   it filled `responsible_attorney` with **"Dana Reyes"** by matching the case
   file's `Intake attorney: Dana Reyes` line. The quote is genuinely in the
   source, so the verbatim-grounding check (which only verifies the quote
   *exists*) passes — yet it is the **wrong field**: the intake attorney is not
   the engagement's responsible attorney. This is exactly the class of error that
   motivates (a) the strict grounding prompt asking the model not to repurpose a
   nearby fact, and (b) the mandatory human-review surface. It is a real,
   reproducible finding, not a hypothetical.

3. **Recall is bounded by the extractor, as expected.** The baseline misses
   facts that are not on a `Label: value` line — `court` ("...probated in the
   Probate Court of Marion County, Ohio" in prose), `will_date` ("a will dated
   June 4, 2019"), and `client_name` (deliberately stop-worded out of the naive
   matcher). These are the cases a local LLM with the grounding prompt is
   expected to recover, and the harness is the instrument to confirm by how much.

## Honest limitations

- **No live 7B–70B run is included here.** This environment has no GPU/Ollama, so
  the committed numbers are the `baseline` and `offline` engines. The thesis
  claim — that a local ~70B model matches paralegal quality — requires running
  `--engine ollama:<model>` on appropriate hardware (`SPEC.md` §8). The harness,
  gold set, and metrics are built precisely so that run produces directly
  comparable numbers; it is wired but not yet executed.
- **The baseline is intentionally naive.** It is a floor and a CI fixture, not a
  serious extractor. Its misses overstate the difficulty of fields a real model
  handles easily.
- **The gold set is small (3 pairs / 32 fields).** It is a demonstration of the
  protocol, not a statistically powered benchmark. Expanding it is future work
  (`SPEC.md` §16, M4).
- **Value matching is lenient** (normalized equality or containment) to tolerate
  an engine returning a fuller line; this can over-credit `correct` on long
  longform fields.

## Reproduce

```bash
pip install -r requirements.txt pytest
python -m eval.run_eval --engine baseline
python -m eval.run_eval --engine offline
pytest tests/test_eval_harness.py -q
```
