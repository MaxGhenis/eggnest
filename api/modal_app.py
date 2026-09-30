from pathlib import Path

import modal

HERE = Path(__file__).parent

app = modal.App("eggnest-api")
job_statuses = modal.Dict.from_name("eggnest-job-statuses", create_if_missing=True)

# Install the runtime dependencies pinned in uv.lock, the versions CI tests.
# Regenerate requirements-modal.txt after changing uv.lock:
#   uv export --frozen --no-dev --no-emit-project --no-hashes --no-header \
#     -o requirements-modal.txt
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(HERE / "requirements-modal.txt"))
    .add_local_dir(str(HERE / "eggnest"), "/root/eggnest")
    .add_local_file(str(HERE / "main.py"), "/root/main.py")
)


class ModalDictJobSnapshotStore:
    """Adapter around Modal Dict for JSON job status snapshots."""

    def __init__(self, modal_dict):
        self._dict = modal_dict

    def put(self, key: str, value: dict) -> None:
        self._dict.put(key, value)

    def get(self, key: str) -> dict | None:
        return self._dict.get(key)

    def delete(self, key: str) -> None:
        self._dict.pop(key, None)

    def items(self) -> list[tuple[str, dict]]:
        import asyncio

        async def collect():
            return [(key, value) async for key, value in self._dict.items()]

        return asyncio.run(collect())


def _prepare_imports() -> None:
    import sys

    sys.path.insert(0, "/root")


@app.function(
    image=image,
    cpu=4.0,
    memory=8192,
    timeout=900,
    max_containers=20,
    scaledown_window=60,
)
def run_simulation_job_worker(job_id: str, params_payload: dict):
    _prepare_imports()

    from eggnest.models import SimulationInput
    from eggnest.simulation_jobs import run_simulation_job_to_store

    run_simulation_job_to_store(
        job_id,
        SimulationInput.model_validate(params_payload),
        ModalDictJobSnapshotStore(job_statuses),
    )


@app.function(
    image=image,
    cpu=4.0,
    memory=8192,
    timeout=900,
    max_containers=20,
    scaledown_window=60,
)
def run_core_job_worker(job_id: str, scenario_payload: dict):
    _prepare_imports()

    from eggnest.core.schemas import EngineScenario
    from eggnest.simulation_jobs import run_core_job_to_store

    run_core_job_to_store(
        job_id,
        EngineScenario.model_validate(scenario_payload),
        ModalDictJobSnapshotStore(job_statuses),
    )


@app.function(
    image=image,
    cpu=4.0,
    memory=8192,
    timeout=900,
    max_containers=4,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def fastapi_app():
    _prepare_imports()

    from main import app, configure_job_external_runners, configure_job_snapshot_store

    configure_job_snapshot_store(ModalDictJobSnapshotStore(job_statuses))
    configure_job_external_runners(
        simulation_runner=lambda job_id, params: run_simulation_job_worker.spawn(
            job_id,
            params.model_dump(mode="json"),
        ),
        core_runner=lambda job_id, scenario: run_core_job_worker.spawn(
            job_id,
            scenario.model_dump(mode="json"),
        ),
    )

    return app
