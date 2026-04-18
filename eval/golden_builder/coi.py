"""Draft-golden builder for ``coi`` (certificate of insurance) documents."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .common import (
    clean_text,
    extract_labeled,
    normalize_currency,
    normalize_date,
    normalize_int,
    unwrap_input,
)

_COVERAGE_TYPES = (
    "general_liability",
    "auto",
    "umbrella",
    "workers_comp",
    "professional_liability",
    "cyber",
)


def _normalize_coverage_type(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    key = text.lower().replace("-", "_").replace(" ", "_")
    return key if key in _COVERAGE_TYPES else key or None


def _build_coverages(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    coverages_src = extraction.get("coverages") or []
    coverages: list[dict[str, Any]] = []
    for cov in coverages_src:
        if not isinstance(cov, dict):
            continue
        coverages.append(
            {
                "coverage_type": _normalize_coverage_type(cov.get("coverage_type")),
                "policy_number": clean_text(cov.get("policy_number")),
                "carrier": clean_text(cov.get("carrier")),
                "effective_date": normalize_date(cov.get("effective_date")),
                "expiration_date": normalize_date(cov.get("expiration_date")),
                "each_occurrence_limit": normalize_currency(cov.get("each_occurrence_limit")),
                "general_aggregate_limit": normalize_currency(cov.get("general_aggregate_limit")),
                "products_completed_ops": normalize_currency(cov.get("products_completed_ops")),
            }
        )
    return coverages


def _dominant_carrier(coverages: list[dict[str, Any]]) -> str | None:
    names = [c.get("carrier") for c in coverages if c.get("carrier")]
    if not names:
        return None
    return Counter(names).most_common(1)[0][0]


def _from_structured(extraction: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    coverages = _build_coverages(extraction)
    top: dict[str, Any] = {
        "insured_name": clean_text(extraction.get("insured_name")),
        "certificate_holder": clean_text(extraction.get("certificate_holder")),
        "producer": clean_text(extraction.get("producer") or extraction.get("producer_name")),
        "carrier": clean_text(extraction.get("carrier")) or _dominant_carrier(coverages),
        "description_of_operations": clean_text(extraction.get("description_of_operations")),
        "coverage_count": len(coverages)
        or normalize_int(extraction.get("coverage_count")),
    }
    return top, coverages


def _from_raw_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    top: dict[str, Any] = {
        "insured_name": extract_labeled(text, "Insured", "Insured Name", "Named Insured"),
        "certificate_holder": extract_labeled(text, "Certificate Holder", "Holder"),
        "producer": extract_labeled(text, "Producer", "Producer Name", "Agent"),
        "carrier": extract_labeled(text, "Carrier", "Insurer"),
        "description_of_operations": extract_labeled(
            text, "Description of Operations", "Description Of Operations"
        ),
        "coverage_count": normalize_int(
            extract_labeled(text, "Coverage Count", "Number of Coverages")
        ),
    }
    return top, []


def build(payload: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
    extraction, raw = unwrap_input(payload)
    if extraction:
        top, coverages = _from_structured(extraction)
    elif raw:
        top, coverages = _from_raw_text(raw)
    else:
        top, coverages = {}, []
    return {
        "document_id": document_id or payload.get("document_id"),
        "doc_type": "coi",
        "_draft": True,
        "top_level_fields": top,
        "coverages": coverages,
    }
