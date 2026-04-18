"""Dataset-registry helpers.

The registry (`eval/datasets/registry.json`) is the single source of truth for
which documents the eval framework iterates over in batch mode. Everything
that needs to enumerate docs goes through here — never hard-code a list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "eval" / "datasets" / "registry.json"


def load_registry(path: Path | str | None = None) -> list[dict[str, Any]]:
    registry_path = Path(path) if path else _REGISTRY_PATH
    with registry_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    docs = data.get("documents", [])
    return [doc for doc in docs if isinstance(doc, dict) and doc.get("document_id")]


def registered_document_ids() -> list[str]:
    return [doc["document_id"] for doc in load_registry()]


def find_document(document_id: str) -> dict[str, Any] | None:
    for doc in load_registry():
        if doc.get("document_id") == document_id:
            return doc
    return None


def golden_path_for(document_id: str) -> Path | None:
    """Return an existing repo-relative golden path for the document, or None."""
    doc = find_document(document_id)
    if not doc:
        return None
    golden = doc.get("golden_path")
    if not golden:
        return None
    candidate = (_REPO_ROOT / golden).resolve()
    return candidate if candidate.is_file() else None


def doc_type_for(document_id: str) -> str | None:
    doc = find_document(document_id)
    return doc.get("doc_type") if doc else None
