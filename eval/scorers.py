from __future__ import annotations

from typing import Any

from normalize import normalize_date, normalize_float, normalize_string


def score_string(predicted: Any, expected: Any) -> dict[str, Any]:
    pred = normalize_string(predicted)
    exp = normalize_string(expected)

    return {
        "passed": pred == exp,
        "predicted": pred,
        "expected": exp,
    }


def score_date(predicted: Any, expected: Any) -> dict[str, Any]:
    pred = normalize_date(predicted)
    exp = normalize_date(expected)

    return {
        "passed": pred == exp,
        "predicted": pred,
        "expected": exp,
    }


def score_float(predicted: Any, expected: Any, tolerance: float = 0.01) -> dict[str, Any]:
    pred = normalize_float(predicted)
    exp = normalize_float(expected)

    if pred is None or exp is None:
        return {
            "passed": False,
            "predicted": pred,
            "expected": exp,
            "reason": "non_numeric_value",
        }

    return {
        "passed": abs(pred - exp) <= tolerance,
        "predicted": pred,
        "expected": exp,
        "difference": round(abs(pred - exp), 4),
    }


def detect_magnitude_error(predicted: Any, expected: Any) -> bool:
    """
    Detect catastrophic numeric errors, like 42,000 becoming 4,200,000.
    """
    pred = normalize_float(predicted)
    exp = normalize_float(expected)

    if pred is None or exp is None:
        return False

    if exp == 0:
        return False

    ratio = abs(pred / exp)
    return ratio > 10 or ratio < 0.1