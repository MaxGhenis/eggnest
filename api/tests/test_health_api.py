"""Tests for API health checks."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_health_endpoint_returns_healthy_payload():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
