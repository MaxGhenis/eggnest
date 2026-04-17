"""EggNest API - Main FastAPI application."""

import asyncio
import atexit
import hashlib
import json
from collections import OrderedDict
from concurrent.futures import ProcessPoolExecutor

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from eggnest.backtest import run_historical_backtest
from eggnest.compensation import analyze_compensation, list_market_benchmarks
from eggnest.config import get_settings
from eggnest.engine import get_engine
from eggnest.household import HouseholdCalculator
from eggnest.models import (
    AllocationComparisonResult,
    AllocationInput,
    AllocationResult,
    AnnuityComparison,
    AnnuityComparisonResult,
    CompensationAnalysisInput,
    CompensationAnalysisResult,
    CompensationBenchmark,
    HistoricalBacktestInput,
    HistoricalBacktestResult,
    HistoricalStrategySummary,
    HouseholdInput,
    HouseholdResult,
    LifeEventComparison,
    LifeEventComparisonInput,
    MortalityRates,
    RothOptimizationInput,
    RothOptimizationResult,
    SavedSimulation,
    SimulationInput,
    SimulationResult,
    SSTimingComparisonResult,
    SSTimingInput,
    SSTimingResult,
    StateComparisonInput,
    StateComparisonResult,
    StateResult,
    StrategyComparisonInput,
    StrategyComparisonItem,
    StrategyComparisonResult,
    StrategyScenarioSummary,
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
COMPARISON_SIMULATION_PARALLELISM = 4
SIMULATION_SUMMARY_CACHE_SIZE = 128
_simulation_process_pool: ProcessPoolExecutor | None = None
_simulation_summary_cache: OrderedDict[
    str, dict[str, float | dict[str, float]]
] = OrderedDict()
_historical_backtest_summary_cache: OrderedDict[str, dict[str, float | int]] = (
    OrderedDict()
)

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


def _run_simulation_summary(
    params_payload: dict,
) -> dict[str, float | dict[str, float]]:
    """Run a single simulation scenario and return the fields comparison endpoints need."""
    params = SimulationInput.model_validate(params_payload)
    result = MonteCarloSimulator(params).run()
    return {
        "success_rate": result.success_rate,
        "median_final_value": result.median_final_value,
        "median_final_value_real": result.median_final_value_real,
        "total_taxes_median": result.total_taxes_median,
        "total_withdrawn_median": result.total_withdrawn_median,
        "percentiles": result.percentiles,
    }


def _run_historical_backtest_summary(params_payload: dict) -> dict[str, float | int]:
    """Run one historical backtest scenario and return comparison fields."""
    params = SimulationInput.model_validate(params_payload)
    result = run_historical_backtest(params)
    worst_cohort = min(
        result.results,
        key=lambda cohort: (cohort.final_value_real, cohort.start_year),
    )
    return {
        "success_rate": result.success_rate,
        "median_final_value": result.median_final_value,
        "median_final_value_real": result.median_final_value_real,
        "total_taxes_median": result.total_taxes_median,
        "total_withdrawn_median": result.total_withdrawn_median,
        "cohort_count": len(result.start_years),
        "strongest_start_year": result.strongest_start_year,
        "weakest_start_year": result.weakest_start_year,
        "worst_final_value_real": worst_cohort.final_value_real,
    }


def _derive_comparison_seed(namespace: str, payload: dict) -> int:
    """Generate a stable seed for comparison scenarios when the caller did not supply one."""
    digest = hashlib.sha256(
        json.dumps({"namespace": namespace, "payload": payload}, sort_keys=True).encode(
            "utf-8"
        )
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _resolve_comparison_seed(
    base_input: SimulationInput, *, namespace: str, payload: dict
) -> int:
    """Use the caller-provided seed when present, otherwise derive a stable comparison seed."""
    if base_input.random_seed is not None:
        return base_input.random_seed
    return _derive_comparison_seed(namespace, payload)


def _simulation_cache_key(params: SimulationInput) -> str:
    """Serialize a simulation input for summary-result caching."""
    return json.dumps(params.model_dump(mode="json"), sort_keys=True)


def _get_cached_simulation_summary(
    cache_key: str,
) -> dict[str, float | dict[str, float]] | None:
    """Fetch a cached comparison summary and refresh its LRU position."""
    cached = _simulation_summary_cache.get(cache_key)
    if cached is not None:
        _simulation_summary_cache.move_to_end(cache_key)
    return cached


def _store_cached_simulation_summary(
    cache_key: str, summary: dict[str, float | dict[str, float]]
) -> None:
    """Store a comparison summary in the bounded LRU cache."""
    _simulation_summary_cache[cache_key] = summary
    _simulation_summary_cache.move_to_end(cache_key)
    while len(_simulation_summary_cache) > SIMULATION_SUMMARY_CACHE_SIZE:
        _simulation_summary_cache.popitem(last=False)


def _get_cached_historical_backtest_summary(
    cache_key: str,
) -> dict[str, float | int] | None:
    """Fetch a cached historical backtest summary and refresh its LRU position."""
    cached = _historical_backtest_summary_cache.get(cache_key)
    if cached is not None:
        _historical_backtest_summary_cache.move_to_end(cache_key)
    return cached


def _store_cached_historical_backtest_summary(
    cache_key: str, summary: dict[str, float | int]
) -> None:
    """Store a historical backtest summary in the bounded LRU cache."""
    _historical_backtest_summary_cache[cache_key] = summary
    _historical_backtest_summary_cache.move_to_end(cache_key)
    while len(_historical_backtest_summary_cache) > SIMULATION_SUMMARY_CACHE_SIZE:
        _historical_backtest_summary_cache.popitem(last=False)


def _get_simulation_process_pool() -> ProcessPoolExecutor:
    """Create the comparison process pool lazily in the main process only."""
    global _simulation_process_pool
    if _simulation_process_pool is None:
        _simulation_process_pool = ProcessPoolExecutor(
            max_workers=COMPARISON_SIMULATION_PARALLELISM
        )
    return _simulation_process_pool


def _shutdown_simulation_process_pool() -> None:
    """Release comparison worker processes on shutdown."""
    global _simulation_process_pool
    if _simulation_process_pool is not None:
        _simulation_process_pool.shutdown(cancel_futures=True)
        _simulation_process_pool = None


async def _run_simulation_batch(
    inputs: list[SimulationInput],
) -> list[dict[str, float | dict[str, float]]]:
    """Run comparison scenarios with bounded concurrency."""
    if not inputs:
        return []
    results: list[dict[str, float | dict[str, float]] | None] = [None] * len(inputs)
    missing_positions: list[int] = []
    missing_keys: list[str] = []
    missing_payloads: list[dict] = []

    for index, params in enumerate(inputs):
        cache_key = _simulation_cache_key(params)
        cached = _get_cached_simulation_summary(cache_key)
        if cached is not None:
            results[index] = cached
            continue
        missing_positions.append(index)
        missing_keys.append(cache_key)
        missing_payloads.append(params.model_dump(mode="python"))

    if not missing_payloads:
        return [result for result in results if result is not None]

    if len(missing_payloads) == 1:
        computed_summaries = [_run_simulation_summary(missing_payloads[0])]
    else:
        loop = asyncio.get_running_loop()
        process_pool = _get_simulation_process_pool()
        computed_summaries = await asyncio.gather(
            *(
                loop.run_in_executor(process_pool, _run_simulation_summary, payload)
                for payload in missing_payloads
            )
        )

    for index, cache_key, summary in zip(
        missing_positions, missing_keys, computed_summaries, strict=True
    ):
        _store_cached_simulation_summary(cache_key, summary)
        results[index] = summary

    return [result for result in results if result is not None]


async def _run_historical_backtest_batch(
    inputs: list[SimulationInput],
) -> list[dict[str, float | int]]:
    """Run historical comparison scenarios with bounded concurrency."""
    if not inputs:
        return []
    results: list[dict[str, float | int] | None] = [None] * len(inputs)
    missing_positions: list[int] = []
    missing_keys: list[str] = []
    missing_payloads: list[dict] = []

    for index, params in enumerate(inputs):
        cache_key = _simulation_cache_key(params)
        cached = _get_cached_historical_backtest_summary(cache_key)
        if cached is not None:
            results[index] = cached
            continue
        missing_positions.append(index)
        missing_keys.append(cache_key)
        missing_payloads.append(params.model_dump(mode="python"))

    if not missing_payloads:
        return [result for result in results if result is not None]

    if len(missing_payloads) == 1:
        computed_summaries = [_run_historical_backtest_summary(missing_payloads[0])]
    else:
        loop = asyncio.get_running_loop()
        process_pool = _get_simulation_process_pool()
        computed_summaries = await asyncio.gather(
            *(
                loop.run_in_executor(
                    process_pool, _run_historical_backtest_summary, payload
                )
                for payload in missing_payloads
            )
        )

    for index, cache_key, summary in zip(
        missing_positions, missing_keys, computed_summaries, strict=True
    ):
        _store_cached_historical_backtest_summary(cache_key, summary)
        results[index] = summary

    return [result for result in results if result is not None]


def _normalize_metric(values: list[float], *, higher_is_better: bool) -> list[float]:
    """Scale a metric into 0-1 scores for blended ranking."""
    if not values:
        return []
    lower = min(values)
    upper = max(values)
    if abs(upper - lower) < 1e-12:
        return [0.5] * len(values)
    if higher_is_better:
        return [(value - lower) / (upper - lower) for value in values]
    return [(upper - value) / (upper - lower) for value in values]


def _strategy_label(strategy: str) -> str:
    """Humanize a withdrawal strategy enum."""
    return strategy.replace("_", " ").title()


atexit.register(_shutdown_simulation_process_pool)


def _run_roth_optimization(payload: dict) -> dict:
    """Run Roth optimization off the request thread and return JSON-safe data."""
    return get_engine().optimize_roth_conversions(payload).model_dump(mode="json")


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


@app.get("/compensation/benchmarks", response_model=list[CompensationBenchmark])
async def get_compensation_benchmarks():
    """List benchmark rows available for employer-side package analysis."""
    return list_market_benchmarks()


@app.post("/compensation/analyze", response_model=list[CompensationAnalysisResult])
async def analyze_compensation_endpoint(input_data: CompensationAnalysisInput):
    """
    Analyze employer packages against market benchmarks and after-tax employee value.

    Returns market position, employer cost, and employee-side net-resources estimates.
    """
    return analyze_compensation(input_data)


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


@app.post("/backtest/historical", response_model=HistoricalBacktestResult)
async def run_historical_backtest_endpoint(input_data: HistoricalBacktestInput):
    """
    Replay the current simulation engine over exact historical return cohorts.

    Mortality is disabled so each cohort is deterministic and directly comparable.
    """
    return run_historical_backtest(input_data)


@app.post("/simulate-uk", response_model=None)
async def run_uk_simulation_endpoint(params: dict):
    """Run a UK Monte Carlo retirement simulation (ISA/SIPP/GIA + State Pension)."""
    from eggnest.models_uk import UKSimulationInput
    from eggnest.simulation_uk import run_uk_simulation

    parsed = UKSimulationInput.model_validate(params)
    if parsed.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )
    result = run_uk_simulation(parsed)
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

    Returns comparison metrics and a neutral summary.
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
        total_medicare_premiums=getattr(simulator, "_total_medicare_premiums", None),
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
        summary=annuity_comparison["summary"],
    )


@app.post(
    "/compare-withdrawal-strategies", response_model=StrategyComparisonResult
)
async def compare_withdrawal_strategies_endpoint(
    comparison: StrategyComparisonInput,
):
    """
    Compare tax-aware withdrawal strategies on the same household assumptions.

    Runs both Monte Carlo and deterministic historical cohort replay for each
    strategy, then ranks them on success, resilience, and tax efficiency.
    """
    if not comparison.base_input.holdings:
        raise HTTPException(
            status_code=400,
            detail=(
                "Withdrawal strategy comparison requires detailed holdings. "
                "Add account-level holdings first."
            ),
        )

    strategies = list(dict.fromkeys(comparison.strategies))
    comparison_seed = _resolve_comparison_seed(
        comparison.base_input,
        namespace="compare-withdrawal-strategies",
        payload={
            "base_input": comparison.base_input.model_dump(mode="json"),
            "strategies": strategies,
        },
    )

    strategy_inputs = [
        comparison.base_input.model_copy(
            update={"withdrawal_strategy": strategy, "random_seed": comparison_seed}
        )
        for strategy in strategies
    ]
    monte_carlo_summaries = await _run_simulation_batch(strategy_inputs)
    historical_summaries = await _run_historical_backtest_batch(strategy_inputs)

    mc_success_scores = _normalize_metric(
        [float(summary["success_rate"]) for summary in monte_carlo_summaries],
        higher_is_better=True,
    )
    historical_success_scores = _normalize_metric(
        [float(summary["success_rate"]) for summary in historical_summaries],
        higher_is_better=True,
    )
    worst_cohort_scores = _normalize_metric(
        [float(summary["worst_final_value_real"]) for summary in historical_summaries],
        higher_is_better=True,
    )
    mc_real_wealth_scores = _normalize_metric(
        [float(summary["median_final_value_real"]) for summary in monte_carlo_summaries],
        higher_is_better=True,
    )
    tax_efficiency_scores = _normalize_metric(
        [float(summary["total_taxes_median"]) for summary in monte_carlo_summaries],
        higher_is_better=False,
    )

    strategy_results: list[StrategyComparisonItem] = []
    for index, (strategy, monte_carlo, historical) in enumerate(
        zip(strategies, monte_carlo_summaries, historical_summaries, strict=True)
    ):
        blended_score = round(
            100
            * (
                mc_success_scores[index] * 0.35
                + historical_success_scores[index] * 0.35
                + worst_cohort_scores[index] * 0.15
                + mc_real_wealth_scores[index] * 0.10
                + tax_efficiency_scores[index] * 0.05
            ),
            1,
        )
        strategy_results.append(
            StrategyComparisonItem(
                strategy=strategy,
                monte_carlo=StrategyScenarioSummary(
                    success_rate=monte_carlo["success_rate"],
                    median_final_value=monte_carlo["median_final_value"],
                    median_final_value_real=monte_carlo["median_final_value_real"],
                    total_taxes_median=monte_carlo["total_taxes_median"],
                    total_withdrawn_median=monte_carlo["total_withdrawn_median"],
                ),
                historical=HistoricalStrategySummary(
                    success_rate=historical["success_rate"],
                    median_final_value=historical["median_final_value"],
                    median_final_value_real=historical["median_final_value_real"],
                    total_taxes_median=historical["total_taxes_median"],
                    total_withdrawn_median=historical["total_withdrawn_median"],
                    cohort_count=historical["cohort_count"],
                    strongest_start_year=historical["strongest_start_year"],
                    weakest_start_year=historical["weakest_start_year"],
                    worst_final_value_real=historical["worst_final_value_real"],
                ),
                blended_score=blended_score,
            )
        )

    top_scoring = max(
        strategy_results,
        key=lambda result: (
            result.blended_score,
            result.historical.success_rate,
            result.monte_carlo.success_rate,
            result.historical.worst_final_value_real,
        ),
    )
    lowest_modeled_tax = min(
        strategy_results,
        key=lambda result: (
            result.monte_carlo.total_taxes_median,
            -result.monte_carlo.success_rate,
        ),
    )
    strongest_historical = max(
        strategy_results,
        key=lambda result: (
            result.historical.success_rate,
            result.historical.worst_final_value_real,
            result.historical.median_final_value_real,
        ),
    )

    top_scoring_label = _strategy_label(top_scoring.strategy)
    summary_parts = [
        f"{top_scoring_label} leads this scorecard after weighting Monte Carlo success at 35%, historical success at 35%, weakest historical cohort at 15%, median real ending wealth at 10%, and lower modeled taxes at 5%."
    ]
    if lowest_modeled_tax.strategy != top_scoring.strategy:
        summary_parts.append(
            f"{_strategy_label(lowest_modeled_tax.strategy)} posts the lowest modeled median taxes."
        )
    if strongest_historical.strategy != top_scoring.strategy:
        summary_parts.append(
            f"{_strategy_label(strongest_historical.strategy)} leads on historical resilience."
        )

    strategy_results.sort(key=lambda result: result.blended_score, reverse=True)

    return StrategyComparisonResult(
        results=strategy_results,
        top_scoring_strategy=top_scoring.strategy,
        lowest_modeled_tax_strategy=lowest_modeled_tax.strategy,
        strongest_historical_strategy=strongest_historical.strategy,
        summary=" ".join(summary_parts),
    )


@app.post("/optimize-roth-conversions", response_model=RothOptimizationResult)
async def optimize_roth_conversions_endpoint(
    optimization: RothOptimizationInput,
):
    """
    Search bounded Roth conversion windows and sizing rules on one plan.

    Returns a scored scenario set along with tax, Medicare, and real-wealth
    leaders so clients can inspect modeled trade-offs without hand-picking
    every candidate scenario up front.
    """
    if optimization.base_input.n_simulations > settings.max_n_simulations:
        raise HTTPException(
            status_code=400,
            detail=f"n_simulations cannot exceed {settings.max_n_simulations}",
        )

    try:
        result = await asyncio.to_thread(
            _run_roth_optimization,
            optimization.model_dump(mode="python"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RothOptimizationResult.model_validate(result)


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
    comparison_seed = _resolve_comparison_seed(
        comparison.base_input,
        namespace="compare-states",
        payload={
            "base_input": comparison.base_input.model_dump(mode="json"),
            "states": all_states,
        },
    )
    state_inputs = [
        comparison.base_input.model_copy(
            update={"state": state, "random_seed": comparison_seed}
        )
        for state in all_states
    ]
    sim_results = await _run_simulation_batch(state_inputs)

    results: list[StateResult] = []
    base_taxes = 0.0

    for state, sim_result in zip(all_states, sim_results, strict=True):
        net_after_tax = (
            sim_result["total_withdrawn_median"] - sim_result["total_taxes_median"]
        )

        result = StateResult(
            state=state,
            success_rate=sim_result["success_rate"],
            median_final_value=sim_result["median_final_value"],
            total_taxes_median=sim_result["total_taxes_median"],
            total_withdrawn_median=sim_result["total_withdrawn_median"],
            net_after_tax_median=net_after_tax,
        )
        results.append(result)

        if state == base_state:
            base_taxes = sim_result["total_taxes_median"]

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
    to compare outcomes under the same household assumptions.
    """
    birth_year = timing_input.birth_year
    pia_monthly = timing_input.pia_monthly
    fra = get_full_retirement_age(birth_year)
    comparison_seed = _resolve_comparison_seed(
        timing_input.base_input,
        namespace="compare-ss-timing",
        payload={
            "base_input": timing_input.base_input.model_dump(mode="json"),
            "birth_year": birth_year,
            "pia_monthly": pia_monthly,
            "claiming_ages": sorted(timing_input.claiming_ages),
        },
    )

    claim_inputs: list[tuple[int, float, float, float, SimulationInput]] = []
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
                "random_seed": comparison_seed,
            }
        )
        claim_inputs.append(
            (
                claiming_age,
                monthly_benefit,
                annual_benefit,
                adjustment_factor,
                sim_input,
            )
        )

    sim_results = await _run_simulation_batch(
        [sim_input for *_, sim_input in claim_inputs]
    )

    results: list[SSTimingResult] = []
    for (
        claiming_age,
        monthly_benefit,
        annual_benefit,
        adjustment_factor,
        _sim_input,
    ), sim_result in zip(claim_inputs, sim_results, strict=True):
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
            success_rate=sim_result["success_rate"],
            median_final_value=sim_result["median_final_value"],
            total_ss_income_median=round(total_ss_income, 2),
            total_taxes_median=sim_result["total_taxes_median"],
            breakeven_vs_62=breakeven_vs_62,
        )
        results.append(result)

    # Determine summary claiming ages
    highest_success = max(results, key=lambda r: r.success_rate)

    # Highest lifetime SS income, which tends to favor delay
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
async def compare_allocations_endpoint(allocation_input: AllocationInput):
    """
    Compare simulation outcomes across different asset allocations.

    Runs the same simulation for each stock/bond allocation and compares
    success rates, volatility, and final values. Helps users decide on
    a portfolio mix under the modeled trade-offs.
    """
    results: list[AllocationResult] = []
    historical_stats = get_historical_stats()
    allocations = sorted(allocation_input.allocations)
    comparison_seed = _resolve_comparison_seed(
        allocation_input.base_input,
        namespace="compare-allocations",
        payload={
            "base_input": allocation_input.base_input.model_dump(mode="json"),
            "allocations": allocations,
        },
    )
    alloc_inputs = [
        allocation_input.base_input.model_copy(
            update={"stock_allocation": stock_alloc, "random_seed": comparison_seed}
        )
        for stock_alloc in allocations
    ]
    sim_results = await _run_simulation_batch(alloc_inputs)

    for stock_alloc, sim_result in zip(allocations, sim_results, strict=True):
        bond_alloc = 1.0 - stock_alloc

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
            success_rate=sim_result["success_rate"],
            median_final_value=sim_result["median_final_value"],
            percentile_5_final_value=sim_result["percentiles"]["p5"],
            percentile_95_final_value=sim_result["percentiles"]["p95"],
            volatility=round(volatility, 4),
            expected_return=round(expected_return, 4),
        )
        results.append(result)

    # Identify comparison leaders
    # Highest success rate
    highest_success = max(results, key=lambda r: r.success_rate)

    # Highest safety: lowest volatility among allocations with success rate >= 80%
    high_success_results = [r for r in results if r.success_rate >= 0.8]
    if high_success_results:
        highest_safety = min(high_success_results, key=lambda r: r.volatility)
    else:
        # If no allocation reaches 80%, pick lowest volatility overall
        highest_safety = min(results, key=lambda r: r.volatility)

    # Generate neutral summary
    if highest_success.success_rate >= 0.9:
        if highest_success.stock_allocation == highest_safety.stock_allocation:
            summary = f"{int(highest_success.stock_allocation * 100)}% stocks delivers both the highest modeled success rate ({highest_success.success_rate:.0%}) and the strongest safety profile in this comparison set."
        else:
            summary = f"{int(highest_success.stock_allocation * 100)}% stocks delivers the highest modeled success ({highest_success.success_rate:.0%}), while {int(highest_safety.stock_allocation * 100)}% stocks shows the lowest volatility among the stronger outcomes."
    elif highest_success.success_rate >= 0.8:
        summary = f"{int(highest_success.stock_allocation * 100)}% stocks produces the highest modeled success rate in this comparison set at {highest_success.success_rate:.0%}."
    else:
        summary = "All tested allocations produce lower modeled success rates in this comparison set."

    return AllocationComparisonResult(
        results=results,
        highest_success_allocation=highest_success.stock_allocation,
        highest_safety_allocation=highest_safety.stock_allocation,
        summary=summary,
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
