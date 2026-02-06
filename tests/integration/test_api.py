from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from graph_agent_automated.api.dependencies import get_service
from graph_agent_automated.application.services import AgentOptimizationService
from graph_agent_automated.core.config import get_settings
from graph_agent_automated.core.database import Base
from graph_agent_automated.main import create_app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test.db"
    artifacts_dir = tmp_path / "artifacts"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CHAT2GRAPH_RUNTIME_MODE", "mock")
    monkeypatch.setenv("JUDGE_BACKEND", "mock")
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    get_settings.cache_clear()

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, class_=Session, autocommit=False, autoflush=False)

    app = create_app()

    def override_service():
        session = local_session()
        try:
            yield AgentOptimizationService(session=session, settings=get_settings())
        finally:
            session.close()

    app.dependency_overrides[get_service] = override_service

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_optimize_and_version_lifecycle(client: TestClient) -> None:
    optimize_resp = client.post(
        "/v1/agents/optimize",
        json={
            "agent_name": "demo-agent",
            "task_desc": "请完成图查询和图分析任务",
            "dataset_size": 8,
        },
    )
    assert optimize_resp.status_code == 200
    optimize_payload = optimize_resp.json()
    assert optimize_payload["version"] == 1

    versions_resp = client.get("/v1/agents/demo-agent/versions")
    assert versions_resp.status_code == 200
    versions = versions_resp.json()
    assert len(versions) == 1

    deploy_resp = client.post("/v1/agents/demo-agent/versions/1/deploy")
    assert deploy_resp.status_code == 200
    assert deploy_resp.json()["lifecycle"] == "deployed"

    optimize_resp_2 = client.post(
        "/v1/agents/optimize",
        json={
            "agent_name": "demo-agent",
            "task_desc": "继续优化图查询精度",
            "dataset_size": 8,
        },
    )
    assert optimize_resp_2.status_code == 200
    assert optimize_resp_2.json()["version"] == 2

    deploy_resp_2 = client.post("/v1/agents/demo-agent/versions/2/deploy")
    assert deploy_resp_2.status_code == 200
    assert deploy_resp_2.json()["version"] == 2

    rollback_resp = client.post("/v1/agents/demo-agent/versions/1/rollback")
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["version"] == 1
    assert rollback_resp.json()["lifecycle"] == "deployed"
