"""
The evaluation harness is itself tested (SPEC §14).

Guarantees that matter most:
  - the offline engine fabricates nothing and abstains perfectly (the safety
    floor under a runtime failure);
  - the baseline engine only emits values it can quote (groundedness);
  - the scorer's category math is internally consistent.
"""
from eval.run_eval import aggregate, score_pair
from eval.baseline_extractor import extract as baseline_extract
from eval.run_eval import _offline_extractor

import glob
import json
import os

GOLD = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "eval", "gold", "*.json")))


def _gold(name):
    path = next(g for g in GOLD if name in g)
    with open(path) as fh:
        return json.load(fh)


def test_offline_engine_never_fabricates_and_abstains():
    pairs = [score_pair(json.load(open(g)), _offline_extractor, "offline") for g in GOLD]
    summary = aggregate(pairs)
    assert summary["fabrications"] == 0
    assert summary["category_counts"]["wrong_value"] == 0
    # With the runtime down, every should-abstain field is correctly abstained.
    assert summary["abstention_correctness"] == 1.0


def test_baseline_only_emits_grounded_values():
    pair = score_pair(_gold("probate_petition"), baseline_extract, "baseline")
    # Every field the engine "found" carries a source document (it was grounded).
    for d in pair["details"]:
        if d["outcome"] in ("correct", "wrong_value", "fabrication"):
            assert d["source_document"]


def test_scorer_categories_cover_every_field():
    pair = score_pair(_gold("probate_petition"), baseline_extract, "baseline")
    total = sum(pair["counts"].values())
    assert total == len(pair["details"]) == 9
