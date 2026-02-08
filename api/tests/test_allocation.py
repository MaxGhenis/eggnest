"""Tests for asset allocation comparison functionality."""

import numpy as np
import pytest

from eggnest.returns import (
    SP500_DIVIDEND_RETURNS,
    SP500_PRICE_RETURNS,
    TREASURY_RETURNS,
    generate_blended_returns,
)


class TestBondReturns:
    """Test bond returns data."""

    def test_bond_returns_exists(self):
        """Test that bond returns data exists."""
        assert TREASURY_RETURNS is not None
        assert len(TREASURY_RETURNS) > 0

    def test_bond_returns_same_years_as_stocks(self):
        """Test that bond returns cover the same years as stock returns."""
        stock_years = set(SP500_PRICE_RETURNS.keys())
        bond_years = set(TREASURY_RETURNS.keys())
        assert stock_years == bond_years

    def test_bond_returns_reasonable_range(self):
        """Test that bond returns are in a reasonable range (-30% to +45%)."""
        for year, ret in TREASURY_RETURNS.items():
            assert -0.30 <= ret <= 0.45, f"Year {year} bond return {ret} out of range"

    def test_bond_mean_return_reasonable(self):
        """Test that mean bond return is in a reasonable range (nominal ~5%)."""
        returns = list(TREASURY_RETURNS.values())
        mean_return = np.mean(returns)
        # Historical nominal bond returns average around 5% (2% real + 3% inflation)
        assert (
            0.02 <= mean_return <= 0.08
        ), f"Mean bond return {mean_return} out of expected range"

    def test_bond_volatility_lower_than_stocks(self):
        """Test that bonds are less volatile than stocks."""
        bond_std = np.std(list(TREASURY_RETURNS.values()))
        stock_std = np.std(list(SP500_PRICE_RETURNS.values()))
        # Bonds should be less volatile than stocks
        assert bond_std < stock_std


class TestBlendedReturns:
    """Test blended stock/bond returns generation."""

    def test_0_percent_stocks(self):
        """Test that 0% stocks (100% bonds) has lower volatility."""
        rng = np.random.default_rng(42)
        bond_price, bond_div = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.0,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        stock_price, stock_div = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=1.0,
            method="bootstrap",
            rng=rng,
        )

        bond_std = np.std(bond_price)
        stock_std = np.std(stock_price)

        # All bonds should be less volatile than all stocks
        assert bond_std < stock_std

    def test_60_40_allocation(self):
        """Test 60/40 allocation produces intermediate volatility."""
        rng = np.random.default_rng(42)
        price_60_40, _ = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.6,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        price_100_0, _ = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=1.0,
            method="bootstrap",
            rng=rng,
        )

        rng = np.random.default_rng(42)
        price_0_100, _ = generate_blended_returns(
            n_simulations=1000,
            n_years=30,
            stock_allocation=0.0,
            method="bootstrap",
            rng=rng,
        )

        std_60_40 = np.std(price_60_40)
        std_100_0 = np.std(price_100_0)
        std_0_100 = np.std(price_0_100)

        # 60/40 should be between all stocks and all bonds
        assert std_0_100 < std_60_40 < std_100_0

    def test_blended_returns_shape(self):
        """Test that blended returns have correct shape."""
        rng = np.random.default_rng(42)
        price_ret, div_ret = generate_blended_returns(
            n_simulations=100,
            n_years=25,
            stock_allocation=0.7,
            rng=rng,
        )
        assert price_ret.shape == (100, 25)
        assert div_ret.shape == (100, 25)

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
        price_ret, div_ret = generate_blended_returns(
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
        assert price_ret.shape == (100, 20)
        assert div_ret.shape == (100, 20)

        # Mean should be between bond and stock returns
        mean_return = np.mean(price_ret)
        # 80% * 7% + 20% * 2% = 6% (but this is price return, so a bit lower)
        assert 0.02 <= mean_return <= 0.10


class TestHistoricalData:
    """Test historical data is reasonable."""

    def test_sp500_stats_reasonable(self):
        """Test that S&P 500 stats are reasonable."""
        total_returns = [
            SP500_PRICE_RETURNS[y] + SP500_DIVIDEND_RETURNS[y]
            for y in SP500_PRICE_RETURNS.keys()
        ]
        mean_total = np.mean(total_returns)
        std_total = np.std(total_returns)

        # S&P 500 nominal total return averages around 10-12%
        assert 0.08 <= mean_total <= 0.15
        # Volatility around 15-20%
        assert 0.15 <= std_total <= 0.25

    def test_bond_stats_reasonable(self):
        """Test that bond stats are reasonable."""
        bond_mean = np.mean(list(TREASURY_RETURNS.values()))
        bond_std = np.std(list(TREASURY_RETURNS.values()))
        stock_mean = np.mean(list(SP500_PRICE_RETURNS.values()))
        stock_std = np.std(list(SP500_PRICE_RETURNS.values()))

        # Bond mean should be lower than stock mean
        assert (
            bond_mean < stock_mean + 0.05
        )  # Bonds usually lower, allow some tolerance

        # Bond volatility should be lower than stock volatility
        assert bond_std < stock_std
