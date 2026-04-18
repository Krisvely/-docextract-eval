# Test Strategy

Practical testing strategy for the DocExtract service. The goal is to fail
fast on things that matter (schema, invariants, bias), tolerate the things
that are inherently noisy (LLM stochasticity), and keep the cost ceiling
compatible with $200/day of eval compute and ~50 new golden labels per
quarter.

## Layers

| Layer | What it tests | Runs where | Owned by | Cost / SLA | Blocks |
| --- | --- | --- | --- | --- | --- |
| Unit | Pure functions: normalization, invariant classes, scoring math, `selector.invariants_for`, registry loader, per-doc-type cross-field builders (`_compute_sov_invariants`, `_compute_binder_invariants`, `_compute_loss_run_invariants`). No network. | Every PR (pytest) | Eng | ms; free | PR merge |
| Schema / contract | FastAPI response shape and enum validity (`doc_type`, `status`), invariant output shape. | Every PR | Eng | seconds | PR merge |
| Integration | `python -m eval.runner --document-id ... --runs 1 --use-seed` against a live mock or `TestClient`. Exercises retry/throttle, extract, and cross-field invariants end-to-end. | Every PR | Eng | ~30s | PR merge |
| Eval (offline, goldens) | `python -m eval.runner --all-docs --runs 3 --use-seed --evaluate` vs. `eval/datasets/goldens/*`. Produces bias + variance. | Nightly + pre-deploy | Eng + DS | ~$5 / run | Deploy |
| Eval (silver / draft-goldens) | Same runner, against `eval/golden_builder/` outputs. Catches regressions before a labeler has signed off. | Nightly | Eng + DS | ~$5 / run | None (dashboards) |
| Reseed regression | `--reseed-before-second-pass` — confirms pipeline is robust to bug rotation, not to specific `document_id` overfits. | Pre-deploy + weekly | Eng | ~2× eval cost | Deploy |
| Canary | 5% of prod traffic, dual-write to shadow queue; compares v2 vs v1 on live docs (no golden required — uses cross-field + calibration invariants only). | Continuous | SRE + Eng | pennies / doc | Promote-to-100% |
| Production monitoring | Confidence distribution, invariant pass rate, 4xx/5xx, p95 latency, cost/doc. | Always | SRE | metrics stack | Page on SLO breach |

## What blocks a deploy

A deploy is blocked if **any** of the following is true on the full offline
golden set (all currently-registered documents):

- Any representative run has status `INACCURATE` or `FAIL` on a doc that was
  `PASS` on the previous release (regression, not absolute level).
- Doc-type-wide auto-commit rate drops by more than 2 percentage points vs.
  the previous release.
- Coefficient of variation of `total_paid` or `total_incurred` rises above
  0.10 on any loss-run doc (defined in the rubric).
- Calibration gap `|mean_confidence − observed_correct_rate| > 0.10` on any
  doc type.
- Reseed pass (`--reseed-before-second-pass`) returns
  `pipeline_robust: false` — i.e. any doc fails to extract cleanly after the
  bug rotation. This is the primary guard against tests that overfit on
  `document_id`.

Sample size: the full registered set plus `--runs 3 --use-seed`. If the
metric is within 1 standard error of the threshold, we re-run with
`--runs 10` before making the call; LLM eval noise is real and single-run
gates are a known anti-pattern.

## What does *not* block a deploy

- Warnings-severity invariant failures.
- Variance or calibration changes that fall within one run's noise band.
- Silver/draft-golden regressions — they feed dashboards and triage queues
  but never gate, because the label is not authoritative.
- New documents that have no golden yet (evaluation runs cross-field only
  and is reported as "human-review-only" in the dashboard).

## Cost model ($200/day compute, 50 labels/quarter)

- **Offline eval**: `runs=3`, ~10 docs, 2 models ⇒ ≤ 60 calls per full run.
  At today's mock pricing this is ~$5; nightly + one pre-deploy run/day
  ⇒ ~$10/day. Well under budget.
- **Reseed regression**: 2× eval cost ⇒ ~$10 weekly.
- **Canary**: piggy-backs on prod traffic; marginal cost ≈ one extra LLM
  call per sampled doc.
- **Label budget**: 50 labels/quarter is spent on (a) new doc-types entering
  prod, (b) disputed prod records that canary surfaced, (c) replacements for
  goldens that the reseed flow invalidated. Silver data from
  `eval/golden_builder/` fills the gap for nightly dashboards.
- **Caching**: extraction outputs are keyed by
  `(document_id, model, seed)` and cached for 24h so evaluation replays are
  free.

## Model-version comparison (v1 vs v2)

1. Run `python -m eval.runner --all-docs --runs 5 --use-seed --evaluate
   --models v1,v2 --output tmp/v1_vs_v2.json`.
2. Compare per-doc `comparison[v1]` vs. `comparison[v2]`: bias (MAE) on
   money fields, variance CoV, calibration gap, status transitions.
3. Ship v2 only if every doc is ≥ v1 on bias **and** variance is not
   materially worse (CoV delta ≤ 0.02 absolute). "Better mean, worse tail"
   is treated as a regression.
4. Run the reseed flow; any post-reseed extraction failure blocks v2.
5. Canary v2 at 5% for 24h. Kill switch: env flag flips back to v1 in
   under a minute, evaluated automatically if invariant pass rate in canary
   drops > 5pp below control.

## CI vs. scheduled vs. manual

- **CI (every PR)**: unit, schema, integration, single-doc eval smoke on
  `loss_run_libertymutual`.
- **Scheduled (nightly)**: full offline eval + silver eval + reseed regression.
- **Pre-deploy (on demand)**: full offline eval with `--runs 5`, v1-vs-v2
  comparison, reseed regression.
- **Manual**: triage of silver/draft-golden regressions, calibration drift
  investigations, new doc-type onboarding.

## Reseed / regression handling

- The mock service exposes `POST /admin/reseed-bugs` which rotates which
  `document_id`s carry which bug. The framework's contract is that the
  pipeline stays structurally healthy (all docs extract, shapes are valid,
  invariant machinery still runs) after a reseed — not that values match
  before and after.
- Reseed verdict lives in `pipeline_robust` in the batch output:
  `documents_baseline_ok`, `documents_post_reseed_ok`,
  `documents_both_ok`, and `documents_degraded_after_reseed` are emitted
  per run. A non-empty `documents_degraded_after_reseed` list blocks the
  build (see rubric §12).
- Tests that `assert` on specific values for a specific `document_id` are
  flagged in review; the reseed flow exists to surface that class of overfit
  automatically.

## Operational resilience (retry & throttle)

The mock service injects realistic operational noise: per-client rate limits
(default 10 req/60s), transient 500s (4%), and latency (0.5–2.0s). Without
protection, a naive `--all-docs --runs N` loses most of its calls.

- `eval/extract.py` retries HTTP 429/500/502/503/504 with exponential
  backoff (`EVAL_EXTRACT_INITIAL_BACKOFF_S`, capped at
  `EVAL_EXTRACT_MAX_BACKOFF_S`), honouring `Retry-After` when the server
  sets it. Retries are bounded by `EVAL_EXTRACT_MAX_RETRIES` (default 5).
- A genuinely-down service still surfaces after retry exhaustion as a
  per-document `status: error` in the batch report — the framework never
  silently swallows failures.
- Optional throttle via `EVAL_EXTRACT_THROTTLE_S` (default `0`). Set to
  `~6` when running `--all-docs --runs ≥ 3 --use-seed` to stay under the
  default rate limit without relying on retries.
- Recommended smoke order before a full suite:
  1. `python -m eval.runner --document-id loss_run_libertymutual --runs 1 --use-seed`
  2. `python -m eval.runner --all-docs --runs 1 --use-seed --evaluate`
  3. `python -m eval.runner --all-docs --runs 3 --use-seed --evaluate --reseed-before-second-pass`
  Steps 1–2 catch environment issues before paying for step 3.

## Goldens vs. draft-goldens (silver)

- **Goldens** (`eval/datasets/goldens/*.json`): human-reviewed; gate deploys.
- **Silver** (`eval/golden_builder/` output): rule-based; gate nothing, but
  drive nightly dashboards and surface candidates for labeling. When a silver
  record is promoted to golden, it is reviewed by the on-call DS.

## Deliberate trade-offs

- No LLM-as-judge in the gate path: calibration on small extraction fields
  is unreliable and the added non-determinism would swamp the signal we are
  trying to measure. LLM-as-judge is used only for triage, never for gates.
- No per-field statistical tests (bootstrap CIs, etc.) in v1 — 10–20 docs is
  too small for meaningful CIs anyway; we rely on per-doc tolerances +
  status regressions instead.
- Reseed flow asserts robustness, not value stability, on purpose; the
  alternative requires maintaining golden sets per-seed which is not
  affordable within the label budget.

## Open questions

- When is a silver record trustworthy enough to auto-promote to golden?
- What is the right rolling window for canary vs. control comparisons
  (hours vs. days) given traffic volume?
- Do we need a separate gate for cost regressions (tokens per doc),
  independent of quality?

