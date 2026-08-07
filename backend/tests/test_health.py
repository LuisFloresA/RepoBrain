"""Tests de los endpoints de salud (F0)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "RepoBrain"
    assert body["environment"] == "development"


def test_health_ready_ok(client: TestClient) -> None:
    resp = client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert "dependencies" in body


def test_security_headers_present(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers
    assert resp.headers["referrer-policy"] == "no-referrer"


def test_openapi_docs_available(client: TestClient) -> None:
    resp = client.get("/docs")
    assert resp.status_code == 200
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/health" in paths
    assert "/health/ready" in paths
