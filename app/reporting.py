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
