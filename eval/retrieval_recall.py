"""
Retrieval recall: the model-independent ceiling on fill accuracy.

A field can only be grounded if the gold value actually appears in the passage
set handed to the model. This analyzer replays the *exact* production retrieval
path (same per-field k, same round-robin selection, same budget formula as
`app.filler.fill`) against the gold fixtures and reports, per fixture and
overall:

  retrieval recall = answerable gold fields whose value appears in the
                     selected passages / all answerable gold fields

No LLM is involved, so this runs anywhere (CI included) and cleanly separates
"retrieval failed to surface the fact" from "the model failed to extract it".
Every miss is listed with its gold value so fixes are actionable.

Usage:
    python -m eval.retrieval_recall
    python -m eval.retrieval_recall --json   # machine-readable
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import catalog                                      # noqa: E402
from app.filler import _retrieval_query, _select_passages    # noqa: E402
from app.ingest import ingest_folder                         # noqa: E402
from app.models import NEEDS_REVIEW                          # noqa: E402
from app.retrieval import auto_retriever                         # noqa: E402
from app.templates import prepare_template, read_template_text  # noqa: E402

GOLD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gold")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _contained(gold: str, passages: List[dict]) -> bool:
    needle = _norm(gold)
    if not needle:
        return False
    for p in passages:
        if needle in _norm(p["text"]):
            return True
    # Token-overlap fallback mirroring filler._locate_evidence: long values can
    # be split across line breaks/chunk boundaries yet still ground the field.
    toks = [t for t in needle.split() if len(t) > 2]
    if len(toks) >= 3:
        qset = set(toks)
        for p in passages:
            hset = set(_norm(p["text"]).split())
            if len(qset & hset) / len(qset) >= 0.75:
                return True
    return False


def _matter_folder_for(name: str) -> Optional[str]:
    for m in catalog.list_matters():
        if m.name == name:
            return catalog.matter_folder(m.id)
    return None


def analyze_fixture(gold: dict) -> Tuple[dict, List[dict]]:
    """Replay production retrieval for one gold fixture; return (stats, misses)."""
    folder = _matter_folder_for(gold["matter"])
    if folder is None:
        raise SystemExit(f"matter not found: {gold['matter']}")
    template_path = os.path.join(
        os.path.dirname(GOLD_DIR), "..", "data", "templates", gold["template_filename"]
    )
    template_path = os.path.normpath(template_path)
    _, raw_text = read_template_text(template_path)
    _, fields = prepare_template(raw_text)

    docs = ingest_folder(folder)
    chunks = [c for d in docs for c in d.chunks]   # exactly as app.filler.fill
    retriever = auto_retriever(chunks)

    # Exactly what app.filler.fill does:
    per_field = {f.key: retriever.retrieve(_retrieval_query(f), k=4) for f in fields}
    budget = min(max(16, len(fields) * 2), 30)
    passages = _select_passages(fields, per_field, budget)

    answerable = {k: v for k, v in gold["expected"].items() if v != NEEDS_REVIEW}
    misses: List[dict] = []
    hits = 0
    for key, value in answerable.items():
        if _contained(value, passages):
            hits += 1
        else:
            misses.append({"field": key, "gold": value})

    stats = {
        "matter": gold["matter"],
        "template": gold["template_filename"],
        "retrieval_mode": retriever.mode,
        "answerable": len(answerable),
        "in_passages": hits,
        "recall": round(hits / len(answerable), 3) if answerable else None,
        "passages_sent": len(passages),
    }
    return stats, misses


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    rows, all_misses = [], []
    for path in sorted(glob.glob(os.path.join(GOLD_DIR, "*.json"))):
        with open(path, "r", encoding="utf-8") as fh:
            gold = json.load(fh)
        stats, misses = analyze_fixture(gold)
        rows.append(stats)
        for m in misses:
            all_misses.append({**m, "matter": stats["matter"], "template": stats["template"]})

    total = sum(r["answerable"] for r in rows)
    hit = sum(r["in_passages"] for r in rows)
    overall = round(hit / total, 3) if total else None

    if args.json:
        print(json.dumps({"fixtures": rows, "overall_recall": overall, "misses": all_misses}, indent=2))
        return 0

    print("# Retrieval recall (model-independent accuracy ceiling)\n")
    print("| matter | template | mode | answerable | in passages | recall |")
    print("|---|---|---|--:|--:|--:|")
    for r in rows:
        print(
            f"| {r['matter']} | {r['template']} | {r['retrieval_mode']} "
            f"| {r['answerable']} | {r['in_passages']} | {r['recall']} |"
        )
    print(f"\nOverall: {hit}/{total} answerable gold values present in the passage set "
          f"-> retrieval recall {overall}")
    if all_misses:
        print("\nMisses (the fact never reached the model):")
        for m in all_misses:
            print(f"  - [{m['matter']} / {m['template']}] {m['field']}: \"{m['gold']}\"")
    else:
        print("\nNo retrieval misses: any remaining errors are extraction-side, not retrieval-side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
