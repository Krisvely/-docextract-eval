"""Thin wrapper around `POST /admin/reseed-bugs`.

The admin endpoint rotates which documents carry which behavioural bugs so
that evals that have silently overfit to `document_id == "..."` checks will
regress. The eval framework treats a successful reseed + stable batch output
as the contract; it does not require identical values before/after.
"""

from __future__ import annotations

from typing import Any

import requests

BASE_URL = "http://localhost:8000"


def reseed_bugs(seed: int | None = None, base_url: str = BASE_URL) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/admin/reseed-bugs"
    if seed is not None:
        url += f"?seed={seed}"
    response = requests.post(url, timeout=10)
    response.raise_for_status()
    return response.json()
