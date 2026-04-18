from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InvariantResult:
    name: str
    passed: bool
    severity: str = "error"  # info | warning | error
    details: dict[str, Any] = field(default_factory=dict)


class Invariant:
    """
    Base class for all invariants.

    extracted_run:
        A single extraction output for one model run.
    golden:
        Ground-truth record for the document, if available.
    """

    name: str = "base_invariant"
    category: str = "base"

    def evaluate(
        self,
        extracted_run: dict[str, Any],
        golden: dict[str, Any] | None = None,
    ) -> InvariantResult:
        raise NotImplementedError("Invariant.evaluate must be implemented by subclasses.")