"""EggNest API - Main FastAPI application."""

import json

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from eggnest.config import get_settings
from eggnest.household import HouseholdCalculator
from eggnest.models import (
    AllocationComparisonResult,
    AllocationInput,
    AllocationResult,
    AnnuityComparison,
    AnnuityComparisonResult,
    HouseholdInput,
    HouseholdResult,
    LifeEventComparison,
    LifeEventComparisonInput,
    MortalityRates,
    SavedSimulation,
    SimulationInput,
    SimulationResult,
    SSTimingComparisonResult,
    SSTimingInput,
    SSTimingResult,
    StateComparisonInput,
    StateComparisonResult,
    StateResult,
)
from eggnest.mortality import calculate_survival_curve, get_mortality_rates
from eggnest.returns import get_historical_stats
from eggnest.simulation import MonteCarloSimulator, compare_to_annuity
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
- **Asset Allocation**: Optimize stock/bond mix for your risk tolerance
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^(http://localhost:\d+|https://[\w-]+\.vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "eggnest-api",
        "version": "0.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.post("/simulate", response_model=SimulationResult)
async def run_simulation(params: SimulationInput):
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

    simulator = MonteCarloSimulator(params)
    return simulator.run()


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


@app.get("/mortality/{gender}", response_model=MortalityRates)
async def get_mortality(gender: str, start_age: int = 65, end_age: int = 100):
    """
    Get mortality rates and survival curve for a given gender.

    Returns annual mortality rates and cumulative survival probability.
    """
    if gender not in ["male", "female"]:
        raise HTTPException(status_code=400, detail="Gender must be 'male' or 'female'")

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
async def compare_annuity_endpoint(comparison: AnnuityComparison):
    """
    Compare a simulation to an annuity option.

    Returns comparison metrics and a recommendation.
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
        recommendation=annuity_comparison["recommendation"],
    )


@app.post("/compare-states", response_model=StateComparisonResult)
async def compare_states_endpoint(comparison: StateComparisonInput):
    """
    Compare simulation outcomes across different states.

    Runs the same simulation for each state and compares tax impact.
    Useful for evaluating relocation decisions.
    """
    base_state = comparison.base_input.state
    all_states = [base_state] + [
        s for s in comparison.compare_states if s != base_state
    ]

    results: list[StateResult] = []
    base_taxes = 0.0

    for state in all_states:
        # Create a copy of input with the new state
        state_input = comparison.base_input.model_copy(update={"state": state})
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
async def compare_ss_timing_endpoint(timing_input: SSTimingInput):
    """
    Compare Social Security claiming strategies at different ages.

    Adjusts benefits for early/delayed claiming and runs simulations
    to compare outcomes. Helps users decide when to claim SS benefits.
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
        sim_input = timing_input.base_input.model_copy(
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

    # Determine optimal claiming ages
    # Highest success rate
    optimal_success = max(results, key=lambda r: r.success_rate)

    # Optimal for longevity (highest total SS income, favors delay)
    optimal_longevity = max(results, key=lambda r: r.total_ss_income_median)

    return SSTimingComparisonResult(
        birth_year=birth_year,
        full_retirement_age=fra,
        pia_monthly=pia_monthly,
        results=results,
        optimal_claiming_age=optimal_success.claiming_age,
        optimal_for_longevity=optimal_longevity.claiming_age,
    )


@app.post("/compare-allocations", response_model=AllocationComparisonResult)
async def compare_allocations_endpoint(allocation_input: AllocationInput):
    """
    Compare simulation outcomes across different asset allocations.

    Runs the same simulation for each stock/bond allocation and compares
    success rates, volatility, and final values. Helps users decide on
    optimal portfolio allocation for their risk tolerance.
    """
    results: list[AllocationResult] = []
    historical_stats = get_historical_stats()

    for stock_alloc in sorted(allocation_input.allocations):
        bond_alloc = 1.0 - stock_alloc

        # Create a copy of input with this allocation
        alloc_input = allocation_input.base_input.model_copy(
            update={"stock_allocation": stock_alloc}
        )
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

    # Find optimal allocations
    # Highest success rate
    optimal_success = max(results, key=lambda r: r.success_rate)

    # Optimal for safety: lowest volatility among allocations with success rate >= 80%
    high_success_results = [r for r in results if r.success_rate >= 0.8]
    if high_success_results:
        optimal_safety = min(high_success_results, key=lambda r: r.volatility)
    else:
        # If no allocation reaches 80%, pick lowest volatility overall
        optimal_safety = min(results, key=lambda r: r.volatility)

    # Generate recommendation
    if optimal_success.success_rate >= 0.9:
        if optimal_success.stock_allocation == optimal_safety.stock_allocation:
            recommendation = f"A {int(optimal_success.stock_allocation * 100)}% stock allocation provides both the highest success rate ({optimal_success.success_rate:.0%}) and acceptable risk."
        else:
            recommendation = f"For maximum success ({optimal_success.success_rate:.0%}), consider {int(optimal_success.stock_allocation * 100)}% stocks. For lower volatility with good success ({optimal_safety.success_rate:.0%}), consider {int(optimal_safety.stock_allocation * 100)}% stocks."
    elif optimal_success.success_rate >= 0.8:
        recommendation = f"A {int(optimal_success.stock_allocation * 100)}% stock allocation achieves {optimal_success.success_rate:.0%} success. Consider increasing savings or reducing spending to improve odds."
    else:
        recommendation = "Success rates are below target across all allocations. Consider increasing savings, reducing spending, or delaying retirement to improve outcomes."

    return AllocationComparisonResult(
        results=results,
        optimal_for_success=optimal_success.stock_allocation,
        optimal_for_safety=optimal_safety.stock_allocation,
        recommendation=recommendation,
    )


# === Household Tax Calculator Endpoints ===


@app.post("/calculate-household", response_model=HouseholdResult)
async def calculate_household_endpoint(household: HouseholdInput):
    """
    Calculate taxes and benefits for a household.

    Supports any household composition: singles, married couples, families with children.
    Returns federal/state taxes, payroll taxes, and benefit amounts (CTC, EITC, etc.).
    """
    calc = HouseholdCalculator()
    return calc.calculate(household)


@app.post("/compare-life-event", response_model=LifeEventComparison)
async def compare_life_event_endpoint(comparison: LifeEventComparisonInput):
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
