from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class EndpointMetric:
    count: int = 0
    error_count: int = 0
    latency_ms_sum: float = 0.0


class InMemoryMetricsRegistry:
    """In-memory metrics collector for request/job telemetry."""

    def __init__(self):
        self._lock = Lock()
        self._requests_total = 0
        self._errors_total = 0
        self._async_jobs_submitted_total = 0
        self._async_jobs_succeeded_total = 0
        self._async_jobs_failed_total = 0
        self._endpoints: dict[str, EndpointMetric] = {}

    def record_request(self, endpoint: str, latency_ms: float, status_code: int) -> None:
        with self._lock:
            self._requests_total += 1
            metric = self._endpoints.get(endpoint)
            if metric is None:
                metric = EndpointMetric()
                self._endpoints[endpoint] = metric
            metric.count += 1
            metric.latency_ms_sum += max(latency_ms, 0.0)
            if status_code >= 500:
                metric.error_count += 1
                self._errors_total += 1

    def record_async_job_submitted(self) -> None:
        with self._lock:
            self._async_jobs_submitted_total += 1

    def record_async_job_succeeded(self) -> None:
        with self._lock:
            self._async_jobs_succeeded_total += 1

    def record_async_job_failed(self) -> None:
        with self._lock:
            self._async_jobs_failed_total += 1

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            endpoints_payload: dict[str, dict[str, float | int]] = {}
            for endpoint, metric in self._endpoints.items():
                avg_latency_ms = (
                    metric.latency_ms_sum / metric.count
                    if metric.count > 0
                    else 0.0
                )
                endpoints_payload[endpoint] = {
                    "count": metric.count,
                    "error_count": metric.error_count,
                    "latency_ms_sum": metric.latency_ms_sum,
                    "latency_ms_avg": avg_latency_ms,
                }

            return {
                "requests_total": self._requests_total,
                "errors_total": self._errors_total,
                "async_jobs_submitted_total": self._async_jobs_submitted_total,
                "async_jobs_succeeded_total": self._async_jobs_succeeded_total,
                "async_jobs_failed_total": self._async_jobs_failed_total,
                "endpoints": endpoints_payload,
            }


METRICS_REGISTRY = InMemoryMetricsRegistry()


def get_metrics_registry() -> InMemoryMetricsRegistry:
    return METRICS_REGISTRY
