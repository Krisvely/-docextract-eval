from __future__ import annotations

import requests

from ground_truth import load_ground_truth

BASE_URL = "http://localhost:8000"


def call_extract(document_id: str, model: str) -> dict:
    payload = {
        "document_id": document_id,
        "model": model,
    }

    response = requests.post(f"{BASE_URL}/extract", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def safe_ratio(pred: float, truth: float) -> float | None:
    if pred == 0 or truth == 0:
        return None
    return max(abs(pred / truth), abs(truth / pred))


def is_catastrophic(pred: float, truth: float) -> bool:
    ratio = safe_ratio(pred, truth)
    return ratio is not None and ratio > 10


def compare_totals(pred: dict, truth: dict):
    fields = ["total_paid", "total_recoveries", "total_incurred"]
    results = []

    for field in fields:
        p = pred.get(field)
        t = truth.get(field)

        if p is None or t is None:
            results.append({
                "field": field,
                "predicted": p,
                "expected": t,
                "error": None,
                "catastrophic": False,
                "status": "missing_field",
            })
            continue

        error = abs(p - t)
        catastrophic = is_catastrophic(p, t)

        results.append({
            "field": field,
            "predicted": p,
            "expected": t,
            "error": error,
            "catastrophic": catastrophic,
            "status": "compared",
        })

    return results


def index_claims(claims: list[dict]) -> dict:
    return {c["claim_number"]: c for c in claims if "claim_number" in c}


def compare_claims(pred_claims: list, truth_claims: list):
    pred_map = index_claims(pred_claims)
    truth_map = index_claims(truth_claims)

    results = []
    catastrophic_count = 0

    for claim_number, truth_claim in truth_map.items():
        pred_claim = pred_map.get(claim_number)

        if not pred_claim:
            results.append({
                "claim_number": claim_number,
                "field": None,
                "error": "missing_claim",
            })
            continue

        for field in ["paid_amount", "reserved_amount", "total_incurred"]:
            p = pred_claim.get(field)
            t = truth_claim.get(field)

            if p is None or t is None:
                results.append({
                    "claim_number": claim_number,
                    "field": field,
                    "predicted": p,
                    "expected": t,
                    "catastrophic": False,
                    "status": "missing_field",
                })
                continue

            catastrophic = is_catastrophic(p, t)
            if catastrophic:
                catastrophic_count += 1

            results.append({
                "claim_number": claim_number,
                "field": field,
                "predicted": p,
                "expected": t,
                "difference": abs(p - t),
                "catastrophic": catastrophic,
                "status": "compared",
            })

    return results, catastrophic_count


def run_eval(document_id: str, model: str):
    print(f"\nRunning truth comparison for {model}...\n")

    response = call_extract(document_id, model)
    pred = response["extraction"]
    truth = load_ground_truth(document_id)

    print("Truth keys:", list(truth.keys()))
    print("Pred keys:", list(pred.keys()))

    total_results = compare_totals(pred, truth)
    claim_results, catastrophic_claims = compare_claims(
        pred.get("claims", []),
        truth.get("claims", [])
    )

    catastrophic_totals = sum(
        1 for r in total_results if r.get("catastrophic")
    )

    print("\nTOTAL FIELD COMPARISON")
    for r in total_results:
        print(r)

    print("\nCLAIM ERRORS (sample)")
    for r in claim_results[:10]:
        print(r)

    print("\nSUMMARY")
    print(f"Compared total fields: {sum(1 for r in total_results if r['status'] == 'compared')}")
    print(f"Compared claim fields: {sum(1 for r in claim_results if r.get('status') == 'compared')}")
    print(f"Catastrophic total errors: {catastrophic_totals}")
    print(f"Catastrophic claim errors: {catastrophic_claims}")


if __name__ == "__main__":
    DOC = "loss_run_libertymutual"

    run_eval(DOC, "v1")
    run_eval(DOC, "v2")