"""Core calculation engine boundary for EggNest.

The core package is intentionally UI/API/auth-free. Product surfaces should
call these stable scenario/result contracts instead of importing simulator
modules directly.
"""

from .router import run_core_scenario
from .schemas import (
    EngineResult,
    EngineScenario,
    ModelSource,
    Reproducibility,
)
from .us_household_resources import (
    build_us_household_resources_scenario,
    run_us_household_resources,
)
from .us_retirement import build_us_retirement_scenario, run_us_retirement

__all__ = [
    "EngineResult",
    "EngineScenario",
    "ModelSource",
    "Reproducibility",
    "build_us_household_resources_scenario",
    "build_us_retirement_scenario",
    "run_core_scenario",
    "run_us_household_resources",
    "run_us_retirement",
]
