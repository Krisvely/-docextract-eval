"""Draft-golden builder for ``temporary_coverage_binder`` documents."""

from __future__ import annotations

from typing import Any

from .common import (
    clean_text,
    diff_days,
    extract_labeled,
    normalize_currency,
    normalize_date,
    normalize_int,
    unwrap_input,
)

_LIMIT_KEY_ALIASES = {
    "each_occurrence_limit": "each_occurrence",
    "general_aggregate_limit": "general_aggregate",
    "products_completed_ops": "products_completed_operations_aggregate",
    "products_completed_operations_aggregate": "products_completed_operations_aggregate",
    "combined_single_limit": "combined_single_limit",
}


def _pretty_coverage_name(raw: str | None) -> str | None:
    if not raw:
        return None
    words = raw.replace("_", " ").replace("-", " ").split()
    return " ".join(w.capitalize() for w in words) if words else None


def _build_limits(coverage: dict[str, Any]) -> dict[str, Any]:
    limits: dict[str, Any] = {}
    for src_key, target_key in _LIMIT_KEY_ALIASES.items():
        if src_key in coverage:
            value = normalize_currency(coverage.get(src_key))
            if value is not None:
                limits[target_key] = value
    if isinstance(coverage.get("limits"), dict):
        for k, v in coverage["limits"].items():
            value = normalize_currency(v)
            if value is not None:
                limits[k] = value
    return limits


def _build_coverages(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    coverages_src = extraction.get("coverages") or []
    coverages: list[dict[str, Any]] = []
    for cov in coverages_src:
        if not isinstance(cov, dict):
            continue
        coverages.append(
            {
                "coverage_name": clean_text(cov.get("coverage_name"))
                or _pretty_coverage_name(cov.get("coverage_type")),
                "binder_policy_number": clean_text(
                    cov.get("binder_policy_number") or cov.get("policy_number")
                ),
                "effective_date": normalize_date(cov.get("effective_date")),
                "expiration_date": normalize_date(cov.get("expiration_date")),
                "limits": _build_limits(cov),
            }
        )
    return coverages


def _from_structured(extraction: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    coverages = _build_coverages(extraction)
    effective = normalize_date(extraction.get("binder_effective_date"))
    expiration = normalize_date(extraction.get("binder_expiration_date"))
    top: dict[str, Any] = {
        "carrier": clean_text(extraction.get("carrier")),
        "insured_name": clean_text(extraction.get("insured_name")),
        "insured_dba": clean_text(extraction.get("insured_dba")),
        "insured_address": clean_text(extraction.get("insured_address")),
        "producer_name": clean_text(extraction.get("producer_name") or extraction.get("producer")),
        "producer_address": clean_text(extraction.get("producer_address")),
        "producer_contact_email": clean_text(extraction.get("producer_contact_email")),
        "producer_contact_phone": clean_text(extraction.get("producer_contact_phone")),
        "binder_number": clean_text(extraction.get("binder_number")),
        "binding_authority_reference": clean_text(extraction.get("binding_authority_reference")),
        "anticipated_policy_number": clean_text(extraction.get("anticipated_policy_number")),
        "naic_number": clean_text(extraction.get("naic_number")),
        "binder_effective_date": effective,
        "binder_expiration_date": expiration,
        "binder_term_days": (
            normalize_int(extraction.get("binder_term_days"))
            if extraction.get("binder_term_days") is not None
            else diff_days(effective, expiration)
        ),
        "interim_premium": normalize_currency(extraction.get("interim_premium")),
        "coverage_count": len(coverages),
    }
    return top, coverages


def _from_raw_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    effective = normalize_date(extract_labeled(text, "Binder Effective Date", "Effective Date"))
    expiration = normalize_date(extract_labeled(text, "Binder Expiration Date", "Expiration Date"))
    top: dict[str, Any] = {
        "carrier": extract_labeled(text, "Carrier", "Insurer"),
        "insured_name": extract_labeled(text, "Insured", "Insured Name", "Named Insured"),
        "insured_dba": extract_labeled(text, "DBA", "Insured DBA"),
        "insured_address": extract_labeled(text, "Insured Address"),
        "producer_name": extract_labeled(text, "Producer", "Producer Name", "Agent"),
        "producer_address": extract_labeled(text, "Producer Address"),
        "producer_contact_email": extract_labeled(text, "Email", "Producer Email"),
        "producer_contact_phone": extract_labeled(text, "Phone", "Producer Phone"),
        "binder_number": extract_labeled(text, "Binder Number", "Binder No", "Binder #"),
        "binding_authority_reference": extract_labeled(text, "Binding Authority Reference"),
        "anticipated_policy_number": extract_labeled(text, "Anticipated Policy Number"),
        "naic_number": extract_labeled(text, "NAIC Number", "NAIC"),
        "binder_effective_date": effective,
        "binder_expiration_date": expiration,
        "binder_term_days": diff_days(effective, expiration),
        "interim_premium": normalize_currency(
            extract_labeled(text, "Interim Premium", "Premium")
        ),
        "coverage_count": normalize_int(extract_labeled(text, "Coverage Count")) or 0,
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
        "doc_type": "temporary_coverage_binder",
        "_draft": True,
        "top_level_fields": top,
        "coverages": coverages,
    }
