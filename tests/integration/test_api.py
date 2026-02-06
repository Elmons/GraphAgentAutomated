from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
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
    manual_blueprints_dir = tmp_path / "manual_blueprints"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CHAT2GRAPH_RUNTIME_MODE", "mock")
    monkeypatch.setenv("JUDGE_BACKEND", "mock")
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("MANUAL_BLUEPRINTS_DIR", str(manual_blueprints_dir))
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


@pytest.fixture
def secured_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "test_auth.db"
    artifacts_dir = tmp_path / "artifacts_auth"
    manual_blueprints_dir = tmp_path / "manual_blueprints_auth"

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("CHAT2GRAPH_RUNTIME_MODE", "mock")
    monkeypatch.setenv("JUDGE_BACKEND", "mock")
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("MANUAL_BLUEPRINTS_DIR", str(manual_blueprints_dir))
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "AUTH_API_KEYS_JSON",
        json.dumps(
            {
                "tenant-a-admin-key": {"tenant_id": "tenant-a", "role": "admin"},
                "tenant-a-viewer-key": {"tenant_id": "tenant-a", "role": "viewer"},
                "tenant-b-admin-key": {"tenant_id": "tenant-b", "role": "admin"},
            },
            ensure_ascii=False,
        ),
    )
    monkeypatch.setenv("AUTH_DEFAULT_TENANT_ID", "default")
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
    assert optimize_payload["run_id"].startswith("run-")
    assert optimize_payload["profile"] == "full_system"
    assert "train_score" in optimize_payload
    assert "val_score" in optimize_payload
    assert "test_score" in optimize_payload

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
            "profile": "baseline_static_prompt_only",
            "seed": 11,
        },
    )
    assert optimize_resp_2.status_code == 200
    assert optimize_resp_2.json()["version"] == 2
    assert optimize_resp_2.json()["profile"] == "baseline_static_prompt_only"

    deploy_resp_2 = client.post("/v1/agents/demo-agent/versions/2/deploy")
    assert deploy_resp_2.status_code == 200
    assert deploy_resp_2.json()["version"] == 2

    rollback_resp = client.post("/v1/agents/demo-agent/versions/1/rollback")
    assert rollback_resp.status_code == 200
    assert rollback_resp.json()["version"] == 1
    assert rollback_resp.json()["lifecycle"] == "deployed"


def test_manual_parity_endpoint(client: TestClient, tmp_path: Path) -> None:
    manual_blueprint = {
        "app": {"name": "manual-agent", "desc": "manual graph task"},
        "tools": [{"name": "CypherExecutor", "type": "LOCAL_TOOL"}],
        "actions": [
            {
                "name": "use_cypherexecutor",
                "desc": "run query",
                "tools": [{"name": "CypherExecutor"}],
            }
        ],
        "experts": [
            {
                "profile": {"name": "ManualExpert", "desc": "manual design"},
                "workflow": [
                    [
                        {
                            "instruction": "answer with evidence",
                            "output_schema": "final_answer: str",
                            "actions": [{"name": "use_cypherexecutor"}],
                        }
                    ]
                ],
            }
        ],
        "leader": {"actions": [{"name": "use_cypherexecutor"}]},
        "env": {"topology": "linear", "meta": {"source": "manual"}},
    }
    manual_dir = tmp_path / "manual_blueprints"
    manual_dir.mkdir(parents=True, exist_ok=True)
    manual_path = manual_dir / "manual.yml"
    with open(manual_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(manual_blueprint, f, sort_keys=False, allow_unicode=True)

    resp = client.post(
        "/v1/agents/benchmark/manual-parity",
        json={
            "agent_name": "manual-parity-agent",
            "task_desc": "图查询任务",
            "manual_blueprint_path": str(manual_path),
            "dataset_size": 8,
            "profile": "full_system",
            "seed": 7,
            "parity_margin": 0.05,
        },
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["run_id"].startswith("run-")
    assert payload["profile"] == "full_system"
    assert payload["split"] in {"train", "val", "test"}
    assert "auto_score" in payload
    assert "manual_score" in payload
    assert "parity_achieved" in payload
    assert payload["evaluated_cases"] > 0


def test_manual_parity_rejects_uncontrolled_path(client: TestClient, tmp_path: Path) -> None:
    outside_path = tmp_path / "outside" / "manual.yml"
    outside_path.parent.mkdir(parents=True, exist_ok=True)
    with open(outside_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"app": {"name": "x"}}, f, sort_keys=False)

    resp = client.post(
        "/v1/agents/benchmark/manual-parity",
        json={
            "agent_name": "manual-parity-secure",
            "task_desc": "图查询任务",
            "manual_blueprint_path": str(outside_path),
            "dataset_size": 8,
            "profile": "full_system",
            "seed": 7,
        },
    )

    assert resp.status_code == 400
    assert "MANUAL_BLUEPRINTS_DIR" in resp.json()["detail"]

    versions_resp = client.get("/v1/agents/manual-parity-secure/versions")
    assert versions_resp.status_code == 200
    assert versions_resp.json() == []


def test_manual_parity_invalid_blueprint_does_not_persist(client: TestClient, tmp_path: Path) -> None:
    manual_dir = tmp_path / "manual_blueprints"
    manual_dir.mkdir(parents=True, exist_ok=True)
    bad_manual_path = manual_dir / "invalid.yml"
    with open(bad_manual_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(["not-a-dict"], f, sort_keys=False)

    resp = client.post(
        "/v1/agents/benchmark/manual-parity",
        json={
            "agent_name": "manual-parity-invalid",
            "task_desc": "图查询任务",
            "manual_blueprint_path": str(bad_manual_path),
            "dataset_size": 8,
            "profile": "full_system",
            "seed": 7,
        },
    )

    assert resp.status_code == 400
    assert "must be a JSON/YAML object" in resp.json()["detail"]

    versions_resp = client.get("/v1/agents/manual-parity-invalid/versions")
    assert versions_resp.status_code == 200
    assert versions_resp.json() == []


def test_auth_enabled_requires_api_key(secured_client: TestClient) -> None:
    resp = secured_client.post(
        "/v1/agents/optimize",
        json={
            "agent_name": "auth-agent",
            "task_desc": "图查询任务",
            "dataset_size": 8,
        },
    )
    assert resp.status_code == 401
    assert "X-API-Key" in resp.json()["detail"]


def test_viewer_role_cannot_optimize(secured_client: TestClient) -> None:
    resp = secured_client.post(
        "/v1/agents/optimize",
        json={
            "agent_name": "viewer-agent",
            "task_desc": "图查询任务",
            "dataset_size": 8,
        },
        headers={"X-API-Key": "tenant-a-viewer-key"},
    )
    assert resp.status_code == 403
    assert "permission denied" in resp.json()["detail"]


def test_tenant_isolation_with_same_agent_name(secured_client: TestClient) -> None:
    payload = {
        "agent_name": "shared-agent",
        "task_desc": "图查询任务",
        "dataset_size": 8,
    }

    optimize_a = secured_client.post(
        "/v1/agents/optimize",
        json=payload,
        headers={"X-API-Key": "tenant-a-admin-key"},
    )
    optimize_b = secured_client.post(
        "/v1/agents/optimize",
        json=payload,
        headers={"X-API-Key": "tenant-b-admin-key"},
    )

    assert optimize_a.status_code == 200
    assert optimize_b.status_code == 200
    assert optimize_a.json()["version"] == 1
    assert optimize_b.json()["version"] == 1

    versions_a = secured_client.get(
        "/v1/agents/shared-agent/versions",
        headers={"X-API-Key": "tenant-a-admin-key"},
    )
    versions_b = secured_client.get(
        "/v1/agents/shared-agent/versions",
        headers={"X-API-Key": "tenant-b-admin-key"},
    )

    assert versions_a.status_code == 200
    assert versions_b.status_code == 200
    assert len(versions_a.json()) == 1
    assert len(versions_b.json()) == 1
    assert versions_a.json()[0]["version"] == 1
    assert versions_b.json()[0]["version"] == 1
