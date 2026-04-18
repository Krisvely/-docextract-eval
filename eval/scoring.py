from __future__ import annotations

from typing import Any

from eval.utils import safe_mean, safe_stdev


def compute_variance_metrics(runs: list[dict[str, Any]], field_name: str) -> dict[str, Any]:
    values: list[float] = []

    for run in runs:
        if field_name == "classification_confidence":
            value = run.get("summary", {}).get("classification_confidence")
        else:
            value = run.get("summary", {}).get("top_level_fields", {}).get(field_name)

        if value is not None:
            values.append(float(value))

    if not values:
        return {
            "min": None,
            "max": None,
            "mean": None,
            "stdev": None,
            "coefficient_of_variation": None,
        }

    mean = safe_mean(values)
    stdev = safe_stdev(values)

    return {
        "min": min(values),
        "max": max(values),
        "mean": mean,
        "stdev": stdev,
        "coefficient_of_variation": (stdev / mean) if mean not in (None, 0) else None,
    }


def compute_bias_metrics(
    runs: list[dict[str, Any]],
    golden: dict[str, Any] | None,
    field_name: str,
) -> dict[str, Any]:
    if not golden:
        return {
            "golden": None,
            "mean_abs_error": None,
            "mean_signed_error": None,
        }

    expected = golden.get("top_level_fields", {}).get(field_name)
    if expected is None:
        return {
            "golden": None,
            "mean_abs_error": None,
            "mean_signed_error": None,
        }

    errors = []
    for run in runs:
        actual = run.get("summary", {}).get("top_level_fields", {}).get(field_name)
        if actual is not None:
            errors.append(float(actual) - float(expected))

    if not errors:
        return {
            "golden": expected,
            "mean_abs_error": None,
            "mean_signed_error": None,
        }

    mean_abs_error = sum(abs(e) for e in errors) / len(errors)
    mean_signed_error = sum(errors) / len(errors)

    return {
        "golden": expected,
        "mean_abs_error": mean_abs_error,
        "mean_signed_error": mean_signed_error,
    }


def summarize_invariant_results(invariant_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not invariant_results:
        return {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "pass_rate": None,
        }

    total = len(invariant_results)
    passed = sum(1 for item in invariant_results if item.get("passed") is True)
    failed = total - passed

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total else None,
    }


def compute_model_status(model_result: dict[str, Any]) -> str:
    """
    Simple first-pass status:
    - FAIL: representative run missing
    - INACCURATE: representative run fails critical precision checks
    - UNSTABLE: high variance in key numeric fields
    - PASS: otherwise
    """
    representative_run = model_result.get("representative_run")
    if not representative_run:
        return "FAIL"

    evaluated = representative_run.get("evaluated_invariants", [])

    critical_precision_fail = any(
        inv.get("category") == "precision" and inv.get("severity") == "error" and not inv.get("passed")
        for inv in evaluated
    )
    if critical_precision_fail:
        return "INACCURATE"

    aggregate = model_result.get("aggregate", {})
    variance = aggregate.get("variance_metrics", {})
    paid_cov = (variance.get("total_paid") or {}).get("coefficient_of_variation")
    incurred_cov = (variance.get("total_incurred") or {}).get("coefficient_of_variation")

    unstable = any(
        cov is not None and cov > 0.10
        for cov in [paid_cov, incurred_cov]
    )
    if unstable:
        return "UNSTABLE"

    return "PASS"