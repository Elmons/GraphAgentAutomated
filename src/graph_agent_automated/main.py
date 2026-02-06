from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from graph_agent_automated.api.routers.agents import router as agents_router
from graph_agent_automated.api.routers.health import router as health_router
from graph_agent_automated.core.config import get_settings
from graph_agent_automated.core.database import ENGINE, Base


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # For local/dev convenience. Production can rely on Alembic migrations.
    Base.metadata.create_all(bind=ENGINE)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.include_router(health_router)
    app.include_router(agents_router)
    return app


app = create_app()
