"""Tests for mortality, inflation, and dividend correctness in the US simulator."""

import numpy as np
import pytest

from eggnest.holdings import HoldingsTracker
from eggnest.models import Holding, SimulationInput, SpouseInput
from eggnest.returns import generate_blended_returns
from eggnest.simulation import MonteCarloSimulator, _household_social_security


def _flat_market_input(**overrides) -> SimulationInput:
    """Deterministic zero-return, zero-dividend market for isolating cash flows."""
    base = {
        "initial_capital": 1_000_000,
        "annual_spending": 40_000,
        "current_age": 65,
        "max_age": 75,
        "gender": "male",
        "state": "TX",
        "filing_status": "single",
        "n_simulations": 100,
        "random_seed": 42,
        "include_mortality": False,
        "return_model": "normal",
        "expected_return": 0.0,
        "return_volatility": 0.0,
        "dividend_yield": 0.0,
        "inflation_rate": 0.0,
    }
    base.update(overrides)
    return SimulationInput(**base)


class TestMortalityAccounting:
    def test_depletion_while_alive_is_failure_even_if_dead_at_horizon(self):
        """A path that runs out of money while alive must count as a failure,
        even when the household later dies before the planning horizon."""
        params = _flat_market_input(
            initial_capital=50_000,
            annual_spending=200_000,  # Depletes in year one, while alive
            current_age=90,
            max_age=110,
            include_mortality=True,
            n_simulations=200,
        )
        result = MonteCarloSimulator(params).run()
        # Nearly every path is dead by 110, but all depleted while alive.
        assert result.success_rate < 0.05

    def test_dead_paths_stop_spending(self):
        """After household death the portfolio freezes instead of being
        drained by phantom spending."""
        params = _flat_market_input(
            initial_capital=1_000_000,
            annual_spending=50_000,
            current_age=95,
            max_age=120,
            include_mortality=True,
            n_simulations=300,
        )
        result = MonteCarloSimulator(params).run()
        # Most paths die within ~10 years; their estates should retain most
        # of the starting capital rather than being spent down to zero.
        assert result.median_final_value > 300_000

    def test_spouse_income_included_when_mortality_disabled(self):
        """Spouse income must flow into the household even with mortality off."""
        params = _flat_market_input(
            social_security_monthly=1_000,
            social_security_start_age=62,
            filing_status="married_filing_jointly",
            has_spouse=True,
            spouse=SpouseInput(
                age=65,
                social_security_monthly=1_000,
                social_security_start_age=62,
            ),
        )
        result = MonteCarloSimulator(params).run()
        assert result.year_breakdown[0].social_security == pytest.approx(
            24_000, rel=0.01
        )

    def test_household_social_security_survivor_rule(self):
        """Both alive -> sum; exactly one alive -> max (survivor); none -> 0."""
        primary_alive = np.array([True, True, False, False])
        spouse_alive = np.array([True, False, True, False])
        ss = _household_social_security(
            4, 24_000.0, 12_000.0, primary_alive, spouse_alive
        )
        np.testing.assert_allclose(ss, [36_000.0, 24_000.0, 24_000.0, 0.0])

    def test_household_social_security_single(self):
        primary_alive = np.array([True, False])
        ss = _household_social_security(2, 24_000.0, 0.0, primary_alive, None)
        np.testing.assert_allclose(ss, [24_000.0, 0.0])


class TestInflation:
    def test_social_security_cola(self):
        """SS benefits should grow with the assumed inflation rate."""
        params = _flat_market_input(
            social_security_monthly=1_000,
            social_security_start_age=62,
            inflation_rate=0.03,
        )
        result = MonteCarloSimulator(params).run()
        assert result.year_breakdown[0].social_security == pytest.approx(
            12_000, rel=0.01
        )
        assert result.year_breakdown[5].social_security == pytest.approx(
            12_000 * 1.03**5, rel=0.01
        )

    def test_spending_grows_with_inflation(self):
        params = _flat_market_input(inflation_rate=0.03)
        result = MonteCarloSimulator(params).run()
        wd0 = result.year_breakdown[0].withdrawal
        wd5 = result.year_breakdown[5].withdrawal
        # Withdrawal covers spending plus taxes; spending alone grows at 3%.
        assert wd5 / wd0 >= 1.03**5 * 0.95

    def test_zero_inflation_keeps_spending_flat(self):
        params = _flat_market_input(inflation_rate=0.0)
        result = MonteCarloSimulator(params).run()
        wd0 = result.year_breakdown[0].withdrawal
        wd5 = result.year_breakdown[5].withdrawal
        assert wd5 == pytest.approx(wd0, rel=0.02)

    def test_inflation_rate_defaults_on(self):
        assert SimulationInput(
            initial_capital=100_000, annual_spending=10_000, current_age=65
        ).inflation_rate == pytest.approx(0.025)


class TestTaxAdvantagedDividends:
    def _tracker(self) -> HoldingsTracker:
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            Holding(account_type="roth_ira", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="vt", balance=100_000),
        ]
        return HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            rng=np.random.default_rng(0),
        )

    def test_tax_advantaged_dividends_reinvest(self):
        """Traditional and Roth holdings grow at total return (dividends
        reinvested); taxable holdings grow at price-only return because their
        dividends are paid out as cash income."""
        tracker = self._tracker()
        trad, roth, taxable = tracker.holdings
        price = trad.price_growth[:, 0]
        divs = trad.div_yields[:, 0]

        tracker.apply_growth(0)

        np.testing.assert_allclose(trad.balance, 100_000 * (1 + price + divs))
        np.testing.assert_allclose(roth.balance, 100_000 * (1 + price + divs))
        np.testing.assert_allclose(taxable.balance, 100_000 * (1 + price))

    def test_apply_growth_freezes_dead_paths(self):
        tracker = self._tracker()
        alive = np.zeros(10, dtype=bool)
        alive[:5] = True
        tracker.apply_growth(0, alive=alive)
        for holding in tracker.holdings:
            np.testing.assert_allclose(holding.balance[~alive[: len(alive)]], 100_000)

    def test_withdraw_skips_rmd_for_dead_paths(self):
        tracker = self._tracker()
        alive = np.zeros(10, dtype=bool)
        alive[:5] = True
        result = tracker.withdraw(np.zeros(10), age=80, alive=alive)
        assert np.all(result["traditional_rmd"][~alive] == 0)
        assert np.all(result["traditional_rmd"][alive] > 0)
        trad = tracker.holdings[0]
        np.testing.assert_allclose(trad.balance[~alive], 100_000)


class TestHoldingsModeTaxes:
    def test_taxes_are_deducted_from_holdings_portfolio(self):
        """Holdings-mode taxes must actually leave the portfolio, mirroring
        legacy mode's gross withdrawal accounting."""
        params = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=1_000_000)
            ],
            annual_spending=50_000,
            current_age=65,
            max_age=70,
            state="TX",
            filing_status="single",
            n_simulations=100,
            random_seed=7,
            include_mortality=False,
            inflation_rate=0.0,
        )
        simulator = MonteCarloSimulator(params)

        fixed_tax = 10_000.0

        def fake_taxes(**kwargs):
            n = len(kwargs["capital_gains_array"])
            return {
                "total_tax": np.full(n, fixed_tax),
                "federal_income_tax": np.full(n, fixed_tax),
                "state_income_tax": np.zeros(n),
            }

        simulator.tax_calc.calculate_batch_taxes = fake_taxes

        holding = simulator.tracker.holdings[0]
        price0 = holding.price_growth[:, 0].copy()
        divs0 = holding.div_yields[:, 0].copy()

        result = simulator.run()

        # Year 0: withdraw spending need + taxes, then grow at total return
        # (traditional dividends reinvest).
        expected_year1 = (1_000_000 - 50_000 - fixed_tax) * (1 + price0 + divs0)
        np.testing.assert_allclose(simulator._paths[:, 1], expected_year1, rtol=1e-9)
        assert result.total_taxes_median == pytest.approx(fixed_tax * 5, rel=1e-6)


class TestNormalModelDividendYield:
    def test_dividend_yield_input_is_used(self):
        _, divs = generate_blended_returns(
            n_simulations=4,
            n_years=3,
            stock_allocation=1.0,
            method="normal",
            dividend_yield=0.05,
            rng=np.random.default_rng(0),
        )
        np.testing.assert_allclose(divs, 0.05)

    def test_dividend_yield_affects_price_mean(self):
        price, _ = generate_blended_returns(
            n_simulations=2_000,
            n_years=10,
            stock_allocation=1.0,
            method="normal",
            expected_stock_return=0.07,
            stock_volatility=0.0,
            dividend_yield=0.05,
            rng=np.random.default_rng(0),
        )
        np.testing.assert_allclose(price, 0.02, atol=1e-9)
