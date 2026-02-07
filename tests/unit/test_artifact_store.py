from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.core.config import Settings
from graph_agent_automated.infrastructure.persistence.artifact_store import (
    InMemoryArtifactStore,
    LocalArtifactStore,
)
from graph_agent_automated.infrastructure.persistence.models import Base
from graph_agent_automated.infrastructure.persistence.repositories import AgentRepository


def test_local_artifact_store_roundtrip_and_listing(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    payload = b"workflow: test\n"

    stored = store.put("agents/demo/run-1/workflow.yml", payload)

    assert stored.uri == "local://agents/demo/run-1/workflow.yml"
    assert stored.local_path is not None
    assert store.exists(stored.uri)
    assert store.get(stored.uri) == payload
    assert store.list("agents/demo/run-1") == [stored.uri]


def test_local_artifact_store_rejects_traversal_path(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)

    with pytest.raises(ValueError, match="illegal traversal"):
        store.put("../escape.txt", b"x")


def test_in_memory_artifact_store_supports_mock_backend_usage() -> None:
    store = InMemoryArtifactStore()
    one = store.put("agents/demo/run-1/workflow.yml", b"one")
    two = store.put("agents/demo/run-1/run_summary.json", b"two")

    assert one.local_path is None
    assert two.local_path is None
    assert store.exists(one.uri)
    assert store.get(two.uri) == b"two"
    assert store.list("memory://agents/demo/run-1") == [two.uri, one.uri]

    store.delete(one.uri)
    assert not store.exists(one.uri)


def test_service_can_run_with_in_memory_artifact_store(tmp_path: Path) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)
    session = maker()
    settings = Settings(
        database_url="sqlite:///:memory:",
        artifacts_dir=str(tmp_path / "artifacts"),
        manual_blueprints_dir=str(tmp_path / "manual_blueprints"),
        chat2graph_runtime_mode="mock",
        judge_backend="mock",
        artifact_store_backend="memory",
    )
    artifact_store = InMemoryArtifactStore()

    service = AgentOptimizationService(
        session=session,
        settings=settings,
        artifact_store=artifact_store,
    )
    report = service.optimize(
        agent_name="demo-memory",
        task_desc="图查询任务",
        dataset_size=6,
        seed=7,
    )

    assert report.registry_record is not None
    assert report.registry_record.artifact_path.startswith("memory://")

    repo = AgentRepository(session)
    run = repo.get_optimization_run(report.run_id)
    assert run is not None
    assert len(run.artifacts) >= 5
    artifact_types = {artifact.artifact_type for artifact in run.artifacts}
    assert {
        "workflow_yaml",
        "dataset_report",
        "round_traces",
        "prompt_variants",
        "run_summary",
    }.issubset(artifact_types)

    version = repo.get_version("demo-memory", 1)
    assert version.workflow_snapshot
