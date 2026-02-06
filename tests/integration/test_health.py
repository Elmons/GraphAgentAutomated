from __future__ import annotations

from fastapi.testclient import TestClient

from graph_agent_automated.main import create_app


def test_healthz() -> None:
    app = create_app()
    with TestClient(app) as client:
        resp = client.get('/healthz')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


def test_metrics_endpoint() -> None:
    app = create_app()
    with TestClient(app) as client:
        _ = client.get('/healthz')
        resp = client.get('/metrics')

    assert resp.status_code == 200
    payload = resp.json()
    assert payload['requests_total'] >= 1
    assert 'errors_total' in payload
    assert 'endpoints' in payload
