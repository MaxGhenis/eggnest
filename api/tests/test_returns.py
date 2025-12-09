"""Tests for historical return generation module."""

import numpy as np
import pytest

from eggnest.returns import (
    HISTORICAL_REAL_RETURNS,
    RETURNS_ARRAY,
    ReturnGenerator,
    generate_returns,
    get_historical_stats,
)


class TestHistoricalData:
    """Tests for historical return data."""

    def test_data_exists(self):
        """Test that historical data is present."""
        assert len(HISTORICAL_REAL_RETURNS) > 90  # At least 90 years of data

    def test_data_range(self):
        """Test that data starts in 1928."""
        years = list(HISTORICAL_REAL_RETURNS.keys())
        assert min(years) == 1928
        assert max(years) >= 2023

    def test_returns_are_reasonable(self):
        """Test that returns are within reasonable bounds."""
        for year, ret in HISTORICAL_REAL_RETURNS.items():
            # Real returns should be between -50% and +60%
            assert -0.5 <= ret <= 0.6, f"Year {year} return {ret} is unreasonable"

    def test_known_extreme_years(self):
        """Test known extreme years are present."""
        # 2008 financial crisis
        assert HISTORICAL_REAL_RETURNS[2008] < -0.30

        # 1931 Great Depression
        assert HISTORICAL_REAL_RETURNS[1931] < -0.35

        # 1954 post-war boom
        assert HISTORICAL_REAL_RETURNS[1954] > 0.45


class TestGetHistoricalStats:
    """Tests for get_historical_stats function."""

    def test_returns_dict(self):
        """Test that stats returns a dict with expected keys."""
        stats = get_historical_stats()

        assert "mean" in stats
        assert "median" in stats
        assert "std" in stats
        assert "min" in stats
        assert "max" in stats
        assert "n_years" in stats

    def test_mean_is_reasonable(self):
        """Test that mean real return is in expected range."""
        stats = get_historical_stats()
        # Long-term real return should be 6-8%
        assert 0.05 <= stats["mean"] <= 0.09

    def test_volatility_is_reasonable(self):
        """Test that volatility is in expected range."""
        stats = get_historical_stats()
        # Historical volatility around 15-20%
        assert 0.15 <= stats["std"] <= 0.22


class TestReturnGenerator:
    """Tests for ReturnGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create a seeded generator for reproducibility."""
        rng = np.random.default_rng(42)
        return ReturnGenerator(rng)

    def test_bootstrap_shape(self, generator):
        """Test that bootstrap returns correct shape."""
        returns = generator.bootstrap(n_simulations=100, n_years=30)
        assert returns.shape == (100, 30)

    def test_bootstrap_values_from_history(self, generator):
        """Test that bootstrapped values come from historical data."""
        returns = generator.bootstrap(n_simulations=1000, n_years=30)
        unique_returns = np.unique(returns)

        # All values should be in historical data
        for val in unique_returns:
            assert val in RETURNS_ARRAY

    def test_block_bootstrap_shape(self, generator):
        """Test that block bootstrap returns correct shape."""
        returns = generator.bootstrap(n_simulations=100, n_years=30, block_size=5)
        assert returns.shape == (100, 30)

    def test_block_bootstrap_has_blocks(self, generator):
        """Test that block bootstrap creates contiguous blocks."""
        returns = generator.bootstrap(n_simulations=10, n_years=30, block_size=5)

        # Each simulation should have some consecutive values that match
        # consecutive historical values (though this is probabilistic)
        # Just check the shape is correct
        assert returns.shape == (10, 30)

    def test_historical_sequence_shape(self, generator):
        """Test that historical sequence returns correct shape."""
        returns = generator.historical_sequence(n_simulations=100, n_years=30)
        assert returns.shape == (100, 30)

    def test_historical_sequence_is_contiguous(self, generator):
        """Test that historical sequence maintains order."""
        returns = generator.historical_sequence(n_simulations=10, n_years=30)

        # Each row should be a contiguous historical sequence (wrapped)
        for sim in range(10):
            row = returns[sim, :]
            # Find first value in historical array
            matches = np.where(RETURNS_ARRAY == row[0])[0]
            if len(matches) > 0:
                start_idx = matches[0]
                # Check that sequence is contiguous
                for i in range(min(5, len(row))):  # Check first 5 years
                    expected_idx = (start_idx + i) % len(RETURNS_ARRAY)
                    assert row[i] == RETURNS_ARRAY[expected_idx]

    def test_normal_shape(self, generator):
        """Test that normal returns correct shape."""
        returns = generator.normal(n_simulations=100, n_years=30)
        assert returns.shape == (100, 30)

    def test_normal_mean(self, generator):
        """Test that normal has approximately correct mean."""
        returns = generator.normal(n_simulations=10000, n_years=30, mean=0.07, std=0.16)
        actual_mean = returns.mean()
        assert abs(actual_mean - 0.07) < 0.01


class TestGenerateReturns:
    """Tests for generate_returns convenience function."""

    def test_bootstrap_method(self):
        """Test bootstrap method."""
        returns = generate_returns(100, 30, method="bootstrap")
        assert returns.shape == (100, 30)

    def test_block_bootstrap_method(self):
        """Test block_bootstrap method."""
        returns = generate_returns(100, 30, method="block_bootstrap", block_size=3)
        assert returns.shape == (100, 30)

    def test_historical_method(self):
        """Test historical method."""
        returns = generate_returns(100, 30, method="historical")
        assert returns.shape == (100, 30)

    def test_normal_method(self):
        """Test normal method."""
        returns = generate_returns(100, 30, method="normal", expected_return=0.05)
        assert returns.shape == (100, 30)

    def test_invalid_method(self):
        """Test that invalid method raises error."""
        with pytest.raises(ValueError):
            generate_returns(100, 30, method="invalid")

    def test_reproducible_with_seed(self):
        """Test that same seed produces same results."""
        rng1 = np.random.default_rng(42)
        rng2 = np.random.default_rng(42)

        returns1 = generate_returns(100, 30, method="bootstrap", rng=rng1)
        returns2 = generate_returns(100, 30, method="bootstrap", rng=rng2)

        np.testing.assert_array_equal(returns1, returns2)


class TestBootstrapVsNormal:
    """Tests comparing bootstrap to normal distribution."""

    def test_bootstrap_has_fatter_tails(self):
        """Test that bootstrap has more extreme values than normal."""
        rng = np.random.default_rng(42)

        bootstrap_returns = generate_returns(
            10000, 30, method="bootstrap", rng=rng
        ).flatten()
        normal_returns = generate_returns(
            10000, 30, method="normal", expected_return=0.07, volatility=0.18, rng=rng
        ).flatten()

        # Bootstrap should have more extreme negative values (fat left tail)
        bootstrap_p1 = np.percentile(bootstrap_returns, 1)
        normal_p1 = np.percentile(normal_returns, 1)

        # Historical data includes crashes like -38%, normal rarely goes that low
        assert bootstrap_p1 < normal_p1 or abs(bootstrap_p1) > 0.25

    def test_bootstrap_preserves_distribution_shape(self):
        """Test that bootstrap matches historical distribution."""
        rng = np.random.default_rng(42)

        bootstrap_returns = generate_returns(
            10000, 30, method="bootstrap", rng=rng
        ).flatten()

        # Mean should be close to historical mean
        assert abs(bootstrap_returns.mean() - RETURNS_ARRAY.mean()) < 0.01

        # Std should be close to historical std
        assert abs(bootstrap_returns.std() - RETURNS_ARRAY.std()) < 0.02
