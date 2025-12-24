"""Tests for holdings-based portfolio model and RMD calculations."""

import pytest
from eggnest.models import Holding, SimulationInput
from eggnest.rmd import calculate_rmd, get_rmd_factor, RMD_START_AGE


class TestHoldingModel:
    """Test the Holding model."""

    def test_holding_creation(self):
        """Test creating a holding."""
        h = Holding(account_type="traditional_401k", fund="vt", balance=100_000)
        assert h.account_type == "traditional_401k"
        assert h.fund == "vt"
        assert h.balance == 100_000

    def test_holding_account_types(self):
        """Test all account types are valid."""
        for account_type in ["traditional_401k", "traditional_ira", "roth_401k", "roth_ira", "taxable"]:
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
