"""EggNest API - Main FastAPI application."""

import json

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from eggnest.comparisons import (
    compare_historical_cohorts,
    compare_withdrawal_strategies,
)
from eggnest.config import get_settings
from eggnest.core.schemas import EngineJobStatus, EngineResult, EngineScenario
from eggnest.household import (
    HouseholdCalculator,
    compare_earnings_grid,
    validate_household_payload,
)
from eggnest.models import (
    AllocationComparisonResult,
    AllocationInput,
    AllocationResult,
    AnnuityComparison,
    AnnuityComparisonResult,
    EarningsGridComparisonResult,
    EarningsGridInput,
    HistoricalCohortComparisonInput,
    HistoricalCohortComparisonResult,
    HouseholdInput,
    HouseholdResult,
    HouseholdValidationResult,
    LifeEventComparison,
    LifeEventComparisonInput,
    MortalityRates,
    ProgramSpec,
    SavedSimulation,
    SimulationInput,
    SimulationJobStatus,
    SimulationResult,
    SSTimingComparisonResult,
    SSTimingInput,
    SSTimingResult,
    StateComparisonInput,
    StateComparisonResult,
    StateResult,
    WithdrawalStrategyComparisonInput,
    WithdrawalStrategyComparisonResult,
)
from eggnest.mortality import calculate_survival_curve, get_mortality_rates
from eggnest.programs import list_programs
from eggnest.returns import get_historical_stats
from eggnest.simulation import MonteCarloSimulator, compare_to_annuity
from eggnest.simulation_jobs import CoreJobManager, SimulationJobManager
from eggnest.ss_timing import (
    calculate_adjusted_benefit,
    get_full_retirement_age,
)
from eggnest.supabase_client import (
    delete_simulation,
    get_user_simulations,
    save_simulation,
    verify_jwt,
)

app = FastAPI(
    title="EggNest API",
    description="""
Monte Carlo financial planning simulation API with real tax calculations.

## Features
- **Retirement Simulation**: Run 10,000+ Monte Carlo simulations with mortality-adjusted outcomes
- **Real Tax Calculations**: Federal and state taxes via PolicyEngine-US
- **Social Security Timing**: Compare claiming strategies from age 62-70
- **Asset Allocation**: Compare stock/bond mixes under shared assumptions
- **State Comparison**: Compare tax impact across different states
- **Life Event Analysis**: See how major life changes affect your taxes

## Quick Start
```python
import httpx

response = httpx.post("https://api.eggnest.co/simulate", json={
    "initial_capital": 500000,
    "annual_spending": 40000,
    "current_age": 65,
    "state": "CA"
})
result = response.json()
print(f"Success rate: {result['success_rate']:.1%}")
```
""",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

settings = get_settings()
simulation_jobs = SimulationJobManager(
    max_workers=settings.simulation_job_workers,
    ttl_seconds=settings.simulation_job_ttl_seconds,
    max_records=settings.simulation_job_max_records,
)
core_jobs = CoreJobManager(
    max_workers=settings.simulation_job_workers,
    ttl_seconds=settings.simulation_job_ttl_seconds,
    max_records=settings.simulation_job_max_records,
)


def configure_job_snapshot_store(snapshot_store) -> None:
    """Attach a shared job status store for multi-container deployments."""
    simulation_jobs.set_snapshot_store(snapshot_store, prefix="simulation:")
    core_jobs.set_snapshot_store(snapshot_store, prefix="core:")


def configure_job_external_runners(
    simulation_runner=None,
    core_runner=None,
) -> None:
    """Attach external execution runners for serverless deployments."""
    simulation_jobs.set_external_runner(simulation_runner)
    core_jobs.set_external_runner(core_runner)


# CORS. The regex admits localhost (dev) and this project's Vercel preview
# deployments only — not arbitrary *.vercel.app origins, which anyone can
# create.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^(http://localhost:\d+|https://eggnest[\w-]*\.vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cap_comparison_simulations(params):
    """Bound per-run paths for comparison endpoints that fan out N runs."""
    cap = settings.comparison_max_simulations
    if params.n_simulations <= cap:
        return params
    return params.model_copy(update={"n_simulations": cap})


async def get_current_user(authorization: str | None = Header(None)) -> dict | None:
    """Extract and verify user from Authorization header."""
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    return await verify_jwt(token)


async def require_user(
    user: dict | None = Depends(get_current_user),  # noqa: B008
) -> dict:
    """Require authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "eggnest-api",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health():
    """Render health check endpoint."""
    return {"status": "healthy"}


@app.post("/simulate", response_model=SimulationResult)
def run_simulation(params: SimulationInput):
    """
    Run a Monte Carlo retirement simulation.

    Returns probability distributions of portfolio outcomes.
    """
    # Validate n_simulations
    if params.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    from eggnest.core.us_retirement import (
        extract_us_simulation_result,
        run_us_retirement,
    )

    core_result = run_us_retirement(params)
    return extract_us_simulation_result(core_result)


@app.post("/simulate/stream")
async def run_simulation_stream(params: SimulationInput):
    """
    Run a Monte Carlo simulation with progress streaming via SSE.

    Sends progress events as JSON, then final result.
    """
    if params.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    def generate():
        simulator = MonteCarloSimulator(params)
        for event in simulator.run_with_progress():
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.post("/simulate/jobs", response_model=SimulationJobStatus, status_code=202)
def create_simulation_job(params: SimulationInput):
    """
    Start a simulation in the background and return a pollable job status.

    This is easier for browsers, CLIs, and AI agents to resume than a single
    long-lived HTTP stream.
    """
    if params.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    return simulation_jobs.submit(params)


@app.get("/simulate/jobs/{job_id}", response_model=SimulationJobStatus)
def get_simulation_job(job_id: str):
    """Get the latest status or final result for a background simulation."""
    job = simulation_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Simulation job not found")
    return job


@app.get("/mortality/{gender}", response_model=MortalityRates)
def get_mortality(
    gender: str,
    start_age: int = Query(default=65, ge=0, le=119),
    end_age: int = Query(default=100, ge=0, le=119),
):
    """
    Get mortality rates and survival curve for a given gender.

    Returns annual mortality rates and cumulative survival probability.
    """
    if gender not in ["male", "female"]:
        raise HTTPException(status_code=400, detail="Gender must be 'male' or 'female'")
    if end_age < start_age:
        raise HTTPException(
            status_code=400, detail="end_age must be at least start_age"
        )

    mortality_rates = get_mortality_rates(gender)
    ages = list(range(start_age, end_age + 1))
    rates = [
        mortality_rates.get(
            age, mortality_rates[max(k for k in mortality_rates if k <= age)]
        )
        for age in ages
    ]
    survival = calculate_survival_curve(start_age, end_age + 1, gender)

    return MortalityRates(ages=ages, rates=rates, survival_curve=survival)


@app.post("/compare-annuity", response_model=AnnuityComparisonResult)
def compare_annuity_endpoint(comparison: AnnuityComparison):
    """
    Compare a simulation to an annuity option.

    Returns comparison metrics and a factual summary.
    """
    simulator = MonteCarloSimulator(comparison.simulation_input)
    sim_result = simulator.run()

    n_years = (
        comparison.simulation_input.max_age - comparison.simulation_input.current_age
    )
    annuity_comparison = compare_to_annuity(
        simulation_result=sim_result,
        annuity_monthly_payment=comparison.annuity_monthly_payment,
        annuity_guarantee_years=comparison.annuity_guarantee_years,
        n_years=n_years,
        total_withdrawn=simulator._total_withdrawn,
        total_taxes=simulator._total_taxes,
    )

    return AnnuityComparisonResult(
        simulation_result=sim_result,
        annuity_total_guaranteed=annuity_comparison["annuity_total_guaranteed"],
        probability_simulation_beats_annuity=annuity_comparison[
            "probability_simulation_beats_annuity"
        ],
        simulation_median_total_income=annuity_comparison[
            "simulation_median_total_income"
        ],
        comparison_summary=annuity_comparison["comparison_summary"],
    )


@app.post("/compare-states", response_model=StateComparisonResult)
def compare_states_endpoint(comparison: StateComparisonInput):
    """
    Compare simulation outcomes across different states.

    Runs the same simulation for each state and compares tax impact.
    Useful for comparing state-level tax differences under shared assumptions.
    """
    base_input = _cap_comparison_simulations(comparison.base_input)
    base_state = base_input.state
    all_states = [base_state] + [
        s for s in comparison.compare_states if s != base_state
    ]

    results: list[StateResult] = []
    base_taxes = 0.0

    for state in all_states:
        # Create a copy of input with the new state
        state_input = base_input.model_copy(update={"state": state})
        simulator = MonteCarloSimulator(state_input)
        sim_result = simulator.run()

        net_after_tax = (
            sim_result.total_withdrawn_median - sim_result.total_taxes_median
        )

        result = StateResult(
            state=state,
            success_rate=sim_result.success_rate,
            median_final_value=sim_result.median_final_value,
            total_taxes_median=sim_result.total_taxes_median,
            total_withdrawn_median=sim_result.total_withdrawn_median,
            net_after_tax_median=net_after_tax,
        )
        results.append(result)

        if state == base_state:
            base_taxes = sim_result.total_taxes_median

    # Calculate tax savings vs base state
    tax_savings = {r.state: base_taxes - r.total_taxes_median for r in results}

    return StateComparisonResult(
        base_state=base_state,
        results=results,
        tax_savings_vs_base=tax_savings,
    )


@app.post("/compare-ss-timing", response_model=SSTimingComparisonResult)
def compare_ss_timing_endpoint(timing_input: SSTimingInput):
    """
    Compare Social Security claiming strategies at different ages.

    Adjusts benefits for early/delayed claiming and runs simulations
    to compare modeled outcomes.
    """
    birth_year = timing_input.birth_year
    pia_monthly = timing_input.pia_monthly
    fra = get_full_retirement_age(birth_year)

    results: list[SSTimingResult] = []
    result_62_ss_income = 0.0  # For breakeven calculation

    for claiming_age in sorted(timing_input.claiming_ages):
        # Calculate adjusted benefit for this claiming age
        monthly_benefit = calculate_adjusted_benefit(
            pia_monthly=pia_monthly,
            birth_year=birth_year,
            claiming_age=claiming_age,
        )
        annual_benefit = monthly_benefit * 12
        adjustment_factor = monthly_benefit / pia_monthly

        # Create simulation input with this SS claiming age and benefit
        sim_input = _cap_comparison_simulations(timing_input.base_input).model_copy(
            update={
                "social_security_monthly": monthly_benefit,
                "social_security_start_age": claiming_age,
            }
        )

        # Run simulation
        simulator = MonteCarloSimulator(sim_input)
        sim_result = simulator.run()

        # Calculate total SS income over lifetime (simplified)
        # Years receiving SS = max_age - claiming_age
        years_receiving_ss = max(0, timing_input.base_input.max_age - claiming_age)
        total_ss_income = annual_benefit * years_receiving_ss

        # Calculate breakeven vs 62 (if this isn't age 62)
        breakeven_vs_62 = None
        if claiming_age == 62:
            result_62_ss_income = total_ss_income
        elif claiming_age > 62 and result_62_ss_income > 0:
            # Simplified breakeven: find age where cumulative benefits equal
            benefit_62 = calculate_adjusted_benefit(pia_monthly, birth_year, 62) * 12
            benefit_this = annual_benefit

            # At what age does delaying catch up?
            # Age 62 gets: benefit_62 * (age - 62)
            # This age gets: benefit_this * (age - claiming_age)
            # Solve: benefit_62 * (age - 62) = benefit_this * (age - claiming_age)
            if benefit_this > benefit_62:
                # age * benefit_62 - 62 * benefit_62 = age * benefit_this - claiming_age * benefit_this
                # age * (benefit_62 - benefit_this) = 62 * benefit_62 - claiming_age * benefit_this
                # age = (62 * benefit_62 - claiming_age * benefit_this) / (benefit_62 - benefit_this)
                numerator = 62 * benefit_62 - claiming_age * benefit_this
                denominator = benefit_62 - benefit_this
                if denominator != 0:
                    breakeven_age = numerator / denominator
                    if breakeven_age > claiming_age:
                        breakeven_vs_62 = int(round(breakeven_age))

        result = SSTimingResult(
            claiming_age=claiming_age,
            monthly_benefit=round(monthly_benefit, 2),
            annual_benefit=round(annual_benefit, 2),
            adjustment_factor=round(adjustment_factor, 4),
            success_rate=sim_result.success_rate,
            median_final_value=sim_result.median_final_value,
            total_ss_income_median=round(total_ss_income, 2),
            total_taxes_median=sim_result.total_taxes_median,
            breakeven_vs_62=breakeven_vs_62,
        )
        results.append(result)

    # Identify rows with the highest modeled values.
    highest_success = max(results, key=lambda r: r.success_rate)

    highest_lifetime_income = max(results, key=lambda r: r.total_ss_income_median)

    return SSTimingComparisonResult(
        birth_year=birth_year,
        full_retirement_age=fra,
        pia_monthly=pia_monthly,
        results=results,
        highest_success_claiming_age=highest_success.claiming_age,
        highest_lifetime_income_claiming_age=highest_lifetime_income.claiming_age,
    )


@app.post("/compare-allocations", response_model=AllocationComparisonResult)
def compare_allocations_endpoint(allocation_input: AllocationInput):
    """
    Compare simulation outcomes across different asset allocations.

    Runs the same simulation for each stock/bond allocation and compares
    success rates, volatility, and final values.
    """
    results: list[AllocationResult] = []
    historical_stats = get_historical_stats()

    for stock_alloc in sorted(allocation_input.allocations):
        bond_alloc = 1.0 - stock_alloc

        # Create a copy of input with this allocation
        alloc_input = _cap_comparison_simulations(
            allocation_input.base_input
        ).model_copy(update={"stock_allocation": stock_alloc})
        simulator = MonteCarloSimulator(alloc_input)
        sim_result = simulator.run()

        # Calculate blended expected return and volatility
        expected_return = (
            stock_alloc * historical_stats["stock_mean"]
            + bond_alloc * historical_stats["bond_mean"]
        )
        # Simplified volatility calculation (doesn't account for correlation)
        # A more accurate calculation would use covariance, but this gives a reasonable estimate
        volatility = (
            stock_alloc * historical_stats["stock_std"]
            + bond_alloc * historical_stats["bond_std"]
        )

        result = AllocationResult(
            stock_allocation=stock_alloc,
            bond_allocation=bond_alloc,
            success_rate=sim_result.success_rate,
            median_final_value=sim_result.median_final_value,
            percentile_5_final_value=sim_result.percentiles["p5"],
            percentile_95_final_value=sim_result.percentiles["p95"],
            volatility=round(volatility, 4),
            expected_return=round(expected_return, 4),
        )
        results.append(result)

    # Identify rows with the highest modeled values.
    highest_success = max(results, key=lambda r: r.success_rate)

    # Lowest volatility among allocations with success rate >= 80%.
    high_success_results = [r for r in results if r.success_rate >= 0.8]
    if high_success_results:
        lowest_volatility = min(high_success_results, key=lambda r: r.volatility)
        volatility_basis = "tested allocations with at least 80% modeled success"
    else:
        # If no allocation reaches 80%, report lowest volatility overall.
        lowest_volatility = min(results, key=lambda r: r.volatility)
        volatility_basis = (
            "all tested allocations because none reached 80% modeled success"
        )

    if highest_success.stock_allocation == lowest_volatility.stock_allocation:
        comparison_summary = (
            f"{int(highest_success.stock_allocation * 100)}% stocks has both the "
            f"highest modeled success rate ({highest_success.success_rate:.0%}) "
            f"and the lowest volatility among {volatility_basis}."
        )
    else:
        comparison_summary = (
            f"{int(highest_success.stock_allocation * 100)}% stocks has the highest "
            f"modeled success rate ({highest_success.success_rate:.0%}); "
            f"{int(lowest_volatility.stock_allocation * 100)}% stocks has the lowest "
            f"volatility among {volatility_basis}."
        )

    return AllocationComparisonResult(
        results=results,
        highest_success_allocation=highest_success.stock_allocation,
        lowest_volatility_allocation=lowest_volatility.stock_allocation,
        comparison_summary=comparison_summary,
    )


@app.post(
    "/compare-withdrawal-strategies",
    response_model=WithdrawalStrategyComparisonResult,
)
def compare_withdrawal_strategies_endpoint(
    comparison: WithdrawalStrategyComparisonInput,
):
    """Compare holdings withdrawal orders under shared assumptions."""
    return compare_withdrawal_strategies(comparison)


@app.post(
    "/compare-historical-cohorts",
    response_model=HistoricalCohortComparisonResult,
)
def compare_historical_cohorts_endpoint(
    comparison: HistoricalCohortComparisonInput,
):
    """Compare contiguous historical market cohorts under shared assumptions."""
    return compare_historical_cohorts(comparison)


@app.get("/programs", response_model=list[ProgramSpec])
def list_programs_endpoint(jurisdiction: str | None = None):
    """List agent-callable calculation programs."""
    return list_programs(jurisdiction=jurisdiction)


@app.post("/household/validate", response_model=HouseholdValidationResult)
def validate_household_endpoint(payload: dict):
    """Validate partial household intake and return next questions."""
    return validate_household_payload(payload)


@app.post("/household/resources", response_model=HouseholdResult)
def calculate_household_resources_endpoint(household: HouseholdInput):
    """Calculate annual US household resources."""
    return HouseholdCalculator().calculate(household)


@app.post(
    "/compare-earnings-grid",
    response_model=EarningsGridComparisonResult,
)
def compare_earnings_grid_endpoint(grid_input: EarningsGridInput):
    """Compare annual household resources across earned-income levels."""
    return compare_earnings_grid(grid_input)


# === Household Tax Calculator Endpoints ===


@app.post("/calculate-household", response_model=HouseholdResult)
def calculate_household_endpoint(household: HouseholdInput):
    """
    Calculate taxes and benefits for a household.

    Supports any household composition: singles, married couples, families with children.
    Returns federal/state taxes, payroll taxes, and benefit amounts (CTC, EITC, etc.).
    """
    calc = HouseholdCalculator()
    return calc.calculate(household)


@app.post("/compare-life-event", response_model=LifeEventComparison)
def compare_life_event_endpoint(comparison: LifeEventComparisonInput):
    """
    Compare tax and benefit outcomes before and after a life event.

    Useful for understanding how life changes (having a child, getting married,
    changing income, moving states) affect your taxes and benefits.
    """
    calc = HouseholdCalculator()
    return calc.compare(comparison.before, comparison.after, comparison.event_name)


# === Authenticated endpoints for saved simulations ===


@app.get("/simulations", response_model=list[SavedSimulation])
async def list_simulations(user: dict = Depends(require_user)):  # noqa: B008
    """List all saved simulations for the current user."""
    simulations = await get_user_simulations(user["id"])
    return [
        SavedSimulation(
            id=s["id"],
            user_id=s["user_id"],
            name=s["name"],
            input_params=SimulationInput(**s["input_params"]),
            created_at=s.get("created_at"),
            updated_at=s.get("updated_at"),
        )
        for s in simulations
    ]


@app.post("/simulations", response_model=SavedSimulation)
async def create_simulation(
    simulation: SavedSimulation, user: dict = Depends(require_user)  # noqa: B008
):
    """Save a new simulation configuration."""
    result = await save_simulation(
        user_id=user["id"],
        name=simulation.name,
        input_params=simulation.input_params.model_dump(),
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to save simulation")
    return SavedSimulation(
        id=result["id"],
        user_id=result["user_id"],
        name=result["name"],
        input_params=SimulationInput(**result["input_params"]),
        created_at=result.get("created_at"),
    )


@app.delete("/simulations/{simulation_id}")
async def remove_simulation(
    simulation_id: str, user: dict = Depends(require_user)  # noqa: B008
):
    """Delete a saved simulation."""
    success = await delete_simulation(user["id"], simulation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {"status": "deleted"}


@app.post("/core/simulate", response_model=EngineResult)
def run_core_simulation_endpoint(scenario: EngineScenario):
    """Run a versioned core calculation scenario.

    This is the stable engine-first contract for API, CLI, MCP, and web
    surfaces. Legacy product endpoints can continue returning their existing
    shapes while delegating to this core layer.
    """
    from eggnest.core.router import run_core_scenario
    from eggnest.models import HouseholdInput, SimulationInput
    from eggnest.models_uk import UKSimulationInput

    try:
        if scenario.engine == "us_retirement":
            parsed = SimulationInput.model_validate(scenario.inputs)
        elif scenario.engine == "uk_retirement":
            parsed = UKSimulationInput.model_validate(scenario.inputs)
        elif scenario.engine == "us_household_resources":
            parsed = HouseholdInput.model_validate(scenario.inputs)
        else:
            parsed = None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    if (
        parsed is not None
        and hasattr(parsed, "n_simulations")
        and parsed.n_simulations > settings.max_n_simulations
    ):
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    try:
        return run_core_scenario(scenario)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/core/jobs", response_model=EngineJobStatus, status_code=202)
def create_core_job(scenario: EngineScenario):
    """Start a stable core engine scenario as a background job."""
    from eggnest.models import HouseholdInput, SimulationInput
    from eggnest.models_uk import UKSimulationInput

    try:
        if scenario.engine == "us_retirement":
            parsed = SimulationInput.model_validate(scenario.inputs)
        elif scenario.engine == "uk_retirement":
            parsed = UKSimulationInput.model_validate(scenario.inputs)
        elif scenario.engine == "us_household_resources":
            parsed = HouseholdInput.model_validate(scenario.inputs)
        else:
            parsed = None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc

    if (
        parsed is not None
        and hasattr(parsed, "n_simulations")
        and parsed.n_simulations > settings.max_n_simulations
    ):
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    return core_jobs.submit(scenario)


@app.get("/core/jobs/{job_id}", response_model=EngineJobStatus)
def get_core_job(job_id: str):
    """Get the latest status or final result for a background core engine job."""
    job = core_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Core job not found")
    return job


@app.post("/simulate-uk", response_model=None)
def run_uk_simulation_endpoint(params: dict):
    """Run a UK Monte Carlo retirement simulation (ISA/SIPP/GIA + State Pension).

    UK income tax, NI, and dividend tax are computed per-sim via
    ``policyengine-uk-compiled`` (Rust). Supports stochastic earnings
    (Meghir-Pistaferri style), historical UK asset-return sampling (JST
    Macrohistory 1871-2020), and the UK-specific UFPLS / MPA / LSA rules.
    """
    from eggnest.core.uk_retirement import (
        extract_uk_simulation_result,
        run_uk_retirement,
    )
    from eggnest.models_uk import UKSimulationInput

    parsed = UKSimulationInput.model_validate(params)
    if parsed.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )
    core_result = run_uk_retirement(parsed)
    result = extract_uk_simulation_result(core_result)
    return result.model_dump()


@app.post("/simulate-uk/stream")
async def run_uk_simulation_stream(params: dict):
    """UK simulation with SSE progress streaming."""
    from eggnest.models_uk import UKSimulationInput
    from eggnest.simulation_uk import run_uk_simulation_with_progress

    parsed = UKSimulationInput.model_validate(params)
    if parsed.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    def generate():
        for event in run_uk_simulation_with_progress(parsed):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
