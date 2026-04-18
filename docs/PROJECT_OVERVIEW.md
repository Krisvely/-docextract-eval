# Project Overview

Evaluation framework for a multi-document extraction service. Given a set of
insurance PDFs (loss runs, binders, SOVs, COIs, endorsements), the framework
runs the service end-to-end, scores each result, and produces a per-document
verdict that a reviewer can act on.

Everything below is runnable against the mock service shipped in `app/`.

---

## 1. How to run it

### Setup (one-time)

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Start the mock extraction service in one terminal:

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Commands

All commands assume the mock is up on `http://localhost:8000`.

```powershell
# Unit tests — no network, < 1 s.
venv\Scripts\python.exe -m pytest tests -v

# Single document, quick sanity run.
venv\Scripts\python.exe -m eval.runner --document-id loss_run_libertymutual --runs 1 --use-seed

# Full suite, single pass, evaluated against goldens.
# Throttle keeps us under the mock's rate limit (10 req / 60 s).
$env:EVAL_EXTRACT_THROTTLE_S='6.5'
venv\Scripts\python.exe -m eval.runner --all-docs --runs 1 --use-seed --evaluate --output tmp\full.json

# Robustness check: baseline pass, reseed bugs, second pass, compare.
venv\Scripts\python.exe -m eval.runner --all-docs --runs 3 --use-seed --evaluate `
  --reseed-before-second-pass --output tmp\reseed.json
```

What to look at in the output:

- `batch_summary.documents_extracted_ok` — should equal `documents_total`.
- `batch_summary.per_model_status_counts` — PASS / INACCURATE / UNSTABLE per model.
- `pipeline_robust.verdict` (only in reseed mode) — must be `"PASS"` and
  `documents_degraded_after_reseed` must be empty.

---

## 2. Deliverable 1 — Eval Framework

The code that actually runs the evaluation. Entry point is
`eval/runner.py`; single-doc and batch flows share the same building blocks.

| Piece | File | Responsibility |
| --- | --- | --- |
| CLI | `eval/runner.py` | Dispatches `--document-id` and `--all-docs`. |
| Extraction | `eval/extract.py` | Calls the service; retries 429/5xx with backoff; applies optional throttle; emits per-doc-type cross-field invariants at extraction time. |
| Batch | `eval/batch.py` | Iterates the registry, evaluates each doc, produces `batch_summary` and `pipeline_robust`. |
| Invariants | `eval/invariants/` | Precision, cross-field, and semantic checks. |
| Selector | `eval/invariants/selector.py` | Maps `doc_type` → list of invariants. Unknown types fall back to loss-run set. |
| Golden builders | `eval/golden_builder/` | One module per doc type; turns `data/ground_truth/*.json` into deployable goldens under `eval/datasets/goldens/`. |
| Registry | `eval/datasets/registry.json` | Source of truth for the 11 documents in the suite. |

How to review: run the two commands in §1, open `tmp\full.json`, and check
that each document has `doc_type`, a populated `evaluation.models[].runs[].evaluated_invariants`
list, and a `status` of PASS / INACCURATE / UNSTABLE.

---

## 3. Deliverable 2 — Eval Rubric

Policy describing how per-field and per-document results turn into an
**auto-commit / human-review / reject** decision. Lives in
`docs/EVAL_RUBRIC_TEMPLATE.md`.

Key sections:

- **§2 Cross-field invariants** — implemented rules per doc type
  (`paid_sum_check`, `incurred_sum_check`, `tiv_sum_check`, `binder_dates_in_order`)
  plus partials and extension points.
- **§5 Normalisation** — carrier synonyms, date/money canonicalisation.
- **§8 Per-doc-type thresholds** — loss_run, binder, SOV, COI, endorsement,
  and the unknown-type fallback.
- **§12 Reseed interaction** — the contract is *robustness*, not value
  equality; a doc's verdict may legitimately change after a reseed.
- **§13 Known gaps** — what is intentionally not implemented yet.

How to review: read `docs/EVAL_RUBRIC_TEMPLATE.md` side by side with
`eval/invariants/selector.py`. Every rule in §2 / §8 is implemented either
in `eval/extract.py` (cross-field) or in `eval/invariants/` (precision and
semantic).

---

## 4. Deliverable 3 — Test Strategy

Layered testing plan that explains *what* is tested *where*. Lives in
`docs/TEST_STRATEGY_TEMPLATE.md`.

Layers:

- **Unit** — pure functions, invariant classes, scoring math, selector,
  registry loader. Runs on every PR via `pytest`.
- **Schema / contract** — FastAPI response shape and enum validity.
- **Integration** — `--document-id ... --runs 1 --use-seed` against the
  mock; exercises retry, throttle, extract, and cross-field invariants.
- **Full suite** — `--all-docs --runs 3 --use-seed --evaluate`, used as a
  pre-release gate.
- **Reseed / regression** — baseline vs post-reseed, gated by the
  `pipeline_robust` block in the batch output.

Also documents:

- Retry + throttle env vars (`EVAL_EXTRACT_MAX_RETRIES`,
  `EVAL_EXTRACT_INITIAL_BACKOFF_S`, `EVAL_EXTRACT_MAX_BACKOFF_S`,
  `EVAL_EXTRACT_THROTTLE_S`).
- Recommended smoke ladder (single doc → full suite → reseed) before
  paying for a long run.
- How to read `pipeline_robust` to decide if a build passes.

How to review: read `docs/TEST_STRATEGY_TEMPLATE.md`, then run
`pytest tests -v` (expect 15/15) and the smoke command from §1.

---

## File map quick reference

```
app/                 mock extraction service (FastAPI)
data/                raw fixtures (documents + ground_truth)
eval/                framework code
  extract.py         call + retry + doc-type invariants
  batch.py           --all-docs + pipeline_robust
  runner.py          CLI
  invariants/        precision / cross-field / semantic
  golden_builder/    build deployable goldens from ground_truth
  datasets/
    registry.json    the 11-doc suite
    goldens/         generated goldens
docs/
  EVAL_FRAMEWORK_README.md   usage guide
  EVAL_RUBRIC_TEMPLATE.md    Deliverable 2
  TEST_STRATEGY_TEMPLATE.md  Deliverable 3
  PROJECT_OVERVIEW.md        this file
tests/               unit tests
```
