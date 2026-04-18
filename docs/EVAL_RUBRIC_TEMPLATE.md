# Eval Rubric

Operational rubric for deciding whether one extraction of one document is
**auto-commit**, **human-review**, or **reject**. Written against the specific
schemas this service emits (`loss_run`, `temporary_coverage_binder`,
`statement_of_values`, `coi`, `endorsement`) and wired into code: every
invariant named below corresponds to a class in `eval/invariants/` and is
selected per doc-type by `eval/invariants/selector.py`. To add or retune a
rule, edit exactly those two places — this document describes the contract,
not a second implementation.

## 1. Field categories and match rules

All comparisons happen **after normalization** (section 5). All tolerances are
encoded in the invariant constructors so reviewers can diff a single file when
policy changes.

| Field type | Examples | Match rule | Tolerance |
| --- | --- | --- | --- |
| Identifiers | `policy_number`, `claim_number`, `binder_number` | Exact after trim + uppercase + strip non-alphanumerics | 0 |
| Party names | `insured_name`, `certificate_holder`, `claimant` | Case- and whitespace-insensitive equality; Levenshtein ≤ 2 flagged as warning | 0 strict / 2 warn |
| Carrier names | `carrier` | Normalized via synonym table (`liberty mutual` ≡ `liberty mut.` ≡ `liberty mutual insurance`) | 0 after lookup |
| Dates | `*_date` | Parsed with `%Y-%m-%d`, `%m/%d/%Y`, `%m/%d/%y`; compared as `date` | 0 days |
| Dollar amounts (atomic) | `paid_amount`, `reserved_amount`, `building_value` | Absolute equality after `$`/`,` strip | ±$0.01 |
| Derived aggregates | `total_paid`, `total_incurred`, `total_recoveries`, `total_tiv`, `loss_ratio` | Same, but **also** recomputed from line items; both must match golden | ±$0.01 / ±0.0001 for ratios |
| Structural / enum | `doc_type`, `status`, `change_type` | Exact; unknown enums = hard fail | 0 |
| Counts | `claim_count`, `location_count` | Exact integer | 0 |
| Optional / nullable | `producer`, `year_built`, `square_footage`, `business_income_value` | Allowed to be `null`; only compared when golden is non-null | n/a |

## 2. Cross-field invariants (ground-truth-free)

Run on every representative run. Failures are `error` severity by default.
Each rule below is produced by `eval/extract.py` at extraction time and
consumed by the per-doc-type selector through `DocumentCheckPassed`; no
golden is required.

- **Loss run** — implemented.
  - `paid_sum_check`: `Σ claims[i].paid_amount == total_paid` (±$0.01)
  - `incurred_sum_check`: `Σ claims[i].incurred_amount == total_incurred` (±$0.01)
  - `claim_incurred_pass_rate ≥ 1.0`: every claim satisfies `paid + reserved - recoveries == incurred`
  - `claim_count_matches_parsed_claims`: `len(claims) == claim_count`
  - Closed claims with `reserved_amount > 0` ⇒ warning (not an automatic fail; subrogation edge cases exist)
- **Binder** — implemented.
  - `binder_dates_in_order`: `binder_expiration_date >= binder_effective_date`;
    unparseable dates fail the check instead of silently skipping.
  - *Partial:* `anticipated_policy_number` presence when
    `binding_authority_reference` is set is documented here but not yet a
    coded invariant; tracked in §12.
- **SOV** — implemented.
  - `tiv_sum_check`: `Σ properties[i].total_insured_value == total_tiv` (±$0.01)
  - *Partial:* per-property
    `building_value + contents_value + business_income_value == total_insured_value`
    when all three are non-null — documented here, extension point in
    `eval/extract.py::_compute_sov_invariants`.
- **COI / Endorsement** — no cross-field rule is added by default; the
  precision invariants in the selector cover correctness. Extension point
  is the same `_compute_invariants_block` dispatch in `eval/extract.py`.

## 3. Semantic invariants

- `required_top_level_fields_present` per doc type (enforced by
  `eval.invariants.semantic.RequiredTopLevelFieldsPresent` for loss runs;
  mirrored by selector entries for binders and SOVs).
- `valuation_date_not_before_policy_effective_date` for loss runs.
- Every extracted coverage / claim / location must be traceable to the
  source `raw_text` span (hallucination guard — warning unless the field is
  numeric and material).

## 4. Calibration expectations

- Target gap: `|mean_confidence − observed_correct_rate| ≤ 0.05` across the batch.
- A **higher** confidence on a wrong answer than on a right one, for the same
  doc type, is a hard fail for the run and blocks promotion.
- Mis-routed `doc_type` (classifier confusion) must reduce confidence below
  0.70; if it does not, the calibration regression is treated as a bug, not a
  data problem.

## 5. Normalization rules

- **Strings**: unicode NFKC, `.strip()`, collapse internal whitespace, `.lower()`.
- **Carriers**: lookup in a curated synonym table; unknown carriers pass
  through the string rule and are flagged for triage.
- **Dates**: parsed, re-emitted as ISO-8601 `YYYY-MM-DD` before compare.
- **Money**: strip `$`, thousands separators, and trailing `.00`; compare as
  `float` with the tolerance in the table above. All values assumed USD
  unless the golden says otherwise; cross-currency is out of scope for v1.
- **Addresses**: normalized via whitespace + USPS-style suffix map
  (`Street → ST`); exact after that.
- **Legacy ACORD layouts**: normalized into the modern schema by the parser;
  the rubric does not change.

## 6. Variance vs. bias

The framework reports both per key numeric field
(`eval/scoring.py::compute_variance_metrics`, `compute_bias_metrics`):

- **Variance** (instability across `--runs N --use-seed`): coefficient of
  variation (CoV) on `total_paid`, `total_incurred`, and
  `classification_confidence`. CoV > 0.10 ⇒ `UNSTABLE`.
- **Bias** (deviation from golden): `mean_abs_error` and `mean_signed_error`
  per numeric field. `mean_abs_error > tolerance` ⇒ `INACCURATE`.
- "Better" model = lower bias **and** variance not materially worse.
  "More stable only" = equal/better CoV with equal-or-worse MAE; this does
  not justify promotion on its own.

## 7. Pass / review / reject thresholds

Applied to the representative run (`eval/report.py::choose_representative_run`).

- **Auto-commit**: all `error`-severity invariants pass, every compared field
  within tolerance, classifier confidence ≥ 0.85, CoV for `total_paid` and
  `total_incurred` ≤ 0.05.
- **Human review**: any `warning`-severity failure, any optional field
  mismatch, CoV between 0.05 and 0.10, or classifier confidence in [0.60, 0.85).
- **Reject**: any precision `error` failure on a required field, any
  cross-field invariant hard fail, CoV > 0.10, or classifier confidence < 0.60.

## 8. Per-doc-type thresholds

- **Loss run**: strictest — `total_paid` and `total_incurred` drive downstream
  reserving; auto-commit requires bias MAE ≤ $0.01 on both. Full cross-field
  and per-claim invariants apply.
- **Binder**: effective/expiration dates and `binder_number` must match
  exactly; `binder_dates_in_order` must pass. Money fields not yet in scope.
- **SOV**: auto-commit requires `total_tiv` within $0.01 of the golden and of
  the property-sum (`tiv_sum_check`), **and** ≥ 95% of locations matched 1:1
  with the golden by address.
- **COI**: precision checks on `insured_name`, `certificate_holder`,
  `producer`, `carrier`, and `coverage_count`. Auto-commit requires all five;
  a missing optional field (e.g. `producer`) downgrades to human-review.
- **Endorsement**: precision checks on `insured_name`, `carrier`,
  `policy_number`, `endorsement_number`, `change_type`, `affected_field`, and
  `premium_delta` (±$0.01). Auto-commit requires all seven.
- **Unknown doc type**: the selector falls back to the loss-run set. This is
  conservative by design — the doc can still pass cross-field/semantic
  checks but cannot auto-commit because the loss-run precision rules will
  return `missing value` warnings rather than numeric matches.

## 9. Partial, disputed, missing ground truth

- **Partial** (`"unknown"` in golden): field excluded from bias metrics; the
  precision invariant returns `passed=False, severity="warning"`.
- **Disputed** (two goldens disagree): the rubric's verdict is the
  intersection; a run passes only if it satisfies **all** goldens. The
  framework surfaces the disagreement in output so labelers can resolve.
- **Missing** (no golden at all): evaluation mode falls back to cross-field
  and semantic invariants only; bias metrics are `null`. Such docs can never
  auto-commit — best outcome is "human review."

## 10. Precision vs. recall

- **Hallucinated fields** (not in `raw_text`): hard fail for the run,
  regardless of golden.
- **Omitted fields** (present in source, absent in extraction): `error` for
  required fields, `warning` for optional — matching the categories above.

## 11. Hard failures vs. warnings

- `severity="error"` contributes to `INACCURATE` / reject decisions.
- `severity="warning"` contributes to "human review" but never blocks a build
  on its own.
- The runner distinguishes them in `evaluated_invariants_summary`.

## 12. Reseed interaction

`POST /admin/reseed-bugs` rotates which documents carry which synthetic bug.
The rubric's contract after a reseed is **robustness**, not value equality:

- A document that was auto-commit in baseline may end up human-review after
  a reseed if its new bug assignment affects a required field. That is
  expected and not a regression on its own.
- `pipeline_robust` in the batch output (see `eval/batch.py`) is the gate:
  every document that extracted OK in baseline must still extract OK after
  the reseed. Any `documents_degraded_after_reseed` entry blocks the build.
- Tests that key on a specific `document_id` for a specific bug are the
  intended trip-wire — they will flip after a reseed, surfacing overfit.

## 13. Known gaps / follow-ups

- No per-claim bias metrics yet (batch reports aggregate-level only).
- Carrier synonym table is hand-curated; should move to a reviewed dataset.
- SOV per-property decomposition (`building + contents + BI == TIV`) is
  described in §2 but not yet coded; extension point is
  `eval/extract.py::_compute_sov_invariants`.
- Binder `anticipated_policy_number` conditional-presence rule is described
  in §2 but not yet coded.
- Cross-currency SOVs and COIs are out of scope for v1.

