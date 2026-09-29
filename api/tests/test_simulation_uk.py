"""Smoke tests for the UK Monte Carlo simulator."""

from __future__ import annotations

import numpy as np
import pytest

from eggnest.models_uk import UKSimulationInput, UKSimulationResult
from eggnest.simulation_uk import run_uk_simulation, run_uk_simulation_with_progress
from eggnest.tax_uk import LATEST_PARAMETER_YEAR, UKYearInputs, calculate_uk_tax


@pytest.fixture
def basic_input() -> UKSimulationInput:
    return UKSimulationInput(
        current_age=65,
        max_age=70,
        annual_spending=25000,
        isa_balance=100000,
        sipp_balance=100000,
        gia_balance=0,
        state_pension_annual=11502,
        state_pension_start_age=67,
        n_simulations=200,
        random_seed=7,
    )


def test_uk_tax_batch_runs_quickly():
    n = 100
    inputs = UKYearInputs(
        age=70,
        year=2025,
        state_pension=np.full(n, 11502.0),
        private_pension_income=np.full(n, 20000.0),
        savings_interest=np.zeros(n),
        dividend_income=np.zeros(n),
        employment_income=np.zeros(n),
    )
    result = calculate_uk_tax(inputs)
    assert result.net_income.shape == (n,)
    assert result.total_tax.shape == (n,)
    assert np.all(result.net_income > 0)
    # All paths identical → all outputs identical
    assert np.allclose(result.net_income, result.net_income[0])


def test_future_year_falls_back_to_latest_parameters():
    n = 2
    inputs = UKYearInputs(
        age=75,
        year=2060,
        state_pension=np.full(n, 11502.0),
        private_pension_income=np.full(n, 20000.0),
        savings_interest=np.zeros(n),
        dividend_income=np.zeros(n),
        employment_income=np.zeros(n),
    )
    # Should not raise — clipped to LATEST_PARAMETER_YEAR
    result = calculate_uk_tax(inputs)
    assert result.net_income.shape == (n,)
    assert LATEST_PARAMETER_YEAR >= 2029


def test_run_uk_simulation_returns_structured_result(basic_input):
    result = run_uk_simulation(basic_input)
    assert isinstance(result, UKSimulationResult)
    assert 0.0 <= result.success_rate <= 1.0
    assert 0.0 <= result.strict_horizon_success_rate <= 1.0
    assert result.strict_horizon_success_rate <= result.success_rate
    assert (
        len(result.year_breakdown) == basic_input.max_age - basic_input.current_age + 1
    )
    for key in ("p5", "p25", "p50", "p75", "p95"):
        assert key in result.percentile_paths
        assert len(result.percentile_paths[key]) == len(result.year_breakdown)


def test_streaming_variant_emits_progress_then_result(basic_input):
    events = list(run_uk_simulation_with_progress(basic_input))
    n_years = basic_input.max_age - basic_input.current_age + 1
    progress_events = [e for e in events if e["type"] == "progress"]
    final_events = [e for e in events if e["type"] == "result"]
    assert len(progress_events) == n_years
    assert progress_events[-1]["current_year"] == n_years
    assert len(final_events) == 1
    assert "success_rate" in final_events[0]["result"]


def test_pre_mpa_paths_cannot_touch_sipp():
    """SIPP drawdown is locked until Minimum Pension Age (55), so a person
    whose only savings are in a SIPP cannot meet spending before then: every
    path fails, and the failures are reported as SIPP-locked."""
    inp = UKSimulationInput(
        current_age=50,
        max_age=54,  # every year in this run is pre-MPA
        annual_spending=40000,
        isa_balance=0,
        sipp_balance=500000,
        gia_balance=0,
        state_pension_annual=0,
        state_pension_start_age=67,
        n_simulations=100,
        random_seed=1,
        include_mortality=False,
    )
    result = run_uk_simulation(inp)
    # Every year breakdown should show zero SIPP drawdown pre-MPA, even though
    # the spending target is far above the accessible ISA/GIA (both zero).
    for b in result.year_breakdown:
        assert b.sipp_withdrawal == 0.0, f"SIPP withdrawn at age {b.age} (pre-MPA)"
        assert b.unmet_spending == pytest.approx(b.spending_target)
        assert b.shortfall_share == 1.0
        assert b.sipp_locked_shortfall_share == 1.0
    assert result.success_rate == 0.0
    assert result.strict_horizon_success_rate == 0.0
    assert result.prob_10_year_failure == 1.0
    assert result.sipp_locked_shortfall_rate == 1.0
    # The money is still there, locked, and growing.
    assert result.median_final_value > 500000


def test_isa_bridges_to_mpa_then_sipp_takes_over():
    """With enough ISA to reach 55, the same person succeeds: the SIPP is
    drawn only from Minimum Pension Age."""
    inp = UKSimulationInput(
        current_age=52,
        max_age=58,
        annual_spending=20000,
        isa_balance=80000,
        sipp_balance=500000,
        state_pension_annual=0,
        state_pension_start_age=67,
        return_source="gaussian",
        expected_return=0.04,
        return_volatility=0.0,
        inflation_rate=0.0,
        n_simulations=100,
        random_seed=1,
        include_mortality=False,
    )
    result = run_uk_simulation(inp)
    assert result.success_rate == 1.0
    assert result.sipp_locked_shortfall_rate == 0.0
    for b in result.year_breakdown:
        if b.age < 55:
            assert b.sipp_withdrawal == 0.0
        assert b.unmet_spending == 0.0
    assert any(b.sipp_withdrawal > 0 for b in result.year_breakdown if b.age >= 55)


def test_strict_success_matches_success_without_mortality(basic_input):
    """Without mortality, success rate is the strict horizon success rate."""
    result = run_uk_simulation(
        basic_input.model_copy(update={"include_mortality": False})
    )
    assert result.strict_horizon_success_rate == result.success_rate


def test_stochastic_earnings_build_up_wealth_pre_retirement():
    """A 35-year-old with stochastic earnings + 8 % savings should end up
    richer than one who just has the same starting pot and does nothing."""
    base = UKSimulationInput(
        current_age=35,
        max_age=66,
        annual_spending=25000,
        isa_balance=0,
        sipp_balance=5000,
        gia_balance=0,
        state_pension_annual=0,
        state_pension_start_age=67,
        employment_income=50000,
        retirement_age=65,
        earnings_model="stochastic",
        savings_rate=0.08,
        sipp_contribution_share=1.0,
        n_simulations=200,
        random_seed=11,
        include_mortality=False,
    )
    no_contrib = base.model_copy(update={"savings_rate": 0.0})
    with_contrib = run_uk_simulation(base)
    without_contrib = run_uk_simulation(no_contrib)
    assert with_contrib.median_final_value > without_contrib.median_final_value
    # Earnings series is non-empty and pinned at year 0.
    assert "p50" in with_contrib.earnings_percentile_paths
    p50 = with_contrib.earnings_percentile_paths["p50"]
    assert p50[0] == pytest.approx(50000, rel=0.01)


def test_flat_earnings_model_reproduces_old_behaviour(basic_input):
    """With earnings_model='flat' and savings_rate=0, result matches default."""
    default = run_uk_simulation(basic_input)
    flat = run_uk_simulation(
        basic_input.model_copy(update={"earnings_model": "flat", "savings_rate": 0.0})
    )
    assert default.success_rate == flat.success_rate


@pytest.mark.parametrize(
    "return_source",
    ["historical_bootstrap", "historical_block_bootstrap", "historical_sequential"],
)
def test_historical_return_sources_produce_valid_result(basic_input, return_source):
    """Every historical return mode should run end-to-end and match the year count."""
    inp = basic_input.model_copy(update={"return_source": return_source})
    result = run_uk_simulation(inp)
    n_years = inp.max_age - inp.current_age + 1
    assert len(result.year_breakdown) == n_years
    assert 0.0 <= result.success_rate <= 1.0
    # With historical UK data the median portfolio should not be exactly zero
    # for a 6-year horizon with a £200k nest egg and £25k spending.
    assert result.median_final_value > 0


def test_historical_bootstrap_differs_from_gaussian(basic_input):
    """The two return models should diverge on the same seed (different draws)."""
    gaus = run_uk_simulation(
        basic_input.model_copy(update={"return_source": "gaussian"})
    )
    hist = run_uk_simulation(
        basic_input.model_copy(update={"return_source": "historical_bootstrap"})
    )
    assert (
        gaus.success_rate != hist.success_rate
        or gaus.median_final_value != hist.median_final_value
    )


def test_tfc_lowers_taxes_vs_full_taxable_sipp(basic_input):
    """The 25 % tax-free split should not produce higher tax than full-taxable SIPP."""
    # Indirect check: when the simulation leans heavily on SIPP (low ISA/GIA),
    # total tax paid should be materially below a naive 20 %-of-SIPP upper bound.
    heavy_sipp = basic_input.model_copy(
        update={
            "isa_balance": 0,
            "gia_balance": 0,
            "sipp_balance": 400_000,
            "annual_spending": 20_000,
            "state_pension_annual": 0,
            "state_pension_start_age": 70,
            "max_age": 72,
        }
    )
    result = run_uk_simulation(heavy_sipp)
    # Year 0 median breakdown
    b0 = result.year_breakdown[0]
    assert b0.sipp_withdrawal > 0, "should be drawing SIPP with no other income"
    # 25 % tax-free portion → effective tax rate should be well below 20 %.
    assert b0.effective_tax_rate < 0.20


@pytest.mark.parametrize(
    "non_sequential_source",
    ["gaussian", "historical_bootstrap", "historical_block_bootstrap"],
)
def test_sequential_exposes_start_years(basic_input, non_sequential_source):
    """Sequential mode populates percentile_path_start_years; other modes don't."""
    seq = run_uk_simulation(
        basic_input.model_copy(update={"return_source": "historical_sequential"})
    )
    assert seq.percentile_path_start_years is not None
    assert set(seq.percentile_path_start_years.keys()) == {
        "p5",
        "p25",
        "p50",
        "p75",
        "p95",
    }
    for y in seq.percentile_path_start_years.values():
        assert 1871 <= y <= 2020, f"percentile start year {y} outside JST range"

    other = run_uk_simulation(
        basic_input.model_copy(update={"return_source": non_sequential_source})
    )
    assert other.percentile_path_start_years is None


def test_percentile_start_year_matches_path():
    """Every per-percentile start year must be a real JST year, and the
    reported start years must vary across percentiles."""
    from eggnest.historical_returns_uk import load_history

    inp = UKSimulationInput(
        current_age=65,
        max_age=75,
        annual_spending=20000,
        isa_balance=100000,
        sipp_balance=200000,
        gia_balance=0,
        state_pension_annual=11502,
        state_pension_start_age=67,
        n_simulations=300,
        random_seed=13,
        include_mortality=False,
        return_source="historical_sequential",
    )
    result = run_uk_simulation(inp)
    assert result.percentile_path_start_years is not None

    hist_years = {int(y) for y in load_history().year}
    for label, year in result.percentile_path_start_years.items():
        assert 1871 <= year <= 2020
        assert year in hist_years, f"{label} start year {year} not in JST history"

    reported = list(result.percentile_path_start_years.values())
    assert (
        len(set(reported)) > 1
    ), "every percentile returned the same start year — path selection broken"


# --- Tax: person-level income tax and employee NI --------------------------


def _tax_inputs(n=1, **overrides) -> UKYearInputs:
    fields = {
        "age": 70,
        "year": 2026,
        "state_pension": np.zeros(n),
        "private_pension_income": np.zeros(n),
        "savings_interest": np.zeros(n),
        "dividend_income": np.zeros(n),
        "employment_income": np.zeros(n),
    }
    for key, value in overrides.items():
        scalar = key in {"age", "year", "region"}
        fields[key] = value if scalar else np.full(n, float(value))
    return UKYearInputs(**fields)


def test_pension_income_tax_matches_hand_calculation():
    """£11,502 State Pension + £20,000 SIPP income in 2026/27 England: £31,502
    less the £12,570 personal allowance, at 20 % = £3,786.40, and no NI."""
    result = calculate_uk_tax(
        _tax_inputs(state_pension=11502, private_pension_income=20000)
    )
    assert result.income_tax[0] == pytest.approx(3786.40, abs=0.01)
    assert result.employee_ni[0] == 0.0
    assert result.total_tax[0] == pytest.approx(3786.40, abs=0.01)
    assert result.net_income[0] == pytest.approx(31502 - 3786.40, abs=0.01)


def test_state_pension_input_is_taxed_and_engine_imputation_is_off():
    """policyengine-uk-compiled imputes its own State Pension from age 66 and
    ignores the input column; tax_uk switches that off and taxes the modeled
    State Pension instead, so tax depends on income, not on age."""
    split = calculate_uk_tax(
        _tax_inputs(state_pension=11502, private_pension_income=20000)
    )
    combined = calculate_uk_tax(_tax_inputs(private_pension_income=31502))
    assert split.total_tax[0] == pytest.approx(combined.total_tax[0], abs=0.01)
    for age in (60, 66, 67, 75):
        at_age = calculate_uk_tax(
            _tax_inputs(age=age, state_pension=11502, private_pension_income=20000)
        )
        assert at_age.total_tax[0] == pytest.approx(split.total_tax[0], abs=0.01)
    # No income, no tax: nothing is imputed.
    nothing = calculate_uk_tax(_tax_inputs(age=70))
    assert nothing.total_tax[0] == 0.0
    assert nothing.net_income[0] == 0.0


def test_net_income_excludes_benefits_and_consumption_taxes():
    """A 60-year-old with no income would get Universal Credit and a 70-year-
    old Pension Credit in PolicyEngine's household totals; the simulator's net
    income counts neither (they ignore the person's savings), and no VAT."""
    for age in (60, 70):
        result = calculate_uk_tax(_tax_inputs(age=age))
        assert result.net_income[0] == 0.0
        assert result.total_tax[0] == 0.0


def test_employment_income_pays_income_tax_and_employee_ni():
    """£40,000 salary, 2026/27: income tax (40,000 - 12,570) x 20 % = £5,486;
    employee NI (40,000 - 12,570) x 8 % = £2,194.40."""
    result = calculate_uk_tax(_tax_inputs(age=40, employment_income=40000))
    assert result.income_tax[0] == pytest.approx(5486.0, abs=0.01)
    assert result.employee_ni[0] == pytest.approx(2194.40, abs=0.01)
    assert result.net_income[0] == pytest.approx(40000 - 5486 - 2194.40, abs=0.01)


def test_scotland_taxes_pension_income_differently_from_london():
    """Scottish income tax bands apply to non-savings income: £60,000 of
    pension income pays more in Scotland than in London (or Wales)."""
    london = calculate_uk_tax(_tax_inputs(private_pension_income=60000))
    scotland = calculate_uk_tax(
        _tax_inputs(private_pension_income=60000, region="Scotland")
    )
    wales = calculate_uk_tax(_tax_inputs(private_pension_income=60000, region="Wales"))
    assert london.income_tax[0] == pytest.approx(11432.0, abs=0.01)
    assert scotland.income_tax[0] > london.income_tax[0] + 1000
    assert wales.income_tax[0] == pytest.approx(london.income_tax[0], abs=0.01)


def test_duplicate_rows_are_computed_once_with_identical_results():
    """Batching deduplicates identical incomes; results must match per-row
    calculation for every path, in order."""
    pensions = np.array([20000.0, 0.0, 20000.0, 55000.0, 0.0, 20000.0])
    batch = calculate_uk_tax(
        UKYearInputs(
            age=70,
            year=2026,
            state_pension=np.full(6, 11502.0),
            private_pension_income=pensions,
            savings_interest=np.zeros(6),
            dividend_income=np.array([0.0, 800.0, 0.0, 0.0, 800.0, 0.0]),
            employment_income=np.zeros(6),
        )
    )
    for i, pension in enumerate(pensions):
        single = calculate_uk_tax(
            _tax_inputs(
                state_pension=11502,
                private_pension_income=pension,
                dividend_income=[0.0, 800.0, 0.0, 0.0, 800.0, 0.0][i],
            )
        )
        assert batch.total_tax[i] == pytest.approx(single.total_tax[0], abs=0.001)
        assert batch.net_income[i] == pytest.approx(single.net_income[0], abs=0.001)


def test_region_flows_from_simulation_inputs_to_tax():
    """The simulator passes inputs.region to the tax engine: the same
    SIPP-funded retirement pays more tax, and so draws more, in Scotland."""
    base = UKSimulationInput(
        current_age=67,
        max_age=69,
        annual_spending=60000,
        sipp_balance=1_000_000,
        state_pension_annual=11502,
        state_pension_start_age=67,
        return_source="gaussian",
        return_volatility=0.0,
        inflation_rate=0.0,
        n_simulations=100,
        random_seed=5,
        include_mortality=False,
    )
    london = run_uk_simulation(base)
    scotland = run_uk_simulation(base.model_copy(update={"region": "Scotland"}))
    for lon, sco in zip(london.year_breakdown, scotland.year_breakdown, strict=True):
        assert sco.total_tax > lon.total_tax + 1000
        assert sco.sipp_withdrawal > lon.sipp_withdrawal
        assert lon.unmet_spending == sco.unmet_spending == 0.0


def test_total_return_applies_to_isa_and_sipp():
    """ISA and SIPP dividends reinvest inside the wrapper: a £100,000 ISA and
    a £100,000 SIPP at a fixed 5 % total return (2.5 % of it dividends) are
    each worth £105,000 a year later."""
    for account in ("isa_balance", "sipp_balance", "gia_balance"):
        inp = UKSimulationInput(
            current_age=60,
            max_age=60,
            annual_spending=0,
            state_pension_annual=0,
            state_pension_start_age=75,
            return_source="gaussian",
            expected_return=0.05,
            return_volatility=0.0,
            dividend_yield=0.025,
            inflation_rate=0.0,
            n_simulations=100,
            random_seed=1,
            include_mortality=False,
            **{account: 100000},
        )
        result = run_uk_simulation(inp)
        # The GIA pays its £2,500 dividend out; it falls within the dividend
        # and personal allowances, so all of it is reinvested.
        assert result.median_final_value == pytest.approx(105000, abs=0.01), account


def test_contributions_are_not_spendable():
    """Earnings saved into an ISA cannot also fund spending: £10,000 of
    earnings, £10,000 of spending and a 50 % savings rate leave a £5,000 gap
    the ISA has to fund."""
    inp = UKSimulationInput(
        current_age=40,
        max_age=40,
        annual_spending=10000,
        employment_income=10000,
        retirement_age=67,
        savings_rate=0.5,
        sipp_contribution_share=0.0,
        state_pension_annual=0,
        state_pension_start_age=75,
        return_source="gaussian",
        expected_return=0.0,
        return_volatility=0.0,
        dividend_yield=0.0,
        inflation_rate=0.0,
        spending_mode="nominal",
        n_simulations=100,
        random_seed=1,
        include_mortality=False,
    )
    result = run_uk_simulation(inp)
    b = result.year_breakdown[0]
    assert b.contributions == pytest.approx(5000)
    assert b.isa_withdrawal == pytest.approx(5000)
    assert b.unmet_spending == 0.0
    assert result.median_final_value == pytest.approx(0.0, abs=0.01)
