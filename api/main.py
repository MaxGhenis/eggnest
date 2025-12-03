"""FinSim API - Main FastAPI application."""

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from finsim.config import get_settings
from finsim.models import (
    AnnuityComparison,
    AnnuityComparisonResult,
    MortalityRates,
    SavedSimulation,
    SimulationInput,
    SimulationResult,
)
from finsim.simulation import MonteCarloSimulator, compare_to_annuity
from finsim.mortality import get_mortality_rates, calculate_survival_curve
from finsim.supabase_client import (
    delete_simulation,
    get_user_simulations,
    save_simulation,
    verify_jwt,
)

app = FastAPI(
    title="FinSim API",
    description="Retirement and financial planning simulation API",
    version="0.1.0",
)

settings = get_settings()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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


async def require_user(user: dict | None = Depends(get_current_user)) -> dict:
    """Require authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "finsim-api", "version": "0.1.0"}


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
    rates = [mortality_rates.get(age, mortality_rates[max(k for k in mortality_rates if k <= age)]) for age in ages]
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

    n_years = comparison.simulation_input.max_age - comparison.simulation_input.current_age
    annuity_comparison = compare_to_annuity(
        simulation_result=sim_result,
        annuity_monthly_payment=comparison.annuity_monthly_payment,
        annuity_guarantee_years=comparison.annuity_guarantee_years,
        n_years=n_years,
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


# === Authenticated endpoints for saved simulations ===


@app.get("/simulations", response_model=list[SavedSimulation])
async def list_simulations(user: dict = Depends(require_user)):
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
    simulation: SavedSimulation, user: dict = Depends(require_user)
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
async def remove_simulation(simulation_id: str, user: dict = Depends(require_user)):
    """Delete a saved simulation."""
    success = await delete_simulation(user["id"], simulation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {"status": "deleted"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
