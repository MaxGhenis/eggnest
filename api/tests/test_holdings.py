"""Tests for holdings-based portfolio model and RMD calculations."""

import numpy as np
import pytest

from eggnest.holdings import HoldingsTracker, create_holdings_tracker
from eggnest.models import Holding, SimulationInput
from eggnest.returns import generate_blended_returns
from eggnest.rmd import RMD_START_AGE, calculate_rmd, get_rmd_factor
from eggnest.withdrawal_policies import resolve_withdrawal_policy


class TestHoldingModel:
    """Test the Holding model."""

    def test_holding_creation(self):
        """Test creating a holding."""
        h = Holding(account_type="traditional_401k", fund="vt", balance=100_000)
        assert h.account_type == "traditional_401k"
        assert h.fund == "vt"
        assert h.balance == 100_000
        assert h.cost_basis is None

    def test_taxable_holding_accepts_cost_basis(self):
        """Taxable holdings may optionally include tax basis."""
        h = Holding(
            account_type="taxable",
            fund="vt",
            balance=100_000,
            cost_basis=80_000,
        )
        assert h.cost_basis == 80_000

    def test_cost_basis_validation(self):
        """Cost basis must be valid and only apply to taxable holdings."""
        with pytest.raises(ValueError, match="cost_basis cannot exceed"):
            Holding(
                account_type="taxable",
                fund="vt",
                balance=100_000,
                cost_basis=120_000,
            )

        with pytest.raises(ValueError, match="cost_basis is only valid"):
            Holding(
                account_type="roth_ira",
                fund="vt",
                balance=100_000,
                cost_basis=50_000,
            )

    def test_holding_account_types(self):
        """Test all account types are valid."""
        for account_type in [
            "traditional_401k",
            "traditional_ira",
            "roth_401k",
            "roth_ira",
            "taxable",
        ]:
            h = Holding(account_type=account_type, fund="vt", balance=1000)
            assert h.account_type == account_type

    def test_holding_fund_types(self):
        """Test all fund types are valid."""
        for fund in ["vt", "sp500", "bnd", "treasury"]:
            h = Holding(account_type="taxable", fund=fund, balance=1000)
            assert h.fund == fund


class TestSimulationInputWithHoldings:
    """Test SimulationInput with holdings."""

    def test_total_capital_from_holdings(self):
        """Test total_capital property with holdings."""
        inp = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=300_000),
                Holding(account_type="traditional_401k", fund="bnd", balance=200_000),
                Holding(account_type="roth_401k", fund="sp500", balance=150_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.total_capital == 650_000

    def test_total_capital_from_initial_capital(self):
        """Test total_capital property with legacy initial_capital."""
        inp = SimulationInput(
            initial_capital=500_000,
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.total_capital == 500_000

    def test_has_traditional_accounts(self):
        """Test has_traditional_accounts property."""
        inp = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=100_000),
                Holding(account_type="roth_ira", fund="vt", balance=50_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.has_traditional_accounts is True

        inp_roth_only = SimulationInput(
            holdings=[
                Holding(account_type="roth_401k", fund="vt", balance=100_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        assert inp_roth_only.has_traditional_accounts is False

    def test_has_roth_accounts(self):
        """Test has_roth_accounts property."""
        inp = SimulationInput(
            holdings=[
                Holding(account_type="roth_ira", fund="vt", balance=100_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.has_roth_accounts is True
    def test_get_balance_by_account_type(self):
        """Test getting balance by account type."""
        inp = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=200_000),
                Holding(account_type="traditional_401k", fund="bnd", balance=100_000),
                Holding(account_type="roth_ira", fund="vt", balance=50_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.get_balance_by_account_type("traditional_401k") == 300_000
        assert inp.get_balance_by_account_type("roth_ira") == 50_000
        assert inp.get_balance_by_account_type("taxable") == 0

    def test_withdrawal_strategy_default(self):
        """Test default withdrawal strategy."""
        inp = SimulationInput(
            initial_capital=100_000,
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.withdrawal_strategy == "taxable_first"

    def test_return_index_defaults_use_long_history_baseline(self):
        """Simple-mode defaults should use the long-history proxy indexes."""
        inp = SimulationInput(
            initial_capital=100_000,
            annual_spending=60_000,
            current_age=60,
        )
        assert inp.stock_index == "sp500"
        assert inp.bond_index == "treasury"


class TestWithdrawalPolicies:
    """Test withdrawal policy resolution and behavior."""

    def test_resolve_unknown_strategy_defaults_to_taxable_first(self):
        """Unknown strategies should fall back to the default policy."""
        policy = resolve_withdrawal_policy("unknown_strategy")
        assert policy.name == "taxable_first"

    def test_pro_rata_policy_withdraws_proportionally(self):
        """Pro-rata policy should spread withdrawals across account types."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            Holding(account_type="roth_ira", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="vt", balance=100_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="pro_rata",
        )

        result = tracker.withdraw(np.full(10, 30_000), age=60, include_rmd=False)

        assert np.allclose(result["traditional"], 10_000)
        assert np.allclose(result["roth"], 10_000)
        assert np.allclose(result["taxable"], 10_000)


class TestRMD:
    """Test RMD calculations."""

    def test_rmd_before_start_age(self):
        """Test RMD is 0 before RMD start age."""
        assert calculate_rmd(500_000, 65) == 0
        assert calculate_rmd(500_000, 72) == 0

    def test_rmd_at_start_age(self):
        """Test RMD at age 73."""
        rmd = calculate_rmd(500_000, 73)
        # 500,000 / 26.5 = 18,867.92
        assert abs(rmd - 18_867.92) < 1

    def test_rmd_increases_with_age(self):
        """Test RMD factor increases with age (shorter distribution period)."""
        factor_75 = get_rmd_factor(75)
        factor_85 = get_rmd_factor(85)
        factor_95 = get_rmd_factor(95)

        assert factor_75 < factor_85 < factor_95

    def test_rmd_zero_balance(self):
        """Test RMD is 0 with zero balance."""
        assert calculate_rmd(0, 80) == 0

    def test_rmd_factor_before_start(self):
        """Test RMD factor is 0 before start age."""
        assert get_rmd_factor(60) == 0
        assert get_rmd_factor(72) == 0

    def test_rmd_start_age_constant(self):
        """Test RMD start age is 73 per SECURE 2.0."""
        assert RMD_START_AGE == 73


class TestHoldingsTracker:
    """Test the HoldingsTracker class."""

    def test_tracker_creation(self):
        """Test creating a holdings tracker."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=300_000),
            Holding(account_type="roth_ira", fund="sp500", balance=100_000),
            Holding(account_type="taxable", fund="bnd", balance=50_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=100,
            n_years=30,
        )
        assert len(tracker.holdings) == 3
        # All simulations start with same balances
        assert np.all(tracker.total_balance == 450_000)

    def test_balance_by_category(self):
        """Test getting balance by account category."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=200_000),
            Holding(account_type="traditional_ira", fund="bnd", balance=100_000),
            Holding(account_type="roth_401k", fund="vt", balance=50_000),
            Holding(account_type="taxable", fund="sp500", balance=25_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
        )
        assert np.all(tracker.traditional_balance == 300_000)
        assert np.all(tracker.roth_balance == 50_000)

    def test_convert_traditional_to_roth_preserves_total_balance(self):
        """Roth conversions should move assets between tax buckets, not out of the portfolio."""
        tracker = HoldingsTracker(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            ],
            n_simulations=10,
            n_years=5,
        )

        converted = tracker.convert_traditional_to_roth(np.full(10, 25_000.0))

        assert np.allclose(converted, 25_000.0)
        assert np.allclose(tracker.traditional_balance, 75_000.0)
        assert np.allclose(tracker.roth_balance, 25_000.0)
        assert np.allclose(tracker.total_balance, 100_000.0)

    def test_apply_growth(self):
        """Test applying growth to holdings."""
        holdings = [
            Holding(account_type="taxable", fund="vt", balance=100_000),
        ]
        rng = np.random.default_rng(42)
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=100,
            n_years=10,
            rng=rng,
        )
        initial = tracker.total_balance.copy()
        tracker.apply_growth(year=0)
        # Balances should have changed (some up, some down)
        assert not np.allclose(tracker.total_balance, initial)

    @pytest.mark.parametrize("return_method", ["bootstrap", "block_bootstrap"])
    def test_returns_preserve_cross_asset_pairing(self, return_method):
        """Holdings mode should preserve same-year stock/bond pairings."""
        holdings = [
            Holding(account_type="taxable", fund="sp500", balance=600_000),
            Holding(account_type="taxable", fund="treasury", balance=400_000),
        ]

        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=25,
            n_years=12,
            return_method=return_method,
            rng=np.random.default_rng(42),
        )
        blended_price, blended_div = generate_blended_returns(
            n_simulations=25,
            n_years=12,
            stock_allocation=0.6,
            method=return_method,
            stock_index="sp500",
            bond_index="treasury",
            rng=np.random.default_rng(42),
        )

        tracker_price = (
            0.6 * tracker._fund_returns["sp500"][0]
            + 0.4 * tracker._fund_returns["treasury"][0]
        )
        tracker_div = (
            0.6 * tracker._fund_returns["sp500"][1]
            + 0.4 * tracker._fund_returns["treasury"][1]
        )

        assert np.allclose(tracker_price, blended_price)
        assert np.allclose(tracker_div, blended_div)

    def test_get_dividends_by_category(self):
        """Test getting dividends by account category."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="bnd", balance=50_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=100,
            n_years=10,
        )
        divs = tracker.get_dividends(year=0)
        assert "traditional" in divs
        assert "roth" in divs
        assert "taxable" in divs
        # Traditional and taxable should have dividends
        assert np.all(divs["traditional"] >= 0)
        assert np.all(divs["taxable"] >= 0)
        # Roth should be 0 (no holdings)
        assert np.all(divs["roth"] == 0)

    def test_withdraw_taxable_first(self):
        """Test taxable-first withdrawal strategy."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="vt", balance=50_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="taxable_first",
        )
        # Withdraw 30k (less than taxable balance)
        result = tracker.withdraw(np.full(10, 30_000), age=60)
        assert np.allclose(result["taxable"], 30_000)
        assert np.allclose(result["traditional"], 0)
        assert np.allclose(tracker.taxable_balance, 20_000)
        assert np.allclose(tracker.traditional_balance, 100_000)

    def test_withdraw_cascades_to_next_account(self):
        """Test withdrawal cascades when first account is depleted."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=100_000),
            Holding(account_type="taxable", fund="vt", balance=30_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="taxable_first",
        )
        # Withdraw 50k (more than taxable balance)
        result = tracker.withdraw(np.full(10, 50_000), age=60)
        assert np.allclose(result["taxable"], 30_000)  # All of taxable
        assert np.allclose(result["traditional"], 20_000)  # Remainder from traditional
        assert np.allclose(tracker.taxable_balance, 0)
        assert np.allclose(tracker.traditional_balance, 80_000)

    def test_rmd_forces_traditional_withdrawal(self):
        """Test RMD forces withdrawal from traditional at age 73+."""
        holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=500_000),
            Holding(account_type="taxable", fund="vt", balance=100_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="taxable_first",
        )
        # At age 73, RMD = 500,000 / 26.5 ≈ 18,868
        result = tracker.withdraw(np.full(10, 10_000), age=73)
        # RMD should be taken even though we only need 10k
        assert np.all(result["traditional_rmd"] > 10_000)
        # No additional taxable withdrawal needed since RMD covers spending
        assert np.allclose(result["taxable"], 0)

    def test_taxable_cash_is_withdrawn_before_taxable_holdings(self):
        """Excess RMD cash should be spendable without realizing new capital gains."""
        holdings = [
            Holding(account_type="taxable", fund="vt", balance=20_000),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="taxable_first",
        )
        tracker.deposit_to_taxable(np.full(10, 5_000))

        result = tracker.withdraw(np.full(10, 7_000), age=60, include_rmd=False)

        assert np.allclose(result["taxable_cash"], 5_000)
        assert np.allclose(result["taxable"], 2_000)
        assert np.allclose(tracker.cash_balance, 0)
        assert np.allclose(tracker.taxable_balance, 18_000)

    def test_taxable_withdrawal_realizes_only_embedded_gain(self):
        """Taxable sales should realize gains based on proportional cost basis."""
        holdings = [
            Holding(
                account_type="taxable",
                fund="vt",
                balance=100_000,
                cost_basis=80_000,
            ),
        ]
        tracker = HoldingsTracker(
            holdings=holdings,
            n_simulations=10,
            n_years=5,
            withdrawal_strategy="taxable_first",
        )

        result = tracker.withdraw(np.full(10, 50_000), age=60, include_rmd=False)

        assert np.allclose(result["taxable"], 50_000)
        assert np.allclose(result["taxable_capital_gains"], 10_000)
        assert np.allclose(tracker.holdings[0].balance, 50_000)
        assert np.allclose(tracker.holdings[0].cost_basis, 40_000)


class TestCreateHoldingsTracker:
    """Test the create_holdings_tracker factory function."""

    def test_returns_none_for_legacy_input(self):
        """Test returns None when no holdings provided."""
        params = SimulationInput(
            initial_capital=500_000,
            annual_spending=60_000,
            current_age=60,
        )
        tracker = create_holdings_tracker(params, n_simulations=100, n_years=30)
        assert tracker is None

    def test_returns_tracker_for_holdings_input(self):
        """Test returns HoldingsTracker when holdings provided."""
        params = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=300_000),
                Holding(account_type="roth_ira", fund="vt", balance=100_000),
            ],
            annual_spending=60_000,
            current_age=60,
        )
        tracker = create_holdings_tracker(params, n_simulations=100, n_years=30)
        assert tracker is not None
        assert np.all(tracker.total_balance == 400_000)
