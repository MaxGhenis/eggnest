"""Tests for the Monte Carlo simulation engine."""

import numpy as np
import pytest

import eggnest.simulation as simulation_module
from eggnest.models import AnnuityInput, Holding, SimulationInput
from eggnest.simulation import MonteCarloSimulator
from eggnest.tax import TaxCalculator


def _mock_tax_results(
    n: int,
    *,
    federal_income_tax: float | np.ndarray = 0.0,
    state_income_tax: float | np.ndarray = 0.0,
    taxable_income: float | np.ndarray = 0.0,
    total_tax: float | np.ndarray = 0.0,
    effective_tax_rate: float | np.ndarray = 0.0,
    adjusted_gross_income: float | np.ndarray = 0.0,
    medicare_part_b_premium: float | np.ndarray = 0.0,
    medicare_part_b_irmaa_increment: float | np.ndarray = 0.0,
    medicare_part_b_irmaa_bracket: str | np.ndarray = "none",
    medicare_part_d_premium_surcharge: float | np.ndarray = 0.0,
    medicare_part_d_irmaa_bracket: str | np.ndarray = "none",
) -> dict[str, np.ndarray]:
    """Build a complete fake PolicyEngine tax payload for simulator tests."""

    def as_array(value):
        if isinstance(value, np.ndarray):
            return value
        return np.full(n, value, dtype=float)

    medicare_part_b_array = as_array(medicare_part_b_premium)
    medicare_part_b_irmaa_increment_array = as_array(medicare_part_b_irmaa_increment)
    medicare_part_d_array = as_array(medicare_part_d_premium_surcharge)
    if isinstance(medicare_part_b_irmaa_bracket, np.ndarray):
        medicare_part_b_irmaa_bracket_array = medicare_part_b_irmaa_bracket
    else:
        medicare_part_b_irmaa_bracket_array = np.full(
            n, medicare_part_b_irmaa_bracket, dtype=object
        )
    if isinstance(medicare_part_d_irmaa_bracket, np.ndarray):
        medicare_part_d_irmaa_bracket_array = medicare_part_d_irmaa_bracket
    else:
        medicare_part_d_irmaa_bracket_array = np.full(
            n, medicare_part_d_irmaa_bracket, dtype=object
        )

    return {
        "federal_income_tax": as_array(federal_income_tax),
        "state_income_tax": as_array(state_income_tax),
        "taxable_income": as_array(taxable_income),
        "total_tax": as_array(total_tax),
        "effective_tax_rate": as_array(effective_tax_rate),
        "adjusted_gross_income": as_array(adjusted_gross_income),
        "medicare_part_b_premium": medicare_part_b_array,
        "medicare_part_b_irmaa_increment": medicare_part_b_irmaa_increment_array,
        "medicare_part_b_irmaa_bracket": medicare_part_b_irmaa_bracket_array,
        "medicare_part_d_premium_surcharge": medicare_part_d_array,
        "medicare_part_d_irmaa_bracket": medicare_part_d_irmaa_bracket_array,
        "total_medicare_premium": medicare_part_b_array + medicare_part_d_array,
    }


def test_simulation_basic():
    """Test basic simulation runs without errors."""
    params = SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48000,
        social_security_monthly=2000,
        current_age=65,
        max_age=75,  # 10 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,  # Small for testing
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    assert 0 <= result.success_rate <= 1
    assert result.median_final_value >= 0
    assert result.mean_final_value >= 0
    assert result.median_final_value_real >= 0
    assert len(result.percentiles) == 5
    assert len(result.percentiles_real) == 5
    assert len(result.percentile_paths["p50"]) == 11  # n_years + 1


def test_simulation_high_withdrawal_depletes():
    """Test that very high withdrawals lead to depletion."""
    params = SimulationInput(
        initial_capital=100_000,
        annual_spending=120_000,  # Very high relative to capital
        social_security_monthly=0,
        current_age=65,
        max_age=95,  # 30 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
        include_mortality=False,  # Disable mortality for pure depletion test
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    # Should have high depletion rate
    assert result.success_rate < 0.5


def test_simulation_low_withdrawal_succeeds():
    """Test that conservative withdrawals have high success rate."""
    params = SimulationInput(
        initial_capital=2_000_000,
        annual_spending=36000,  # ~1.8% withdrawal rate
        social_security_monthly=2000,
        current_age=65,
        max_age=95,  # 30 years
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    # Should have high success rate
    assert result.success_rate > 0.8


def test_simulation_percentiles_ordered():
    """Test that percentiles are in correct order."""
    params = SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48000,
        current_age=65,
        max_age=75,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
    )

    simulator = MonteCarloSimulator(params)
    result = simulator.run()

    assert result.percentiles["p5"] <= result.percentiles["p25"]
    assert result.percentiles["p25"] <= result.percentiles["p50"]
    assert result.percentiles["p50"] <= result.percentiles["p75"]
    assert result.percentiles["p75"] <= result.percentiles["p95"]


def test_random_seed_makes_simulation_reproducible():
    """A fixed RNG seed should produce identical Monte Carlo results."""
    params = SimulationInput(
        initial_capital=1_000_000,
        annual_spending=48_000,
        current_age=65,
        max_age=75,
        gender="male",
        state="CA",
        filing_status="single",
        n_simulations=100,
        include_mortality=False,
        random_seed=12345,
    )

    first = MonteCarloSimulator(params).run()
    second = MonteCarloSimulator(params).run()

    assert first.success_rate == pytest.approx(second.success_rate)
    assert first.median_final_value == pytest.approx(second.median_final_value)
    assert first.total_taxes_median == pytest.approx(second.total_taxes_median)
    assert first.percentiles == pytest.approx(second.percentiles)
    assert first.percentile_paths["p50"] == pytest.approx(second.percentile_paths["p50"])


def test_real_spending_mode_tracks_constant_inflation():
    """Real spending should rise with inflation and real finals should be deflated."""
    params = SimulationInput(
        holdings=[Holding(account_type="roth_ira", fund="sp500", balance=100)],
        annual_spending=10,
        spending_mode="real",
        inflation_model="constant",
        inflation_rate=0.10,
        current_age=60,
        max_age=62,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    result = simulator.run()

    assert result.year_breakdown[0].spending_target == pytest.approx(10.0)
    assert result.year_breakdown[1].spending_target == pytest.approx(11.0)
    assert result.median_final_value == pytest.approx(79.0)
    assert result.median_final_value_real == pytest.approx(79.0 / 1.21)


def test_social_security_cola_tracks_inflation(monkeypatch):
    """Inflation-adjusted Social Security should step up with the inflation path."""
    params = SimulationInput(
        initial_capital=100,
        annual_spending=1,
        social_security_monthly=1000,
        social_security_start_age=62,
        social_security_inflation_adjusted=True,
        inflation_model="constant",
        inflation_rate=0.10,
        current_age=62,
        max_age=64,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    monkeypatch.setattr(
        simulator.tax_calc,
        "calculate_batch_taxes",
        lambda **kwargs: _mock_tax_results(len(kwargs["capital_gains_array"])),
    )

    result = simulator.run()

    assert result.year_breakdown[0].social_security == pytest.approx(12_000)
    assert result.year_breakdown[1].social_security == pytest.approx(13_200)


def test_pension_cola_rate_increases_income(monkeypatch):
    """Pension COLA should step income up each year."""
    params = SimulationInput(
        initial_capital=100,
        annual_spending=1,
        pension_annual=10_000,
        pension_cola_rate=0.03,
        inflation_model="constant",
        inflation_rate=0.02,
        current_age=60,
        max_age=62,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    monkeypatch.setattr(
        simulator.tax_calc,
        "calculate_batch_taxes",
        lambda **kwargs: _mock_tax_results(len(kwargs["capital_gains_array"])),
    )

    result = simulator.run()

    assert result.year_breakdown[0].pension == pytest.approx(10_000)
    assert result.year_breakdown[1].pension == pytest.approx(10_300)


def test_holdings_portfolio_pays_taxes_from_assets(monkeypatch):
    """Holdings mode should reduce balances for taxes as well as spending."""
    params = SimulationInput(
        holdings=[Holding(account_type="taxable", fund="vt", balance=100)],
        annual_spending=10,
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
        inflation_model="constant",
        inflation_rate=0,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def fake_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n, federal_income_tax=2.0, total_tax=2.0)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", fake_taxes)

    result = simulator.run()

    assert result.median_final_value == pytest.approx(88.0)
    assert result.total_withdrawn_median == pytest.approx(12.0)
    assert result.total_taxes_median == pytest.approx(2.0)


def test_legacy_income_surplus_covers_taxes_before_portfolio(monkeypatch):
    """Legacy mode should not pull from the portfolio when other income covers tax."""

    def zero_returns(
        n_simulations,
        n_years,
        stock_allocation,
        method,
        expected_stock_return,
        stock_volatility,
        stock_index,
        bond_index,
        rng,
    ):
        return np.zeros((n_simulations, n_years)), np.zeros((n_simulations, n_years))

    monkeypatch.setattr(simulation_module, "generate_blended_returns", zero_returns)

    params = SimulationInput(
        initial_capital=100,
        annual_spending=50,
        employment_income=60,
        retirement_age=65,
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    def fake_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n, federal_income_tax=5.0, total_tax=5.0)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", fake_taxes)

    result = simulator.run()

    assert result.median_final_value == pytest.approx(100.0)
    assert result.total_withdrawn_median == pytest.approx(0.0)
    assert result.total_taxes_median == pytest.approx(5.0)


def test_excess_rmd_is_retained_in_taxable_cash(monkeypatch):
    """RMD cash that is not needed for spending should stay in the portfolio."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=100)],
        annual_spending=1,
        pension_annual=1,
        current_age=73,
        max_age=74,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def zero_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    result = simulator.run()

    assert result.median_final_value == pytest.approx(100.0)
    assert result.total_withdrawn_median == pytest.approx(0.0)
    assert result.total_taxes_median == pytest.approx(0.0)


def test_holdings_tax_calculation_uses_realized_gains(monkeypatch):
    """PolicyEngine input should use realized gains, not gross taxable proceeds."""
    params = SimulationInput(
        holdings=[
            Holding(
                account_type="taxable",
                fund="vt",
                balance=100,
                cost_basis=80,
            )
        ],
        annual_spending=50,
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    observed: dict[str, np.ndarray] = {}

    def zero_taxes(**kwargs):
        observed["capital_gains_array"] = kwargs["capital_gains_array"]
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    result = simulator.run()

    assert np.allclose(observed["capital_gains_array"], 10.0)
    assert result.median_final_value == pytest.approx(50.0)


def test_roth_conversion_moves_assets_and_enters_taxable_income(monkeypatch):
    """Roth conversions should stay invested and be taxed as ordinary income."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=100)],
        annual_spending=0.01,
        pension_annual=0.01,
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
        roth_conversion_amount=10,
        roth_conversion_start_age=60,
        roth_conversion_end_age=60,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    observed: dict[str, np.ndarray] = {}

    def zero_taxes(**kwargs):
        observed["employment_income_array"] = kwargs["employment_income_array"]
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n, adjusted_gross_income=kwargs["employment_income_array"])

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    result = simulator.run()

    assert np.allclose(observed["employment_income_array"], 10.01)
    assert result.total_roth_conversions_median == pytest.approx(10.0)
    assert result.year_breakdown[0].roth_conversion == pytest.approx(10.0)
    assert result.year_breakdown[0].ordinary_income == pytest.approx(10.01)
    assert result.total_taxes_median == pytest.approx(0.0)
    assert result.median_final_value == pytest.approx(100.0)


def test_pension_and_annuity_enter_taxable_income_in_legacy_mode(monkeypatch):
    """Tax calculations should include pension and annuity cash as ordinary income."""
    params = SimulationInput(
        initial_capital=100,
        annual_spending=0.01,
        employment_income=5,
        pension_annual=10,
        has_annuity=True,
        annuity=AnnuityInput(monthly_payment=1),
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
        inflation_model="constant",
        inflation_rate=0,
    )
    simulator = MonteCarloSimulator(params)

    monkeypatch.setattr(
        simulation_module,
        "generate_blended_returns",
        lambda **kwargs: (
            np.zeros((100, 1)),
            np.zeros((100, 1)),
            np.full((100, 1), 1970, dtype=int),
        ),
    )
    observed: dict[str, np.ndarray] = {}

    def zero_taxes(**kwargs):
        observed["employment_income_array"] = kwargs["employment_income_array"]
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n, adjusted_gross_income=kwargs["employment_income_array"])

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    simulator.run()

    assert np.allclose(observed["employment_income_array"], 27.0)


@pytest.mark.parametrize(
    ("policy", "expected_conversion"),
    [
        ("fill_standard_deduction", 9.99),
        ("fill_12_percent_bracket", 19.99),
        ("fill_22_percent_bracket", 100.0),
    ],
)
def test_roth_conversion_policies_follow_modeled_tax_headroom(
    monkeypatch, policy, expected_conversion
):
    """Bracket-fill Roth policies should size conversions from modeled federal tax."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=100)],
        annual_spending=0.01,
        pension_annual=0.01,
        current_age=60,
        max_age=61,
        n_simulations=100,
        include_mortality=False,
        inflation_model="constant",
        inflation_rate=0,
        roth_conversion_policy=policy,
        roth_conversion_start_age=60,
        roth_conversion_end_age=60,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def piecewise_taxes(**kwargs):
        ordinary_income = np.asarray(kwargs["employment_income_array"], dtype=float)
        taxable_income = np.maximum(ordinary_income - 10.0, 0.0)
        federal_tax = np.where(
            taxable_income <= 10.0,
            taxable_income * 0.12,
            1.2 + (taxable_income - 10.0) * 0.22,
        )
        n = len(ordinary_income)
        return _mock_tax_results(
            n,
            federal_income_tax=federal_tax,
            taxable_income=taxable_income,
            total_tax=federal_tax,
            effective_tax_rate=np.where(
                ordinary_income > 0, federal_tax / ordinary_income, 0
            ),
            adjusted_gross_income=ordinary_income,
        )

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", piecewise_taxes)

    result = simulator.run()

    assert result.total_roth_conversions_median == pytest.approx(
        expected_conversion, abs=0.2
    )
    assert result.year_breakdown[0].roth_conversion == pytest.approx(
        expected_conversion, abs=0.2
    )


def test_rmd_happens_before_same_year_roth_conversion(monkeypatch):
    """Age-73+ conversions should only use the post-RMD traditional balance."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=100)],
        annual_spending=0.01,
        pension_annual=0.01,
        current_age=73,
        max_age=74,
        n_simulations=100,
        include_mortality=False,
        roth_conversion_amount=100,
        roth_conversion_start_age=73,
        roth_conversion_end_age=73,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def zero_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    result = simulator.run()

    expected_rmd = 100 / 26.5
    expected_conversion = 100 - expected_rmd

    assert result.total_roth_conversions_median == pytest.approx(expected_conversion)
    assert result.year_breakdown[0].traditional_rmd == pytest.approx(expected_rmd)
    assert result.year_breakdown[0].roth_conversion == pytest.approx(expected_conversion)
    assert result.year_breakdown[0].ordinary_income == pytest.approx(
        expected_rmd + expected_conversion + 0.01
    )
    assert result.year_breakdown[0].traditional_balance_end == pytest.approx(0.0)
    assert result.year_breakdown[0].roth_balance_end == pytest.approx(expected_conversion)
    assert result.year_breakdown[0].taxable_balance_end == pytest.approx(expected_rmd)
    assert np.median(simulator.tracker.taxable_balance) == pytest.approx(expected_rmd)
    assert np.median(simulator.tracker.roth_balance) == pytest.approx(expected_conversion)
    assert result.median_final_value == pytest.approx(100.0)


def test_tax_calculator_uses_prior_agi_for_medicare_part_b_premium():
    """The PE-backed tax wrapper should surface IRMAA-sensitive Part B premiums."""
    calculator = TaxCalculator(state="CA", year=2025)

    base_result = calculator.calculate_batch_taxes(
        capital_gains_array=np.array([0.0]),
        social_security_array=np.array([0.0]),
        ages=np.array([67]),
        filing_status="single",
        employment_income_array=np.array([0.0]),
        agi_two_years_prior_array=np.array([0.0]),
        year=2025,
    )
    irmaa_result = calculator.calculate_batch_taxes(
        capital_gains_array=np.array([0.0]),
        social_security_array=np.array([0.0]),
        ages=np.array([67]),
        filing_status="single",
        employment_income_array=np.array([0.0]),
        agi_two_years_prior_array=np.array([120_000.0]),
        year=2025,
    )

    assert float(base_result["medicare_part_b_premium"][0]) == pytest.approx(2_220.0)
    assert float(irmaa_result["medicare_part_b_premium"][0]) == pytest.approx(3_108.0)


def test_tax_calculator_surfaces_part_d_irmaa_surcharge():
    """The PE-backed tax wrapper should expose Part D IRMAA when available."""
    calculator = TaxCalculator(state="CA", year=2025)

    result = calculator.calculate_batch_taxes(
        capital_gains_array=np.array([0.0]),
        social_security_array=np.array([0.0]),
        ages=np.array([67]),
        filing_status="joint",
        employment_income_array=np.array([0.0]),
        agi_two_years_prior_array=np.array([266_001.0]),
        year=2025,
    )

    assert float(result["medicare_part_d_premium_surcharge"][0]) == pytest.approx(423.6)
    assert float(result["medicare_part_b_premium"][0]) == pytest.approx(4_440.0)
    assert float(result["total_medicare_premium"][0]) == pytest.approx(4_440.0 + 423.6)


def test_medicare_part_b_premium_uses_two_year_agi_lag(monkeypatch):
    """IRMAA should use AGI from two simulated years earlier, not the current year."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=500)],
        annual_spending=0.01,
        current_age=65,
        max_age=68,
        n_simulations=100,
        include_mortality=False,
        inflation_model="constant",
        inflation_rate=0,
        roth_conversion_amount=50,
        roth_conversion_start_age=65,
        roth_conversion_end_age=65,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def fake_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        agi_prior = np.asarray(kwargs["agi_two_years_prior_array"], dtype=float)
        ordinary_income = np.asarray(kwargs["employment_income_array"], dtype=float)
        premium = np.where(agi_prior > 0, 100.0, 0.0)
        return _mock_tax_results(
            n,
            adjusted_gross_income=ordinary_income,
            medicare_part_b_premium=premium,
            medicare_part_d_premium_surcharge=premium / 2,
        )

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", fake_taxes)

    result = simulator.run()

    assert result.total_medicare_premiums_median == pytest.approx(150.0)
    assert result.year_breakdown[0].medicare_part_b_premium == pytest.approx(0.0)
    assert result.year_breakdown[0].medicare_part_d_premium_surcharge == pytest.approx(0.0)
    assert result.year_breakdown[1].medicare_part_b_premium == pytest.approx(0.0)
    assert result.year_breakdown[1].medicare_part_d_premium_surcharge == pytest.approx(0.0)
    assert result.year_breakdown[2].medicare_part_b_premium == pytest.approx(100.0)
    assert result.year_breakdown[2].medicare_part_d_premium_surcharge == pytest.approx(50.0)
    assert result.year_breakdown[2].withdrawal == pytest.approx(150.01)


def test_roth_year_breakdown_surfaces_cliff_explainability(monkeypatch):
    """Representative Roth ledger should expose bracket and Medicare cliff fields."""
    params = SimulationInput(
        holdings=[Holding(account_type="traditional_401k", fund="vt", balance=500)],
        annual_spending=0.01,
        pension_annual=10_000,
        current_age=65,
        max_age=66,
        n_simulations=100,
        include_mortality=False,
        inflation_model="constant",
        inflation_rate=0,
        roth_conversion_amount=50,
        roth_conversion_start_age=65,
        roth_conversion_end_age=65,
    )
    simulator = MonteCarloSimulator(params)

    for holding in simulator.tracker.holdings:
        holding.price_growth[:] = 0
        holding.div_yields[:] = 0

    def fake_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        ordinary_income = np.asarray(kwargs["employment_income_array"], dtype=float)
        conversion = np.maximum(0.0, ordinary_income - 10_000.0)
        return _mock_tax_results(
            n,
            federal_income_tax=ordinary_income * 0.12,
            taxable_income=ordinary_income,
            total_tax=ordinary_income * 0.12,
            effective_tax_rate=np.where(ordinary_income > 0, 0.12, 0.0),
            adjusted_gross_income=ordinary_income,
            medicare_part_b_premium=np.where(conversion > 0, 3_108.0, 2_220.0),
            medicare_part_b_irmaa_increment=np.where(conversion > 0, 888.0, 0.0),
            medicare_part_b_irmaa_bracket=np.where(
                conversion > 0, "$106,001-$133,000 MAGI", "none"
            ),
            medicare_part_d_premium_surcharge=np.where(conversion > 0, 423.6, 0.0),
            medicare_part_d_irmaa_bracket=np.where(
                conversion > 0, "$106,001-$133,000 MAGI", "none"
            ),
        )

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", fake_taxes)

    result = simulator.run()
    row = result.year_breakdown[0]

    assert row.federal_taxable_income == pytest.approx(10_050.0)
    assert row.federal_taxable_income_without_roth_conversion == pytest.approx(10_000.0)
    assert row.federal_bracket_headroom_used == pytest.approx(50.0)
    assert row.federal_marginal_rate_on_last_conversion_dollar == pytest.approx(0.12)
    assert row.medicare_part_b_irmaa_increment == pytest.approx(888.0)
    assert row.medicare_part_b_irmaa_bracket == "$106,001-$133,000 MAGI"
    assert row.medicare_part_d_irmaa_bracket == "$106,001-$133,000 MAGI"
    assert row.medicare_total_premium == pytest.approx(3_531.6)
    assert row.medicare_premium_delta_vs_no_roth_conversion == pytest.approx(1_311.6)


def test_balances_freeze_after_death(monkeypatch):
    """Once the household is dead, the simulator should stop spending and growth."""

    def fake_alive_mask(n_simulations, n_years, current_age, gender, rng):
        alive = np.ones((n_simulations, n_years + 1), dtype=bool)
        alive[:, 1:] = False
        return alive

    def fake_returns(
        n_simulations,
        n_years,
        stock_allocation,
        method,
        expected_stock_return,
        stock_volatility,
        stock_index,
        bond_index,
        rng,
    ):
        return np.full((n_simulations, n_years), 0.10), np.zeros(
            (n_simulations, n_years)
        )

    monkeypatch.setattr(simulation_module, "generate_alive_mask", fake_alive_mask)
    monkeypatch.setattr(simulation_module, "generate_blended_returns", fake_returns)

    params = SimulationInput(
        initial_capital=100,
        annual_spending=1,
        pension_annual=1,
        current_age=65,
        max_age=68,
        n_simulations=100,
        include_mortality=True,
    )
    simulator = MonteCarloSimulator(params)

    def zero_taxes(**kwargs):
        n = len(kwargs["capital_gains_array"])
        return _mock_tax_results(n)

    monkeypatch.setattr(simulator.tax_calc, "calculate_batch_taxes", zero_taxes)

    result = simulator.run()

    assert result.median_final_value == pytest.approx(110.0)
