"""All-docs batch orchestration.

Responsibilities
----------------
* Iterate every registered document and call the single-doc extraction path.
* Optionally evaluate each per-doc report against its registered golden.
* Optionally run a baseline pass, hit ``POST /admin/reseed-bugs``, and run a
  second pass so reviewers can compare stability after bug rotation.

Design notes
------------
The batch layer reuses ``eval.extract.build_extraction_report`` and
``eval.runner.evaluate_existing_output`` instead of re-implementing either;
adding a new doc type or a new invariant therefore requires no change here.
Per-doc failures are captured in-place so a single broken document never
aborts the whole batch.
"""

from __future__ import annotations

from typing import Any

from eval.extract import build_extraction_report
from eval.registry import doc_type_for, golden_path_for, load_registry
from eval.reseed import reseed_bugs
from eval.utils import load_json


def _extract_one(
    document_id: str,
    runs: int,
    use_seed: bool,
    models: list[str],
) -> dict[str, Any]:
    try:
        report = build_extraction_report(
            document_id=document_id,
            runs=runs,
            use_seed=use_seed,
            models=models,
        )
        return {"document_id": document_id, "status": "ok", "report": report}
    except Exception as exc:  # noqa: BLE001 - surface in output, don't abort batch
        return {
            "document_id": document_id,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }


def extract_all(
    runs: int,
    use_seed: bool,
    models: list[str],
) -> dict[str, Any]:
    registry = load_registry()
    results = [
        _extract_one(doc["document_id"], runs, use_seed, models) for doc in registry
    ]
    return {"runs": runs, "use_seed": use_seed, "models": models, "documents": results}


def _evaluate_one(entry: dict[str, Any]) -> dict[str, Any]:
    # Local import keeps batch import cheap for pure-extraction callers.
    from eval.runner import evaluate_existing_output

    if entry.get("status") != "ok":
        return entry
    document_id = entry["document_id"]
    report = entry["report"]

    golden_path = golden_path_for(document_id)
    golden = load_json(str(golden_path)) if golden_path else None
    doc_type = doc_type_for(document_id)

    evaluated = evaluate_existing_output(report, golden, doc_type=doc_type)
    return {
        "document_id": document_id,
        "status": "ok",
        "doc_type": doc_type,
        "golden_path": str(golden_path) if golden_path else None,
        "report": report,
        "evaluation": evaluated,
    }


def evaluate_all(pass_payload: dict[str, Any]) -> dict[str, Any]:
    evaluated = [_evaluate_one(entry) for entry in pass_payload.get("documents", [])]
    return {**pass_payload, "documents": evaluated, "batch_summary": _summarize(evaluated)}


def _summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
    per_model_status: dict[str, dict[str, int]] = {}
    errored = 0
    evaluated = 0
    for entry in entries:
        if entry.get("status") != "ok":
            errored += 1
            continue
        evaluation = entry.get("evaluation") or {}
        if not evaluation:
            continue
        evaluated += 1
        for model_name, model_summary in (evaluation.get("comparison") or {}).items():
            status = model_summary.get("status", "UNKNOWN")
            per_model_status.setdefault(model_name, {}).setdefault(status, 0)
            per_model_status[model_name][status] += 1
    return {
        "documents_total": len(entries),
        "documents_extracted_ok": sum(1 for e in entries if e.get("status") == "ok"),
        "documents_errored": errored,
        "documents_evaluated": evaluated,
        "per_model_status_counts": per_model_status,
    }


def _robustness_summary(
    baseline_docs: list[dict[str, Any]],
    post_reseed_docs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Per-document baseline-vs-post-reseed extraction status.

    The reseed contract is *robustness* (every doc still extracts cleanly
    after bug rotation), not output equality. This block gives reviewers
    the information they need to apply that rule without re-walking the
    full report: which docs degraded, which stayed OK, which were broken
    on both passes.
    """
    baseline_by_id = {d.get("document_id"): d.get("status") for d in baseline_docs}
    post_by_id = {d.get("document_id"): d.get("status") for d in post_reseed_docs}
    all_ids = sorted(set(baseline_by_id) | set(post_by_id))

    per_doc = []
    for doc_id in all_ids:
        b = baseline_by_id.get(doc_id, "missing")
        p = post_by_id.get(doc_id, "missing")
        per_doc.append(
            {
                "document_id": doc_id,
                "baseline_status": b,
                "post_reseed_status": p,
                "both_ok": b == "ok" and p == "ok",
            }
        )

    degraded = [
        e["document_id"]
        for e in per_doc
        if e["baseline_status"] == "ok" and e["post_reseed_status"] != "ok"
    ]
    return {
        "documents_total": len(per_doc),
        "documents_baseline_ok": sum(1 for e in per_doc if e["baseline_status"] == "ok"),
        "documents_post_reseed_ok": sum(
            1 for e in per_doc if e["post_reseed_status"] == "ok"
        ),
        "documents_both_ok": sum(1 for e in per_doc if e["both_ok"]),
        "documents_degraded_after_reseed": degraded,
        "all_post_reseed_ok": len(post_reseed_docs) > 0
        and all(e["post_reseed_status"] == "ok" for e in per_doc),
        "verdict": "PASS" if not degraded and post_reseed_docs else "FAIL",
        "per_document": per_doc,
    }


def run_batch(
    runs: int,
    use_seed: bool,
    models: list[str],
    evaluate: bool = False,
    reseed_before_second_pass: bool = False,
) -> dict[str, Any]:
    baseline = extract_all(runs=runs, use_seed=use_seed, models=models)
    if evaluate:
        baseline = evaluate_all(baseline)

    if not reseed_before_second_pass:
        return {"mode": "single_pass", "baseline": baseline}

    reseed_result = reseed_bugs()
    second = extract_all(runs=runs, use_seed=use_seed, models=models)
    if evaluate:
        second = evaluate_all(second)

    return {
        "mode": "reseed",
        "baseline": baseline,
        "reseed": reseed_result,
        "post_reseed": second,
        "pipeline_robust": _robustness_summary(
            baseline.get("documents", []) or [],
            second.get("documents", []) or [],
        ),
    }
