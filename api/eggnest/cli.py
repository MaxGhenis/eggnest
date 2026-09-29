"""Command-line interface for EggNest.

Filesystem-first financial planning. AI agents can explore your scenarios.
"""

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .auth import (
    clear_credentials,
    device_login,
    get_current_user,
    is_logged_in,
)
from .comparisons import compare_historical_cohorts, compare_withdrawal_strategies
from .core.router import run_core_scenario
from .core.schemas import EngineResult, EngineScenario
from .core.uk_retirement import (
    OUTPUT_KEY as UK_OUTPUT_KEY,
)
from .core.uk_retirement import (
    build_uk_retirement_scenario,
)
from .core.us_household_resources import (
    OUTPUT_KEY as HOUSEHOLD_OUTPUT_KEY,
)
from .core.us_household_resources import (
    build_us_household_resources_scenario,
)
from .core.us_retirement import OUTPUT_KEY, build_us_retirement_scenario
from .household import compare_earnings_grid, validate_household_payload
from .models import (
    EarningsGridInput,
    HistoricalCohortComparisonInput,
    HouseholdInput,
    SimulationInput,
    WithdrawalStrategyComparisonInput,
)
from .models_uk import UKSimulationInput
from .programs import list_programs
from .sync import DEFAULT_SCENARIOS_DIR, get_sync_client

# Setup rich console
console = Console()
MACHINE_OUTPUT_FORMATS = ("summary", "result", "envelope")
CORE_OUTPUT_FORMATS = ("envelope", "outputs", "legacy")
WITHDRAWAL_STRATEGY_CHOICES = (
    "taxable_first",
    "traditional_first",
    "roth_first",
    "pro_rata",
)
STOCK_INDEX_CHOICES = ("sp500", "vt")
BOND_INDEX_CHOICES = ("treasury", "bnd")


def setup_logging(verbose: bool = False) -> None:
    """Setup logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def _read_structured_input(path: Path) -> dict:
    """Read JSON or YAML from a file path or stdin."""
    import yaml

    text = sys.stdin.read() if str(path) == "-" else path.read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Input must be a JSON or YAML object")
    return data


def _write_json_payload(payload: dict, output: Path | None = None) -> None:
    """Write a JSON payload to stdout or an output file."""
    serialized = json.dumps(payload, indent=2)
    if output:
        output.write_text(serialized + "\n")
    else:
        click.echo(serialized)


def _core_result_dict(result: EngineResult | dict) -> dict:
    """Return a JSON-safe dict for a core result."""
    if isinstance(result, EngineResult):
        return result.model_dump(mode="json")
    return result


def _output_key_for_engine(engine: str) -> str:
    """Return the legacy output key for a core engine."""
    if engine == "us_retirement":
        return OUTPUT_KEY
    if engine == "uk_retirement":
        return UK_OUTPUT_KEY
    if engine == "us_household_resources":
        return HOUSEHOLD_OUTPUT_KEY
    raise ValueError(f"Unsupported engine: {engine}")


def _format_core_output(core_result: EngineResult | dict, output_format: str) -> dict:
    """Format a core result for machine-readable callers."""
    result = _core_result_dict(core_result)
    if output_format == "envelope":
        return result
    if output_format == "outputs":
        return result["outputs"]
    if output_format == "result":
        return result["outputs"][_output_key_for_engine(result["engine"])]
    if output_format == "legacy":
        return result["outputs"][_output_key_for_engine(result["engine"])]
    raise ValueError(f"Unsupported output format: {output_format}")


def _run_core_job(
    api_url: str,
    scenario: EngineScenario,
    poll_interval: float,
    progress: Progress | None = None,
    task: int | None = None,
) -> dict:
    """Run a remote core job to completion and return the result envelope."""
    import time

    import httpx

    base_url = api_url.rstrip("/")
    response = httpx.post(
        f"{base_url}/core/jobs",
        json=scenario.model_dump(),
        timeout=30.0,
    )
    response.raise_for_status()
    status = response.json()
    job_id = status["job_id"]

    while status["status"] in {"queued", "running"}:
        if progress is not None and task is not None:
            percent = int(float(status.get("progress") or 0) * 100)
            message = status.get("message") or "Running core engine"
            progress.update(
                task,
                description=f"{message} ({percent}%)",
            )
        time.sleep(poll_interval)
        response = httpx.get(f"{base_url}/core/jobs/{job_id}", timeout=30.0)
        response.raise_for_status()
        status = response.json()

    if status["status"] == "failed":
        raise click.ClickException(status.get("error") or "Core job failed")

    result = status.get("result")
    if not result:
        raise click.ClickException("Core job completed without a result")
    return result


def _looks_like_uk_input(data: dict) -> bool:
    """Infer UK retirement inputs from UK-specific account fields."""
    uk_markers = {
        "isa_balance",
        "sipp_balance",
        "gia_balance",
        "state_pension_annual",
        "state_pension_start_age",
        "equity_weight",
        "return_source",
    }
    return bool(uk_markers.intersection(data))


def _looks_like_household_input(data: dict) -> bool:
    """Infer US household-resource inputs from household member fields."""
    return "people" in data and "annual_spending" not in data


def _build_core_scenario(
    data: dict,
    engine: str = "auto",
    country: str | None = None,
) -> EngineScenario:
    """Build or validate a core scenario envelope from JSON/YAML input."""
    if "engine" in data and "inputs" in data:
        scenario = EngineScenario.model_validate(data)
        if engine != "auto" and scenario.engine != engine:
            raise ValueError(
                f"Scenario engine is {scenario.engine}, but --engine={engine} was requested"
            )
        return scenario

    resolved_engine = engine
    if resolved_engine == "auto":
        if _looks_like_uk_input(data):
            resolved_engine = "uk_retirement"
        elif _looks_like_household_input(data):
            resolved_engine = "us_household_resources"
        else:
            resolved_engine = "us_retirement"

    if resolved_engine == "us_retirement":
        scenario = build_us_retirement_scenario(SimulationInput.model_validate(data))
    elif resolved_engine == "uk_retirement":
        scenario = build_uk_retirement_scenario(UKSimulationInput.model_validate(data))
    elif resolved_engine == "us_household_resources":
        scenario = build_us_household_resources_scenario(
            HouseholdInput.model_validate(data)
        )
    else:
        raise ValueError(f"Unsupported engine: {resolved_engine}")

    if country:
        scenario = scenario.model_copy(update={"country": country})
    return scenario


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--scenarios-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"Scenarios directory (default: {DEFAULT_SCENARIOS_DIR})",
)
@click.pass_context
def main(ctx: click.Context, verbose: bool, scenarios_dir: Path | None) -> None:
    """EggNest - Monte Carlo retirement planning with real tax calculations.

    Your financial scenarios as local YAML files. Edit with any tool.
    AI agents can explore and modify your plans.

    \b
    Quick start:
      eggnest auth login        # Authenticate
      eggnest sync pull         # Download your scenarios
      eggnest simulate          # Run simulations
    """
    setup_logging(verbose)

    ctx.ensure_object(dict)
    ctx.obj["scenarios_dir"] = scenarios_dir or DEFAULT_SCENARIOS_DIR
    ctx.obj["verbose"] = verbose


# === Auth Commands ===


@main.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Manage authentication (login, logout, status)."""
    pass


@auth.command()
@click.pass_context
def login(ctx: click.Context) -> None:
    """Login to EggNest via browser (OAuth device flow)."""
    if is_logged_in():
        user = get_current_user()
        console.print(f"[yellow]Already logged in as {user}[/yellow]")
        if not click.confirm("Login again?"):
            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Opening browser...", total=None)
        creds = device_login()

        if creds:
            progress.update(task, description="Login successful!")
            console.print(f"\n[green]Logged in as {creds.user_email}[/green]")
        else:
            console.print("\n[red]Login failed[/red]")
            sys.exit(1)


@auth.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Logout and clear stored credentials."""
    if not is_logged_in():
        console.print("[yellow]Not currently logged in[/yellow]")
        return

    user = get_current_user()
    clear_credentials()
    console.print(f"[green]Logged out from {user}[/green]")


@auth.command()
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show current authentication status."""
    if is_logged_in():
        user = get_current_user()
        console.print(f"[green]Logged in as {user}[/green]")
    else:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Run 'eggnest auth login' to authenticate[/dim]")


# === Sync Commands ===


@main.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync scenarios with cloud (pull, push, status)."""
    pass


@sync.command()
@click.option("--scenario", "-s", help="Specific scenario ID to pull")
@click.pass_context
def pull(ctx: click.Context, scenario: str | None) -> None:
    """Pull scenarios from cloud to local YAML files."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    if not is_logged_in():
        console.print("[red]Not logged in. Run 'eggnest auth login' first.[/red]")
        sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Pulling scenarios...", total=None)

        try:
            sync_client = get_sync_client(scenarios_dir)
            stats = sync_client.pull(scenario)

            progress.update(task, description="Done!")
            console.print(
                f"\n[green]Pulled {stats['scenarios']} scenarios to {scenarios_dir}[/green]"
            )
        except Exception as e:
            console.print(f"\n[red]Pull failed: {e}[/red]")
            sys.exit(1)


@sync.command()
@click.option(
    "--file",
    "-f",
    type=click.Path(exists=True, path_type=Path),
    help="Specific file to push",
)
@click.pass_context
def push(ctx: click.Context, file: Path | None) -> None:
    """Push local YAML files to cloud."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    if not is_logged_in():
        console.print("[red]Not logged in. Run 'eggnest auth login' first.[/red]")
        sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Pushing scenarios...", total=None)

        try:
            sync_client = get_sync_client(scenarios_dir)
            stats = sync_client.push(file)

            progress.update(task, description="Done!")
            console.print(f"\n[green]Pushed {stats['scenarios']} scenarios[/green]")

            if stats.get("errors"):
                console.print("\n[yellow]Errors:[/yellow]")
                for error in stats["errors"]:
                    console.print(f"  [red]{error}[/red]")
        except Exception as e:
            console.print(f"\n[red]Push failed: {e}[/red]")
            sys.exit(1)


@sync.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show sync status and list scenarios."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    # Local scenarios
    sync_client = get_sync_client(scenarios_dir)
    local = sync_client.list_local()

    console.print(f"\n[bold]Local scenarios ({scenarios_dir}):[/bold]")
    if local:
        table = Table(show_header=True)
        table.add_column("Name")
        table.add_column("File")
        for s in local:
            table.add_row(s["name"], s["file"])
        console.print(table)
    else:
        console.print(
            "  [dim]No local scenarios. Run 'eggnest sync pull' to download.[/dim]"
        )

    # Remote scenarios (if logged in)
    if is_logged_in():
        try:
            remote = sync_client.list_remote()
            console.print("\n[bold]Cloud scenarios:[/bold]")
            if remote:
                table = Table(show_header=True)
                table.add_column("Name")
                table.add_column("ID")
                table.add_column("Updated")
                for s in remote:
                    table.add_row(
                        s.get("name", "Unnamed"),
                        s["id"][:8] + "...",
                        s.get("updated_at", "")[:10],
                    )
                console.print(table)
            else:
                console.print("  [dim]No saved scenarios in cloud.[/dim]")
        except Exception as e:
            console.print(f"  [yellow]Could not fetch remote: {e}[/yellow]")
    else:
        console.print("\n[dim]Login to see cloud scenarios: eggnest auth login[/dim]")


# === Core Engine Commands ===


@main.group()
def programs() -> None:
    """List agent-callable EggNest programs."""
    pass


@programs.command("list")
@click.option(
    "--jurisdiction",
    help="Optional jurisdiction or country filter, e.g. us or USA.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def programs_list(jurisdiction: str | None, output: Path | None) -> None:
    """Emit the machine-readable program catalog."""
    payload = {
        "programs": [
            program.model_dump(mode="json")
            for program in list_programs(jurisdiction=jurisdiction)
        ]
    }
    _write_json_payload(payload, output)


@main.group()
def core() -> None:
    """Run stable core engines for API, agent, and MCP-style callers."""
    pass


@core.command("schema")
@click.argument(
    "kind",
    type=click.Choice(
        ["scenario", "result", "us-input", "uk-input", "household-input"]
    ),
    default="scenario",
)
def core_schema(kind: str) -> None:
    """Print JSON Schema for core envelopes or engine inputs."""
    model = {
        "scenario": EngineScenario,
        "result": EngineResult,
        "us-input": SimulationInput,
        "uk-input": UKSimulationInput,
        "household-input": HouseholdInput,
    }[kind]
    _write_json_payload(model.model_json_schema())


@core.command("run")
@click.argument("scenario_file", type=click.Path(path_type=Path))
@click.option(
    "--engine",
    type=click.Choice(
        ["auto", "us_retirement", "uk_retirement", "us_household_resources"]
    ),
    default="auto",
    show_default=True,
    help="Engine for raw input files. Core envelopes carry their own engine.",
)
@click.option(
    "--country",
    help="Optional country override for raw input files.",
)
@click.option(
    "--output-format",
    type=click.Choice(CORE_OUTPUT_FORMATS),
    default="envelope",
    show_default=True,
    help="JSON shape to emit.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def core_run(
    scenario_file: Path,
    engine: str,
    country: str | None,
    output_format: str,
    output: Path | None,
) -> None:
    """Run a core scenario locally and emit machine-readable JSON.

    SCENARIO_FILE may be a core envelope or raw engine inputs in JSON/YAML.
    Use '-' to read from stdin.
    """
    try:
        data = _read_structured_input(scenario_file)
        scenario = _build_core_scenario(data, engine=engine, country=country)
        core_result = run_core_scenario(scenario)
        payload = _format_core_output(core_result, output_format)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(payload, output)


# === Household Resource Commands ===


@main.group()
def household() -> None:
    """Run and validate household resource scenarios for agents."""
    pass


@household.command("validate")
@click.argument("household_file", type=click.Path(path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def household_validate(household_file: Path, output: Path | None) -> None:
    """Validate partial household intake and return next questions."""
    try:
        data = _read_structured_input(household_file)
        data = dict(data)
        data.pop("name", None)
        data.pop("id", None)
        result = validate_household_payload(data)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(result.model_dump(mode="json"), output)


@household.command("run")
@click.argument("household_file", type=click.Path(path_type=Path))
@click.option(
    "--output-format",
    type=click.Choice(CORE_OUTPUT_FORMATS),
    default="envelope",
    show_default=True,
    help="JSON shape to emit.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def household_run(
    household_file: Path,
    output_format: str,
    output: Path | None,
) -> None:
    """Run annual US household resources and emit JSON."""
    try:
        data = _read_structured_input(household_file)
        data = dict(data)
        data.pop("name", None)
        data.pop("id", None)
        household_input = HouseholdInput.model_validate(data)
        scenario = build_us_household_resources_scenario(household_input)
        core_result = run_core_scenario(scenario)
        payload = _format_core_output(core_result, output_format)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(payload, output)


# === Comparison Commands ===


@main.group()
def compare() -> None:
    """Run deterministic scenario comparisons for tool callers."""
    pass


@compare.command("withdrawal-strategies")
@click.argument("scenario_file", type=click.Path(path_type=Path))
@click.option(
    "--strategy",
    "strategies",
    multiple=True,
    type=click.Choice(WITHDRAWAL_STRATEGY_CHOICES),
    help="Strategy to include. Repeat to compare a subset.",
)
@click.option(
    "--random-seed",
    type=int,
    default=0,
    show_default=True,
    help="Shared seed for all strategy runs.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def compare_withdrawal_strategies_command(
    scenario_file: Path,
    strategies: tuple[str, ...],
    random_seed: int,
    output: Path | None,
) -> None:
    """Compare US holdings withdrawal strategies and emit JSON."""
    try:
        data = _read_structured_input(scenario_file)
        data = dict(data)
        data.pop("name", None)
        data.pop("id", None)
        sim_input = SimulationInput.model_validate(data)
        comparison_kwargs = {
            "base_input": sim_input,
            "random_seed": random_seed,
        }
        if strategies:
            comparison_kwargs["strategies"] = list(strategies)
        comparison = WithdrawalStrategyComparisonInput.model_validate(comparison_kwargs)
        result = compare_withdrawal_strategies(comparison)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(result.model_dump(mode="json"), output)


@compare.command("historical-cohorts")
@click.argument("scenario_file", type=click.Path(path_type=Path))
@click.option(
    "--start-year",
    "start_years",
    multiple=True,
    type=int,
    help="Historical start year to include. Repeat to compare a subset.",
)
@click.option(
    "--stock-index",
    type=click.Choice(STOCK_INDEX_CHOICES),
    default="sp500",
    show_default=True,
    help="Stock index for historical cohorts.",
)
@click.option(
    "--bond-index",
    type=click.Choice(BOND_INDEX_CHOICES),
    default="treasury",
    show_default=True,
    help="Bond index for historical cohorts.",
)
@click.option(
    "--include-mortality",
    is_flag=True,
    help="Include stochastic mortality in cohort outcomes.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def compare_historical_cohorts_command(
    scenario_file: Path,
    start_years: tuple[int, ...],
    stock_index: str,
    bond_index: str,
    include_mortality: bool,
    output: Path | None,
) -> None:
    """Compare US historical market cohorts and emit JSON."""
    try:
        data = _read_structured_input(scenario_file)
        data = dict(data)
        data.pop("name", None)
        data.pop("id", None)
        sim_input = SimulationInput.model_validate(data)
        comparison = HistoricalCohortComparisonInput.model_validate(
            {
                "base_input": sim_input,
                "start_years": list(start_years) if start_years else None,
                "stock_index": stock_index,
                "bond_index": bond_index,
                "include_mortality": include_mortality,
            }
        )
        result = compare_historical_cohorts(comparison)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(result.model_dump(mode="json"), output)


@compare.command("earnings-grid")
@click.argument("household_file", type=click.Path(path_type=Path))
@click.option(
    "--person-index",
    type=int,
    default=0,
    show_default=True,
    help="Person index whose annual employment income varies.",
)
@click.option(
    "--income-min",
    type=float,
    default=0.0,
    show_default=True,
    help="Lowest annual employment income.",
)
@click.option(
    "--income-max",
    type=float,
    default=80_000.0,
    show_default=True,
    help="Highest annual employment income.",
)
@click.option(
    "--step",
    type=float,
    default=1_000.0,
    show_default=True,
    help="Annual employment income increment.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Write JSON to this file instead of stdout.",
)
def compare_earnings_grid_command(
    household_file: Path,
    person_index: int,
    income_min: float,
    income_max: float,
    step: float,
    output: Path | None,
) -> None:
    """Compare US household resources across earned-income levels."""
    try:
        data = _read_structured_input(household_file)
        data = dict(data)
        data.pop("name", None)
        data.pop("id", None)
        household_input = HouseholdInput.model_validate(data)
        grid_input = EarningsGridInput(
            base_input=household_input,
            person_index=person_index,
            income_min=income_min,
            income_max=income_max,
            step=step,
        )
        result = compare_earnings_grid(grid_input)
    except Exception as e:
        raise click.ClickException(str(e)) from e

    _write_json_payload(result.model_dump(mode="json"), output)


# === Simulate Command ===


@main.command()
@click.argument("scenario_file", type=click.Path(path_type=Path), required=False)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for results (JSON)",
)
@click.option(
    "--api-url",
    default="http://localhost:8000",
    help="API URL (default: localhost:8000)",
)
@click.option(
    "--local",
    is_flag=True,
    help="Run the core engine in-process instead of calling the API.",
)
@click.option(
    "--job",
    is_flag=True,
    help="Use the pollable remote /core/jobs API instead of one blocking request.",
)
@click.option(
    "--poll-interval",
    type=float,
    default=1.0,
    show_default=True,
    help="Seconds between remote job status polls.",
)
@click.option(
    "--output-format",
    type=click.Choice(MACHINE_OUTPUT_FORMATS),
    default="summary",
    show_default=True,
    help="Use result or envelope for machine-readable JSON.",
)
@click.pass_context
def simulate(
    ctx: click.Context,
    scenario_file: Path | None,
    output: Path | None,
    api_url: str,
    local: bool,
    job: bool,
    poll_interval: float,
    output_format: str,
) -> None:
    """Run a Monte Carlo simulation on a scenario.

    If no scenario file is provided, uses the first YAML in the scenarios directory.
    """
    import httpx

    scenarios_dir = ctx.obj["scenarios_dir"]
    machine_output = output_format != "summary"
    if local and job:
        raise click.ClickException("Use either --local or --job, not both.")

    # Find scenario file
    if not scenario_file:
        yaml_files = list(scenarios_dir.glob("*.yaml"))
        if not yaml_files:
            raise click.ClickException(
                f"No scenario files found in {scenarios_dir}. "
                "Create a scenario file or run 'eggnest sync pull' to download."
            )
        scenario_file = yaml_files[0]
        if not machine_output:
            console.print(f"[dim]Using scenario: {scenario_file.name}[/dim]")

    # Load scenario
    try:
        data = _read_structured_input(scenario_file)
    except Exception as e:
        raise click.ClickException(f"Could not read scenario: {e}") from e

    # Remove non-simulation fields
    data = dict(data)
    name = data.pop("name", scenario_file.stem)
    data.pop("id", None)

    # Validate with Pydantic
    try:
        scenario = _build_core_scenario(data, engine="us_retirement")
        sim_input = SimulationInput.model_validate(scenario.inputs)
    except Exception as e:
        raise click.ClickException(f"Invalid scenario: {e}") from e

    if not machine_output:
        console.print(f"\n[bold]Running simulation: {name}[/bold]")
        console.print(f"  Capital: ${sim_input.total_capital:,.0f}")
        console.print(f"  Annual spending: ${sim_input.annual_spending:,.0f}")
        console.print(f"  Age: {sim_input.current_age} → {sim_input.max_age}")
        console.print(f"  Simulations: {sim_input.n_simulations:,}")

    try:
        if local:
            core_result = _core_result_dict(run_core_scenario(scenario))
        elif job:
            if machine_output:
                core_result = _run_core_job(api_url, scenario, poll_interval)
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Starting simulation job...", total=None)
                    core_result = _run_core_job(
                        api_url,
                        scenario,
                        poll_interval,
                        progress=progress,
                        task=task,
                    )
                    progress.update(task, description="Done!")
        elif machine_output:
            response = httpx.post(
                f"{api_url}/core/simulate",
                json=scenario.model_dump(),
                timeout=120.0,
            )
            response.raise_for_status()
            core_result = response.json()
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Running Monte Carlo simulation...", total=None
                )
                response = httpx.post(
                    f"{api_url}/core/simulate",
                    json=scenario.model_dump(),
                    timeout=120.0,
                )
                response.raise_for_status()
                core_result = response.json()
                progress.update(task, description="Done!")
    except httpx.ConnectError as e:
        if machine_output:
            raise click.ClickException(f"Could not connect to API at {api_url}") from e
        console.print(f"\n[red]Could not connect to API at {api_url}[/red]")
        console.print(
            "[dim]Start the API with: cd api && uv run uvicorn main:app --port 8000[/dim]"
        )
        sys.exit(1)
    except Exception as e:
        if machine_output:
            raise click.ClickException(f"Simulation failed: {e}") from e
        console.print(f"\n[red]Simulation failed: {e}[/red]")
        sys.exit(1)

    result = core_result["outputs"][OUTPUT_KEY]

    if machine_output:
        _write_json_payload(_format_core_output(core_result, output_format), output)
        return

    # Display results
    console.print("\n")
    console.print(
        Panel(
            f"[bold green]{result['success_rate']*100:.1f}% success rate[/bold green]\n\n"
            f"Median final portfolio: ${result['median_final_value']:,.0f}\n"
            f"Initial withdrawal rate: {result['initial_withdrawal_rate']:.1f}%\n\n"
            f"[dim]Percentiles at end:[/dim]\n"
            f"  5th:  ${result['percentiles']['p5']:,.0f}\n"
            f"  25th: ${result['percentiles']['p25']:,.0f}\n"
            f"  50th: ${result['percentiles']['p50']:,.0f}\n"
            f"  75th: ${result['percentiles']['p75']:,.0f}\n"
            f"  95th: ${result['percentiles']['p95']:,.0f}",
            title=f"[bold]{name}[/bold]",
            border_style="green" if result["success_rate"] > 0.9 else "yellow",
        )
    )

    # Save results if requested
    if output:
        output.write_text(json.dumps(result, indent=2) + "\n")
        console.print(f"\n[dim]Results saved to {output}[/dim]")


# === Init Command ===


@main.command()
@click.argument("name", default="my-retirement")
@click.pass_context
def init(ctx: click.Context, name: str) -> None:
    """Create a new scenario file from a template."""

    scenarios_dir = ctx.obj["scenarios_dir"]
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{name}.yaml"
    filepath = scenarios_dir / filename

    if filepath.exists():
        console.print(f"[yellow]Scenario '{filename}' already exists[/yellow]")
        if not click.confirm("Overwrite?"):
            return

    # Create template (used for reference; actual file uses YAML format below)
    _template = {
        "name": name,
        "initial_capital": 1000000,
        "annual_spending": 60000,
        "current_age": 60,
        "max_age": 95,
        "gender": "male",
        "social_security_monthly": 2500,
        "social_security_start_age": 67,
        "pension_annual": 0,
        "employment_income": 0,
        "retirement_age": 65,
        "state": "CA",
        "filing_status": "single",
        "expected_return": 0.05,
        "return_volatility": 0.16,
        "dividend_yield": 0.02,
        "n_simulations": 10000,
        "include_mortality": True,
        "has_spouse": False,
        "has_annuity": False,
    }

    # Write with comments
    content = f"""# EggNest Scenario: {name}
# Edit this file, then run: eggnest simulate {filename}

name: {name}

# === Your Situation ===
initial_capital: 1000000      # Starting portfolio value
annual_spending: 60000        # Desired annual spending (today's dollars)
current_age: 60               # Your current age
max_age: 95                   # Planning horizon
gender: male                  # For mortality tables: male or female

# === Income Sources ===
social_security_monthly: 2500  # Your monthly SS benefit
social_security_start_age: 67  # When you'll claim (62-70)
pension_annual: 0              # Annual pension income
employment_income: 0           # Current employment income
retirement_age: 65             # When employment income stops

# === Tax Settings ===
state: CA                      # Two-letter state code
filing_status: single          # single, married_filing_jointly, head_of_household

# === Market Assumptions (real returns, after inflation) ===
expected_return: 0.05          # Expected annual return (5%)
return_volatility: 0.16        # Annual volatility (16%)
dividend_yield: 0.02           # Dividend yield (2%)

# === Simulation ===
n_simulations: 10000           # Number of Monte Carlo paths
include_mortality: true        # Account for mortality risk

# === Optional: Spouse ===
has_spouse: false
# spouse:
#   age: 58
#   gender: female
#   social_security_monthly: 2000
#   social_security_start_age: 67

# === Optional: Annuity ===
has_annuity: false
# annuity:
#   monthly_payment: 3000
#   annuity_type: life_with_guarantee
#   guarantee_years: 20
"""

    filepath.write_text(content)
    console.print(f"[green]Created scenario: {filepath}[/green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. Edit the scenario: [cyan]{filepath}[/cyan]")
    console.print(f"  2. Run simulation: [cyan]eggnest simulate {filename}[/cyan]")
    console.print("  3. Save to cloud: [cyan]eggnest sync push[/cyan]")


# === List Command ===


@main.command("list")
@click.pass_context
def list_scenarios(ctx: click.Context) -> None:
    """List all local scenario files."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    sync_client = get_sync_client(scenarios_dir)
    local = sync_client.list_local()

    if local:
        console.print(f"\n[bold]Scenarios in {scenarios_dir}:[/bold]\n")
        for s in local:
            console.print(f"  [cyan]{s['file']}[/cyan] - {s['name']}")
    else:
        console.print(f"[dim]No scenarios found in {scenarios_dir}[/dim]")
        console.print("[dim]Run 'eggnest init' to create one.[/dim]")


if __name__ == "__main__":
    main()
