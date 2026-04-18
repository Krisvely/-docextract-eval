"""Draft-golden builder for ``loss_run`` documents."""

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

_TOP_LEVEL_KEYS = (
    "insured_name",
    "carrier",
    "policy_number",
)


def _from_structured(extraction: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    top: dict[str, Any] = {}
    for key in _TOP_LEVEL_KEYS:
        top[key] = clean_text(extraction.get(key))
    top["policy_effective_date"] = normalize_date(extraction.get("policy_effective_date"))
    top["valuation_date"] = normalize_date(extraction.get("valuation_date"))
    top["total_paid"] = normalize_currency(extraction.get("total_paid"))
    top["total_recoveries"] = normalize_currency(extraction.get("total_recoveries"))
    top["total_incurred"] = normalize_currency(extraction.get("total_incurred"))

    loss_ratio = extraction.get("loss_ratio")
    try:
        top["loss_ratio"] = float(loss_ratio) if loss_ratio is not None else None
    except (TypeError, ValueError):
        top["loss_ratio"] = None

    claims_src = extraction.get("claims") or []
    claims: list[dict[str, Any]] = []
    for claim in claims_src:
        if not isinstance(claim, dict):
            continue
        claims.append(
            {
                "claim_number": clean_text(claim.get("claim_number")),
                "incurred": normalize_currency(
                    claim.get("total_incurred")
                    if claim.get("total_incurred") is not None
                    else claim.get("incurred")
                ),
            }
        )
    top["claim_count"] = len(claims) if claims else normalize_int(extraction.get("claim_count"))
    return top, claims


def _from_raw_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    top: dict[str, Any] = {
        "insured_name": extract_labeled(text, "Insured", "Insured Name", "Named Insured"),
        "carrier": extract_labeled(text, "Carrier", "Insurer", "Insurance Company"),
        "policy_number": extract_labeled(text, "Policy Number", "Policy No", "Policy #"),
        "policy_effective_date": normalize_date(
            extract_labeled(text, "Policy Effective Date", "Effective Date", "Policy Effective")
        ),
        "valuation_date": normalize_date(
            extract_labeled(text, "Valuation Date", "Loss Run Date", "As Of")
        ),
        "total_paid": normalize_currency(extract_labeled(text, "Total Paid", "Paid Total")),
        "total_recoveries": normalize_currency(
            extract_labeled(text, "Total Recoveries", "Recoveries")
        ),
        "total_incurred": normalize_currency(
            extract_labeled(text, "Total Incurred", "Incurred Total")
        ),
        "loss_ratio": None,
        "claim_count": normalize_int(extract_labeled(text, "Claim Count", "Number of Claims")),
    }
    ratio_txt = extract_labeled(text, "Loss Ratio")
    if ratio_txt:
        cleaned = ratio_txt.replace("%", "").strip()
        try:
            value = float(cleaned)
            top["loss_ratio"] = round(value / 100, 4) if "%" in ratio_txt else value
        except ValueError:
            top["loss_ratio"] = None
    return top, []


def build(payload: dict[str, Any], document_id: str | None = None) -> dict[str, Any]:
    extraction, raw = unwrap_input(payload)
    if extraction:
        top, claims = _from_structured(extraction)
    elif raw:
        top, claims = _from_raw_text(raw)
    else:
        top, claims = {}, []

    return {
        "document_id": document_id or payload.get("document_id"),
        "doc_type": "loss_run",
        "_draft": True,
        "top_level_fields": top,
        "claims": claims,
    }
