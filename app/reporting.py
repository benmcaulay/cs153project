"""
Per-(model, style) accuracy reporting (FR-14).

Aggregates administrator flags across run records into accuracy, needs-review
rate, and average inference time so an administrator can fit the best model to
each document class. This is the evaluation instrument of §14.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List

from .models import ModelStyleStats
from .store import list_runs


def model_style_report() -> List[ModelStyleStats]:
    buckets = defaultdict(
        lambda: {
            "runs": 0,
            "flagged": 0,
            "correct": 0,
            "incorrect": 0,
            "needs_review": 0,
            "total": 0,
            "time_sum": 0.0,
        }
    )

    for run in list_runs():
        style = run.style or "unassigned"
        b = buckets[(run.model, style)]
        b["runs"] += 1
        b["time_sum"] += run.inference_seconds
        for f in run.fields:
            b["total"] += 1
            if not f.found:
                b["needs_review"] += 1
            if f.admin_flag == "correct":
                b["flagged"] += 1
                b["correct"] += 1
            elif f.admin_flag == "incorrect":
                b["flagged"] += 1
                b["incorrect"] += 1

    report: List[ModelStyleStats] = []
    for (model, style), b in sorted(buckets.items()):
        report.append(
            ModelStyleStats(
                model=model,
                style=style,
                runs=b["runs"],
                fields_flagged=b["flagged"],
                fields_correct=b["correct"],
                fields_incorrect=b["incorrect"],
                needs_review_fields=b["needs_review"],
                total_fields=b["total"],
                avg_inference_seconds=round(b["time_sum"] / b["runs"], 3) if b["runs"] else 0.0,
            )
        )
    return report


# --------------------------------------------------------------------------- #
# Pilot report: deployment-wide aggregate across all runs
# --------------------------------------------------------------------------- #
def pilot_report() -> dict:
    """One honest paragraph of numbers for a deployment (e.g. a firm pilot).

    Aggregates every run record on this host: volume, fill vs needs-review
    rates, attorney-verified accuracy among flagged fields, and latency. These
    are the figures a pilot write-up or pitch should quote — measured, not
    asserted. `verified_accuracy` is only computed over fields a human actually
    flagged; unflagged fields are never counted as correct.
    """
    runs = list_runs()
    total_fields = filled = needs_review = flagged = correct = incorrect = 0
    time_sum = 0.0
    matters, templates, models = set(), set(), set()
    first_ts: str | None = None
    last_ts: str | None = None

    for run in runs:
        matters.add(run.matter_id)
        templates.add(run.template_id)
        models.add(run.model)
        time_sum += run.inference_seconds
        ts = run.timestamp
        first_ts = ts if first_ts is None or ts < first_ts else first_ts
        last_ts = ts if last_ts is None or ts > last_ts else last_ts
        for f in run.fields:
            total_fields += 1
            if f.found:
                filled += 1
            else:
                needs_review += 1
            if f.admin_flag == "correct":
                flagged += 1
                correct += 1
            elif f.admin_flag == "incorrect":
                flagged += 1
                incorrect += 1

    def _rate(n: int, d: int) -> float | None:
        return round(n / d, 4) if d else None

    return {
        "runs": len(runs),
        "matters": len(matters),
        "templates": len(templates),
        "models_used": sorted(models),
        "first_run": first_ts,
        "last_run": last_ts,
        "fields_total": total_fields,
        "fields_filled": filled,
        "fields_needs_review": needs_review,
        "fill_rate": _rate(filled, total_fields),
        "needs_review_rate": _rate(needs_review, total_fields),
        "fields_human_flagged": flagged,
        "flagged_correct": correct,
        "flagged_incorrect": incorrect,
        "verified_accuracy": _rate(correct, flagged),
        "avg_inference_seconds": round(time_sum / len(runs), 2) if runs else None,
    }


def pilot_report_markdown() -> str:
    r = pilot_report()
    pct = lambda v: f"{v * 100:.1f}%" if v is not None else "n/a"  # noqa: E731
    lines = [
        "# Verbatim pilot report",
        "",
        f"- Period: {r['first_run']} to {r['last_run']}" if r["runs"] else "- No runs recorded yet.",
        f"- Runs: {r['runs']} across {r['matters']} matter(s), {r['templates']} template(s); "
        f"models: {', '.join(r['models_used']) or 'none'}",
        f"- Fields processed: {r['fields_total']} - filled {r['fields_filled']} ({pct(r['fill_rate'])}), "
        f"needs-review {r['fields_needs_review']} ({pct(r['needs_review_rate'])})",
        f"- Human-verified fields: {r['fields_human_flagged']} flagged - "
        f"{r['flagged_correct']} correct / {r['flagged_incorrect']} incorrect "
        f"(verified accuracy {pct(r['verified_accuracy'])})",
        f"- Avg inference time per run: {r['avg_inference_seconds']}s" if r["runs"] else "- Avg inference time per run: n/a",
        "",
        "_All figures computed from immutable local run records "
        "(`python -m app.reporting`). Verified accuracy covers only fields an "
        "attorney explicitly flagged; unflagged fields are never assumed correct._",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(pilot_report_markdown())
