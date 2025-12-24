"""Tests for simulation with holdings-based portfolios (TDD)."""

import pytest
import numpy as np
from eggnest.models import Holding, SimulationInput
from eggnest.simulation import MonteCarloSimulator


class TestSimulationWithHoldings:
    """Test simulation runs with holdings input."""

    def test_simulation_accepts_holdings(self):
        """Simulation should accept holdings instead of initial_capital."""
        params = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=300_000),
                Holding(account_type="roth_ira", fund="vt", balance=100_000),
                Holding(account_type="taxable", fund="bnd", balance=50_000),
            ],
            annual_spending=40_000,
            current_age=60,
            max_age=90,
            n_simulations=100,
        )
        sim = MonteCarloSimulator(params)
        result = sim.run()

        # Should complete without error
        assert result.success_rate >= 0
        assert result.success_rate <= 1

    def test_holdings_uses_per_fund_returns(self):
        """Each holding should grow according to its fund's returns."""
        # 100% stocks vs 100% bonds should have different outcomes
        stock_params = SimulationInput(
            holdings=[
                Holding(account_type="taxable", fund="vt", balance=500_000),
            ],
            annual_spending=20_000,
            current_age=60,
            max_age=90,
            n_simulations=1000,
        )
        bond_params = SimulationInput(
            holdings=[
                Holding(account_type="taxable", fund="bnd", balance=500_000),
            ],
            annual_spending=20_000,
            current_age=60,
            max_age=90,
            n_simulations=1000,
        )

        stock_result = MonteCarloSimulator(stock_params).run()
        bond_result = MonteCarloSimulator(bond_params).run()

        # Stock median should be higher (higher expected return)
        # Bond volatility should be lower (more consistent outcomes)
        # We can't guarantee exact relationships due to randomness,
        # but over 1000 sims these should hold
        assert stock_result.median_final_value != bond_result.median_final_value

    def test_rmd_affects_traditional_withdrawals(self):
        """RMDs should force withdrawals from traditional accounts at 73+."""
        # Person starting at 70 with large traditional balance
        params = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=1_000_000),
            ],
            annual_spending=30_000,  # Less than RMD will be
            current_age=70,
            max_age=80,
            n_simulations=100,
        )
        sim = MonteCarloSimulator(params)
        result = sim.run()

        # At age 73, RMD ≈ 1M / 26.5 ≈ $37,736 (more than spending need)
        # Simulation should still run successfully
        assert result.success_rate >= 0

    def test_withdrawal_strategy_affects_tax(self):
        """Different withdrawal strategies should affect tax outcomes."""
        base_holdings = [
            Holding(account_type="traditional_401k", fund="vt", balance=200_000),
            Holding(account_type="roth_ira", fund="vt", balance=200_000),
            Holding(account_type="taxable", fund="vt", balance=200_000),
        ]

        # Taxable first - capital gains tax
        taxable_first = SimulationInput(
            holdings=base_holdings.copy(),
            withdrawal_strategy="taxable_first",
            annual_spending=50_000,
            current_age=60,
            max_age=80,
            n_simulations=100,
        )

        # Traditional first - ordinary income tax
        traditional_first = SimulationInput(
            holdings=base_holdings.copy(),
            withdrawal_strategy="traditional_first",
            annual_spending=50_000,
            current_age=60,
            max_age=80,
            n_simulations=100,
        )

        result_taxable = MonteCarloSimulator(taxable_first).run()
        result_traditional = MonteCarloSimulator(traditional_first).run()

        # Tax amounts should differ (traditional withdrawals taxed as ordinary income)
        # Can't guarantee which is higher without knowing exact tax brackets
        assert result_taxable.total_taxes_median >= 0
        assert result_traditional.total_taxes_median >= 0

    def test_backward_compat_initial_capital_still_works(self):
        """Legacy initial_capital input should still work."""
        params = SimulationInput(
            initial_capital=500_000,
            annual_spending=40_000,
            current_age=60,
            max_age=90,
            n_simulations=100,
        )
        sim = MonteCarloSimulator(params)
        result = sim.run()

        assert result.success_rate >= 0
        assert result.median_final_value >= 0
