"""
Computed results for the EggNest methodology paper.

This module provides a single source of truth for all numerical values
cited in the paper. Run this module to regenerate values or import `r`
for access to precomputed results.
"""

import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Add the API module to path
api_path = Path(__file__).parent.parent / "api"
sys.path.insert(0, str(api_path))
RESULTS_PATH = Path(__file__).with_name("eggnest_results.json")
DOCS_RESULTS_REGENERATE_COMMAND = (
    "cd api && EGGNEST_REGENERATE_RESULTS=1 uv run python ../docs/eggnest_results.py"
)
DEFAULT_DOCS_SIMULATIONS = 100
DEFAULT_DOCS_SEED = 20_260_321
STRATEGY_KEYS = (
    "taxable_first",
    "traditional_first",
    "roth_first",
    "pro_rata",
)


@dataclass
class ReferenceCase:
    """Reference case individual for baseline comparisons."""
    age: int = 55
    retirement_age: int = 65
    max_age: int = 95
    gender: str = "male"
    state: str = "CA"
    filing_status: str = "single"

    # Portfolio
    initial_capital: int = 1_000_000
    traditional_401k: int = 600_000
    roth_ira: int = 200_000
    taxable: int = 200_000
    taxable_cost_basis: int = 0

    # Income
    annual_spending: int = 50_000
    social_security_monthly: int = 2_500
    social_security_start_age: int = 67

    @property
    def description(self) -> str:
        return f"{self.age}-year-old {self.gender} in {self.state}"

    @property
    def portfolio_description(self) -> str:
        return (f"${self.initial_capital:,} total "
                f"(${self.traditional_401k:,} traditional 401k, "
                f"${self.roth_ira:,} Roth IRA, "
                f"${self.taxable:,} taxable)")


@dataclass
class SimulationResult:
    """Results from a simulation run."""
    strategy: str
    success_rate: float
    median_final: float
    total_taxes_median: float
    p5_final: float
    p95_final: float
    median_final_real: float = 0

    @property
    def success_pct(self) -> str:
        return f"{self.success_rate * 100:.1f}%"

    @property
    def median_final_fmt(self) -> str:
        return f"${self.median_final:,.0f}"

    @property
    def median_final_real_fmt(self) -> str:
        return f"${self.median_final_real:,.0f}"

    @property
    def taxes_fmt(self) -> str:
        return f"${self.total_taxes_median:,.0f}"


@dataclass
class StrategyComparison:
    """Comparison of withdrawal strategies."""
    taxable_first: SimulationResult = None
    traditional_first: SimulationResult = None
    roth_first: SimulationResult = None
    pro_rata: SimulationResult = None

    @property
    def best_success(self) -> str:
        strategies = [self.taxable_first, self.traditional_first,
                     self.roth_first, self.pro_rata]
        best = max(strategies, key=lambda x: x.success_rate if x else 0)
        return best.strategy if best else "N/A"

    @property
    def tax_savings_traditional_vs_taxable(self) -> str:
        if self.taxable_first and self.traditional_first:
            diff = self.taxable_first.total_taxes_median - self.traditional_first.total_taxes_median
            return f"${diff:,.0f}"
        return "N/A"


@dataclass
class TaxBracketInflation:
    """Demonstrates bracket inflation over time."""
    income: int = 100_000
    tax_2025: float = 0
    tax_2035: float = 0
    tax_2045: float = 0

    @property
    def reduction_2045(self) -> str:
        if self.tax_2025 > 0:
            pct = (self.tax_2025 - self.tax_2045) / self.tax_2025 * 100
            return f"{pct:.0f}%"
        return "N/A"


@dataclass
class RMDExample:
    """RMD calculation example."""
    age: int = 75
    traditional_balance: int = 300_000
    divisor: float = 24.6
    rmd_amount: float = 0

    @property
    def rmd_fmt(self) -> str:
        return f"${self.rmd_amount:,.0f}"

    @property
    def calculation(self) -> str:
        return f"${self.traditional_balance:,} ÷ {self.divisor} = ${self.rmd_amount:,.0f}"


@dataclass
class MortalitySummary:
    """Mortality table summary statistics."""
    male_life_expectancy_65: float = 0
    female_life_expectancy_65: float = 0
    male_prob_survive_85: float = 0
    female_prob_survive_85: float = 0

    @property
    def male_le_fmt(self) -> str:
        return f"{self.male_life_expectancy_65:.1f} years"

    @property
    def female_le_fmt(self) -> str:
        return f"{self.female_life_expectancy_65:.1f} years"


@dataclass
class Results:
    """All computed results for the paper."""
    reference: ReferenceCase = field(default_factory=ReferenceCase)
    strategies: StrategyComparison = field(default_factory=StrategyComparison)
    bracket_inflation: TaxBracketInflation = field(default_factory=TaxBracketInflation)
    rmd_example: RMDExample = field(default_factory=RMDExample)
    mortality: MortalitySummary = field(default_factory=MortalitySummary)

    # Simulation parameters
    n_simulations: int = DEFAULT_DOCS_SIMULATIONS
    random_seed: int = DEFAULT_DOCS_SEED

    # Historical return assumptions
    stock_mean_return: float = 0.07
    stock_std: float = 0.18
    bond_mean_return: float = 0.03
    bond_std: float = 0.06

    @property
    def stock_return_fmt(self) -> str:
        return f"{self.stock_mean_return * 100:.0f}%"

    @property
    def bond_return_fmt(self) -> str:
        return f"{self.bond_mean_return * 100:.0f}%"


def _simulation_result_from_dict(data: dict | None) -> SimulationResult | None:
    """Hydrate a SimulationResult from a persisted dict."""
    return SimulationResult(**data) if data is not None else None


def results_from_dict(data: dict) -> Results:
    """Hydrate Results dataclasses from a persisted JSON artifact."""
    strategies_data = data.get("strategies", {})
    return Results(
        reference=ReferenceCase(**data["reference"]),
        strategies=StrategyComparison(
            taxable_first=_simulation_result_from_dict(
                strategies_data.get("taxable_first")
            ),
            traditional_first=_simulation_result_from_dict(
                strategies_data.get("traditional_first")
            ),
            roth_first=_simulation_result_from_dict(strategies_data.get("roth_first")),
            pro_rata=_simulation_result_from_dict(strategies_data.get("pro_rata")),
        ),
        bracket_inflation=TaxBracketInflation(**data["bracket_inflation"]),
        rmd_example=RMDExample(**data["rmd_example"]),
        mortality=MortalitySummary(**data["mortality"]),
        n_simulations=data.get("n_simulations", DEFAULT_DOCS_SIMULATIONS),
        random_seed=data.get("random_seed", DEFAULT_DOCS_SEED),
        stock_mean_return=data.get("stock_mean_return", 0.07),
        stock_std=data.get("stock_std", 0.18),
        bond_mean_return=data.get("bond_mean_return", 0.03),
        bond_std=data.get("bond_std", 0.06),
    )


def save_results(results: Results, path: Path = RESULTS_PATH) -> None:
    """Persist results to a JSON artifact for reproducible docs builds."""
    path.write_text(json.dumps(asdict(results), indent=2) + "\n")


def load_results(path: Path = RESULTS_PATH) -> Results:
    """Load persisted results from disk."""
    return results_from_dict(json.loads(path.read_text()))


def _resolve_docs_worker_count() -> int:
    """Return the process count to use for strategy generation."""
    configured = int(os.getenv("EGGNEST_DOCS_MAX_WORKERS", os.cpu_count() or 1))
    return max(1, min(len(STRATEGY_KEYS), configured))


def _compute_strategy_result(
    strategy: str,
    reference_data: dict,
    n_simulations: int,
    random_seed: int,
) -> tuple[str, SimulationResult]:
    """Compute a single strategy result in an isolated worker."""
    from eggnest.models import Holding, SimulationInput
    from eggnest.simulation import MonteCarloSimulator

    ref = ReferenceCase(**reference_data)
    holdings = [
        Holding(
            account_type="traditional_401k",
            fund="sp500",
            balance=ref.traditional_401k,
        ),
        Holding(account_type="roth_ira", fund="sp500", balance=ref.roth_ira),
        Holding(
            account_type="taxable",
            fund="treasury",
            balance=ref.taxable,
            cost_basis=ref.taxable_cost_basis,
        ),
    ]

    params = SimulationInput(
        holdings=holdings,
        withdrawal_strategy=strategy,
        annual_spending=ref.annual_spending,
        current_age=ref.age,
        retirement_age=ref.retirement_age,
        max_age=ref.max_age,
        gender=ref.gender,
        state=ref.state,
        filing_status=ref.filing_status,
        social_security_monthly=ref.social_security_monthly,
        social_security_start_age=ref.social_security_start_age,
        n_simulations=n_simulations,
        random_seed=random_seed,
    )

    result = MonteCarloSimulator(params).run()
    return (
        strategy,
        SimulationResult(
            strategy=strategy.replace("_", " ").title(),
            success_rate=result.success_rate,
            median_final=result.median_final_value,
            median_final_real=result.median_final_value_real,
            total_taxes_median=result.total_taxes_median,
            p5_final=result.percentile_paths["p5"][-1],
            p95_final=result.percentile_paths["p95"][-1],
        ),
    )


def _compute_strategy_results(r: Results) -> StrategyComparison:
    """Compute the reference-case strategy comparison."""
    reference_data = asdict(r.reference)
    strategy_results: dict[str, SimulationResult] = {}
    worker_count = _resolve_docs_worker_count()

    if worker_count == 1:
        for index, strategy in enumerate(STRATEGY_KEYS):
            name, result = _compute_strategy_result(
                strategy,
                reference_data,
                r.n_simulations,
                r.random_seed + index,
            )
            strategy_results[name] = result
    else:
        previous_autoload = os.environ.get("EGGNEST_SKIP_RESULTS_AUTOLOAD")
        os.environ["EGGNEST_SKIP_RESULTS_AUTOLOAD"] = "1"
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        _compute_strategy_result,
                        strategy,
                        reference_data,
                        r.n_simulations,
                        r.random_seed + index,
                    ): strategy
                    for index, strategy in enumerate(STRATEGY_KEYS)
                }
                for future in as_completed(futures):
                    name, result = future.result()
                    strategy_results[name] = result
        finally:
            if previous_autoload is None:
                os.environ.pop("EGGNEST_SKIP_RESULTS_AUTOLOAD", None)
            else:
                os.environ["EGGNEST_SKIP_RESULTS_AUTOLOAD"] = previous_autoload

    return StrategyComparison(
        taxable_first=strategy_results.get("taxable_first"),
        traditional_first=strategy_results.get("traditional_first"),
        roth_first=strategy_results.get("roth_first"),
        pro_rata=strategy_results.get("pro_rata"),
    )


def compute_results() -> Results:
    """Compute all results for the paper."""
    r = Results()
    allow_placeholders = os.getenv("EGGNEST_ALLOW_PLACEHOLDERS") == "1"
    r.n_simulations = max(
        100, int(os.getenv("EGGNEST_DOCS_N_SIMULATIONS", r.n_simulations))
    )
    r.random_seed = int(os.getenv("EGGNEST_DOCS_SEED", r.random_seed))

    try:
        from policyengine_us import Simulation

        from eggnest.rmd import UNIFORM_LIFETIME_TABLE

        r.strategies = _compute_strategy_results(r)

        # Tax bracket inflation
        income = 100_000
        for year in [2025, 2035, 2045]:
            sim = Simulation(
                situation={
                    "people": {"person": {"age": {year: 65}, "employment_income": {year: income}}},
                    "tax_units": {"tax_unit": {"members": ["person"]}},
                    "households": {"household": {"members": ["person"], "state_code": {year: "CA"}}},
                }
            )
            fed_tax = float(sim.calculate("income_tax", year)[0])
            state_tax = float(sim.calculate("ca_income_tax", year)[0])
            total = fed_tax + state_tax

            if year == 2025:
                r.bracket_inflation.tax_2025 = total
            elif year == 2035:
                r.bracket_inflation.tax_2035 = total
            else:
                r.bracket_inflation.tax_2045 = total

        r.bracket_inflation.income = income

        # RMD example
        r.rmd_example.age = 75
        r.rmd_example.traditional_balance = 300_000
        r.rmd_example.divisor = UNIFORM_LIFETIME_TABLE[75]
        r.rmd_example.rmd_amount = r.rmd_example.traditional_balance / r.rmd_example.divisor

        # Mortality (hardcoded from SSA tables)
        r.mortality.male_life_expectancy_65 = 18.2
        r.mortality.female_life_expectancy_65 = 20.8
        r.mortality.male_prob_survive_85 = 0.45
        r.mortality.female_prob_survive_85 = 0.58

    except ImportError as e:
        if not allow_placeholders:
            raise RuntimeError(
                "Could not import the EggNest API dependencies needed to "
                "compute documentation results. Run from the project environment "
                "or set EGGNEST_ALLOW_PLACEHOLDERS=1 to opt into placeholder values."
            ) from e

        print(f"Warning: Could not import simulation modules: {e}")
        print("Using placeholder values because EGGNEST_ALLOW_PLACEHOLDERS=1")

        # Placeholder values for when modules aren't available
        r.strategies = StrategyComparison(
            taxable_first=SimulationResult("Taxable First", 0.82, 450000, 85000, 0, 1500000),
            traditional_first=SimulationResult("Traditional First", 0.78, 380000, 95000, 0, 1400000),
            roth_first=SimulationResult("Roth First", 0.75, 520000, 45000, 0, 1600000),
            pro_rata=SimulationResult("Pro Rata", 0.80, 420000, 75000, 0, 1450000),
        )
        r.bracket_inflation = TaxBracketInflation(100000, 16950, 15140, 11919)
        r.rmd_example = RMDExample(75, 300000, 24.6, 12195)
        r.mortality = MortalitySummary(18.2, 20.8, 0.45, 0.58)

    return r


def load_or_compute_results(path: Path = RESULTS_PATH) -> Results:
    """Load the checked-in artifact or require explicit regeneration."""
    force_regenerate = os.getenv("EGGNEST_REGENERATE_RESULTS") == "1"
    override_generation_settings = any(
        name in os.environ for name in ("EGGNEST_DOCS_N_SIMULATIONS", "EGGNEST_DOCS_SEED")
    )

    if path.exists() and not force_regenerate and not override_generation_settings:
        return load_results(path)

    if not force_regenerate:
        raise RuntimeError(
            f"Missing documentation results artifact at {path}. "
            "Regenerate it explicitly from the API environment with: "
            f"`{DOCS_RESULTS_REGENERATE_COMMAND}`"
        )

    results = compute_results()
    save_results(results, path)
    return results


# Singleton instance for import
if os.getenv("EGGNEST_SKIP_RESULTS_AUTOLOAD") == "1" or __name__ == "__main__":
    r = None
else:
    r = load_or_compute_results()


if __name__ == "__main__":
    r = compute_results()
    save_results(r)

    print("EggNest Paper Results")
    print("=" * 50)
    print(f"\nWrote artifact: {RESULTS_PATH}")
    print(f"Simulations: {r.n_simulations}")
    print(f"Seed: {r.random_seed}")
    print(f"\nReference Case: {r.reference.description}")
    print(f"Portfolio: {r.reference.portfolio_description}")
    print("\nWithdrawal Strategies:")
    for name, result in [("Taxable First", r.strategies.taxable_first),
                        ("Traditional First", r.strategies.traditional_first),
                        ("Roth First", r.strategies.roth_first),
                        ("Pro Rata", r.strategies.pro_rata)]:
        if result:
            print(
                f"  {name}: {result.success_pct} success, "
                f"{result.median_final_fmt} nominal median, "
                f"{result.median_final_real_fmt} real median, "
                f"{result.taxes_fmt} taxes"
            )

    print(f"\nTax Bracket Inflation (${r.bracket_inflation.income:,} income):")
    print(f"  2025: ${r.bracket_inflation.tax_2025:,.0f}")
    print(f"  2035: ${r.bracket_inflation.tax_2035:,.0f}")
    print(f"  2045: ${r.bracket_inflation.tax_2045:,.0f}")
    print(f"  Reduction by 2045: {r.bracket_inflation.reduction_2045}")

    print(f"\nRMD Example: {r.rmd_example.calculation}")
