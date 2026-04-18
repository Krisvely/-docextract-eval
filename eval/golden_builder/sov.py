"""Draft-golden builder for ``statement_of_values`` documents."""

from __future__ import annotations

from typing import Any

from .common import (
    clean_text,
    extract_labeled,
    normalize_currency,
    normalize_date,
    normalize_int,
    unwrap_input,
)


def _compose_address(prop: dict[str, Any]) -> str | None:
    if prop.get("address") and any(prop.get(k) for k in ("city", "state", "zip_code")):
        parts = [
            clean_text(prop.get("address")),
            clean_text(prop.get("city")),
            clean_text(prop.get("state")),
            clean_text(prop.get("zip_code")),
        ]
        parts = [p for p in parts if p]
        joined = ", ".join(parts[:-1]) + (f" {parts[-1]}" if len(parts) > 1 else "")
        return joined or None
    return clean_text(prop.get("address"))


def _build_locations(extraction: dict[str, Any]) -> list[dict[str, Any]]:
    props = extraction.get("properties") or extraction.get("locations") or []
    locations: list[dict[str, Any]] = []
    for idx, prop in enumerate(props, start=1):
        if not isinstance(prop, dict):
            continue
        square_feet = normalize_int(prop.get("square_feet") or prop.get("square_footage"))
        locations.append(
            {
                "location_number": normalize_int(prop.get("location_number")) or idx,
                "address": _compose_address(prop),
                "construction_type": clean_text(prop.get("construction_type")),
                "construction_class": clean_text(prop.get("construction_class")),
                "year_built": normalize_int(prop.get("year_built")),
                "square_feet": square_feet,
                "occupancy": clean_text(prop.get("occupancy")),
                "building_value": normalize_currency(prop.get("building_value")),
                "contents_value": normalize_currency(prop.get("contents_value")),
                "business_income_value": normalize_currency(prop.get("business_income_value")),
                "location_tiv": normalize_currency(
                    prop.get("location_tiv") or prop.get("total_insured_value")
                ),
            }
        )
    return locations


def _from_structured(extraction: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    locations = _build_locations(extraction)
    top: dict[str, Any] = {
        "insured_name": clean_text(extraction.get("insured_name")),
        "carrier": clean_text(extraction.get("carrier")),
        "policy_number": clean_text(extraction.get("policy_number")),
        "policy_effective_date": normalize_date(
            extraction.get("policy_effective_date") or extraction.get("effective_date")
        ),
        "policy_expiration_date": normalize_date(
            extraction.get("policy_expiration_date") or extraction.get("expiration_date")
        ),
        "total_insured_value": normalize_currency(
            extraction.get("total_insured_value") or extraction.get("total_tiv")
        ),
        "location_count": len(locations) or normalize_int(extraction.get("location_count")),
    }
    return top, locations


def _from_raw_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    top: dict[str, Any] = {
        "insured_name": extract_labeled(text, "Insured", "Insured Name", "Named Insured"),
        "carrier": extract_labeled(text, "Carrier", "Insurer"),
        "policy_number": extract_labeled(text, "Policy Number", "Policy No"),
        "policy_effective_date": normalize_date(
            extract_labeled(text, "Policy Effective Date", "Effective Date")
        ),
        "policy_expiration_date": normalize_date(
            extract_labeled(text, "Policy Expiration Date", "Expiration Date")
        ),
        "total_insured_value": normalize_currency(
            extract_labeled(text, "Total Insured Value", "Total TIV", "TIV")
        ),
        "location_count": normalize_int(
            extract_labeled(text, "Location Count", "Number of Locations")
        ),
    }
    return top, []


def build(payload: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
    extraction, raw = unwrap_input(payload)
    if extraction:
        top, locations = _from_structured(extraction)
    elif raw:
        top, locations = _from_raw_text(raw)
    else:
        top, locations = {}, []
    return {
        "document_id": document_id or payload.get("document_id"),
        "doc_type": "statement_of_values",
        "_draft": True,
        "top_level_fields": top,
        "locations": locations,
    }
