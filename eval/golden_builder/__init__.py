"""Draft-golden builder package.

Produces *silver* data (draft goldens) that a human reviewer can promote to a
real golden. Never invents values — unknown fields are emitted as ``null``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import binder, coi, endorsement, loss_run, sov

_DOC_TYPE_ALIASES: dict[str, str] = {
    "loss_run": "loss_run",
    "binder": "temporary_coverage_binder",
    "temporary_coverage_binder": "temporary_coverage_binder",
    "sov": "statement_of_values",
    "statement_of_values": "statement_of_values",
    "coi": "coi",
    "certificate_of_insurance": "coi",
    "acord_25": "coi",
    "endorsement": "endorsement",
    "policy_endorsement": "endorsement",
}

_BUILDERS = {
    "loss_run": loss_run.build,
    "temporary_coverage_binder": binder.build,
    "statement_of_values": sov.build,
    "coi": coi.build,
    "endorsement": endorsement.build,
}


def _infer_doc_type(payload: dict[str, Any]) -> str | None:
    explicit = payload.get("doc_type") if isinstance(payload, dict) else None
    if explicit:
        canonical = _DOC_TYPE_ALIASES.get(str(explicit).strip().lower())
        if canonical:
            return canonical

    extraction = payload.get("extraction") if isinstance(payload, dict) else None
    source = extraction if isinstance(extraction, dict) else payload
    if isinstance(source, dict):
        if "endorsement_number" in source or "endorsement_effective_date" in source or (
            "change_type" in source and "affected_field" in source
        ):
            return "endorsement"
        if "claims" in source or "loss_ratio" in source:
            return "loss_run"
        if "binder_number" in source or "binder_effective_date" in source:
            return "temporary_coverage_binder"
        if "properties" in source or "total_tiv" in source or "total_insured_value" in source:
            return "statement_of_values"
        if "certificate_holder" in source or (
            "coverages" in source and "description_of_operations" in source
        ):
            return "coi"

    raw = payload.get("raw_text") if isinstance(payload, dict) else None
    if isinstance(raw, str):
        text = raw.lower()
        if "endorsement number" in text or "policy endorsement" in text or "endorsement effective" in text:
            return "endorsement"
        if "loss run" in text or "claim number" in text:
            return "loss_run"
        if "binder number" in text or "binder effective" in text:
            return "temporary_coverage_binder"
        if "statement of values" in text or "total insured value" in text:
            return "statement_of_values"
        if "certificate of insurance" in text or "certificate holder" in text or "acord 25" in text:
            return "coi"
    return None


def build_golden(
    payload: dict[str, Any],
    doc_type: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any]:
    """Produce a draft golden from a structured or raw-text payload."""
    canonical: str | None
    if doc_type:
        canonical = _DOC_TYPE_ALIASES.get(doc_type.strip().lower())
        if canonical is None:
            raise ValueError(f"Unsupported doc_type: {doc_type!r}")
    else:
        canonical = _infer_doc_type(payload)
    if canonical is None:
        raise ValueError(
            "Could not infer doc_type. Pass --doc-type with one of: "
            + ", ".join(sorted(set(_BUILDERS)))
        )
    builder_fn = _BUILDERS[canonical]
    return builder_fn(payload, document_id=document_id)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="eval.golden_builder",
        description="Generate draft (silver) golden JSON for human review.",
    )
    parser.add_argument("--input", help="Path to a single source JSON (structured or raw_text)")
    parser.add_argument("--output", help="Path to write the draft golden JSON (single-file mode)")
    parser.add_argument(
        "--doc-type",
        help="Override doc_type (loss_run | binder | sov | temporary_coverage_binder | statement_of_values)",
    )
    parser.add_argument("--document-id", help="Override document_id in the emitted golden")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Batch mode: iterate every *.json in --source-dir and write drafts to --output-dir",
    )
    parser.add_argument(
        "--source-dir",
        default="data/ground_truth",
        help="Batch source directory (default: data/ground_truth)",
    )
    parser.add_argument(
        "--output-dir",
        default="eval/datasets/goldens",
        help="Batch output directory (default: eval/datasets/goldens)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Batch mode: overwrite existing golden files (default: skip)",
    )
    return parser.parse_args(argv)


def _write_single(payload: dict[str, Any], args: argparse.Namespace) -> int:
    draft = build_golden(
        payload,
        doc_type=args.doc_type,
        document_id=args.document_id,
    )
    serialized = json.dumps(draft, indent=2, ensure_ascii=False)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(serialized + "\n", encoding="utf-8")
        print(f"Wrote draft golden to {out}")
    else:
        print(serialized)
    return 0


def _run_batch(args: argparse.Namespace) -> int:
    src_dir = Path(args.source_dir)
    out_dir = Path(args.output_dir)
    if not src_dir.is_dir():
        print(f"source dir not found: {src_dir}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    skipped: list[tuple[str, str]] = []
    failed: list[tuple[str, str]] = []

    for src in sorted(src_dir.glob("*.json")):
        try:
            with src.open("r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:  # noqa: BLE001
            failed.append((src.name, f"read error: {exc}"))
            continue

        out_path = out_dir / src.name
        if out_path.exists() and not args.overwrite:
            skipped.append((src.name, "exists (use --overwrite to replace)"))
            continue

        try:
            draft = build_golden(payload)
        except ValueError as exc:
            skipped.append((src.name, str(exc)))
            continue
        except Exception as exc:  # noqa: BLE001
            failed.append((src.name, f"{type(exc).__name__}: {exc}"))
            continue

        out_path.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(src.name)

    print(f"wrote {len(written)} draft golden(s) to {out_dir}")
    for name in written:
        print(f"  + {name}")
    if skipped:
        print(f"skipped {len(skipped)}:")
        for name, reason in skipped:
            print(f"  - {name}: {reason}")
    if failed:
        print(f"failed {len(failed)}:", file=sys.stderr)
        for name, reason in failed:
            print(f"  ! {name}: {reason}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.all:
        return _run_batch(args)

    if not args.input:
        print("must supply --input (single-file mode) or --all (batch mode)", file=sys.stderr)
        return 2

    src = Path(args.input)
    if not src.is_file():
        print(f"input not found: {src}", file=sys.stderr)
        return 2
    with src.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    return _write_single(payload, args)


__all__ = ["build_golden", "main"]
