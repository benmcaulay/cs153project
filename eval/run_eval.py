"""
Verbatim evaluation harness (operationalizes SPEC §14).

Runs each (matter, template) gold fixture through the real fill pipeline under a
selected engine, compares the produced fields to hand-labeled gold answers, and
reports the metrics that matter for a safety-first legal tool:

  - correct            : grounded value that matches gold
  - correct_abstention : gold is NEEDS_REVIEW and the engine correctly abstained
  - FABRICATION        : gold is NEEDS_REVIEW but the engine filled a value  <-- the
                         critical safety failure this whole system exists to avoid
  - wrong_value        : grounded value that does NOT match gold
  - miss               : gold has a value but the engine abstained (recall loss)

Engines:
  --engine baseline          reproducible rule-based extractor, no LLM (default)
  --engine offline           simulate an unreachable runtime (NFR-3 degradation)
  --engine ollama:<model>    a live local model, e.g. ollama:llama3.1:8b

Usage:
  python -m eval.run_eval --engine baseline
  python -m eval.run_eval --engine ollama:llama3.1:8b
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import catalog                      # noqa: E402
from app import ollama_client                # noqa: E402
from app.filler import fill                  # noqa: E402
from app.models import NEEDS_REVIEW          # noqa: E402
from app.templates import prepare_template, read_template_text  # noqa: E402
from eval.baseline_extractor import extract as baseline_extract  # noqa: E402

GOLD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold")
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _value_matches(produced: str, gold: str) -> bool:
    a, b = _norm(produced), _norm(gold)
    if not a or not b:
        return False
    if a == b:
        return True
    # Tolerate the engine returning a fuller line that contains the gold answer
    # (or vice-versa) — both directions, for answers longer than a token.
    return (len(b) > 3 and b in a) or (len(a) > 3 and a in b)


def _offline_extractor(model, fields, passages, temperature):
    raise ollama_client.OllamaUnavailable("simulated offline runtime", kind="connection")


def _resolve_extractor(engine: str):
    if engine == "baseline":
        return baseline_extract, "baseline"
    if engine == "offline":
        return _offline_extractor, "offline"
    if engine.startswith("ollama:"):
        return None, engine.split(":", 1)[1]  # None => app.filler uses the real Ollama client
    raise SystemExit(f"unknown engine: {engine}")


def _matter_folder_for(name: str) -> Optional[str]:
    for m in catalog.list_matters():
        if m.name == name:
            return catalog.matter_folder(m.id), m.id, m.name
    return None


def _template_by_filename(filename: str):
    for t in catalog.list_templates():
        if t.filename == filename:
            return t
    return None


def score_pair(gold: dict, extractor, model: str) -> dict:
    matter = _matter_folder_for(gold["matter"])
    template = _template_by_filename(gold["template_filename"])
    if matter is None or template is None:
        raise SystemExit(f"gold references missing matter/template: {gold['matter']} / {gold['template_filename']}")
    folder, matter_id, matter_name = matter

    _kind, raw = read_template_text(catalog.template_path(template.id))
    canonical, _f = prepare_template(raw)
    result = fill(folder, matter_id, matter_name, template, canonical, model=model, extractor=extractor)

    produced = {f.key: f for f in result.fields}
    counts = {"correct": 0, "correct_abstention": 0, "fabrication": 0, "wrong_value": 0, "miss": 0}
    details = []
    for key, gold_val in gold["expected"].items():
        pf = produced.get(key)
        if pf is None:
            continue
        gold_blank = gold_val.strip().upper() == NEEDS_REVIEW
        if gold_blank:
            outcome = "correct_abstention" if not pf.found else "fabrication"
        elif not pf.found:
            outcome = "miss"
        else:
            outcome = "correct" if _value_matches(pf.value, gold_val) else "wrong_value"
        counts[outcome] += 1
        details.append(
            {
                "key": key,
                "gold": gold_val,
                "produced": pf.value if pf.found else NEEDS_REVIEW,
                "outcome": outcome,
                "source_document": pf.source_document,
            }
        )

    return {
        "matter": gold["matter"],
        "template": gold["template_filename"],
        "status": result.status,
        "inference_seconds": result.inference_seconds,
        "counts": counts,
        "details": details,
    }


def aggregate(pairs: list[dict]) -> dict:
    agg = {"correct": 0, "correct_abstention": 0, "fabrication": 0, "wrong_value": 0, "miss": 0}
    total = 0
    latency = 0.0
    for p in pairs:
        for k, v in p["counts"].items():
            agg[k] += v
            total += v
        latency += p["inference_seconds"]
    answerable = agg["correct"] + agg["wrong_value"] + agg["miss"]
    should_abstain = agg["correct_abstention"] + agg["fabrication"]
    return {
        "fields_total": total,
        "recall_on_answerable": round(agg["correct"] / answerable, 3) if answerable else None,
        "abstention_correctness": round(agg["correct_abstention"] / should_abstain, 3) if should_abstain else None,
        "fabrications": agg["fabrication"],
        "fabrication_rate": round(agg["fabrication"] / total, 3) if total else None,
        "wrong_values": agg["wrong_value"],
        "avg_latency_seconds": round(latency / len(pairs), 3) if pairs else 0.0,
        "category_counts": agg,
    }


def print_report(engine: str, pairs: list[dict], summary: dict) -> None:
    print(f"\n# Verbatim evaluation - engine: {engine}\n")
    print("| matter | template | status | correct | abstain_ok | FABRICATION | wrong | miss |")
    print("|---|---|---|--:|--:|--:|--:|--:|")
    for p in pairs:
        c = p["counts"]
        print(
            f"| {p['matter']} | {p['template']} | {p['status']} | "
            f"{c['correct']} | {c['correct_abstention']} | {c['fabrication']} | "
            f"{c['wrong_value']} | {c['miss']} |"
        )
    s = summary
    print("\n## Summary")
    print(f"- fields evaluated:        {s['fields_total']}")
    print(f"- recall on answerable:    {s['recall_on_answerable']}")
    print(f"- abstention correctness:  {s['abstention_correctness']}")
    print(f"- FABRICATIONS (lower=better, target 0): {s['fabrications']}  (rate {s['fabrication_rate']})")
    print(f"- wrong values:            {s['wrong_values']}")
    print(f"- avg latency (s):         {s['avg_latency_seconds']}")


def main() -> None:
    # Windows consoles default to cp1252 and choke on non-ASCII; be safe.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Run the Verbatim evaluation harness.")
    ap.add_argument("--engine", default="baseline", help="baseline | offline | ollama:<model>")
    ap.add_argument("--no-write", action="store_true", help="do not write a results file")
    args = ap.parse_args()

    extractor, model = _resolve_extractor(args.engine)
    gold_files = sorted(glob.glob(os.path.join(GOLD_DIR, "*.json")))
    if not gold_files:
        raise SystemExit("no gold fixtures found in eval/gold/")

    pairs = []
    for gf in gold_files:
        with open(gf, "r", encoding="utf-8") as fh:
            gold = json.load(fh)
        pairs.append(score_pair(gold, extractor, model))

    summary = aggregate(pairs)
    print_report(args.engine, pairs, summary)

    if not args.no_write:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        safe = re.sub(r"[^a-z0-9]+", "_", args.engine.lower()).strip("_")
        out = os.path.join(RESULTS_DIR, f"{safe}.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"engine": args.engine, "summary": summary, "pairs": pairs}, fh, indent=2)
        print(f"\nwrote {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
