from __future__ import annotations

import json
from dataclasses import asdict
from typing import Sequence

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from graph_agent_automated.domain.enums import AgentLifecycle
from graph_agent_automated.domain.models import EvaluationSummary, WorkflowBlueprint
from graph_agent_automated.infrastructure.persistence.models import (
    AgentORM,
    AgentVersionORM,
    EvaluationCaseORM,
)


class AgentRepository:
    """Repository implementing agent/version persistence with SQLAlchemy."""

    def __init__(self, session: Session):
        self._session = session

    def get_or_create_agent(self, name: str, description: str = "") -> AgentORM:
        stmt: Select[tuple[AgentORM]] = select(AgentORM).where(AgentORM.name == name)
        existing = self._session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing

        agent = AgentORM(name=name, description=description)
        self._session.add(agent)
        self._session.flush()
        return agent

    def next_version(self, agent_id: int) -> int:
        stmt = (
            select(AgentVersionORM)
            .where(AgentVersionORM.agent_id == agent_id)
            .order_by(desc(AgentVersionORM.version))
            .limit(1)
        )
        latest = self._session.execute(stmt).scalar_one_or_none()
        return 1 if latest is None else int(latest.version) + 1

    def create_version(
        self,
        agent_name: str,
        blueprint: WorkflowBlueprint,
        evaluation: EvaluationSummary,
        artifact_path: str,
        lifecycle: AgentLifecycle = AgentLifecycle.VALIDATED,
        notes: str = "",
    ) -> AgentVersionORM:
        agent = self.get_or_create_agent(agent_name)
        version = self.next_version(agent.id)

        version_row = AgentVersionORM(
            agent_id=agent.id,
            version=version,
            lifecycle=lifecycle,
            blueprint_id=blueprint.blueprint_id,
            blueprint_json=json.dumps(asdict(blueprint), ensure_ascii=False),
            score=evaluation.mean_score,
            artifact_path=artifact_path,
            notes=notes,
        )
        self._session.add(version_row)
        self._session.flush()

        for case in evaluation.case_results:
            self._session.add(
                EvaluationCaseORM(
                    agent_version_id=version_row.id,
                    case_id=case.case_id,
                    question=case.question,
                    expected=case.expected,
                    output=case.output,
                    score=case.score,
                    rationale=case.rationale,
                    latency_ms=case.latency_ms,
                    token_cost=case.token_cost,
                )
            )

        return version_row

    def list_versions(self, agent_name: str) -> list[AgentVersionORM]:
        stmt = (
            select(AgentVersionORM)
            .join(AgentORM, AgentVersionORM.agent_id == AgentORM.id)
            .where(AgentORM.name == agent_name)
            .order_by(desc(AgentVersionORM.version))
        )
        return list(self._session.execute(stmt).scalars().all())

    def update_lifecycle(self, agent_name: str, version: int, lifecycle: AgentLifecycle) -> AgentVersionORM:
        version_row = self.get_version(agent_name=agent_name, version=version)
        version_row.lifecycle = lifecycle

        if lifecycle == AgentLifecycle.DEPLOYED:
            versions = self.list_versions(agent_name)
            for row in versions:
                if row.version != version and row.lifecycle == AgentLifecycle.DEPLOYED:
                    row.lifecycle = AgentLifecycle.VALIDATED

        self._session.flush()
        return version_row

    def get_version(self, agent_name: str, version: int) -> AgentVersionORM:
        stmt = (
            select(AgentVersionORM)
            .join(AgentORM, AgentVersionORM.agent_id == AgentORM.id)
            .where(AgentORM.name == agent_name, AgentVersionORM.version == version)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            raise ValueError(f"Agent version not found: {agent_name}@{version}")
        return row

    def active_version(self, agent_name: str) -> AgentVersionORM | None:
        stmt = (
            select(AgentVersionORM)
            .join(AgentORM, AgentVersionORM.agent_id == AgentORM.id)
            .where(AgentORM.name == agent_name, AgentVersionORM.lifecycle == AgentLifecycle.DEPLOYED)
            .order_by(desc(AgentVersionORM.version))
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()


class UnitOfWork:
    """Simple SQLAlchemy transaction boundary."""

    def __init__(self, session: Session):
        self.session = session
        self.agents = AgentRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "UnitOfWork":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()
        self.close()
        return False


def to_version_dict(version: AgentVersionORM) -> dict[str, object]:
    return {
        "id": version.id,
        "version": version.version,
        "lifecycle": version.lifecycle.value,
        "blueprint_id": version.blueprint_id,
        "score": version.score,
        "artifact_path": version.artifact_path,
        "notes": version.notes,
        "created_at": version.created_at.isoformat(),
    }


def list_to_dict(rows: Sequence[AgentVersionORM]) -> list[dict[str, object]]:
    return [to_version_dict(row) for row in rows]
