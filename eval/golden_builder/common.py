"""Shared normalization helpers used by the per-doc-type builders.

Design rule: every helper returns ``None`` on low-confidence input rather than
guessing. The builders intentionally produce silver data and never invent.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_NULL_TOKENS = {
    "",
    "none",
    "null",
    "n/a",
    "na",
    "unknown",
    "not reported",
    "(not reported)",
    "tbd",
    "-",
    "—",
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%d/%m/%y",
    "%Y/%m/%d",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
)

_CURRENCY_SUFFIX = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def is_null_token(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _NULL_TOKENS
    return False


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or is_null_token(text):
        return None
    return " ".join(text.split())


def normalize_date(value: Any) -> str | None:
    if is_null_token(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y-%m-%d")
    text = str(value).strip().strip(",").strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_currency(value: Any) -> float | None:
    """Parse $1,234.56 / $9.0M / $500K / 4125 / '(not reported)'."""
    if is_null_token(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().lower()
    if not text or is_null_token(text):
        return None
    text = text.replace("usd", "").replace("$", "").replace(",", "").strip()
    text = text.split()[0] if text else ""
    if not text:
        return None
    suffix_mult = 1.0
    if text[-1] in _CURRENCY_SUFFIX:
        suffix_mult = _CURRENCY_SUFFIX[text[-1]]
        text = text[:-1]
    try:
        return round(float(text) * suffix_mult, 2)
    except ValueError:
        return None


def normalize_int(value: Any) -> int | None:
    if is_null_token(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    text = str(value).strip().replace(",", "")
    if not text or is_null_token(text):
        return None
    try:
        return int(text)
    except ValueError:
        try:
            f = float(text)
            return int(f) if f.is_integer() else None
        except ValueError:
            return None


def diff_days(start_iso: str | None, end_iso: str | None) -> int | None:
    if not start_iso or not end_iso:
        return None
    try:
        a = datetime.strptime(start_iso, "%Y-%m-%d")
        b = datetime.strptime(end_iso, "%Y-%m-%d")
    except ValueError:
        return None
    return (b - a).days


def extract_labeled(text: str, *labels: str) -> str | None:
    """Pull the value that follows any of ``labels`` on the same line."""
    for label in labels:
        pattern = rf"(?mi)^\s*{re.escape(label)}\s*[:\-]\s*(.+?)\s*$"
        match = re.search(pattern, text)
        if match:
            value = clean_text(match.group(1))
            if value:
                return value
    return None


def unwrap_input(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Return (structured_fields, raw_text) from a loose input payload."""
    raw = payload.get("raw_text") if isinstance(payload, dict) else None
    if isinstance(payload, dict) and isinstance(payload.get("extraction"), dict):
        return payload["extraction"], raw
    return (payload or {}), raw
