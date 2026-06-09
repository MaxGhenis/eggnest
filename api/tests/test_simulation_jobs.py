"""Tests for background simulation job endpoints."""

import time
from threading import Lock

from fastapi.testclient import TestClient

from eggnest.core.us_retirement import OUTPUT_KEY, build_us_retirement_scenario
from eggnest.models import SimulationInput
from eggnest.simulation_jobs import CoreJobManager, run_core_job_to_store
from main import app

client = TestClient(app)


class MemorySnapshotStore:
    """Thread-safe in-memory snapshot store for cross-manager tests."""

    def __init__(self):
        self._data: dict[str, dict] = {}
        self._lock = Lock()

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._data[key] = value

    def get(self, key: str) -> dict | None:
        with self._lock:
            return self._data.get(key)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def items(self) -> list[tuple[str, dict]]:
        with self._lock:
            return list(self._data.items())


def small_input() -> SimulationInput:
    return SimulationInput(
        current_age=65,
        max_age=66,
        initial_capital=100_000,
        annual_spending=10_000,
        social_security_monthly=0,
        pension_annual=0,
        state="CA",
        filing_status="single",
        n_simulations=100,
        random_seed=123,
        include_mortality=False,
    )


def test_simulation_job_runs_to_completion():
    response = client.post("/simulate/jobs", json=small_input().model_dump())

    assert response.status_code == 202
    created = response.json()
    assert created["status"] in {"queued", "running"}
    assert created["total_years"] == 1

    job_id = created["job_id"]
    data = created
    for _ in range(100):
        poll = client.get(f"/simulate/jobs/{job_id}")
        assert poll.status_code == 200
        data = poll.json()
        if data["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert data["status"] == "succeeded"
    assert data["progress"] == 1
    assert data["result"]["success_rate"] == 1.0
    assert data["error"] is None


def test_missing_simulation_job_returns_404():
    response = client.get("/simulate/jobs/not-a-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Simulation job not found"


def test_core_job_returns_stable_envelope():
    scenario = build_us_retirement_scenario(small_input())

    response = client.post("/core/jobs", json=scenario.model_dump())

    assert response.status_code == 202
    created = response.json()
    assert created["status"] in {"queued", "running"}
    assert created["engine"] == "us_retirement"
    assert created["total_years"] == 1

    job_id = created["job_id"]
    data = created
    for _ in range(100):
        poll = client.get(f"/core/jobs/{job_id}")
        assert poll.status_code == 200
        data = poll.json()
        if data["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert data["status"] == "succeeded"
    assert data["progress"] == 1
    assert data["result"]["schema_version"] == "eggnest.result.v1"
    assert data["result"]["engine"] == "us_retirement"
    assert data["result"]["outputs"][OUTPUT_KEY]["success_rate"] == 1.0


def test_missing_core_job_returns_404():
    response = client.get("/core/jobs/not-a-job")

    assert response.status_code == 404
    assert response.json()["detail"] == "Core job not found"


def test_core_job_status_can_be_read_from_shared_store():
    store = MemorySnapshotStore()
    writer = CoreJobManager(
        max_workers=1,
        ttl_seconds=3600,
        max_records=100,
        snapshot_store=store,
    )
    reader = CoreJobManager(
        max_workers=1,
        ttl_seconds=3600,
        max_records=100,
        snapshot_store=store,
    )
    scenario = build_us_retirement_scenario(small_input())

    created = writer.submit(scenario)
    data = reader.get(created.job_id)

    assert data is not None
    assert data.job_id == created.job_id
    assert data.status in {"queued", "running"}

    for _ in range(100):
        data = reader.get(created.job_id)
        assert data is not None
        if data.status in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert data is not None
    assert data.status == "succeeded"
    assert data.result is not None
    assert data.result.outputs[OUTPUT_KEY]["success_rate"] == 1.0


def test_core_job_can_run_with_external_runner():
    store = MemorySnapshotStore()
    writer = CoreJobManager(
        max_workers=1,
        ttl_seconds=3600,
        max_records=100,
        snapshot_store=store,
    )
    reader = CoreJobManager(
        max_workers=1,
        ttl_seconds=3600,
        max_records=100,
        snapshot_store=store,
    )
    writer.set_external_runner(
        lambda job_id, scenario: run_core_job_to_store(job_id, scenario, store)
    )
    scenario = build_us_retirement_scenario(small_input())

    created = writer.submit(scenario)
    data = reader.get(created.job_id)

    assert data is not None
    assert data.status == "succeeded"
    assert data.result is not None
    assert data.result.outputs[OUTPUT_KEY]["success_rate"] == 1.0
