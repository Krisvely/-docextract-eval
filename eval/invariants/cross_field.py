from __future__ import annotations

from typing import Any

from .base import Invariant, InvariantResult


class ClaimCountMatchesParsedClaims(Invariant):
    name = "claim_count_matches_parsed_claims"
    category = "cross_field"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        summary = extracted_run.get("summary", {})
        top = summary.get("top_level_fields", {})
        claims = summary.get("claims", [])

        declared_count = top.get("claim_count")
        parsed_count = len(claims)

        # If claims are not yet present in extraction output, don't hard fail the framework.
        if declared_count is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": "claim_count missing from top_level_fields"},
            )

        if not isinstance(claims, list):
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": "claims field missing or not a list"},
            )

        return InvariantResult(
            name=self.name,
            passed=(declared_count == parsed_count) if claims else True,
            severity="warning" if not claims else "error",
            details={
                "declared_claim_count": declared_count,
                "parsed_claim_count": parsed_count,
                "claims_present": bool(claims),
            },
        )


class DocumentCheckPassed(Invariant):
    """
    Reuses the document-level checks already present in the model output.
    """

    def __init__(self, check_name: str):
        self.check_name = check_name
        self.name = f"document_check_{check_name}"
        self.category = "cross_field"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        checks = (
            extracted_run.get("summary", {})
            .get("invariants", {})
            .get("document_checks", {})
        )

        check = checks.get(self.check_name)
        if not check:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": f"document check '{self.check_name}' not found"},
            )

        return InvariantResult(
            name=self.name,
            passed=bool(check.get("passed")),
            severity="error",
            details=check,
        )


class ClaimIncurredPassRateThreshold(Invariant):
    def __init__(self, min_pass_rate: float = 1.0):
        self.min_pass_rate = min_pass_rate
        self.name = f"claim_incurred_pass_rate_gte_{min_pass_rate:.2f}"
        self.category = "cross_field"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        pass_rate = (
            extracted_run.get("summary", {})
            .get("invariants", {})
            .get("claim_incurred_pass_rate")
        )

        if pass_rate is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": "claim_incurred_pass_rate missing"},
            )

        return InvariantResult(
            name=self.name,
            passed=pass_rate >= self.min_pass_rate,
            severity="error",
            details={"actual": pass_rate, "minimum_required": self.min_pass_rate},
        )