"""In-process background jobs for long-running simulation requests."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Protocol
from uuid import uuid4

from eggnest.core.schemas import (
    EngineJobState,
    EngineJobStatus,
    EngineResult,
    EngineScenario,
)
from eggnest.models import (
    SimulationInput,
    SimulationJobState,
    SimulationJobStatus,
    SimulationResult,
)
from eggnest.simulation import MonteCarloSimulator


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class JobSnapshotStore(Protocol):
    """Minimal shared store for job status snapshots."""

    def put(self, key: str, value: dict) -> None: ...

    def get(self, key: str) -> dict | None: ...

    def delete(self, key: str) -> None: ...

    def items(self) -> list[tuple[str, dict]]: ...


@dataclass
class _JobRecord:
    job_id: str
    params: SimulationInput
    status: SimulationJobState
    current_year: float
    total_years: int
    progress: float
    message: str | None
    year_summary: dict | None
    result: SimulationResult | None
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    future: Future | None = None

    def snapshot(self) -> SimulationJobStatus:
        return SimulationJobStatus(
            job_id=self.job_id,
            status=self.status,
            current_year=self.current_year,
            total_years=self.total_years,
            progress=self.progress,
            message=self.message,
            year_summary=self.year_summary,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )


class SimulationJobManager:
    """Small in-memory job manager for API clients that prefer polling."""

    def __init__(
        self,
        max_workers: int,
        ttl_seconds: int,
        max_records: int,
        snapshot_store: JobSnapshotStore | None = None,
        snapshot_prefix: str = "simulation:",
    ):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="simulation-job",
        )
        self._ttl_seconds = ttl_seconds
        self._max_records = max_records
        self._snapshot_store = snapshot_store
        self._snapshot_prefix = snapshot_prefix
        self._external_runner: Callable[[str, SimulationInput], None] | None = None
        self._jobs: dict[str, _JobRecord] = {}
        self._lock = Lock()

    def set_snapshot_store(
        self, snapshot_store: JobSnapshotStore | None, prefix: str = "simulation:"
    ) -> None:
        """Configure the shared status store used across API containers."""
        self._snapshot_store = snapshot_store
        self._snapshot_prefix = prefix

    def set_external_runner(
        self, runner: Callable[[str, SimulationInput], None] | None
    ) -> None:
        """Run newly submitted jobs outside this API process when configured."""
        self._external_runner = runner

    def submit(self, params: SimulationInput) -> SimulationJobStatus:
        self._cleanup()
        job_id = uuid4().hex
        now = _now_iso()
        record = _JobRecord(
            job_id=job_id,
            params=params.model_copy(deep=True),
            status="queued",
            current_year=0,
            total_years=params.max_age - params.current_age,
            progress=0,
            message="Queued",
            year_summary=None,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )

        with self._lock:
            self._jobs[job_id] = record
            self._put_snapshot(record)

        if self._external_runner is not None:
            try:
                self._external_runner(job_id, record.params.model_copy(deep=True))
            except Exception as exc:
                self._update(
                    job_id,
                    status="failed",
                    message="Failed to start worker",
                    error=str(exc),
                    updated_at=_now_iso(),
                    completed_at=_now_iso(),
                )
            return record.snapshot()

        with self._lock:
            record.future = self._executor.submit(self._run, job_id)

        return record.snapshot()

    def get(self, job_id: str) -> SimulationJobStatus | None:
        self._cleanup()
        snapshot = self._get_snapshot(job_id)
        if snapshot is not None:
            return snapshot
        with self._lock:
            record = self._jobs.get(job_id)
            if record:
                return record.snapshot()
        return self._get_snapshot(job_id)

    def _run(self, job_id: str) -> None:
        self._update(
            job_id,
            status="running",
            message="Starting simulation",
            updated_at=_now_iso(),
        )
        try:
            with self._lock:
                record = self._jobs[job_id]
                params = record.params

            simulator = MonteCarloSimulator(params)
            for event in simulator.run_with_progress():
                if event["type"] == "progress":
                    self._update(
                        job_id,
                        status="running",
                        current_year=float(event["year"]),
                        total_years=int(event["total_years"]),
                        progress=float(event.get("progress", 0)),
                        message=event.get("message"),
                        year_summary=event.get("year_summary"),
                        updated_at=_now_iso(),
                    )
                elif event["type"] == "complete":
                    result = SimulationResult.model_validate(event["result"])
                    now = _now_iso()
                    self._update(
                        job_id,
                        status="succeeded",
                        current_year=params.max_age - params.current_age,
                        progress=1,
                        message="Complete",
                        result=result,
                        updated_at=now,
                        completed_at=now,
                    )
        except (
            Exception
        ) as exc:  # pragma: no cover - defensive catch for worker threads
            now = _now_iso()
            self._update(
                job_id,
                status="failed",
                message="Failed",
                error=str(exc),
                updated_at=now,
                completed_at=now,
            )

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            for key, value in updates.items():
                setattr(record, key, value)
            self._put_snapshot(record)

    def _snapshot_key(self, job_id: str) -> str:
        return f"{self._snapshot_prefix}{job_id}"

    def _put_snapshot(self, record: _JobRecord) -> None:
        if self._snapshot_store is None:
            return
        self._snapshot_store.put(
            self._snapshot_key(record.job_id),
            record.snapshot().model_dump(mode="json"),
        )

    def _get_snapshot(self, job_id: str) -> SimulationJobStatus | None:
        if self._snapshot_store is None:
            return None
        data = self._snapshot_store.get(self._snapshot_key(job_id))
        return SimulationJobStatus.model_validate(data) if data else None

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            removable = []
            for job_id, record in self._jobs.items():
                if record.status not in {"succeeded", "failed"}:
                    continue
                completed_at = record.completed_at or record.updated_at
                completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                if (now - completed).total_seconds() > self._ttl_seconds:
                    removable.append(job_id)

            for job_id in removable:
                self._jobs.pop(job_id, None)

            if len(self._jobs) <= self._max_records:
                return

            finished = [
                record
                for record in self._jobs.values()
                if record.status in {"succeeded", "failed"}
            ]
            finished.sort(key=lambda record: record.updated_at)
            excess = len(self._jobs) - self._max_records
            for record in finished[:excess]:
                self._jobs.pop(record.job_id, None)
                if self._snapshot_store is not None:
                    self._snapshot_store.delete(self._snapshot_key(record.job_id))

        self._cleanup_snapshots(now)

    def _cleanup_snapshots(self, now: datetime) -> None:
        if self._snapshot_store is None:
            return
        entries = [
            (key, value)
            for key, value in self._snapshot_store.items()
            if key.startswith(self._snapshot_prefix)
        ]
        removable = []
        finished = []
        for key, value in entries:
            status = value.get("status")
            if status not in {"succeeded", "failed"}:
                continue
            completed_at = value.get("completed_at") or value.get("updated_at")
            if not completed_at:
                continue
            completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            if (now - completed).total_seconds() > self._ttl_seconds:
                removable.append(key)
            else:
                finished.append((key, value))

        for key in removable:
            self._snapshot_store.delete(key)

        if len(entries) <= self._max_records:
            return

        finished.sort(key=lambda item: item[1].get("updated_at", ""))
        excess = len(entries) - self._max_records
        for key, _ in finished[:excess]:
            self._snapshot_store.delete(key)


@dataclass
class _CoreJobRecord:
    job_id: str
    scenario: EngineScenario
    status: EngineJobState
    progress: float
    current_year: float | None
    total_years: int | None
    message: str | None
    year_summary: dict | None
    result: EngineResult | None
    error: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    future: Future | None = None

    def snapshot(self) -> EngineJobStatus:
        return EngineJobStatus(
            job_id=self.job_id,
            status=self.status,
            engine=self.scenario.engine,
            country=self.scenario.country,
            progress=self.progress,
            current_year=self.current_year,
            total_years=self.total_years,
            message=self.message,
            year_summary=self.year_summary,
            result=self.result,
            error=self.error,
            created_at=self.created_at,
            updated_at=self.updated_at,
            completed_at=self.completed_at,
        )


class CoreJobManager:
    """In-memory background jobs for stable core engine envelopes."""

    def __init__(
        self,
        max_workers: int,
        ttl_seconds: int,
        max_records: int,
        snapshot_store: JobSnapshotStore | None = None,
        snapshot_prefix: str = "core:",
    ):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="core-job",
        )
        self._ttl_seconds = ttl_seconds
        self._max_records = max_records
        self._snapshot_store = snapshot_store
        self._snapshot_prefix = snapshot_prefix
        self._external_runner: Callable[[str, EngineScenario], None] | None = None
        self._jobs: dict[str, _CoreJobRecord] = {}
        self._lock = Lock()

    def set_snapshot_store(
        self, snapshot_store: JobSnapshotStore | None, prefix: str = "core:"
    ) -> None:
        """Configure the shared status store used across API containers."""
        self._snapshot_store = snapshot_store
        self._snapshot_prefix = prefix

    def set_external_runner(
        self, runner: Callable[[str, EngineScenario], None] | None
    ) -> None:
        """Run newly submitted jobs outside this API process when configured."""
        self._external_runner = runner

    def submit(self, scenario: EngineScenario) -> EngineJobStatus:
        self._cleanup()
        job_id = uuid4().hex
        now = _now_iso()
        total_years = None
        if scenario.engine == "us_retirement":
            inputs = SimulationInput.model_validate(scenario.inputs)
            total_years = inputs.max_age - inputs.current_age

        record = _CoreJobRecord(
            job_id=job_id,
            scenario=scenario.model_copy(deep=True),
            status="queued",
            progress=0,
            current_year=0 if total_years is not None else None,
            total_years=total_years,
            message="Queued",
            year_summary=None,
            result=None,
            error=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )

        with self._lock:
            self._jobs[job_id] = record
            self._put_snapshot(record)

        if self._external_runner is not None:
            try:
                self._external_runner(job_id, record.scenario.model_copy(deep=True))
            except Exception as exc:
                self._update(
                    job_id,
                    status="failed",
                    message="Failed to start worker",
                    error=str(exc),
                    updated_at=_now_iso(),
                    completed_at=_now_iso(),
                )
            return record.snapshot()

        with self._lock:
            record.future = self._executor.submit(self._run, job_id)

        return record.snapshot()

    def get(self, job_id: str) -> EngineJobStatus | None:
        self._cleanup()
        snapshot = self._get_snapshot(job_id)
        if snapshot is not None:
            return snapshot
        with self._lock:
            record = self._jobs.get(job_id)
            if record:
                return record.snapshot()
        return self._get_snapshot(job_id)

    def _run(self, job_id: str) -> None:
        self._update(
            job_id,
            status="running",
            progress=0.01,
            message="Starting core engine",
            updated_at=_now_iso(),
        )
        try:
            with self._lock:
                scenario = self._jobs[job_id].scenario

            if scenario.engine == "us_retirement":
                result = self._run_us_retirement(job_id, scenario)
            else:
                from eggnest.core.router import run_core_scenario

                self._update(
                    job_id,
                    status="running",
                    progress=0.25,
                    message="Running core engine",
                    updated_at=_now_iso(),
                )
                result = run_core_scenario(scenario)

            now = _now_iso()
            self._update(
                job_id,
                status="succeeded",
                progress=1,
                message="Complete",
                result=result,
                updated_at=now,
                completed_at=now,
            )
        except (
            Exception
        ) as exc:  # pragma: no cover - defensive catch for worker threads
            now = _now_iso()
            self._update(
                job_id,
                status="failed",
                message="Failed",
                error=str(exc),
                updated_at=now,
                completed_at=now,
            )

    def _run_us_retirement(self, job_id: str, scenario: EngineScenario) -> EngineResult:
        from eggnest.core.us_retirement import build_us_retirement_result

        params = SimulationInput.model_validate(scenario.inputs)
        simulator = MonteCarloSimulator(params)
        for event in simulator.run_with_progress():
            if event["type"] == "progress":
                self._update(
                    job_id,
                    status="running",
                    current_year=float(event["year"]),
                    total_years=int(event["total_years"]),
                    progress=float(event.get("progress", 0)),
                    message=event.get("message"),
                    year_summary=event.get("year_summary"),
                    updated_at=_now_iso(),
                )
            elif event["type"] == "complete":
                simulation_result = SimulationResult.model_validate(event["result"])
                return build_us_retirement_result(scenario, params, simulation_result)
        raise RuntimeError("Core job did not produce a result")

    def _update(self, job_id: str, **updates: object) -> None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return
            for key, value in updates.items():
                setattr(record, key, value)
            self._put_snapshot(record)

    def _snapshot_key(self, job_id: str) -> str:
        return f"{self._snapshot_prefix}{job_id}"

    def _put_snapshot(self, record: _CoreJobRecord) -> None:
        if self._snapshot_store is None:
            return
        self._snapshot_store.put(
            self._snapshot_key(record.job_id),
            record.snapshot().model_dump(mode="json"),
        )

    def _get_snapshot(self, job_id: str) -> EngineJobStatus | None:
        if self._snapshot_store is None:
            return None
        data = self._snapshot_store.get(self._snapshot_key(job_id))
        return EngineJobStatus.model_validate(data) if data else None

    def _cleanup(self) -> None:
        now = datetime.now(UTC)
        with self._lock:
            removable = []
            for job_id, record in self._jobs.items():
                if record.status not in {"succeeded", "failed"}:
                    continue
                completed_at = record.completed_at or record.updated_at
                completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                if (now - completed).total_seconds() > self._ttl_seconds:
                    removable.append(job_id)

            for job_id in removable:
                self._jobs.pop(job_id, None)

            if len(self._jobs) <= self._max_records:
                return

            finished = [
                record
                for record in self._jobs.values()
                if record.status in {"succeeded", "failed"}
            ]
            finished.sort(key=lambda record: record.updated_at)
            excess = len(self._jobs) - self._max_records
            for record in finished[:excess]:
                self._jobs.pop(record.job_id, None)
                if self._snapshot_store is not None:
                    self._snapshot_store.delete(self._snapshot_key(record.job_id))

        self._cleanup_snapshots(now)

    def _cleanup_snapshots(self, now: datetime) -> None:
        if self._snapshot_store is None:
            return
        entries = [
            (key, value)
            for key, value in self._snapshot_store.items()
            if key.startswith(self._snapshot_prefix)
        ]
        removable = []
        finished = []
        for key, value in entries:
            status = value.get("status")
            if status not in {"succeeded", "failed"}:
                continue
            completed_at = value.get("completed_at") or value.get("updated_at")
            if not completed_at:
                continue
            completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            if (now - completed).total_seconds() > self._ttl_seconds:
                removable.append(key)
            else:
                finished.append((key, value))

        for key in removable:
            self._snapshot_store.delete(key)

        if len(entries) <= self._max_records:
            return

        finished.sort(key=lambda item: item[1].get("updated_at", ""))
        excess = len(entries) - self._max_records
        for key, _ in finished[:excess]:
            self._snapshot_store.delete(key)


def _merge_snapshot(
    store: JobSnapshotStore,
    key: str,
    model_cls,
    fallback: dict,
    updates: dict,
) -> None:
    current = store.get(key) or fallback
    payload = model_cls.model_validate(current).model_dump(mode="json")
    payload.update(updates)
    store.put(key, payload)


def run_simulation_job_to_store(
    job_id: str,
    params: SimulationInput,
    snapshot_store: JobSnapshotStore,
    snapshot_prefix: str = "simulation:",
) -> None:
    """Execute a legacy simulation job and persist status to a shared store."""
    key = f"{snapshot_prefix}{job_id}"
    now = _now_iso()
    fallback = SimulationJobStatus(
        job_id=job_id,
        status="queued",
        current_year=0,
        total_years=params.max_age - params.current_age,
        progress=0,
        message="Queued",
        year_summary=None,
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")

    def update(**updates: object) -> None:
        _merge_snapshot(
            snapshot_store,
            key,
            SimulationJobStatus,
            fallback,
            {**updates, "updated_at": _now_iso()},
        )

    update(status="running", message="Starting simulation")
    try:
        simulator = MonteCarloSimulator(params)
        for event in simulator.run_with_progress():
            if event["type"] == "progress":
                update(
                    status="running",
                    current_year=float(event["year"]),
                    total_years=int(event["total_years"]),
                    progress=float(event.get("progress", 0)),
                    message=event.get("message"),
                    year_summary=event.get("year_summary"),
                )
            elif event["type"] == "complete":
                result = SimulationResult.model_validate(event["result"])
                completed_at = _now_iso()
                update(
                    status="succeeded",
                    current_year=params.max_age - params.current_age,
                    progress=1,
                    message="Complete",
                    result=result.model_dump(mode="json"),
                    completed_at=completed_at,
                )
                return
        raise RuntimeError("Simulation job did not produce a result")
    except Exception as exc:
        completed_at = _now_iso()
        update(
            status="failed",
            message="Failed",
            error=str(exc),
            completed_at=completed_at,
        )


def run_core_job_to_store(
    job_id: str,
    scenario: EngineScenario,
    snapshot_store: JobSnapshotStore,
    snapshot_prefix: str = "core:",
) -> None:
    """Execute a core engine job and persist status to a shared store."""
    key = f"{snapshot_prefix}{job_id}"
    now = _now_iso()
    total_years = None
    if scenario.engine == "us_retirement":
        params = SimulationInput.model_validate(scenario.inputs)
        total_years = params.max_age - params.current_age
    fallback = EngineJobStatus(
        job_id=job_id,
        status="queued",
        engine=scenario.engine,
        country=scenario.country,
        progress=0,
        current_year=0 if total_years is not None else None,
        total_years=total_years,
        message="Queued",
        year_summary=None,
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")

    def update(**updates: object) -> None:
        _merge_snapshot(
            snapshot_store,
            key,
            EngineJobStatus,
            fallback,
            {**updates, "updated_at": _now_iso()},
        )

    update(status="running", progress=0.01, message="Starting core engine")
    try:
        if scenario.engine == "us_retirement":
            from eggnest.core.us_retirement import build_us_retirement_result

            params = SimulationInput.model_validate(scenario.inputs)
            simulator = MonteCarloSimulator(params)
            for event in simulator.run_with_progress():
                if event["type"] == "progress":
                    update(
                        status="running",
                        current_year=float(event["year"]),
                        total_years=int(event["total_years"]),
                        progress=float(event.get("progress", 0)),
                        message=event.get("message"),
                        year_summary=event.get("year_summary"),
                    )
                elif event["type"] == "complete":
                    simulation_result = SimulationResult.model_validate(event["result"])
                    result = build_us_retirement_result(
                        scenario, params, simulation_result
                    )
                    completed_at = _now_iso()
                    update(
                        status="succeeded",
                        progress=1,
                        current_year=params.max_age - params.current_age,
                        message="Complete",
                        result=result.model_dump(mode="json"),
                        completed_at=completed_at,
                    )
                    return
            raise RuntimeError("Core job did not produce a result")

        from eggnest.core.router import run_core_scenario

        update(status="running", progress=0.25, message="Running core engine")
        result = run_core_scenario(scenario)
        completed_at = _now_iso()
        update(
            status="succeeded",
            progress=1,
            message="Complete",
            result=result.model_dump(mode="json"),
            completed_at=completed_at,
        )
    except Exception as exc:
        completed_at = _now_iso()
        update(
            status="failed",
            message="Failed",
            error=str(exc),
            completed_at=completed_at,
        )
