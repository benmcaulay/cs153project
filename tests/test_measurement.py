"""
Tests for the measurement instruments: pilot report + retrieval recall.

These exist so the numbers Verbatim quotes externally are themselves under
test — a reporting bug that inflated fill rate or verified accuracy would be a
worse integrity failure than a model error.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def store(monkeypatch, tmp_path):
    monkeypatch.setenv("VERBATIM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("VERBATIM_DATA_KEY", raising=False)
    import app.store as store_mod

    importlib.reload(store_mod)
    return store_mod


def _run(run_id, *, fields, model="m1", matter="A", seconds=10.0, ts="2026-06-01T00:00:00"):
    from app.models import FilledField, FillResult

    return FillResult(
        run_id=run_id,
        timestamp=ts,
        matter_id=matter,
        matter_name=matter,
        template_id="t1",
        template_name="T",
        model=model,
        fields=fields,
        original_text="",
        filled_text="",
        inference_seconds=seconds,
        blanks_total=len(fields),
        blanks_filled=sum(1 for f in fields if f.found),
        blanks_needs_review=sum(1 for f in fields if not f.found),
        retrieval_mode="lexical",
        status="ok",
    )


def test_pilot_report_aggregates_correctly(store):
    from app.models import FilledField
    from app.reporting import pilot_report

    f_ok = FilledField(key="a", label="A", value="x", found=True, admin_flag="correct")
    f_bad = FilledField(key="b", label="B", value="y", found=True, admin_flag="incorrect")
    f_rev = FilledField(key="c", label="C", value="NEEDS_REVIEW", found=False)
    f_unflagged = FilledField(key="d", label="D", value="z", found=True)

    store.save_run(_run("r1", fields=[f_ok, f_rev], seconds=10.0, ts="2026-06-01T00:00:00"))
    store.save_run(_run("r2", fields=[f_bad, f_unflagged], matter="B", seconds=20.0,
                        ts="2026-06-02T00:00:00"))

    r = pilot_report()
    assert r["runs"] == 2 and r["matters"] == 2
    assert r["fields_total"] == 4
    assert r["fields_filled"] == 3 and r["fields_needs_review"] == 1
    assert r["fill_rate"] == 0.75 and r["needs_review_rate"] == 0.25
    # Verified accuracy counts ONLY flagged fields: 1 correct of 2 flagged.
    # The unflagged filled field must not inflate it.
    assert r["fields_human_flagged"] == 2
    assert r["verified_accuracy"] == 0.5
    assert r["avg_inference_seconds"] == 15.0
    assert r["first_run"].startswith("2026-06-01")
    assert r["last_run"].startswith("2026-06-02")


def test_pilot_report_empty_store(store):
    from app.reporting import pilot_report, pilot_report_markdown

    r = pilot_report()
    assert r["runs"] == 0 and r["fill_rate"] is None and r["verified_accuracy"] is None
    assert "No runs recorded" in pilot_report_markdown()


def test_retrieval_recall_runs_on_shipped_fixtures():
    """The analyzer must replay production retrieval over every gold fixture.

    Asserts structural integrity, not a frozen recall value — the number may
    legitimately move as fixtures/templates evolve. CI failing on a recall
    *drop* is handled by the printed report, reviewed in PRs.
    """
    import glob
    import json
    import os

    from eval.retrieval_recall import GOLD_DIR, analyze_fixture

    paths = sorted(glob.glob(os.path.join(GOLD_DIR, "*.json")))
    assert paths, "gold fixtures missing"
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            gold = json.load(fh)
        stats, misses = analyze_fixture(gold)
        assert stats["answerable"] > 0
        assert 0 <= stats["in_passages"] <= stats["answerable"]
        assert len(misses) == stats["answerable"] - stats["in_passages"]
