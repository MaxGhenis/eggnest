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


def _defaults_frame(defaults: dict, n: int) -> dict[str, np.ndarray]:
    """Broadcast the PE-UK scalar defaults into n-row columns."""
    return {key: np.full(n, value) for key, value in defaults.items()}


def calculate_uk_tax(inputs: UKYearInputs) -> UKYearResults:
    """Run a single batched UK tax calculation for all paths in one year."""
    n = int(inputs.state_pension.shape[0])
    ids = np.arange(n)
    id_strs = ids.astype(str)

    persons = _defaults_frame(PERSON_DEFAULTS, n)
    persons.update(
        person_id=ids,
        benunit_id=ids,
        household_id=ids,
        age=np.full(n, int(inputs.age)),
        state_pension=inputs.state_pension.astype(float),
        private_pension_income=inputs.private_pension_income.astype(float),
        savings_interest=inputs.savings_interest.astype(float),
        dividend_income=inputs.dividend_income.astype(float),
        employment_income=inputs.employment_income.astype(float),
    )

    benunits = _defaults_frame(BENUNIT_DEFAULTS, n)
    benunits.update(benunit_id=ids, household_id=ids, person_ids=id_strs)

    households = _defaults_frame(HOUSEHOLD_DEFAULTS, n)
    households.update(
        household_id=ids,
        benunit_ids=id_strs,
        person_ids=id_strs,
        region=np.full(n, inputs.region),
    )

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
