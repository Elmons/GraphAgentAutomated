from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from graph_agent_automated.core.database import Base
from graph_agent_automated.domain.enums import AgentLifecycle


class AgentORM(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    versions: Mapped[list[AgentVersionORM]] = relationship(
        "AgentVersionORM", back_populates="agent", cascade="all, delete-orphan"
    )


class AgentVersionORM(Base):
    __tablename__ = "agent_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[AgentLifecycle] = mapped_column(
        Enum(AgentLifecycle, native_enum=False), nullable=False, default=AgentLifecycle.DRAFT
    )
    blueprint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    blueprint_json: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(512), nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    agent: Mapped[AgentORM] = relationship("AgentORM", back_populates="versions")
    evaluations: Mapped[list[EvaluationCaseORM]] = relationship(
        "EvaluationCaseORM", back_populates="agent_version", cascade="all, delete-orphan"
    )


class EvaluationCaseORM(Base):
    __tablename__ = "evaluation_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_version_id: Mapped[int] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    output: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    token_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    agent_version: Mapped[AgentVersionORM] = relationship("AgentVersionORM", back_populates="evaluations")
