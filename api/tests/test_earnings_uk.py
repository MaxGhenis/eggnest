"""Tests for the UK stochastic earnings sampler."""

from __future__ import annotations

import numpy as np
import pytest

from eggnest.earnings_uk import sample_earnings_paths


@pytest.fixture
def working_ages():
    # Someone aged 30 planning to retire at 67, observed for 37 years.
    return np.arange(30, 67, dtype=np.int64)


def test_flat_matches_legacy_behaviour(working_ages):
    rng = np.random.default_rng(0)
    earnings = sample_earnings_paths(
        n_sims=50,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="flat",
        persistent_sigma=0.10,
        transitory_sigma=0.20,
        persistence=0.97,
        peak_growth=0.40,
        rng=rng,
    )
    assert earnings.shape == (50, len(working_ages))
    assert np.all(earnings == 50_000)


def test_zero_after_retirement_age():
    ages = np.arange(60, 75, dtype=np.int64)
    rng = np.random.default_rng(0)
    earnings = sample_earnings_paths(
        n_sims=100,
        ages=ages,
        starting_earnings=60_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=0.10,
        transitory_sigma=0.20,
        persistence=0.97,
        peak_growth=0.40,
        rng=rng,
    )
    retired_cols = np.where(ages >= 67)[0]
    assert np.all(earnings[:, retired_cols] == 0.0)
    # Working columns must have some non-zero variation
    working_cols = np.where(ages < 67)[0]
    assert np.any(earnings[:, working_cols] > 0)


def test_deterministic_profile_is_hump_shaped(working_ages):
    rng = np.random.default_rng(0)
    earnings = sample_earnings_paths(
        n_sims=1,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="deterministic",
        persistent_sigma=0.0,
        transitory_sigma=0.0,
        persistence=0.0,
        peak_growth=0.40,
        rng=rng,
    )
    series = earnings[0]
    # Peaks somewhere near age 52, should be higher than entry and tail.
    peak_idx = int(np.argmax(series))
    peak_age = int(working_ages[peak_idx])
    assert 48 <= peak_age <= 56, f"peak age {peak_age} outside [48,56]"
    assert series[0] < series[peak_idx]


def test_stochastic_year0_is_pinned(working_ages):
    """Every path starts at the user-stated level so the input is meaningful."""
    rng = np.random.default_rng(42)
    earnings = sample_earnings_paths(
        n_sims=200,
        ages=working_ages,
        starting_earnings=55_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=0.10,
        transitory_sigma=0.20,
        persistence=0.97,
        peak_growth=0.40,
        rng=rng,
    )
    assert np.allclose(earnings[:, 0], 55_000)


def test_stochastic_dispersion_grows_with_horizon(working_ages):
    """AR(1) permanent shocks accumulate — cross-sectional variance must grow."""
    rng = np.random.default_rng(7)
    earnings = sample_earnings_paths(
        n_sims=2000,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=0.10,
        transitory_sigma=0.0,  # turn off transitory to isolate persistence
        persistence=0.97,
        peak_growth=0.0,  # flat deterministic component so dispersion is all noise
        rng=rng,
    )
    log = np.log(earnings)
    var_by_year = log.var(axis=0)
    # Year 0 is pinned (variance 0); subsequent years rise monotonically under
    # pure persistent shocks with ρ < 1. Check a few year-on-year increments.
    assert var_by_year[0] < 1e-12
    assert var_by_year[5] > var_by_year[1]
    assert var_by_year[20] > var_by_year[10]


def test_stochastic_moments_in_ballpark(working_ages):
    """At long horizons the log-variance should approach σ_η² / (1 - ρ²)."""
    rng = np.random.default_rng(1)
    sigma_eta = 0.10
    rho = 0.97
    earnings = sample_earnings_paths(
        n_sims=5000,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=sigma_eta,
        transitory_sigma=0.0,
        persistence=rho,
        peak_growth=0.0,
        rng=rng,
    )
    log = np.log(earnings)
    stationary_var = sigma_eta**2 / (1 - rho**2)
    # By age 66 (36 years in) we're reasonably close to the stationary value.
    observed_var = log[:, -1].var()
    # Allow a 40 % tolerance band given finite samples and not-yet-stationary.
    assert 0.6 * stationary_var < observed_var < 1.5 * stationary_var


def test_country_multiplier_increases_spread(working_ages):
    """Scaling σ_η up (e.g. switching UK → US calibration) must fatten the tails."""
    rng_uk = np.random.default_rng(3)
    rng_us = np.random.default_rng(3)
    uk = sample_earnings_paths(
        n_sims=2000,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=0.10,
        transitory_sigma=0.20,
        persistence=0.97,
        peak_growth=0.40,
        rng=rng_uk,
    )
    us = sample_earnings_paths(
        n_sims=2000,
        ages=working_ages,
        starting_earnings=50_000,
        retirement_age=67,
        model="stochastic",
        persistent_sigma=0.14,
        transitory_sigma=0.26,
        persistence=0.97,
        peak_growth=0.55,
        rng=rng_us,
    )
    uk_spread = np.log(uk[:, -1]).std()
    us_spread = np.log(us[:, -1]).std()
    assert us_spread > uk_spread
