from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    runs: Mapped[list[OptimizationRunORM]] = relationship(
        "OptimizationRunORM", back_populates="agent", cascade="all, delete-orphan"
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
    workflow_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    agent: Mapped[AgentORM] = relationship("AgentORM", back_populates="versions")
    evaluations: Mapped[list[EvaluationCaseORM]] = relationship(
        "EvaluationCaseORM", back_populates="agent_version", cascade="all, delete-orphan"
    )
    run_id: Mapped[int | None] = mapped_column(ForeignKey("optimization_runs.id"), nullable=True)
    optimization_run: Mapped[OptimizationRunORM | None] = relationship(
        "OptimizationRunORM", back_populates="versions"
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


class OptimizationRunORM(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    task_desc: Mapped[str] = mapped_column(Text, nullable=False)
    dataset_report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    best_blueprint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    best_train_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    best_val_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    best_test_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    artifact_dir: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    agent: Mapped[AgentORM] = relationship("AgentORM", back_populates="runs")
    round_traces: Mapped[list[OptimizationRoundTraceORM]] = relationship(
        "OptimizationRoundTraceORM", back_populates="run", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list[OptimizationArtifactORM]] = relationship(
        "OptimizationArtifactORM", back_populates="run", cascade="all, delete-orphan"
    )
    versions: Mapped[list[AgentVersionORM]] = relationship("AgentVersionORM", back_populates="optimization_run")


class OptimizationRoundTraceORM(Base):
    __tablename__ = "optimization_round_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False
    )
    round_num: Mapped[int] = mapped_column(Integer, nullable=False)
    selected_node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_blueprint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    mutation: Mapped[str] = mapped_column(String(256), nullable=False)
    train_objective: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    val_objective: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    best_train_objective: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    best_val_objective: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    improvement: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    regret: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    run: Mapped[OptimizationRunORM] = relationship("OptimizationRunORM", back_populates="round_traces")


class OptimizationArtifactORM(Base):
    __tablename__ = "optimization_artifacts"
    __table_args__ = (
        UniqueConstraint("run_id", "artifact_type", name="uq_optimization_artifacts_run_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uri: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped[OptimizationRunORM] = relationship("OptimizationRunORM", back_populates="artifacts")
