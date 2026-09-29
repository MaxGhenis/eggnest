"""UK tax integration via policyengine-uk-compiled (Rust).

Single batched call per simulation year: all N Monte Carlo paths become N
separate households in one Simulation.run_microdata() call. The Rust engine
handles ~0.1ms per household, so a 10k-path year completes in ~1s.

The simulator needs the direct personal tax on the income it models (income
tax plus employee National Insurance), so this module reads person-level
results rather than household ``baseline_net_income`` / ``baseline_total_tax``.
Those household totals add modeled benefits (Universal Credit, Pension Credit,
Housing Benefit) computed without the person's ISA/SIPP/GIA capital, plus
consumption taxes such as VAT, neither of which is a cost or proceed of
drawing income.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from policyengine_uk_compiled import Parameters, Simulation
from policyengine_uk_compiled.engine import (
    BENUNIT_DEFAULTS,
    HOUSEHOLD_DEFAULTS,
    PERSON_DEFAULTS,
)
from policyengine_uk_compiled.models import StatePensionParams

# PE-UK-rust ships parameters through 2029/30. Later years are clipped to the
# latest available — parameters are assumed to persist (a reasonable default
# given that future UK fiscal years haven't been legislated yet).
LATEST_PARAMETER_YEAR = 2029

# policyengine-uk-compiled ignores the ``state_pension`` input column and
# imputes a full new State Pension for everyone over its State Pension age
# (0.20.0: £12,522 in 2026 at age 66+). The simulator's State Pension amount
# and start age are user inputs, so we zero the engine's imputation with this
# overlay, read the overlay's (``reform_``) person results, and pass the
# user's State Pension through the pension-income column: income tax treats
# State Pension and private pension alike as non-savings income, and neither
# attracts National Insurance.
_NO_IMPUTED_STATE_PENSION = Parameters(
    state_pension=StatePensionParams(
        new_state_pension_weekly=0.0, old_basic_pension_weekly=0.0
    )
)

# The engine must see exactly the income we pass. A larger gap means it
# imputed or dropped income (as it does with State Pension above), which
# would silently mis-state the tax.
_INCOME_TOLERANCE = 0.01


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

    # Gross modeled income minus income tax and employee NI. Benefits are not
    # included, and nor are consumption taxes.
    net_income: np.ndarray  # £
    total_tax: np.ndarray  # income tax + employee NI, £
    income_tax: np.ndarray  # £
    employee_ni: np.ndarray  # £


def _defaults_frame(defaults: dict, n: int) -> dict[str, np.ndarray]:
    """Broadcast the PE-UK scalar defaults into n-row columns."""
    return {key: np.full(n, value) for key, value in defaults.items()}


def gross_income(inputs: UKYearInputs) -> np.ndarray:
    """Total modeled gross income for each path, £."""
    return (
        inputs.state_pension.astype(float)
        + inputs.private_pension_income.astype(float)
        + inputs.savings_interest.astype(float)
        + inputs.dividend_income.astype(float)
        + inputs.employment_income.astype(float)
    )


def _engine_direct_tax(
    inputs: UKYearInputs, rows: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Run PolicyEngine on ``rows`` of (state pension, private pension,
    savings interest, dividends, employment) and return (income tax, NI)."""
    n = int(rows.shape[0])
    ids = np.arange(n)
    id_strs = ids.astype(str)
    state_pension, private_pension, savings, dividends, employment = rows.T

    persons = _defaults_frame(PERSON_DEFAULTS, n)
    persons.update(
        person_id=ids,
        benunit_id=ids,
        household_id=ids,
        age=np.full(n, int(inputs.age)),
        state_pension=np.zeros(n),
        private_pension_income=state_pension + private_pension,
        savings_interest=savings,
        dividend_income=dividends,
        employment_income=employment,
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
    result = sim.run_microdata(policy=_NO_IMPUTED_STATE_PENSION)

    person = result.persons.sort_values("person_id").reset_index(drop=True)
    gross = rows.sum(axis=1)
    engine_income = person["reform_total_income"].to_numpy(dtype=float)
    if not np.allclose(engine_income, gross, rtol=0.0, atol=_INCOME_TOLERANCE):
        worst = int(np.argmax(np.abs(engine_income - gross)))
        raise RuntimeError(
            "policyengine-uk-compiled total income differs from the modeled "
            f"income (row {worst}: engine £{engine_income[worst]:,.2f}, "
            f"modeled £{gross[worst]:,.2f}); refusing to use its tax."
        )
    return (
        person["reform_income_tax"].to_numpy(dtype=float),
        person["reform_employee_ni"].to_numpy(dtype=float),
    )


def calculate_uk_tax(inputs: UKYearInputs) -> UKYearResults:
    """Run a single batched UK tax calculation for all paths in one year.

    Paths with identical incomes (common before retirement, or when no path
    holds a GIA) are sent to the engine once.
    """
    rows = np.column_stack(
        [
            inputs.state_pension.astype(float),
            inputs.private_pension_income.astype(float),
            inputs.savings_interest.astype(float),
            inputs.dividend_income.astype(float),
            inputs.employment_income.astype(float),
        ]
    )
    unique_rows, inverse = np.unique(rows, axis=0, return_inverse=True)
    income_tax, employee_ni = _engine_direct_tax(inputs, unique_rows)
    inverse = inverse.reshape(-1)
    income_tax = income_tax[inverse]
    employee_ni = employee_ni[inverse]
    direct_tax = income_tax + employee_ni
    return UKYearResults(
        net_income=gross_income(inputs) - direct_tax,
        total_tax=direct_tax,
        income_tax=income_tax,
        employee_ni=employee_ni,
    )


def get_uk_tax_calculator():
    """Resolve the UK tax backend from EGGNEST_UK_TAX_ENGINE.

    "policyengine" (default) uses policyengine-uk-compiled. "axiom" uses the
    experimental Axiom rules engine backend (statute-encoded rules); it
    requires the engine binary and a rulespec-uk checkout, and falls back to
    PolicyEngine with a warning when unavailable.
    """
    import os

    choice = os.environ.get("EGGNEST_UK_TAX_ENGINE", "policyengine").lower()
    if choice == "axiom":
        from . import axiom_uk

        if axiom_uk.available():
            return axiom_uk.calculate_uk_tax_axiom
        import logging

        logging.getLogger(__name__).warning(
            "EGGNEST_UK_TAX_ENGINE=axiom but the Axiom engine is unavailable; "
            "falling back to policyengine-uk-compiled"
        )
    return calculate_uk_tax
