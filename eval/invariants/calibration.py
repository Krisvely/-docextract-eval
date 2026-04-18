from __future__ import annotations

from typing import Any

from .base import InvariantResult


def compute_run_correctness_proxy(run_result: dict[str, Any]) -> bool:
    """
    Temporary correctness proxy:
    - all document_checks pass
    - claim_incurred_pass_rate == 1.0

    Later, this should be replaced or complemented with golden-based correctness.
    """
    invariants = run_result.get("summary", {}).get("invariants", {})
    document_checks = invariants.get("document_checks", {})
    claim_pass_rate = invariants.get("claim_incurred_pass_rate")

    document_check_results = [
        bool(value.get("passed"))
        for value in document_checks.values()
        if isinstance(value, dict) and "passed" in value
    ]

    docs_ok = all(document_check_results) if document_check_results else False
    claims_ok = claim_pass_rate == 1.0

    return docs_ok and claims_ok


def summarize_calibration(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Very simple first pass:
    compares average confidence to observed correctness proxy.

    Later you can expand to:
    - confidence bins
    - ECE
    - Brier-style metric
    """
    if not runs:
        return {
            "run_count": 0,
            "mean_confidence": None,
            "observed_correct_rate": None,
            "overconfidence_gap": None,
        }

    confidences = []
    correctness = []

    for run in runs:
        confidence = run.get("summary", {}).get("classification_confidence")
        if confidence is not None:
            confidences.append(float(confidence) / 100.0)
            correctness.append(1.0 if compute_run_correctness_proxy(run) else 0.0)

    if not confidences:
        return {
            "run_count": len(runs),
            "mean_confidence": None,
            "observed_correct_rate": None,
            "overconfidence_gap": None,
        }

    mean_confidence = sum(confidences) / len(confidences)
    observed_correct_rate = sum(correctness) / len(correctness)
    overconfidence_gap = mean_confidence - observed_correct_rate

    return {
        "run_count": len(runs),
        "mean_confidence": round(mean_confidence, 4),
        "observed_correct_rate": round(observed_correct_rate, 4),
        "overconfidence_gap": round(overconfidence_gap, 4),
    }