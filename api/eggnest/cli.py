"""Command-line interface for EggNest.

Filesystem-first financial planning. AI agents can explore your scenarios.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

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
from .models import SimulationInput
from .sync import get_sync_client, DEFAULT_SCENARIOS_DIR

# Setup rich console
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Setup logging with rich handler."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--scenarios-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help=f"Scenarios directory (default: {DEFAULT_SCENARIOS_DIR})",
)
@click.pass_context
def main(ctx: click.Context, verbose: bool, scenarios_dir: Optional[Path]) -> None:
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
def pull(ctx: click.Context, scenario: Optional[str]) -> None:
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
@click.option("--file", "-f", type=click.Path(exists=True, path_type=Path), help="Specific file to push")
@click.pass_context
def push(ctx: click.Context, file: Optional[Path]) -> None:
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
        console.print("  [dim]No local scenarios. Run 'eggnest sync pull' to download.[/dim]")

    # Remote scenarios (if logged in)
    if is_logged_in():
        try:
            remote = sync_client.list_remote()
            console.print(f"\n[bold]Cloud scenarios:[/bold]")
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


# === Simulate Command ===


@main.command()
@click.argument("scenario_file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output file for results (JSON)")
@click.option("--api-url", default="http://localhost:8000", help="API URL (default: localhost:8000)")
@click.pass_context
def simulate(
    ctx: click.Context,
    scenario_file: Optional[Path],
    output: Optional[Path],
    api_url: str,
) -> None:
    """Run a Monte Carlo simulation on a scenario.

    If no scenario file is provided, uses the first YAML in the scenarios directory.
    """
    import httpx
    import yaml

    scenarios_dir = ctx.obj["scenarios_dir"]

    # Find scenario file
    if not scenario_file:
        yaml_files = list(scenarios_dir.glob("*.yaml"))
        if not yaml_files:
            console.print(
                f"[red]No scenario files found in {scenarios_dir}[/red]\n"
                "Create a scenario file or run 'eggnest sync pull' to download."
            )
            sys.exit(1)
        scenario_file = yaml_files[0]
        console.print(f"[dim]Using scenario: {scenario_file.name}[/dim]")

    # Load scenario
    with open(scenario_file) as f:
        data = yaml.safe_load(f)

    # Remove non-simulation fields
    name = data.pop("name", scenario_file.stem)
    data.pop("id", None)

    # Validate with Pydantic
    try:
        sim_input = SimulationInput(**data)
    except Exception as e:
        console.print(f"[red]Invalid scenario: {e}[/red]")
        sys.exit(1)

    console.print(f"\n[bold]Running simulation: {name}[/bold]")
    console.print(f"  Capital: ${sim_input.initial_capital:,.0f}")
    console.print(f"  Annual spending: ${sim_input.annual_spending:,.0f}")
    console.print(f"  Age: {sim_input.current_age} → {sim_input.max_age}")
    console.print(f"  Simulations: {sim_input.n_simulations:,}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running Monte Carlo simulation...", total=None)

        try:
            response = httpx.post(
                f"{api_url}/simulate",
                json=sim_input.model_dump(),
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()
        except httpx.ConnectError:
            console.print(f"\n[red]Could not connect to API at {api_url}[/red]")
            console.print("[dim]Start the API with: cd api && uv run uvicorn main:app --port 8000[/dim]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]Simulation failed: {e}[/red]")
            sys.exit(1)

        progress.update(task, description="Done!")

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
        output.write_text(json.dumps(result, indent=2))
        console.print(f"\n[dim]Results saved to {output}[/dim]")


# === Init Command ===


@main.command()
@click.argument("name", default="my-retirement")
@click.pass_context
def init(ctx: click.Context, name: str) -> None:
    """Create a new scenario file from a template."""
    import yaml

    scenarios_dir = ctx.obj["scenarios_dir"]
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{name}.yaml"
    filepath = scenarios_dir / filename

    if filepath.exists():
        console.print(f"[yellow]Scenario '{filename}' already exists[/yellow]")
        if not click.confirm("Overwrite?"):
            return

    # Create template
    template = {
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
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. Edit the scenario: [cyan]{filepath}[/cyan]")
    console.print(f"  2. Run simulation: [cyan]eggnest simulate {filename}[/cyan]")
    console.print(f"  3. Save to cloud: [cyan]eggnest sync push[/cyan]")


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
