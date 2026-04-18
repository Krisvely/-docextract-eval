from __future__ import annotations

import json
import requests

from invariants import (
    check_claim_incurred_invariant,
    check_document_paid_sum,
    check_document_incurred_sum,
)

BASE_URL = "http://localhost:8000"


def fetch_extraction(document_id: str, model: str = "v1", seed: int = 42) -> dict:
    """
    Call the /extract endpoint and return the JSON response.
    """
    url = f"{BASE_URL}/extract"

    payload = {
        "document_id": document_id,
        "model": model,
        "seed": seed,
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    return response.json()


def run_claim_invariants(extraction: dict) -> list[dict]:
    """
    Run invariants on each claim.
    """
    results = []

    claims = extraction.get("claims", [])

    for claim in claims:
        result = check_claim_incurred_invariant(claim)

        results.append({
            "claim_number": claim.get("claim_number"),
            "result": result,
        })

    return results


def run_document_invariants(extraction: dict) -> dict:
    """
    Run document-level invariants.
    """
    return {
        "paid_sum_check": check_document_paid_sum(extraction),
        "incurred_sum_check": check_document_incurred_sum(extraction),
    }


def print_summary(claim_results: list[dict], doc_results: dict) -> None:
    """
    Print a readable summary.
    """
    total = len(claim_results)
    passed = sum(1 for r in claim_results if r["result"]["passed"])

    print("\n📊 CLAIM INVARIANTS")
    print(f"Passed: {passed}/{total}")

    failures = [r for r in claim_results if not r["result"]["passed"]]

    if failures:
        print("\n❌ Failed claims:")
        for f in failures[:5]:  # limit output
            print(f" - {f['claim_number']}: {f['result']}")

    print("\n📊 DOCUMENT INVARIANTS")

    for name, result in doc_results.items():
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{name}: {status} | {result}")


def main():
    document_id = "loss_run_libertymutual"

    print("Running eval...\n")

    for model in ["v1", "v2"]:
        print("\n" + "=" * 50)
        print(f"MODEL: {model}")
        print("=" * 50)

        data = fetch_extraction(document_id, model=model)
        extraction = data.get("extraction", {})

        claim_results = run_claim_invariants(extraction)
        doc_results = run_document_invariants(extraction)

        print_summary(claim_results, doc_results)


if __name__ == "__main__":
    main()