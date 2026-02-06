from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Callable
from uuid import uuid4


@dataclass
class AsyncJobRecord:
    job_id: str
    job_type: str
    tenant_id: str
    agent_name: str
    status: str
    created_at: str
    updated_at: str
    result: dict[str, object] | None = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class InMemoryJobQueue:
    """In-process async queue for long-running optimize/parity jobs."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="gaa-job")
        self._lock = Lock()
        self._jobs: dict[str, AsyncJobRecord] = {}

    def submit(
        self,
        *,
        job_type: str,
        tenant_id: str,
        agent_name: str,
        metadata: dict[str, object] | None,
        runner: Callable[[], dict[str, object]],
    ) -> AsyncJobRecord:
        now = _utc_now_iso()
        job = AsyncJobRecord(
            job_id=f"job-{uuid4().hex[:12]}",
            job_type=job_type,
            tenant_id=tenant_id,
            agent_name=agent_name,
            status="queued",
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._lock:
            self._jobs[job.job_id] = job

        self._executor.submit(self._execute_job, job.job_id, runner)
        return job

    def get(self, job_id: str) -> AsyncJobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return AsyncJobRecord(
                job_id=job.job_id,
                job_type=job.job_type,
                tenant_id=job.tenant_id,
                agent_name=job.agent_name,
                status=job.status,
                created_at=job.created_at,
                updated_at=job.updated_at,
                result=dict(job.result) if job.result is not None else None,
                error=job.error,
                metadata=dict(job.metadata),
            )

    def _execute_job(
        self,
        job_id: str,
        runner: Callable[[], dict[str, object]],
    ) -> None:
        self._set_running(job_id)
        try:
            result = runner()
        except Exception as exc:
            self._set_failed(job_id, str(exc))
            return
        self._set_succeeded(job_id, result)

    def _set_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            job.updated_at = _utc_now_iso()

    def _set_succeeded(self, job_id: str, result: dict[str, object]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "succeeded"
            job.result = result
            job.error = None
            job.updated_at = _utc_now_iso()

    def _set_failed(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "failed"
            job.error = error
            job.updated_at = _utc_now_iso()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
