"""Validation tests for API request models."""

import pytest
from pydantic import ValidationError

from eggnest.models import (
    AnnuityInput,
    Holding,
    SimulationInput,
    SpouseInput,
    StateComparisonInput,
)


def valid_input(**overrides) -> dict:
    data = {
        "initial_capital": 500_000,
        "annual_spending": 40_000,
        "current_age": 65,
        "max_age": 90,
        "state": "CA",
    }
    data.update(overrides)
    return data


def test_simulation_input_requires_portfolio_source():
    with pytest.raises(ValidationError, match="Either holdings or initial_capital"):
        SimulationInput(**valid_input(initial_capital=None))


def test_simulation_input_accepts_holdings_without_initial_capital():
    params = SimulationInput(
        **valid_input(
            initial_capital=None,
            holdings=[
                Holding(account_type="taxable", fund="vt", balance=250_000),
            ],
        )
    )

    assert params.total_capital == 250_000


def test_simulation_input_requires_max_age_after_current_age():
    with pytest.raises(ValidationError, match="max_age must be greater"):
        SimulationInput(**valid_input(current_age=70, max_age=70))


def test_simulation_input_normalizes_and_validates_state():
    params = SimulationInput(**valid_input(state="ny"))

    assert params.state == "NY"

    with pytest.raises(ValidationError, match="Unsupported state code"):
        SimulationInput(**valid_input(state="XX"))


def test_simulation_input_requires_spouse_details_when_enabled():
    with pytest.raises(ValidationError, match="spouse is required"):
        SimulationInput(**valid_input(has_spouse=True, spouse=None))

    params = SimulationInput(
        **valid_input(
            has_spouse=True,
            spouse=SpouseInput(age=64),
        )
    )
    assert params.spouse is not None


def test_simulation_input_requires_annuity_details_when_enabled():
    with pytest.raises(ValidationError, match="annuity is required"):
        SimulationInput(**valid_input(has_annuity=True, annuity=None))

    params = SimulationInput(
        **valid_input(
            has_annuity=True,
            annuity=AnnuityInput(monthly_payment=1_000),
        )
    )
    assert params.annuity is not None


def test_state_comparison_normalizes_and_validates_states():
    comparison = StateComparisonInput(
        base_input=SimulationInput(**valid_input()),
        compare_states=["tx", "FL"],
    )

    assert comparison.compare_states == ["TX", "FL"]

    with pytest.raises(ValidationError, match="Unsupported state code"):
        StateComparisonInput(
            base_input=SimulationInput(**valid_input()),
            compare_states=["TX", "XX"],
        )


def test_uk_input_rejects_max_age_below_current_age():
    from eggnest.models_uk import UKSimulationInput

    with pytest.raises(ValidationError, match="max_age"):
        UKSimulationInput(current_age=80, max_age=70, annual_spending=20_000)

    # Inclusive single-year horizon stays valid.
    assert (
        UKSimulationInput(current_age=70, max_age=70, annual_spending=20_000).max_age
        == 70
    )
