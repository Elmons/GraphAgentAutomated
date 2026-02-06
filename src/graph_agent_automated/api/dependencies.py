from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.core.config import get_settings
from graph_agent_automated.core.database import get_db


def get_db_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_service(session: Session = Depends(get_db_session)) -> AgentOptimizationService:
    return AgentOptimizationService(session=session, settings=get_settings())
