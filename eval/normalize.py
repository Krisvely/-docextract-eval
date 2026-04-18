from __future__ import annotations

from datetime import datetime
from typing import Any


def normalize_string(value: Any) -> str | None:
    """
    Normalize text values for safer comparisons.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return " ".join(text.lower().split())


def normalize_float(value: Any) -> float | None:
    """
    Normalize numeric values to float.
    """
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_date(value: Any) -> str | None:
    """
    Convert supported date formats into ISO format: YYYY-MM-DD
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    supported_formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
    ]

    for fmt in supported_formats:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return text


def claims_by_number(claims: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    """
    Convert a claims list into a dictionary keyed by claim_number.
    """
    if not claims:
        return {}

    result: dict[str, dict[str, Any]] = {}

    for claim in claims:
        claim_number = claim.get("claim_number")
        if claim_number is not None:
            result[str(claim_number)] = claim

    return result