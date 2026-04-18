"""Doc-type aware invariant selection.

The invariants themselves are generic; this module is the single place that
decides which ones apply to which doc type. Add a new doc type by writing a
selector function and registering it in ``_SELECTORS`` — no runner change
required.
"""

from __future__ import annotations

from typing import Callable

from .cross_field import (
    ClaimCountMatchesParsedClaims,
    ClaimIncurredPassRateThreshold,
    DocumentCheckPassed,
)
from .precision import NumericFieldMatchesGolden, StringFieldMatchesGolden
from .semantic import (
    RequiredTopLevelFieldsPresent,
    ValuationDateNotBeforePolicyEffectiveDate,
)


def _loss_run_invariants() -> list:
    return [
        RequiredTopLevelFieldsPresent(),
        ValuationDateNotBeforePolicyEffectiveDate(),
        DocumentCheckPassed("paid_sum_check"),
        DocumentCheckPassed("incurred_sum_check"),
        ClaimIncurredPassRateThreshold(1.0),
        ClaimCountMatchesParsedClaims(),
        StringFieldMatchesGolden("insured_name"),
        StringFieldMatchesGolden("carrier"),
        StringFieldMatchesGolden("policy_number"),
        NumericFieldMatchesGolden("total_paid", tolerance=0.01),
        NumericFieldMatchesGolden("total_recoveries", tolerance=0.01),
        NumericFieldMatchesGolden("total_incurred", tolerance=0.01),
        NumericFieldMatchesGolden("loss_ratio", tolerance=0.0001),
        NumericFieldMatchesGolden("claim_count", tolerance=0.0),
    ]


def _binder_invariants() -> list:
    return [
        DocumentCheckPassed("binder_dates_in_order"),
        StringFieldMatchesGolden("insured_name"),
        StringFieldMatchesGolden("carrier"),
        StringFieldMatchesGolden("binder_number"),
        StringFieldMatchesGolden("anticipated_policy_number"),
        StringFieldMatchesGolden("binder_effective_date"),
        StringFieldMatchesGolden("binder_expiration_date"),
    ]


def _sov_invariants() -> list:
    return [
        DocumentCheckPassed("tiv_sum_check"),
        StringFieldMatchesGolden("insured_name"),
        StringFieldMatchesGolden("carrier"),
        StringFieldMatchesGolden("policy_number"),
        NumericFieldMatchesGolden("total_tiv", tolerance=0.01),
        NumericFieldMatchesGolden("total_insured_value", tolerance=0.01),
        NumericFieldMatchesGolden("location_count", tolerance=0.0),
    ]


def _coi_invariants() -> list:
    return [
        StringFieldMatchesGolden("insured_name"),
        StringFieldMatchesGolden("certificate_holder"),
        StringFieldMatchesGolden("producer"),
        StringFieldMatchesGolden("carrier"),
        NumericFieldMatchesGolden("coverage_count", tolerance=0.0),
    ]


def _endorsement_invariants() -> list:
    return [
        StringFieldMatchesGolden("insured_name"),
        StringFieldMatchesGolden("carrier"),
        StringFieldMatchesGolden("policy_number"),
        StringFieldMatchesGolden("endorsement_number"),
        StringFieldMatchesGolden("change_type"),
        StringFieldMatchesGolden("affected_field"),
        NumericFieldMatchesGolden("premium_delta", tolerance=0.01),
    ]


_SELECTORS: dict[str, Callable[[], list]] = {
    "loss_run": _loss_run_invariants,
    "binder": _binder_invariants,
    "temporary_coverage_binder": _binder_invariants,
    "sov": _sov_invariants,
    "statement_of_values": _sov_invariants,
    "coi": _coi_invariants,
    "certificate_of_insurance": _coi_invariants,
    "endorsement": _endorsement_invariants,
    "policy_endorsement": _endorsement_invariants,
}


def invariants_for(doc_type: str | None) -> list:
    """Return the invariant list for ``doc_type`` (case-insensitive).

    Falls back to the loss-run set when ``doc_type`` is unknown or ``None`` —
    this preserves the historic runner behaviour for the loss_run flow while
    letting new doc types opt into their own invariants.
    """
    if doc_type:
        selector = _SELECTORS.get(doc_type.strip().lower())
        if selector is not None:
            return selector()
    return _loss_run_invariants()
