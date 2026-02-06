from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI, Request, Response

from graph_agent_automated.api.routers.agents import router as agents_router
from graph_agent_automated.api.routers.health import router as health_router
from graph_agent_automated.core.config import get_settings
from graph_agent_automated.core.database import ENGINE, Base
from graph_agent_automated.infrastructure.observability.metrics import get_metrics_registry

REQUEST_LOGGER = logging.getLogger("graph_agent_automated.request")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # For local/dev convenience. Production can rely on Alembic migrations.
    Base.metadata.create_all(bind=ENGINE)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    metrics = get_metrics_registry()

    @app.middleware("http")
    async def request_observability_middleware(request: Request, call_next) -> Response:
        started = perf_counter()
        path = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            latency_ms = (perf_counter() - started) * 1000
            metrics.record_request(endpoint=f"{method} {path}", latency_ms=latency_ms, status_code=500)
            REQUEST_LOGGER.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "method": method,
                        "path": path,
                        "status_code": 500,
                        "latency_ms": round(latency_ms, 3),
                    },
                    ensure_ascii=False,
                )
            )
            raise

        latency_ms = (perf_counter() - started) * 1000
        metrics.record_request(
            endpoint=f"{method} {path}",
            latency_ms=latency_ms,
            status_code=status_code,
        )
        REQUEST_LOGGER.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 3),
                },
                ensure_ascii=False,
            )
        )
        return response

    app.include_router(health_router)
    app.include_router(agents_router)
    return app


app = create_app()
