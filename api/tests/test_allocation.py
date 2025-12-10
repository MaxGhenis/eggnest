"""Tests for asset allocation comparison functionality."""

import pytest
import numpy as np

from eggnest.returns import (
    HISTORICAL_REAL_RETURNS,
    HISTORICAL_BOND_RETURNS,
    generate_returns,
    generate_blended_returns,
    get_historical_stats,
)


class TestBondReturns:
    """Test bond returns data."""

    def test_bond_returns_exists(self):
        """Test that bond returns data exists."""
        assert HISTORICAL_BOND_RETURNS is not None
        assert len(HISTORICAL_BOND_RETURNS) > 0

    def test_bond_returns_same_years_as_stocks(self):
        """Test that bond returns cover the same years as stock returns."""
        stock_years = set(HISTORICAL_REAL_RETURNS.keys())
        bond_years = set(HISTORICAL_BOND_RETURNS.keys())
        assert stock_years == bond_years

    def test_bond_returns_reasonable_range(self):
        """Test that bond returns are in a reasonable range (-30% to +30%)."""
        for year, ret in HISTORICAL_BOND_RETURNS.items():
            assert -0.30 <= ret <= 0.35, f"Year {year} bond return {ret} out of range"

    def test_bond_mean_return_reasonable(self):
        """Test that mean bond return is historically accurate (~2-3% real)."""
        returns = list(HISTORICAL_BOND_RETURNS.values())
        mean_return = np.mean(returns)
        # Historical real bond returns average around 2%
        assert 0.00 <= mean_return <= 0.05, f"Mean bond return {mean_return} out of expected range"

    def test_bond_volatility_lower_than_stocks(self):
        """Test that bonds are less volatile than stocks."""
        bond_std = np.std(list(HISTORICAL_BOND_RETURNS.values()))
        stock_std = np.std(list(HISTORICAL_REAL_RETURNS.values()))
        # Bonds should be less volatile than stocks
        assert bond_std < stock_std


class TestBlendedReturns:
    """Test blended stock/bond returns generation."""

    def test_100_percent_stocks(self):
        """Test that 100% stocks matches pure stock returns."""
        rng = np.random.default_rng(42)
        stock_returns = generate_returns(
            n_simulations=100,
            n_years=10,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)  # Reset RNG
        blended_returns = generate_blended_returns(
            n_simulations=100,
            n_years=10,
            stock_allocation=1.0,
            method="bootstrap",
            rng=rng,
        )

        np.testing.assert_array_almost_equal(stock_returns, blended_returns)

    def test_0_percent_stocks(self):
        """Test that 0% stocks (100% bonds) has lower volatility."""
        rng = np.random.default_rng(42)
        bond_returns = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.0,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        stock_returns = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=1.0,
            method="bootstrap",
            rng=rng,
        )

        bond_std = np.std(bond_returns)
        stock_std = np.std(stock_returns)

        # All bonds should be less volatile than all stocks
        assert bond_std < stock_std

    def test_60_40_allocation(self):
        """Test 60/40 allocation produces intermediate volatility."""
        rng = np.random.default_rng(42)
        returns_60_40 = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.6,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        returns_100_0 = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=1.0,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        returns_0_100 = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.0,
            method="bootstrap",
            rng=rng,
        )

        std_60_40 = np.std(returns_60_40)
        std_100_0 = np.std(returns_100_0)
        std_0_100 = np.std(returns_0_100)

        # 60/40 should be between all stocks and all bonds
        assert std_0_100 < std_60_40 < std_100_0

    def test_blended_returns_shape(self):
        """Test that blended returns have correct shape."""
        rng = np.random.default_rng(42)
        returns = generate_blended_returns(
            n_simulations=100,
            n_years=25,
            stock_allocation=0.7,
            rng=rng,
        )
        assert returns.shape == (100, 25)

    def test_allocation_bounds(self):
        """Test that allocation must be between 0 and 1."""
        rng = np.random.default_rng(42)

        with pytest.raises(ValueError):
            generate_blended_returns(
                n_simulations=10,
                n_years=5,
                stock_allocation=1.5,  # Invalid
                rng=rng,
            )

        with pytest.raises(ValueError):
            generate_blended_returns(
                n_simulations=10,
                n_years=5,
                stock_allocation=-0.1,  # Invalid
                rng=rng,
            )

    def test_normal_method_with_allocation(self):
        """Test that normal method works with allocation."""
        rng = np.random.default_rng(42)
        returns = generate_blended_returns(
            n_simulations=100,
            n_years=20,
            stock_allocation=0.8,
            method="normal",
            expected_stock_return=0.07,
            stock_volatility=0.16,
            expected_bond_return=0.02,
            bond_volatility=0.08,
            rng=rng,
        )
        assert returns.shape == (100, 20)

        # Mean should be between bond and stock returns
        mean_return = np.mean(returns)
        # 80% * 7% + 20% * 2% = 6%
        assert 0.04 <= mean_return <= 0.08


class TestHistoricalStatsWithBonds:
    """Test historical stats include bond data."""

    def test_get_historical_stats_includes_bonds(self):
        """Test that historical stats include bond return info."""
        stats = get_historical_stats()

        assert "stock_mean" in stats
        assert "stock_std" in stats
        assert "bond_mean" in stats
        assert "bond_std" in stats

    def test_bond_stats_reasonable(self):
        """Test that bond stats are reasonable."""
        stats = get_historical_stats()

        # Bond mean should be lower than stock mean
        assert stats["bond_mean"] < stats["stock_mean"]

        # Bond volatility should be lower than stock volatility
        assert stats["bond_std"] < stats["stock_std"]
