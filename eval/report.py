from __future__ import annotations

from typing import Any


def choose_representative_run(model_runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    First version:
    choose the run with highest classification confidence.

    Later you can improve this with:
    - invariant pass count
    - golden error
    - outlier rejection
    """
    if not model_runs:
        return None

    return max(
        model_runs,
        key=lambda run: run.get("summary", {}).get("classification_confidence", 0),
    )