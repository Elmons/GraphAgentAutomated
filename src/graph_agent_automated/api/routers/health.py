from __future__ import annotations

from fastapi import APIRouter

from graph_agent_automated.api.schemas import HealthResponse, MetricsResponse
from graph_agent_automated.infrastructure.observability.metrics import get_metrics_registry

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/metrics", response_model=MetricsResponse)
def metrics() -> MetricsResponse:
    snapshot = get_metrics_registry().snapshot()
    return MetricsResponse(**snapshot)
