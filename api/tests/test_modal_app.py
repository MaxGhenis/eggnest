"""Tests for the Modal job snapshot store adapter in modal_app.py.

The job managers sweep the shared store on every submit and poll, so the
adapter's items() runs on the request path. modal is not a test dependency,
so the module is imported with modal stubbed out and the Dict replaced by a
stand-in for Modal's blocking interface.
"""

import importlib
import sys
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest


class BlockingModalDict:
    """Mirrors modal.Dict's blocking interface: items() is a plain generator,
    which `async for` rejects with TypeError."""

    def __init__(self):
        self._data: dict[str, dict] = {}

    def put(self, key, value):
        self._data[key] = value

    def get(self, key, default=None):
        return self._data.get(key, default)

    def pop(self, key, default=None):
        return self._data.pop(key, default)

    def items(self):
        yield from list(self._data.items())


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setitem(sys.modules, "modal", MagicMock())
    monkeypatch.delitem(sys.modules, "modal_app", raising=False)
    modal_app = importlib.import_module("modal_app")
    yield modal_app.ModalDictJobSnapshotStore(BlockingModalDict())
    sys.modules.pop("modal_app", None)


def test_items_reads_the_blocking_dict(store):
    store.put("core:a", {"status": "succeeded"})
    store.put("simulation:b", {"status": "running"})

    assert sorted(store.items()) == [
        ("core:a", {"status": "succeeded"}),
        ("simulation:b", {"status": "running"}),
    ]
    store.delete("core:a")
    store.delete("never-stored")
    assert store.items() == [("simulation:b", {"status": "running"})]


@pytest.mark.parametrize("kind", ["core", "simulation"])
def test_job_reads_sweep_the_modal_store(store, kind):
    """A read below local capacity sweeps the shared store; with the Modal
    adapter that sweep must expire snapshots instead of failing the read."""
    from eggnest.simulation_jobs import CoreJobManager, SimulationJobManager

    manager_class = CoreJobManager if kind == "core" else SimulationJobManager
    manager = manager_class(
        max_workers=1, ttl_seconds=60, max_records=100, snapshot_store=store
    )
    expired = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    store.put(
        f"{kind}:old",
        {"status": "succeeded", "completed_at": expired, "updated_at": expired},
    )

    assert manager.get("missing") is None
    assert store.items() == []
