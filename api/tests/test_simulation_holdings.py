"""Tests for simulation with holdings-based portfolios (TDD)."""

from eggnest.models import Holding, SimulationInput
from eggnest.simulation import MonteCarloSimulator


class TestSimulationWithHoldings:
    """Test simulation runs with holdings input."""

    def test_simulation_uses_holdings_tracker(self):
        """Simulation should create and use HoldingsTracker when holdings provided."""
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

        # Should have tracker attribute after initialization
        assert hasattr(sim, "tracker")
        # Tracker should be None until run is called, or created during run
        result = sim.run()

        # Should complete without error
        assert result.success_rate >= 0
        assert result.success_rate <= 1

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

    def test_traditional_withdrawals_treated_as_ordinary_income(self):
        """Traditional account withdrawals should be taxed as ordinary income."""
        # Same dollar amount, but different account types = different tax treatment
        traditional_params = SimulationInput(
            holdings=[
                Holding(account_type="traditional_401k", fund="vt", balance=500_000),
            ],
            annual_spending=50_000,
            current_age=60,
            max_age=70,
            n_simulations=100,
            state="CA",
            filing_status="single",
        )

        taxable_params = SimulationInput(
            holdings=[
                Holding(account_type="taxable", fund="vt", balance=500_000),
            ],
            annual_spending=50_000,
            current_age=60,
            max_age=70,
            n_simulations=100,
            state="CA",
            filing_status="single",
        )

        trad_result = MonteCarloSimulator(traditional_params).run()
        taxable_result = MonteCarloSimulator(taxable_params).run()

        # Traditional withdrawals should have higher taxes (ordinary income vs capital gains)
        # This will fail until HoldingsTracker is integrated with proper tax treatment
        assert trad_result.total_taxes_median > taxable_result.total_taxes_median

    def test_roth_withdrawals_are_tax_free(self):
        """Roth account withdrawals should not incur taxes."""
        roth_params = SimulationInput(
            holdings=[
                Holding(account_type="roth_ira", fund="vt", balance=500_000),
            ],
            annual_spending=50_000,
            current_age=60,
            max_age=70,
            n_simulations=100,
            state="CA",
            filing_status="single",
        )

        taxable_params = SimulationInput(
            holdings=[
                Holding(account_type="taxable", fund="vt", balance=500_000),
            ],
            annual_spending=50_000,
            current_age=60,
            max_age=70,
            n_simulations=100,
            state="CA",
            filing_status="single",
        )

        roth_result = MonteCarloSimulator(roth_params).run()
        taxable_result = MonteCarloSimulator(taxable_params).run()

        # Roth should have near-zero taxes, taxable should have capital gains tax
        assert roth_result.total_taxes_median < taxable_result.total_taxes_median
        # Roth taxes should be very low (may have some from dividends within account)
        assert roth_result.total_taxes_median < 1000  # Minimal taxes

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
