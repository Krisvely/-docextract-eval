"""Draft-golden builder for ``endorsement`` documents."""

from __future__ import annotations

from typing import Any

from .common import (
    clean_text,
    extract_labeled,
    normalize_currency,
    normalize_date,
    unwrap_input,
)

_CHANGE_TYPES = (
    "change_limit",
    "change_of_limit",
    "add_coverage",
    "remove_coverage",
    "change_deductible",
    "change_insured",
    "cancellation",
    "reinstatement",
    "other",
)


def _normalize_change_type(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower().replace("-", "_").replace(" ", "_")
    # "change of limit" → "change_limit" (canonical form in golden examples).
    if key == "change_of_limit":
        key = "change_limit"
    return key if key in _CHANGE_TYPES else key


def _from_structured(extraction: dict[str, Any]) -> dict[str, Any]:
    return {
        "insured_name": clean_text(extraction.get("insured_name")),
        "policy_number": clean_text(extraction.get("policy_number")),
        "carrier": clean_text(extraction.get("carrier")),
        "endorsement_number": clean_text(extraction.get("endorsement_number")),
        "endorsement_effective_date": normalize_date(
            extraction.get("endorsement_effective_date") or extraction.get("effective_date")
        ),
        "change_type": _normalize_change_type(extraction.get("change_type")),
        "affected_field": clean_text(extraction.get("affected_field")),
        "old_value": clean_text(extraction.get("old_value")),
        "new_value": clean_text(extraction.get("new_value")),
        "premium_delta": normalize_currency(
            extraction.get("premium_delta") or extraction.get("additional_premium")
        ),
    }


def _from_raw_text(text: str) -> dict[str, Any]:
    return {
        "insured_name": extract_labeled(text, "Named Insured", "Insured", "Insured Name"),
        "policy_number": extract_labeled(text, "Policy Number", "Policy No", "Policy #"),
        "carrier": extract_labeled(text, "Carrier", "Insurer"),
        "endorsement_number": extract_labeled(
            text, "Endorsement Number", "Endorsement No", "Endorsement #"
        ),
        "endorsement_effective_date": normalize_date(
            extract_labeled(
                text, "Endorsement Effective Date", "Effective Date", "Endt Effective Date"
            )
        ),
        "change_type": _normalize_change_type(
            extract_labeled(text, "Change Type", "Change")
        ),
        "affected_field": extract_labeled(text, "Affected Field"),
        "old_value": extract_labeled(text, "Prior Value", "Old Value"),
        "new_value": extract_labeled(text, "New Value"),
        "premium_delta": normalize_currency(
            extract_labeled(text, "Additional Premium", "Premium Delta", "Premium Change")
        ),
    }


def build(payload: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
    extraction, raw = unwrap_input(payload)
    if extraction:
        top = _from_structured(extraction)
    elif raw:
        top = _from_raw_text(raw)
    else:
        top = {}
    return {
        "document_id": document_id or payload.get("document_id"),
        "doc_type": "endorsement",
        "_draft": True,
        "top_level_fields": top,
    }
