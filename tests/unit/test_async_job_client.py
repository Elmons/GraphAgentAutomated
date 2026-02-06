from __future__ import annotations

import json

import httpx
import pytest

from graph_agent_automated.infrastructure.runtime.async_job_client import (
    poll_job_until_complete,
)


def _client_with_handler(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="http://test", transport=transport)


def test_poll_job_until_complete_returns_result_on_success() -> None:
    state = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        if state["count"] == 1:
            body = {"status": "queued"}
        elif state["count"] == 2:
            body = {"status": "running"}
        else:
            body = {"status": "succeeded", "result": {"score_delta": 0.1}}
        return httpx.Response(200, json=body)

    with _client_with_handler(handler) as client:
        result = poll_job_until_complete(
            client,
            job_id="job-1",
            poll_interval_seconds=0.001,
            timeout_seconds=1.0,
        )
    assert result == {"score_delta": 0.1}


def test_poll_job_until_complete_raises_on_failed_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "failed", "error": "boom"})

    with _client_with_handler(handler) as client:
        with pytest.raises(RuntimeError, match="job job-2 failed: boom"):
            poll_job_until_complete(
                client,
                job_id="job-2",
                poll_interval_seconds=0.001,
                timeout_seconds=1.0,
            )


def test_poll_job_until_complete_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"status": "queued"}).encode("utf-8"))

    with _client_with_handler(handler) as client:
        with pytest.raises(TimeoutError, match="job job-3 did not complete"):
            poll_job_until_complete(
                client,
                job_id="job-3",
                poll_interval_seconds=0.001,
                timeout_seconds=0.01,
            )
