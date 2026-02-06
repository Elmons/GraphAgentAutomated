from __future__ import annotations

from time import monotonic, sleep
from typing import Any

import httpx


def poll_job_until_complete(
    client: httpx.Client,
    *,
    job_id: str,
    poll_interval_seconds: float = 1.0,
    timeout_seconds: float = 1800.0,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not job_id.strip():
        raise ValueError("job_id must not be empty")
    if poll_interval_seconds <= 0:
        raise ValueError("poll_interval_seconds must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    deadline = monotonic() + timeout_seconds
    while monotonic() < deadline:
        response = client.get(f"/v1/agents/jobs/{job_id}", headers=headers)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("job status response must be a JSON object")

        status = str(payload.get("status", "")).strip().lower()
        if status == "succeeded":
            result = payload.get("result")
            if not isinstance(result, dict):
                raise ValueError(f"job {job_id} succeeded but result is missing")
            return result
        if status == "failed":
            error = str(payload.get("error") or "unknown async job error")
            raise RuntimeError(f"job {job_id} failed: {error}")
        if status in {"queued", "running"}:
            sleep(poll_interval_seconds)
            continue

        raise ValueError(f"job {job_id} returned unsupported status: {status}")

    raise TimeoutError(f"job {job_id} did not complete within {timeout_seconds:.1f}s")
