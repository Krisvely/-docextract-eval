from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Any

import requests

from eval.invariants1 import (
    check_claim_incurred_invariant,
    check_document_incurred_sum,
    check_document_paid_sum,
)

BASE_URL = "http://localhost:8000"

# Deterministic seed series used when --use-seed is supplied.
_SEED_SERIES = [100, 101, 102, 103, 104, 105, 106, 107]

# Retry policy for /extract. The mock deliberately injects HTTP 429
# (rate-limit) and transient 500s; without retries an --all-docs run
# loses most of its calls. The policy is intentionally modest so that
# a genuinely down service still surfaces the failure in batch output.
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_MAX_RETRIES = int(os.environ.get("EVAL_EXTRACT_MAX_RETRIES", "5"))
_INITIAL_BACKOFF_S = float(os.environ.get("EVAL_EXTRACT_INITIAL_BACKOFF_S", "1.0"))
_MAX_BACKOFF_S = float(os.environ.get("EVAL_EXTRACT_MAX_BACKOFF_S", "16.0"))
# Optional inter-request throttle. Set EVAL_EXTRACT_THROTTLE_S to ~6.0 to
# stay under the mock's default 10-req/60s ceiling without relying on
# retry sleeps.
_THROTTLE_S = float(os.environ.get("EVAL_EXTRACT_THROTTLE_S", "0.0"))


def _retry_after_seconds(response: requests.Response | None) -> float | None:
    if response is None:
        return None
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _post_with_retry(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    backoff = _INITIAL_BACKOFF_S
    for attempt in range(_MAX_RETRIES + 1):
        if _THROTTLE_S > 0:
            time.sleep(_THROTTLE_S)
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status not in _RETRYABLE_STATUSES or attempt == _MAX_RETRIES:
                raise
            sleep_s = _retry_after_seconds(exc.response) or backoff
            time.sleep(sleep_s)
            backoff = min(backoff * 2, _MAX_BACKOFF_S)
    # Unreachable: the loop either returns a response or re-raises.
    raise RuntimeError("_post_with_retry exhausted without returning or raising")


def _flatten_top_level_fields(extraction: dict[str, Any]) -> dict[str, Any]:
    top = {k: v for k, v in extraction.items() if not isinstance(v, (list, dict))}
    if "claims" in extraction and "claim_count" not in top:
        top["claim_count"] = len(extraction["claims"])
    if "properties" in extraction and "location_count" not in top:
        top["location_count"] = len(extraction["properties"])
    if "coverages" in extraction and "coverage_count" not in top:
        top["coverage_count"] = len(extraction["coverages"])
    return top


def _compute_loss_run_invariants(extraction: dict[str, Any]) -> dict[str, Any]:
    claims = extraction.get("claims", []) or []
    claim_checks = []
    for claim in claims:
        result = check_claim_incurred_invariant(claim)
        claim_checks.append(
            {
                "claim_number": claim.get("claim_number"),
                "passed": bool(result.get("passed")),
                "details": result,
            }
        )
    pass_rate = (
        sum(1 for c in claim_checks if c["passed"]) / len(claim_checks)
        if claim_checks
        else None
    )
    return {
        "claim_incurred_checks": claim_checks,
        "claim_incurred_pass_rate": pass_rate,
        "document_checks": {
            "paid_sum_check": check_document_paid_sum(extraction),
            "incurred_sum_check": check_document_incurred_sum(extraction),
        },
    }


def _compute_sov_invariants(extraction: dict[str, Any]) -> dict[str, Any]:
    """Cross-field invariants for SOVs.

    ``tiv_sum_check`` asserts that the sum of per-property
    ``total_insured_value`` matches the top-level ``total_tiv`` to within
    one cent. Wired into the SOV selector via ``DocumentCheckPassed``.
    """
    properties = extraction.get("properties", []) or []
    expected = extraction.get("total_tiv")
    values = [
        float(p.get("total_insured_value"))
        for p in properties
        if isinstance(p, dict) and p.get("total_insured_value") is not None
    ]
    actual = round(sum(values), 2)
    passed = (
        expected is not None
        and abs(actual - float(expected)) <= 0.01
    )
    return {
        "document_checks": {
            "tiv_sum_check": {
                "passed": bool(passed),
                "actual": actual,
                "expected": expected,
                "tolerance": 0.01,
                "property_count": len(properties),
            },
        },
    }


_BINDER_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m/%d/%y")


def _parse_loose_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    for fmt in _BINDER_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _compute_binder_invariants(extraction: dict[str, Any]) -> dict[str, Any]:
    """Cross-field invariants for binders.

    ``binder_dates_in_order`` asserts that the binder expiration date is
    at or after the binder effective date. Unparseable dates surface as
    ``passed=False`` so the selector's ``DocumentCheckPassed`` wrapper can
    treat the check as failed rather than missing.
    """
    eff_raw = extraction.get("binder_effective_date")
    exp_raw = extraction.get("binder_expiration_date")
    eff = _parse_loose_date(eff_raw)
    exp = _parse_loose_date(exp_raw)
    passed = eff is not None and exp is not None and exp >= eff
    return {
        "document_checks": {
            "binder_dates_in_order": {
                "passed": bool(passed),
                "effective": eff_raw,
                "expiration": exp_raw,
                "parsed": eff is not None and exp is not None,
            },
        },
    }


def _compute_invariants_block(doc_type: str | None, extraction: dict[str, Any]) -> dict[str, Any]:
    if doc_type == "loss_run":
        return _compute_loss_run_invariants(extraction)
    if doc_type in ("sov", "statement_of_values"):
        return _compute_sov_invariants(extraction)
    if doc_type in ("binder", "temporary_coverage_binder"):
        return _compute_binder_invariants(extraction)
    return {}


def _call_extract(document_id: str, model: str, seed: int | None) -> dict[str, Any]:
    payload: dict[str, Any] = {"document_id": document_id, "model": model}
    if seed is not None:
        payload["seed"] = seed
    return _post_with_retry(f"{BASE_URL}/extract", payload)


def _run_once(
    document_id: str,
    model: str,
    seed: int | None,
    run_index: int,
) -> dict[str, Any]:
    started = time.monotonic()
    response = _call_extract(document_id, model, seed)
    wall = round(time.monotonic() - started, 3)

    extraction = response.get("extraction", {}) or {}
    classification = response.get("classification", {}) or {}
    metadata = response.get("metadata", {}) or {}

    invariants_block = _compute_invariants_block(classification.get("doc_type"), extraction)

    summary: dict[str, Any] = {
        "doc_type": classification.get("doc_type"),
        "classification_confidence": classification.get("confidence"),
        "processing_time_ms": metadata.get("processing_time_ms"),
        "model_name": metadata.get("model"),
        "model_version": metadata.get("model_version"),
        "top_level_fields": _flatten_top_level_fields(extraction),
        "invariants": invariants_block,
    }
    if isinstance(extraction.get("claims"), list):
        summary["claims"] = extraction["claims"]
    if isinstance(extraction.get("properties"), list):
        summary["properties"] = extraction["properties"]
    if isinstance(extraction.get("coverages"), list):
        summary["coverages"] = extraction["coverages"]

    return {
        "run_index": run_index,
        "seed": seed,
        "wall_time_s": wall,
        "summary": summary,
    }


def build_extraction_report(
    document_id: str,
    runs: int,
    use_seed: bool,
    models: list[str] | None = None,
) -> dict[str, Any]:
    models = models or ["v1", "v2"]
    report: dict[str, Any] = {"document_id": document_id, "models": []}
    for model in models:
        model_runs: list[dict[str, Any]] = []
        for i in range(runs):
            seed = _SEED_SERIES[i % len(_SEED_SERIES)] if use_seed else None
            model_runs.append(_run_once(document_id, model, seed, i + 1))
        report["models"].append({"model": model, "runs": model_runs})
    return report
