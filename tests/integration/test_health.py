from __future__ import annotations

from fastapi.testclient import TestClient

from graph_agent_automated.main import create_app


def test_healthz() -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'
