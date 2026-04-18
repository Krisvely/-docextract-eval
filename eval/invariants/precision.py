from __future__ import annotations

from typing import Any

from .base import Invariant, InvariantResult


class NumericFieldMatchesGolden(Invariant):
    category = "precision"

    def __init__(self, field_name: str, tolerance: float = 0.01):
        self.field_name = field_name
        self.tolerance = tolerance
        self.name = f"numeric_field_matches_golden::{field_name}"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        if golden is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": "golden not provided"},
            )

        actual = extracted_run.get("summary", {}).get("top_level_fields", {}).get(self.field_name)
        expected = golden.get("top_level_fields", {}).get(self.field_name)

        if actual is None or expected is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"actual": actual, "expected": expected, "reason": "missing value"},
            )

        passed = abs(float(actual) - float(expected)) <= self.tolerance
        return InvariantResult(
            name=self.name,
            passed=passed,
            severity="error",
            details={
                "actual": actual,
                "expected": expected,
                "tolerance": self.tolerance,
                "abs_error": abs(float(actual) - float(expected)),
            },
        )


class StringFieldMatchesGolden(Invariant):
    category = "precision"

    def __init__(self, field_name: str, normalize: bool = True):
        self.field_name = field_name
        self.normalize = normalize
        self.name = f"string_field_matches_golden::{field_name}"

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value).strip().lower()

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        if golden is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"reason": "golden not provided"},
            )

        actual = extracted_run.get("summary", {}).get("top_level_fields", {}).get(self.field_name)
        expected = golden.get("top_level_fields", {}).get(self.field_name)

        if actual is None or expected is None:
            return InvariantResult(
                name=self.name,
                passed=False,
                severity="warning",
                details={"actual": actual, "expected": expected, "reason": "missing value"},
            )

        if self.normalize:
            passed = self._norm(actual) == self._norm(expected)
        else:
            passed = actual == expected

        return InvariantResult(
            name=self.name,
            passed=passed,
            severity="error",
            details={"actual": actual, "expected": expected, "normalized": self.normalize},
        )