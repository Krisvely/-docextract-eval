from __future__ import annotations

from typing import Any

from eval.normalize import normalize_float


def almost_equal(a: Any, b: Any, tolerance: float = 0.01) -> bool:
    """
    Compare two numeric values with tolerance.
    """
    a_num = normalize_float(a)
    b_num = normalize_float(b)

    if a_num is None or b_num is None:
        return False

    return abs(a_num - b_num) <= tolerance


def check_claim_incurred_invariant(claim: dict[str, Any], tolerance: float = 0.01) -> dict[str, Any]:
    """
    Check if paid_amount + reserved_amount ~= total_incurred for a single claim.
    """
    paid = normalize_float(claim.get("paid_amount"))
    reserved = normalize_float(claim.get("reserved_amount"))
    incurred = normalize_float(claim.get("total_incurred"))

    if paid is None or reserved is None or incurred is None:
        return {
            "passed": False,
            "reason": "missing_numeric_field",
        }

    expected = paid + reserved
    passed = abs(expected - incurred) <= tolerance

    return {
        "passed": passed,
        "expected": round(expected, 2),
        "actual": round(incurred, 2),
    }


def check_document_paid_sum(extraction: dict[str, Any], tolerance: float = 0.01) -> dict[str, Any]:
    """
    Check if the sum of claim paid_amount values matches total_paid.
    """
    claims = extraction.get("claims", [])
    total_paid = normalize_float(extraction.get("total_paid"))

    if total_paid is None:
        return {
            "passed": False,
            "reason": "missing_total_paid",
        }

    paid_sum = 0.0
    for claim in claims:
        paid_value = normalize_float(claim.get("paid_amount"))
        if paid_value is not None:
            paid_sum += paid_value

    passed = abs(paid_sum - total_paid) <= tolerance

    return {
        "passed": passed,
        "expected": round(paid_sum, 2),
        "actual": round(total_paid, 2),
    }


def check_document_incurred_sum(extraction: dict[str, Any], tolerance: float = 0.01) -> dict[str, Any]:
    """
    Check if the sum of claim total_incurred values matches document total_incurred.
    """
    claims = extraction.get("claims", [])
    total_incurred = normalize_float(extraction.get("total_incurred"))

    if total_incurred is None:
        return {
            "passed": False,
            "reason": "missing_total_incurred",
        }

    incurred_sum = 0.0
    for claim in claims:
        incurred_value = normalize_float(claim.get("total_incurred"))
        if incurred_value is not None:
            incurred_sum += incurred_value

    passed = abs(incurred_sum - total_incurred) <= tolerance

    return {
        "passed": passed,
        "expected": round(incurred_sum, 2),
        "actual": round(total_incurred, 2),
    }