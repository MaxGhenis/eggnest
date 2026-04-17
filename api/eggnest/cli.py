"""Command-line interface for EggNest.

Filesystem-first scenario editing plus direct access to the local modeling engine.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

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
from .engine import describe_engine, get_engine
from .models import (
    HistoricalBacktestInput,
    RothConversionInput,
    RothOptimizationInput,
    SimulationInput,
    StrategyComparisonInput,
)
from .roth_reporting import build_roth_optimization_report_artifact
from .sync import DEFAULT_SCENARIOS_DIR, get_sync_client, yaml_to_scenario

console = Console()
WITHDRAWAL_STRATEGIES = [
    "taxable_first",
    "traditional_first",
    "roth_first",
    "pro_rata",
]
DEFAULT_ROTH_CONVERSION_AMOUNTS = [0.0, 25_000.0, 50_000.0, 100_000.0]
DEFAULT_ROTH_CONVERSION_POLICIES = [
    "fill_standard_deduction",
    "fill_12_percent_bracket",
    "fill_22_percent_bracket",
]
DEFAULT_ROTH_OPTIMIZATION_WINDOW_LENGTHS = [5, 10]


def setup_logging(verbose: bool = False) -> None:
    """Setup logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def _resolve_scenario_file(
    scenario_file: Path | None,
    scenarios_dir: Path,
) -> Path:
    """Resolve an explicit scenario path or default to the first local YAML file."""
    if scenario_file is not None:
        return scenario_file

    yaml_files = list(scenarios_dir.glob("*.yaml"))
    if not yaml_files:
        raise FileNotFoundError(
            f"No scenario files found in {scenarios_dir}. "
            "Create a scenario file or run 'eggnest sync pull' to download."
        )
    chosen = sorted(yaml_files)[0]
    console.print(f"[dim]Using scenario: {chosen.name}[/dim]")
    return chosen


def _load_simulation_input(
    scenario_file: Path | None,
    scenarios_dir: Path,
) -> tuple[Path, str, SimulationInput]:
    """Load and validate one simulation scenario file."""
    resolved = _resolve_scenario_file(scenario_file, scenarios_dir)
    scenario = yaml_to_scenario(resolved)
    name = scenario["name"]

    try:
        sim_input = SimulationInput.model_validate(scenario["input_params"])
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid scenario: {exc}") from exc

    return resolved, name, sim_input


def _jsonable(value: Any) -> Any:
    """Convert Pydantic models or nested structures into JSON-serializable data."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _write_json_output(output: Path | None, payload: Any) -> None:
    """Write a JSON payload to disk when requested."""
    if output is None:
        return
    output.write_text(json.dumps(_jsonable(payload), indent=2))
    console.print(f"\n[dim]Results saved to {output}[/dim]")


def _print_json(payload: Any) -> None:
    """Emit machine-readable JSON to stdout."""
    console.print_json(data=_jsonable(payload))


def _print_simulation_summary(
    name: str,
    sim_input: SimulationInput,
    result: Any,
    *,
    execution_label: str,
) -> None:
    """Render a concise human summary for a simulation result."""
    console.print(f"\n[bold]Running simulation: {name}[/bold]")
    console.print(f"  Capital: ${sim_input.initial_capital or 0:,.0f}")
    console.print(f"  Annual spending: ${sim_input.annual_spending:,.0f}")
    console.print(f"  Age: {sim_input.current_age} → {sim_input.max_age}")
    console.print(f"  Simulations: {sim_input.n_simulations:,}")
    console.print(f"  Engine: {execution_label}")
    console.print("\n")
    console.print(
        Panel(
            f"[bold cyan]{result.success_rate*100:.1f}% success rate[/bold cyan]\n\n"
            f"Median final portfolio: ${result.median_final_value:,.0f}\n"
            f"Median final portfolio (real): ${result.median_final_value_real:,.0f}\n"
            f"Initial withdrawal rate: {result.initial_withdrawal_rate:.1f}%\n"
            f"Median taxes paid: ${result.total_taxes_median:,.0f}\n\n"
            f"[dim]Percentiles at end:[/dim]\n"
            f"  5th:  ${result.percentiles['p5']:,.0f}\n"
            f"  25th: ${result.percentiles['p25']:,.0f}\n"
            f"  50th: ${result.percentiles['p50']:,.0f}\n"
            f"  75th: ${result.percentiles['p75']:,.0f}\n"
            f"  95th: ${result.percentiles['p95']:,.0f}",
            title=f"[bold]{name}[/bold]",
            border_style="cyan",
        )
    )


def _print_backtest_summary(name: str, result: Any) -> None:
    """Render a concise historical backtest summary."""
    console.print(f"\n[bold]Running historical backtest: {name}[/bold]\n")
    console.print(
        Panel(
            f"[bold cyan]{result.success_rate*100:.1f}% historical success[/bold cyan]\n\n"
            f"Cohorts tested: {len(result.start_years)}\n"
            f"Strongest start year: {result.strongest_start_year}\n"
            f"Weakest start year: {result.weakest_start_year}\n"
            f"Median final portfolio: ${result.median_final_value:,.0f}\n"
            f"Median final portfolio (real): ${result.median_final_value_real:,.0f}\n"
            f"Median taxes paid: ${result.total_taxes_median:,.0f}",
            title=f"[bold]{name}[/bold]",
            border_style="cyan",
        )
    )


def _print_strategy_summary(name: str, result: Any) -> None:
    """Render a strategy-comparison scorecard."""
    console.print(f"\n[bold]Comparing withdrawal strategies: {name}[/bold]\n")
    console.print(f"[dim]{result.summary}[/dim]\n")

    table = Table(show_header=True)
    table.add_column("Strategy")
    table.add_column("Score", justify="right")
    table.add_column("MC Success", justify="right")
    table.add_column("Hist Success", justify="right")
    table.add_column("Median Taxes", justify="right")

    for item in result.results:
        table.add_row(
            item.strategy,
            f"{item.blended_score:.1f}",
            f"{item.monte_carlo.success_rate:.1%}",
            f"{item.historical.success_rate:.1%}",
            f"${item.monte_carlo.total_taxes_median:,.0f}",
        )
    console.print(table)


def _format_conversion_amount(amount: float) -> str:
    """Humanize a fixed annual Roth conversion amount."""
    if abs(amount) < 1e-9:
        return "No conversion"
    return f"${amount:,.0f}/yr"


def _print_roth_conversion_summary(name: str, result: Any) -> None:
    """Render a Roth conversion comparison scorecard."""
    console.print(f"\n[bold]Comparing Roth conversion scenarios: {name}[/bold]\n")
    console.print(f"[dim]{result.summary}[/dim]\n")
    if result.baseline_scenario_label:
        console.print(
            f"[dim]Baseline for deltas: {result.baseline_scenario_label}[/dim]\n"
        )
    if hasattr(result, "candidate_count"):
        console.print(
            "[dim]Search space: "
            f"{result.candidate_count} candidates across start ages "
            f"{', '.join(str(age) for age in result.candidate_start_ages)} "
            f"and window lengths "
            f"{', '.join(str(length) for length in result.window_lengths)} years."
            "[/dim]\n"
        )

    table = Table(show_header=True)
    table.add_column("Scenario")
    table.add_column("Score", justify="right")
    table.add_column("MC Success", justify="right")
    table.add_column("Hist Success", justify="right")
    table.add_column("Real Δ", justify="right")
    table.add_column("Tax Δ", justify="right")
    table.add_column("Medicare Δ", justify="right")
    table.add_column("Median Taxes", justify="right")
    table.add_column("Median Converted", justify="right")

    for item in result.results:
        table.add_row(
            item.scenario_label,
            f"{item.blended_score:.1f}",
            f"{item.monte_carlo.success_rate:.1%}",
            f"{item.historical.success_rate:.1%}",
            f"${item.delta_vs_baseline.monte_carlo_median_final_value_real_delta:+,.0f}",
            f"${item.delta_vs_baseline.monte_carlo_total_taxes_median_delta:+,.0f}",
            f"${item.delta_vs_baseline.monte_carlo_total_medicare_premiums_median_delta:+,.0f}",
            f"${item.monte_carlo.total_taxes_median:,.0f}",
            f"${item.monte_carlo.total_roth_conversions_median:,.0f}",
        )
    console.print(table)
    if hasattr(result, "lowest_medicare_premium_scenario_label"):
        console.print(
            "[dim]Lowest Medicare premiums: "
            f"{result.lowest_medicare_premium_scenario_label}. "
            f"Highest real ending wealth: "
            f"{result.highest_real_ending_wealth_scenario_label}.[/dim]\n"
        )

    score_leader = next(
        (
            item
            for item in result.results
            if item.scenario_label == result.top_scoring_scenario_label
        ),
        None,
    )
    if score_leader is None or not score_leader.monte_carlo.year_breakdown:
        return

    ledger_rows = [
        row
        for row in score_leader.monte_carlo.year_breakdown
        if (
            abs(row.roth_conversion) > 1e-9
            or abs(row.medicare_premium_delta_vs_baseline) > 1e-9
            or row.medicare_part_b_irmaa_bracket != "none"
            or row.medicare_part_d_irmaa_bracket != "none"
        )
    ]
    if not ledger_rows:
        return

    console.print(
        f"\n[bold]Representative cliff ledger: {score_leader.scenario_label}[/bold]"
    )
    if result.baseline_scenario_label:
        console.print(
            f"[dim]Medicare deltas are relative to {result.baseline_scenario_label}.[/dim]\n"
        )

    ledger = Table(show_header=True)
    ledger.add_column("Age", justify="right")
    ledger.add_column("Convert", justify="right")
    ledger.add_column("Taxable Δ", justify="right")
    ledger.add_column("Marginal", justify="right")
    ledger.add_column("Part B Band")
    ledger.add_column("Part D Surcharge", justify="right")
    ledger.add_column("Medicare Δ", justify="right")

    for row in ledger_rows:
        ledger.add_row(
            str(row.age),
            f"${row.roth_conversion:,.0f}",
            f"${row.federal_bracket_headroom_used:,.0f}",
            f"{row.federal_marginal_rate_on_last_conversion_dollar:.1%}",
            row.medicare_part_b_irmaa_bracket,
            f"${row.medicare_part_d_premium_surcharge:,.0f}",
            f"${row.medicare_premium_delta_vs_baseline:+,.0f}",
        )
    console.print(ledger)


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
    """EggNest - local retirement and tax modeling engine.

    Your financial scenarios as local YAML files. Edit with any tool.
    Use the local engine directly via CLI, Python, or MCP.

    \b
    Quick start:
      eggnest init                     # Create a scenario file
      eggnest simulate                 # Run locally
      eggnest backtest                 # Replay historical cohorts
      eggnest compare-strategies       # Compare withdrawal strategies
      eggnest compare-roth-conversions # Compare fixed Roth conversion amounts
      eggnest optimize-roth-conversions # Search Roth windows and sizing rules
      eggnest mcp                      # Run a local MCP server
    """
    setup_logging(verbose)

    ctx.ensure_object(dict)
    ctx.obj["scenarios_dir"] = scenarios_dir or DEFAULT_SCENARIOS_DIR
    ctx.obj["verbose"] = verbose


@main.group()
@click.pass_context
def auth(ctx: click.Context) -> None:
    """Manage authentication (login, logout, status)."""
    del ctx


@auth.command()
@click.pass_context
def login(ctx: click.Context) -> None:
    """Login to EggNest via browser (OAuth device flow)."""
    del ctx
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
    del ctx
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
    del ctx
    if is_logged_in():
        user = get_current_user()
        console.print(f"[green]Logged in as {user}[/green]")
    else:
        console.print("[yellow]Not logged in[/yellow]")
        console.print("[dim]Run 'eggnest auth login' to authenticate[/dim]")


@main.group()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Sync scenarios with cloud (pull, push, status)."""
    del ctx


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
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Pull failed: {exc}[/red]")
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
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Push failed: {exc}[/red]")
            sys.exit(1)


@sync.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show sync status and list scenarios."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    sync_client = get_sync_client(scenarios_dir)
    local = sync_client.list_local()

    console.print(f"\n[bold]Local scenarios ({scenarios_dir}):[/bold]")
    if local:
        table = Table(show_header=True)
        table.add_column("Name")
        table.add_column("File")
        for scenario in local:
            table.add_row(scenario["name"], scenario["file"])
        console.print(table)
    else:
        console.print(
            "  [dim]No local scenarios. Run 'eggnest sync pull' to download.[/dim]"
        )

    if is_logged_in():
        try:
            remote = sync_client.list_remote()
            console.print("\n[bold]Cloud scenarios:[/bold]")
            if remote:
                table = Table(show_header=True)
                table.add_column("Name")
                table.add_column("ID")
                table.add_column("Updated")
                for scenario in remote:
                    table.add_row(
                        scenario.get("name", "Unnamed"),
                        scenario["id"][:8] + "...",
                        scenario.get("updated_at", "")[:10],
                    )
                console.print(table)
            else:
                console.print("  [dim]No saved scenarios in cloud.[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [yellow]Could not fetch remote: {exc}[/yellow]")
    else:
        console.print("\n[dim]Login to see cloud scenarios: eggnest auth login[/dim]")


@main.command()
@click.argument(
    "scenario_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for full JSON results",
)
@click.option(
    "--api-url",
    default=None,
    help="Optional remote API URL. If omitted, runs through the local engine.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"], case_sensitive=False),
    default="summary",
    show_default=True,
    help="Render a human summary or emit raw JSON to stdout.",
)
@click.pass_context
def simulate(
    ctx: click.Context,
    scenario_file: Path | None,
    output: Path | None,
    api_url: str | None,
    output_format: str,
) -> None:
    """Run a Monte Carlo simulation on a scenario."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    try:
        _, name, sim_input = _load_simulation_input(scenario_file, scenarios_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    if api_url:
        import httpx

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running remote simulation...", total=None)
            try:
                response = httpx.post(
                    f"{api_url}/simulate",
                    json=sim_input.model_dump(mode="json"),
                    timeout=120.0,
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.ConnectError:
                console.print(f"\n[red]Could not connect to API at {api_url}[/red]")
                sys.exit(1)
            except Exception as exc:  # noqa: BLE001
                console.print(f"\n[red]Simulation failed: {exc}[/red]")
                sys.exit(1)
            progress.update(task, description="Done!")

        _write_json_output(output, payload)
        if output_format == "json":
            _print_json(payload)
        else:
            _print_simulation_summary(
                name,
                sim_input,
                SimpleNamespace(**payload),
                execution_label=f"remote API ({api_url})",
            )
        return

    engine = get_engine()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running local simulation...", total=None)
        try:
            result = engine.simulate(sim_input)
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Simulation failed: {exc}[/red]")
            sys.exit(1)
        progress.update(task, description="Done!")

    _write_json_output(output, result)
    if output_format == "json":
        _print_json(result)
    else:
        _print_simulation_summary(name, sim_input, result, execution_label="local engine")


@main.command()
@click.argument(
    "scenario_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--start-year",
    "start_years",
    type=int,
    multiple=True,
    help="Specific historical start year to include. Repeat for multiple years.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for full JSON results",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"], case_sensitive=False),
    default="summary",
    show_default=True,
)
@click.pass_context
def backtest(
    ctx: click.Context,
    scenario_file: Path | None,
    start_years: tuple[int, ...],
    output: Path | None,
    output_format: str,
) -> None:
    """Replay the current plan across historical return cohorts."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    try:
        _, name, sim_input = _load_simulation_input(scenario_file, scenarios_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    request = HistoricalBacktestInput(
        base_input=sim_input,
        start_years=list(start_years) or None,
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running historical backtest...", total=None)
        try:
            result = get_engine().historical_backtest(request)
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Historical backtest failed: {exc}[/red]")
            sys.exit(1)
        progress.update(task, description="Done!")

    _write_json_output(output, result)
    if output_format == "json":
        _print_json(result)
    else:
        _print_backtest_summary(name, result)


@main.command("compare-strategies")
@click.argument(
    "scenario_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--strategy",
    "strategies",
    multiple=True,
    type=click.Choice(WITHDRAWAL_STRATEGIES, case_sensitive=False),
    help="Withdrawal strategy to include. Repeat for multiple strategies.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for full JSON results",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"], case_sensitive=False),
    default="summary",
    show_default=True,
)
@click.pass_context
def compare_strategies(
    ctx: click.Context,
    scenario_file: Path | None,
    strategies: tuple[str, ...],
    output: Path | None,
    output_format: str,
) -> None:
    """Compare withdrawal strategies using Monte Carlo and historical replay."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    try:
        _, name, sim_input = _load_simulation_input(scenario_file, scenarios_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    request = StrategyComparisonInput(
        base_input=sim_input,
        strategies=list(strategies) or WITHDRAWAL_STRATEGIES,
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Comparing strategy scenarios...", total=None)
        try:
            result = get_engine().compare_withdrawal_strategies(request)
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Strategy comparison failed: {exc}[/red]")
            sys.exit(1)
        progress.update(task, description="Done!")

    _write_json_output(output, result)
    if output_format == "json":
        _print_json(result)
    else:
        _print_strategy_summary(name, result)


@main.command("compare-roth-conversions")
@click.argument(
    "scenario_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--annual-amount",
    "annual_amounts",
    multiple=True,
    type=float,
    help="Annual Roth conversion amount to include. Repeat for multiple values.",
)
@click.option(
    "--policy",
    "conversion_policies",
    multiple=True,
    type=click.Choice(
        [
            "fill_standard_deduction",
            "fill_12_percent_bracket",
            "fill_22_percent_bracket",
        ],
        case_sensitive=False,
    ),
    help="Dynamic Roth conversion policy to include. Repeat for multiple policies.",
)
@click.option(
    "--start-age",
    type=int,
    default=None,
    help="Age when conversions start. Defaults to current age.",
)
@click.option(
    "--end-age",
    type=int,
    default=None,
    help="Age when conversions stop. Defaults to age 72 before RMDs begin, otherwise max_age.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for full JSON results",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json"], case_sensitive=False),
    default="summary",
    show_default=True,
)
@click.pass_context
def compare_roth_conversions(
    ctx: click.Context,
    scenario_file: Path | None,
    annual_amounts: tuple[float, ...],
    conversion_policies: tuple[str, ...],
    start_age: int | None,
    end_age: int | None,
    output: Path | None,
    output_format: str,
) -> None:
    """Compare fixed and bracket-fill Roth conversion scenarios on one plan."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    try:
        _, name, sim_input = _load_simulation_input(scenario_file, scenarios_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    request = RothConversionInput(
        base_input=sim_input,
        annual_conversion_amounts=list(annual_amounts)
        or DEFAULT_ROTH_CONVERSION_AMOUNTS,
        conversion_policies=list(conversion_policies)
        or DEFAULT_ROTH_CONVERSION_POLICIES,
        conversion_start_age=start_age,
        conversion_end_age=end_age,
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Comparing Roth conversion scenarios...", total=None)
        try:
            result = get_engine().compare_roth_conversions(request)
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Roth conversion comparison failed: {exc}[/red]")
            sys.exit(1)
        progress.update(task, description="Done!")

    _write_json_output(output, result)
    if output_format == "json":
        _print_json(result)
    else:
        _print_roth_conversion_summary(name, result)


@main.command("optimize-roth-conversions")
@click.argument(
    "scenario_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--annual-amount",
    "annual_amounts",
    multiple=True,
    type=float,
    help="Fixed annual Roth conversion amount to include in the search. Repeat for multiple values.",
)
@click.option(
    "--policy",
    "conversion_policies",
    multiple=True,
    type=click.Choice(
        [
            "fill_standard_deduction",
            "fill_12_percent_bracket",
            "fill_22_percent_bracket",
        ],
        case_sensitive=False,
    ),
    help="Dynamic Roth conversion policy to include in the search. Repeat for multiple policies.",
)
@click.option(
    "--candidate-start-age",
    "candidate_start_ages",
    multiple=True,
    type=int,
    help="Candidate age when conversions can start. Repeat for multiple ages.",
)
@click.option(
    "--window-length",
    "window_lengths",
    multiple=True,
    type=int,
    help="Candidate conversion-window length in years. Repeat for multiple lengths.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for full JSON results",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["summary", "json", "report-json"], case_sensitive=False),
    default="summary",
    show_default=True,
)
@click.pass_context
def optimize_roth_conversions(
    ctx: click.Context,
    scenario_file: Path | None,
    annual_amounts: tuple[float, ...],
    conversion_policies: tuple[str, ...],
    candidate_start_ages: tuple[int, ...],
    window_lengths: tuple[int, ...],
    output: Path | None,
    output_format: str,
) -> None:
    """Search bounded Roth conversion windows and sizing rules on one plan."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    try:
        _, name, sim_input = _load_simulation_input(scenario_file, scenarios_dir)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]{exc}[/red]")
        sys.exit(1)

    request = RothOptimizationInput(
        base_input=sim_input,
        annual_conversion_amounts=list(annual_amounts)
        or DEFAULT_ROTH_CONVERSION_AMOUNTS,
        conversion_policies=list(conversion_policies)
        or DEFAULT_ROTH_CONVERSION_POLICIES,
        candidate_start_ages=list(candidate_start_ages) or None,
        window_lengths=list(window_lengths)
        or DEFAULT_ROTH_OPTIMIZATION_WINDOW_LENGTHS,
    )
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Searching Roth conversion scenarios...", total=None)
        try:
            result = get_engine().optimize_roth_conversions(request)
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Roth conversion optimization failed: {exc}[/red]")
            sys.exit(1)
        progress.update(task, description="Done!")

    _write_json_output(output, result)
    if output_format == "json":
        _print_json(result)
    elif output_format == "report-json":
        _print_json(build_roth_optimization_report_artifact(result))
    else:
        _print_roth_conversion_summary(name, result)


@main.command("engine-info")
def engine_info() -> None:
    """Describe the local engine surface for Python, CLI, and MCP users."""
    _print_json(describe_engine())


@main.command("mcp")
def mcp() -> None:
    """Run EggNest as a local stdio MCP server."""
    from .mcp_server import main as run_mcp_server

    run_mcp_server()


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

    content = f"""# EggNest Scenario: {name}
# Edit this file, then run: eggnest simulate {filename}

name: {name}

# === Your Situation ===
initial_capital: 1000000
annual_spending: 60000
current_age: 60
max_age: 95
gender: male

# === Income Sources ===
social_security_monthly: 2500
social_security_start_age: 67
pension_annual: 0
employment_income: 0
retirement_age: 65

# === Tax Settings ===
state: CA
filing_status: single

# === Market Assumptions ===
expected_return: 0.05
return_volatility: 0.16
dividend_yield: 0.02

# === Simulation ===
n_simulations: 10000
include_mortality: true

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
    console.print(f"  3. Replay history: [cyan]eggnest backtest {filename}[/cyan]")
    console.print("  4. Save to cloud: [cyan]eggnest sync push[/cyan]")


@main.command("list")
@click.pass_context
def list_scenarios(ctx: click.Context) -> None:
    """List all local scenario files."""
    scenarios_dir = ctx.obj["scenarios_dir"]

    sync_client = get_sync_client(scenarios_dir)
    local = sync_client.list_local()

    if local:
        console.print(f"\n[bold]Scenarios in {scenarios_dir}:[/bold]\n")
        for scenario in local:
            console.print(f"  [cyan]{scenario['file']}[/cyan] - {scenario['name']}")
    else:
        console.print(f"[dim]No scenarios found in {scenarios_dir}[/dim]")
        console.print("[dim]Run 'eggnest init' to create one.[/dim]")


if __name__ == "__main__":
    main()
