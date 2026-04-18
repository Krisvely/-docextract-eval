from __future__ import annotations

import argparse
import json
from typing import Any

from eval.invariants.calibration import summarize_calibration
from eval.invariants.selector import invariants_for
from eval.report import choose_representative_run
from eval.scoring import (
    compute_bias_metrics,
    compute_model_status,
    compute_variance_metrics,
    summarize_invariant_results,
)
from eval.utils import load_json


def build_invariants(doc_type: str | None = None) -> list:
    """Return the invariant list for ``doc_type``.

    ``doc_type=None`` preserves the historic loss_run behaviour, so the
    existing single-doc loss_run flow keeps working unchanged.
    """
    return invariants_for(doc_type)


def evaluate_run(
    run: dict[str, Any],
    golden: dict[str, Any] | None,
    invariants: list,
) -> list[dict[str, Any]]:
    results = []
    for invariant in invariants:
        result = invariant.evaluate(run, golden)
        results.append(
            {
                "name": result.name,
                "category": getattr(invariant, "category", "unknown"),
                "passed": result.passed,
                "severity": result.severity,
                "details": result.details,
            }
        )
    return results


def _infer_doc_type(runs: list[dict[str, Any]], golden: dict[str, Any] | None) -> str | None:
    for run in runs:
        dt = run.get("summary", {}).get("doc_type")
        if dt:
            return dt
    if golden:
        return golden.get("doc_type") or golden.get("top_level_fields", {}).get("doc_type")
    return None


def evaluate_model_block(
    model_block: dict[str, Any],
    golden: dict[str, Any] | None,
    doc_type: str | None = None,
) -> dict[str, Any]:
    runs = model_block.get("runs", [])
    resolved_doc_type = doc_type or _infer_doc_type(runs, golden)
    invariants = build_invariants(resolved_doc_type)

    evaluated_runs = []
    for run in runs:
        invariant_results = evaluate_run(run, golden, invariants)
        run_copy = dict(run)
        run_copy["evaluated_invariants"] = invariant_results
        run_copy["evaluated_invariants_summary"] = summarize_invariant_results(invariant_results)
        evaluated_runs.append(run_copy)

    representative_run = choose_representative_run(evaluated_runs)

    aggregate = {
        "variance_metrics": {
            "total_paid": compute_variance_metrics(evaluated_runs, "total_paid"),
            "total_incurred": compute_variance_metrics(evaluated_runs, "total_incurred"),
            "classification_confidence": compute_variance_metrics(evaluated_runs, "classification_confidence"),
        },
        "bias_metrics": {
            "total_paid": compute_bias_metrics(evaluated_runs, golden, "total_paid"),
            "total_incurred": compute_bias_metrics(evaluated_runs, golden, "total_incurred"),
            "total_recoveries": compute_bias_metrics(evaluated_runs, golden, "total_recoveries"),
        },
        "calibration": summarize_calibration(evaluated_runs),
    }

    model_result = {
        "model": model_block.get("model"),
        "runs": evaluated_runs,
        "representative_run": representative_run,
        "aggregate": aggregate,
    }
    model_result["status"] = compute_model_status(model_result)
    return model_result


def evaluate_existing_output(
    output_json: dict[str, Any],
    golden: dict[str, Any] | None,
    doc_type: str | None = None,
) -> dict[str, Any]:
    models = output_json.get("models", [])
    resolved_doc_type = doc_type
    if resolved_doc_type is None and models:
        resolved_doc_type = _infer_doc_type(models[0].get("runs", []), golden)
    evaluated_models = [
        evaluate_model_block(model_block, golden, resolved_doc_type)
        for model_block in models
    ]

    comparison = {}
    for model in evaluated_models:
        rep = model.get("representative_run") or {}
        comparison[model["model"]] = {
            "doc_type": rep.get("summary", {}).get("doc_type"),
            "claim_count": rep.get("summary", {}).get("top_level_fields", {}).get("claim_count"),
            "total_paid": rep.get("summary", {}).get("top_level_fields", {}).get("total_paid"),
            "total_incurred": rep.get("summary", {}).get("top_level_fields", {}).get("total_incurred"),
            "classification_confidence": rep.get("summary", {}).get("classification_confidence"),
            "status": model.get("status"),
            "aggregate": model.get("aggregate", {}),
        }

    return {
        "document_id": output_json.get("document_id"),
        "doc_type": resolved_doc_type,
        "models": evaluated_models,
        "comparison": comparison,
    }


def _write_json(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Dual-mode runner. "
            "Extract mode: --document-id [--runs N --use-seed --models v1,v2 --output PATH]. "
            "Batch mode:   --all-docs [--runs N --use-seed --evaluate "
            "--reseed-before-second-pass --output PATH]. "
            "Evaluate mode: --output-json PATH [--golden-json PATH]."
        ),
    )
    # Evaluate-mode args.
    parser.add_argument("--output-json", help="Path to existing extraction report JSON (evaluate mode)")
    parser.add_argument("--golden-json", help="Path to golden JSON for the same document")
    # Extract / batch args.
    parser.add_argument("--document-id", help="Document id to extract (extract mode)")
    parser.add_argument("--all-docs", action="store_true", help="Iterate every document in the registry")
    parser.add_argument("--runs", type=int, default=3, help="Number of extraction runs per model")
    parser.add_argument("--use-seed", action="store_true", help="Use a deterministic seed series")
    parser.add_argument("--models", default="v1,v2", help="Comma-separated model versions to run")
    parser.add_argument("--output", help="Path to write the generated report JSON")
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="After extraction, evaluate each doc against its registered golden",
    )
    parser.add_argument(
        "--reseed-before-second-pass",
        action="store_true",
        help="Run a baseline pass, call POST /admin/reseed-bugs, then re-run and emit both",
    )

    args = parser.parse_args()

    if args.all_docs:
        from eval.batch import run_batch

        models = [m.strip() for m in args.models.split(",") if m.strip()]
        payload = run_batch(
            runs=args.runs,
            use_seed=args.use_seed,
            models=models,
            evaluate=args.evaluate,
            reseed_before_second_pass=args.reseed_before_second_pass,
        )
        if args.output:
            _write_json(args.output, payload)
            print(f"Wrote batch report to {args.output}")
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if args.document_id:
        from eval.extract import build_extraction_report

        models = [m.strip() for m in args.models.split(",") if m.strip()]
        report = build_extraction_report(
            document_id=args.document_id,
            runs=args.runs,
            use_seed=args.use_seed,
            models=models,
        )
        if args.output:
            _write_json(args.output, report)
            print(f"Wrote extraction report to {args.output}")
        else:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    if not args.output_json:
        parser.error(
            "must supply --document-id (extract mode), --all-docs (batch mode), "
            "or --output-json (evaluate mode)"
        )

    output_json = load_json(args.output_json)
    golden = load_json(args.golden_json) if args.golden_json else None

    result = evaluate_existing_output(output_json, golden)
    if args.output:
        _write_json(args.output, result)
        print(f"Wrote evaluation report to {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()