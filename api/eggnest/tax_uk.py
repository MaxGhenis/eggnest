"""UK tax integration via policyengine-uk-compiled (Rust).

Single batched call per simulation year: all N Monte Carlo paths become N
separate households in one Simulation.run_microdata() call. The Rust engine
handles ~0.1ms per household, so a 10k-path year completes in ~1s.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from policyengine_uk_compiled import Simulation
from policyengine_uk_compiled.engine import (
    BENUNIT_DEFAULTS,
    HOUSEHOLD_DEFAULTS,
    PERSON_DEFAULTS,
)

# PE-UK-rust ships parameters through 2029/30. Later years are clipped to the
# latest available — parameters are assumed to persist (a reasonable default
# given that future UK fiscal years haven't been legislated yet).
LATEST_PARAMETER_YEAR = 2029


@dataclass
class UKYearInputs:
    """Per-path inputs for a single UK simulation year."""

    age: int
    year: int
    state_pension: np.ndarray  # annual, £
    private_pension_income: np.ndarray  # SIPP drawdown (taxable), £
    savings_interest: np.ndarray  # GIA interest, £
    dividend_income: np.ndarray  # GIA dividends, £
    employment_income: np.ndarray  # if still working, £
    region: str = "London"


@dataclass
class UKYearResults:
    """Per-path outputs for a single UK simulation year."""

    net_income: np.ndarray  # after-tax, after-benefits £
    total_tax: np.ndarray  # income tax + NI + dividend tax, £


def calculate_uk_tax(inputs: UKYearInputs) -> UKYearResults:
    """Run a single batched UK tax calculation for all paths in one year."""
    n = int(inputs.state_pension.shape[0])

    persons = [
        {
            **PERSON_DEFAULTS,
            "person_id": i,
            "benunit_id": i,
            "household_id": i,
            "age": int(inputs.age),
            "state_pension": float(inputs.state_pension[i]),
            "private_pension_income": float(inputs.private_pension_income[i]),
            "savings_interest": float(inputs.savings_interest[i]),
            "dividend_income": float(inputs.dividend_income[i]),
            "employment_income": float(inputs.employment_income[i]),
        }
        for i in range(n)
    ]
    benunits = [
        {**BENUNIT_DEFAULTS, "benunit_id": i, "household_id": i, "person_ids": str(i)}
        for i in range(n)
    ]
    households = [
        {
            **HOUSEHOLD_DEFAULTS,
            "household_id": i,
            "benunit_ids": str(i),
            "person_ids": str(i),
            "region": inputs.region,
        }
        for i in range(n)
    ]

    sim = Simulation(
        year=min(inputs.year, LATEST_PARAMETER_YEAR),
        persons=pd.DataFrame(persons),
        benunits=pd.DataFrame(benunits),
        households=pd.DataFrame(households),
    )
    result = sim.run_microdata()

    hh = result.households.sort_values("household_id").reset_index(drop=True)
    return UKYearResults(
        net_income=hh["baseline_net_income"].to_numpy(dtype=float),
        total_tax=hh["baseline_total_tax"].to_numpy(dtype=float),
    )
