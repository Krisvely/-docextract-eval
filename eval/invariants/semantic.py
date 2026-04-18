from __future__ import annotations

from datetime import datetime
from typing import Any

from .base import Invariant, InvariantResult


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None

    formats = [
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%m/%d/%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class ValuationDateNotBeforePolicyEffectiveDate(Invariant):
    name = "valuation_date_not_before_policy_effective_date"
    category = "semantic"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        top = extracted_run.get("summary", {}).get("top_level_fields", {})
        policy_effective_date = top.get("policy_effective_date")
        valuation_date = top.get("valuation_date")

        policy_dt = _parse_date(policy_effective_date)
        valuation_dt = _parse_date(valuation_date)

        if not policy_dt or not valuation_dt:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={
                    "policy_effective_date": policy_effective_date,
                    "valuation_date": valuation_date,
                    "reason": "could not parse one or both dates",
                },
            )

        return InvariantResult(
            name=self.name,
            passed=valuation_dt >= policy_dt,
            severity="error",
            details={
                "policy_effective_date": policy_effective_date,
                "valuation_date": valuation_date,
            },
        )


class RequiredTopLevelFieldsPresent(Invariant):
    name = "required_top_level_fields_present"
    category = "semantic"

    REQUIRED_FIELDS = [
        "insured_name",
        "carrier",
        "policy_number",
        "policy_effective_date",
        "valuation_date",
        "total_paid",
        "total_incurred",
        "claim_count",
    ]

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        top = extracted_run.get("summary", {}).get("top_level_fields", {})
        missing = [field for field in self.REQUIRED_FIELDS if top.get(field) in (None, "", [])]

        return InvariantResult(
            name=self.name,
            passed=(len(missing) == 0),
            severity="error",
            details={"missing_fields": missing},
        )