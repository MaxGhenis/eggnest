"""Filesystem sync functionality for EggNest CLI.

Syncs scenarios between local YAML files and Supabase.
Enables AI agents to explore and edit financial scenarios as files.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from supabase import Client

from .auth import get_authenticated_client, get_current_user_id, is_logged_in
from .models import AnnuityInput, SpouseInput

logger = logging.getLogger(__name__)

# Default directory for scenarios
DEFAULT_SCENARIOS_DIR = Path.home() / ".eggnest" / "scenarios"


@dataclass
class SyncConfig:
    """Configuration for Supabase sync."""

    supabase_url: str
    supabase_key: str
    scenarios_dir: Path

    @classmethod
    def from_env(cls, scenarios_dir: Path | None = None) -> "SyncConfig":
        """Create config from environment variables."""
        url = os.environ.get("EGGNEST_SUPABASE_URL", "")
        key = os.environ.get("EGGNEST_SUPABASE_ANON_KEY", "")

        if not url or not key:
            raise ValueError(
                "EGGNEST_SUPABASE_URL and EGGNEST_SUPABASE_ANON_KEY are required"
            )

        return cls(
            supabase_url=url,
            supabase_key=key,
            scenarios_dir=scenarios_dir or DEFAULT_SCENARIOS_DIR,
        )


def scenario_to_yaml(scenario: dict[str, Any]) -> str:
    """Convert a scenario dict to YAML with helpful comments."""
    # Extract the input params
    params = scenario.get("input_params", scenario)

    # Build a structured YAML with comments
    yaml_content = f"""# EggNest Scenario: {scenario.get('name', 'Unnamed')}
# Last synced: {datetime.now().isoformat()}
# Edit this file and run 'eggnest sync push' to update

name: {scenario.get('name', 'My Scenario')}

# === Core Parameters ===
initial_capital: {params.get('initial_capital', 1000000)}
annual_spending: {params.get('annual_spending', 60000)}
current_age: {params.get('current_age', 60)}
max_age: {params.get('max_age', 95)}
gender: {params.get('gender', 'male')}

# === Income Sources ===
social_security_monthly: {params.get('social_security_monthly', 0)}
social_security_start_age: {params.get('social_security_start_age', 67)}
pension_annual: {params.get('pension_annual', 0)}
employment_income: {params.get('employment_income', 0)}
employment_growth_rate: {params.get('employment_growth_rate', 0.03)}
retirement_age: {params.get('retirement_age', 65)}

# === Tax Settings ===
state: {params.get('state', 'CA')}
filing_status: {params.get('filing_status', 'single')}

# === Market Assumptions (real returns, after inflation) ===
expected_return: {params.get('expected_return', 0.05)}  # 5% real return
return_volatility: {params.get('return_volatility', 0.16)}  # 16% volatility
dividend_yield: {params.get('dividend_yield', 0.02)}  # 2% dividend yield

# === Simulation Settings ===
n_simulations: {params.get('n_simulations', 10000)}
include_mortality: {params.get('include_mortality', True)}
"""

    # Add spouse section if present
    if params.get("has_spouse") and params.get("spouse"):
        spouse = params["spouse"]
        yaml_content += f"""
# === Spouse ===
has_spouse: true
spouse:
  age: {spouse.get('age', 60)}
  gender: {spouse.get('gender', 'female')}
  social_security_monthly: {spouse.get('social_security_monthly', 0)}
  social_security_start_age: {spouse.get('social_security_start_age', 67)}
  pension_annual: {spouse.get('pension_annual', 0)}
  employment_income: {spouse.get('employment_income', 0)}
  retirement_age: {spouse.get('retirement_age', 65)}
"""
    else:
        yaml_content += "\nhas_spouse: false\n"

    # Add annuity section if present
    if params.get("has_annuity") and params.get("annuity"):
        annuity = params["annuity"]
        yaml_content += f"""
# === Annuity ===
has_annuity: true
annuity:
  monthly_payment: {annuity.get('monthly_payment', 0)}
  annuity_type: {annuity.get('annuity_type', 'life_with_guarantee')}
  guarantee_years: {annuity.get('guarantee_years', 15)}
"""
    else:
        yaml_content += "has_annuity: false\n"

    return yaml_content


def yaml_to_scenario(filepath: Path) -> dict[str, Any]:
    """Parse a YAML scenario file into a scenario dict."""
    with open(filepath) as f:
        data = yaml.safe_load(f)

    # Extract name and build input params
    name = data.pop("name", filepath.stem)

    # Handle spouse
    if data.get("has_spouse") and data.get("spouse"):
        data["spouse"] = SpouseInput(**data["spouse"]).model_dump()

    # Handle annuity
    if data.get("has_annuity") and data.get("annuity"):
        data["annuity"] = AnnuityInput(**data["annuity"]).model_dump()

    return {
        "name": name,
        "input_params": data,
    }


class EggNestSync:
    """Handles syncing between local YAML files and Supabase."""

    def __init__(self, scenarios_dir: Path | None = None):
        self.scenarios_dir = scenarios_dir or DEFAULT_SCENARIOS_DIR
        self.scenarios_dir.mkdir(parents=True, exist_ok=True)
        self.client: Client | None = None

    def _get_client(self) -> Client:
        """Get authenticated Supabase client."""
        if self.client:
            return self.client

        if is_logged_in():
            self.client = get_authenticated_client()
            if self.client:
                return self.client

        raise ValueError("Not logged in. Run 'eggnest auth login' first.")

    def pull(self, scenario_id: str | None = None) -> dict[str, Any]:
        """
        Pull scenarios from Supabase to local YAML files.

        Args:
            scenario_id: Optional specific scenario to pull. If None, pulls all.

        Returns:
            Dict with stats about what was pulled.
        """
        stats = {"scenarios": 0, "files_written": 0}
        client = self._get_client()
        user_id = get_current_user_id()

        if not user_id:
            raise ValueError("Could not get user ID")

        # Fetch scenarios
        query = client.table("saved_simulations").select("*").eq("user_id", user_id)
        if scenario_id:
            query = query.eq("id", scenario_id)

        result = query.execute()
        scenarios = result.data or []

        for scenario in scenarios:
            # Generate filename from name or id
            filename = f"{scenario.get('name', scenario['id'])}.yaml"
            # Sanitize filename
            filename = "".join(
                c if c.isalnum() or c in "._- " else "_" for c in filename
            )
            filepath = self.scenarios_dir / filename

            # Write YAML file
            yaml_content = scenario_to_yaml(scenario)
            filepath.write_text(yaml_content)

            # Also write a hidden .id file to track the scenario ID
            id_file = self.scenarios_dir / f".{filepath.stem}.id"
            id_file.write_text(scenario["id"])

            stats["files_written"] += 1
            stats["scenarios"] += 1
            logger.info(f"Pulled scenario '{scenario.get('name')}' to {filepath}")

        return stats

    def push(self, scenario_file: Path | None = None) -> dict[str, Any]:
        """
        Push local YAML files to Supabase.

        Args:
            scenario_file: Optional specific file to push. If None, pushes all.

        Returns:
            Dict with stats about what was pushed.
        """
        stats = {"scenarios": 0, "errors": []}
        client = self._get_client()
        user_id = get_current_user_id()

        if not user_id:
            raise ValueError("Could not get user ID")

        # Find YAML files
        if scenario_file:
            yaml_files = [scenario_file]
        else:
            yaml_files = list(self.scenarios_dir.glob("*.yaml"))

        for filepath in yaml_files:
            try:
                scenario = yaml_to_scenario(filepath)

                # Check for existing ID
                id_file = self.scenarios_dir / f".{filepath.stem}.id"
                scenario_id = id_file.read_text().strip() if id_file.exists() else None

                # Build record
                record = {
                    "user_id": user_id,
                    "name": scenario["name"],
                    "input_params": scenario["input_params"],
                    "updated_at": datetime.now().isoformat(),
                }

                if scenario_id:
                    record["id"] = scenario_id
                    # Update existing
                    client.table("saved_simulations").update(record).eq(
                        "id", scenario_id
                    ).execute()
                else:
                    # Insert new
                    result = client.table("saved_simulations").insert(record).execute()
                    if result.data:
                        # Save the new ID
                        new_id = result.data[0]["id"]
                        id_file.write_text(new_id)

                stats["scenarios"] += 1
                logger.info(f"Pushed scenario '{scenario['name']}'")

            except Exception as e:
                stats["errors"].append(f"{filepath.name}: {e}")
                logger.error(f"Failed to push {filepath.name}: {e}")

        return stats

    def list_local(self) -> list[dict[str, Any]]:
        """List all local scenario files."""
        scenarios = []
        for filepath in self.scenarios_dir.glob("*.yaml"):
            try:
                with open(filepath) as f:
                    data = yaml.safe_load(f)
                scenarios.append(
                    {
                        "file": filepath.name,
                        "name": data.get("name", filepath.stem),
                        "path": str(filepath),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to read {filepath}: {e}")
        return scenarios

    def list_remote(self) -> list[dict[str, Any]]:
        """List all remote scenarios for the current user."""
        client = self._get_client()
        user_id = get_current_user_id()

        if not user_id:
            return []

        result = (
            client.table("saved_simulations")
            .select("id, name, created_at, updated_at")
            .eq("user_id", user_id)
            .execute()
        )
        return result.data or []


def get_sync_client(scenarios_dir: Path | None = None) -> EggNestSync:
    """Get a configured sync client."""
    return EggNestSync(scenarios_dir)
