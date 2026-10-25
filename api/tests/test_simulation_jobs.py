"""Tests for background simulation job endpoints."""

import time
from datetime import UTC, datetime, timedelta
from threading import Lock

import pytest
from fastapi.testclient import TestClient

from eggnest.core.us_retirement import OUTPUT_KEY, build_us_retirement_scenario
from eggnest.models import SimulationInput
from eggnest.simulation_jobs import (
    CoreJobManager,
    SimulationJobManager,
    run_core_job_to_store,
    run_simulation_job_to_store,
)
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


def _iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def _finished_snapshot(job_id: str, finished_at: datetime) -> dict:
    stamp = _iso(finished_at)
    return {
        "job_id": job_id,
        "status": "succeeded",
        "created_at": stamp,
        "updated_at": stamp,
        "completed_at": stamp,
    }


def _manager_with_external_runner(
    kind: str, store, ttl_seconds: int, max_records, sweep_interval: float = 0.0
):
    manager_cls = CoreJobManager if kind == "core" else SimulationJobManager
    manager = manager_cls(
        max_workers=1,
        ttl_seconds=ttl_seconds,
        max_records=max_records,
        snapshot_store=store,
        snapshot_prefix=f"{kind}:",
        snapshot_sweep_interval_seconds=sweep_interval,
    )
    if kind == "core":
        manager.set_external_runner(
            lambda job_id, scenario: run_core_job_to_store(
                job_id, scenario, store, snapshot_prefix="core:"
            )
        )
    else:
        manager.set_external_runner(
            lambda job_id, params: run_simulation_job_to_store(
                job_id, params, store, snapshot_prefix="simulation:"
            )
        )
    return manager


def _submit(kind: str, manager):
    if kind == "core":
        return manager.submit(build_us_retirement_scenario(small_input()))
    return manager.submit(small_input())


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_expired_shared_snapshots_are_removed_below_local_capacity(kind):
    """Jobs run by an external runner (or another container) never enter
    this manager's local registry, so the registry stays under capacity; the
    shared store must still expire their snapshots after the TTL."""
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(
        kind, store, ttl_seconds=60, max_records=100
    )
    now = datetime.now(UTC)
    for i in range(6):
        store.put(
            f"{kind}:expired-{i}",
            _finished_snapshot(f"expired-{i}", now - timedelta(minutes=5)),
        )
    store.put(f"{kind}:fresh", _finished_snapshot("fresh", now))
    store.put("other-prefix:expired", _finished_snapshot("x", now - timedelta(hours=1)))

    created = _submit(kind, manager)

    keys = {key for key, _ in store.items()}
    assert not any(key.startswith(f"{kind}:expired-") for key in keys)
    assert f"{kind}:fresh" in keys
    assert f"{kind}:{created.job_id}" in keys
    # Other managers' snapshots are left alone.
    assert "other-prefix:expired" in keys
    # Reads also sweep: expire the fresh one and read the new job.
    store.put(f"{kind}:fresh", _finished_snapshot("fresh", now - timedelta(minutes=5)))
    assert manager.get(created.job_id) is not None
    assert f"{kind}:fresh" not in {key for key, _ in store.items()}


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_capacity_trim_counts_only_unexpired_snapshots(kind):
    """Expired snapshots removed by the TTL sweep must not also count toward
    the capacity trim, or unexpired results are deleted early."""
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=60, max_records=3)
    now = datetime.now(UTC)
    for i in range(2):
        store.put(
            f"{kind}:expired-{i}",
            _finished_snapshot(f"expired-{i}", now - timedelta(minutes=5)),
        )
    for i in range(3):
        store.put(
            f"{kind}:fresh-{i}",
            _finished_snapshot(f"fresh-{i}", now - timedelta(seconds=10 - i)),
        )

    manager.get("missing")

    keys = sorted(key for key, _ in store.items())
    assert keys == [f"{kind}:fresh-0", f"{kind}:fresh-1", f"{kind}:fresh-2"]


def _snapshot(job_id: str, status: str, updated: datetime, finished=None) -> dict:
    data = {
        "job_id": job_id,
        "status": status,
        "created_at": _iso(updated),
        "updated_at": _iso(updated),
    }
    if finished is not None:
        data["completed_at"] = _iso(finished)
    return data


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_in_flight_snapshots_survive_and_stale_ones_expire(kind):
    """A running job's snapshot stays while it keeps updating; one whose
    worker died (no update for longer than the TTL) is expired, as the local
    registry already does."""
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=60, max_records=3)
    now = datetime.now(UTC)
    store.put(f"{kind}:running", _snapshot("running", "running", now))
    store.put(f"{kind}:queued", _snapshot("queued", "queued", now))
    store.put(f"{kind}:dead", _snapshot("dead", "running", now - timedelta(minutes=5)))

    manager.get("missing")

    keys = {key for key, _ in store.items()}
    assert keys == {f"{kind}:running", f"{kind}:queued"}


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_only_finished_snapshots_count_toward_capacity(kind):
    """Many in-flight jobs must not evict a result a client is about to
    read: the capacity trim counts and removes finished snapshots only."""
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=60, max_records=3)
    now = datetime.now(UTC)
    for i in range(5):
        store.put(f"{kind}:running-{i}", _snapshot(f"running-{i}", "running", now))
    for i in range(4):
        moment = now - timedelta(seconds=10 - i)
        store.put(
            f"{kind}:done-{i}", _snapshot(f"done-{i}", "succeeded", moment, moment)
        )

    manager.get("missing")

    keys = {key for key, _ in store.items()}
    assert {f"{kind}:running-{i}" for i in range(5)} <= keys
    # Four finished against a limit of three: only the oldest goes.
    assert {key for key in keys if "done" in key} == {
        f"{kind}:done-1",
        f"{kind}:done-2",
        f"{kind}:done-3",
    }


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_unreadable_timestamps_do_not_fail_requests(kind):
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=60, max_records=3)
    store.put(f"{kind}:bad", {"status": "succeeded", "completed_at": "not a date"})
    store.put(f"{kind}:none", {"status": "running"})
    store.put(f"{kind}:junk", "not a snapshot")

    assert manager.get("missing") is None
    assert len(store.items()) == 3


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_shared_store_sweep_is_throttled(kind):
    """Polls arrive every 1-3 s; the full-store sweep runs at most once per
    interval per manager."""
    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(
        kind, store, ttl_seconds=60, max_records=3, sweep_interval=60.0
    )
    old = datetime.now(UTC) - timedelta(minutes=5)
    store.put(f"{kind}:a", _snapshot("a", "succeeded", old, old))
    manager.get("missing")
    assert store.items() == []

    store.put(f"{kind}:b", _snapshot("b", "succeeded", old, old))
    manager.get("missing")  # within the interval: no second sweep
    assert [key for key, _ in store.items()] == [f"{kind}:b"]


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_snapshot_refreshed_during_a_sweep_survives(kind):
    """A worker can refresh its snapshot after the sweep lists the store but
    before it deletes; the sweep re-reads an expired entry first."""

    class RefreshingStore(MemorySnapshotStore):
        def items(self):
            listed = super().items()
            self.put(f"{kind}:slow", _snapshot("slow", "running", datetime.now(UTC)))
            return listed

    store = RefreshingStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=60, max_records=3)
    stale = datetime.now(UTC) - timedelta(seconds=61)
    store.put(f"{kind}:slow", _snapshot("slow", "running", stale))
    store.put(f"{kind}:dead", _snapshot("dead", "running", stale))

    manager.get("missing")

    keys = {key for key, _ in store.items()}
    assert keys == {f"{kind}:slow"}


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_concurrent_requests_share_one_sweep(kind):
    """Pause one request between the throttle check and claiming the sweep,
    and let a second request run meanwhile: the store is listed once."""
    import inspect
    import sys
    import threading

    class CountingStore(MemorySnapshotStore):
        scans = 0

        def items(self):
            CountingStore.scans += 1
            return super().items()

    store = CountingStore()
    manager = _manager_with_external_runner(
        kind, store, ttl_seconds=60, max_records=3, sweep_interval=60.0
    )
    method = type(manager)._cleanup_snapshots
    lines, start = inspect.getsourcelines(method)
    claim_line = start + next(
        i for i, line in enumerate(lines) if "self._last_snapshot_sweep = now" in line
    )
    other = threading.Thread(target=manager.get, args=("missing",))

    def trace(frame, event, arg):
        if (
            frame.f_code is method.__code__
            and event == "line"
            and frame.f_lineno == claim_line
            and not other.is_alive()
            and other.ident is None
        ):
            other.start()
            # Fixed code holds the lock here, so the other request waits.
            other.join(timeout=0.5)
        return trace

    sys.settrace(trace)
    try:
        manager.get("missing")
    finally:
        sys.settrace(None)
    other.join(timeout=10)

    assert not other.is_alive()
    assert CountingStore.scans == 1


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_local_capacity_counts_only_finished_records(kind):
    """Queued and running jobs in this container's registry must not evict
    the newest finished results (or their shared snapshots)."""
    from eggnest.simulation_jobs import _CoreJobRecord, _JobRecord

    store = MemorySnapshotStore()
    manager = _manager_with_external_runner(kind, store, ttl_seconds=600, max_records=3)
    now = datetime.now(UTC)

    def record(job_id: str, status: str, moment: datetime):
        stamp = _iso(moment)
        done = stamp if status == "succeeded" else None
        if kind == "core":
            return _CoreJobRecord(
                job_id=job_id,
                scenario=build_us_retirement_scenario(small_input()),
                status=status,
                progress=1.0 if done else 0.0,
                current_year=None,
                total_years=None,
                message=None,
                year_summary=None,
                result=None,
                error=None,
                created_at=stamp,
                updated_at=stamp,
                completed_at=done,
            )
        return _JobRecord(
            job_id=job_id,
            params=small_input(),
            status=status,
            current_year=0,
            total_years=1,
            progress=1.0 if done else 0.0,
            message=None,
            year_summary=None,
            result=None,
            error=None,
            created_at=stamp,
            updated_at=stamp,
            completed_at=done,
        )

    for i in range(4):
        manager._jobs[f"running-{i}"] = record(f"running-{i}", "running", now)
    manager._jobs["done"] = record("done", "succeeded", now - timedelta(seconds=1))
    store.put(f"{kind}:done", _snapshot("done", "succeeded", now, now))

    manager.get("missing")

    assert set(manager._jobs) == {f"running-{i}" for i in range(4)} | {"done"}
    assert store.get(f"{kind}:done") is not None
