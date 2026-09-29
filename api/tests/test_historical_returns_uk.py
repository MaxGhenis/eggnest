"""Tests for the UK historical return sampler."""

from __future__ import annotations

import numpy as np
import pytest

from eggnest.historical_returns_uk import (
    BLOCK_SIZE,
    UKHistoricalReturns,
    load_history,
    sample_historical_returns,
)


def test_history_loads_expected_range():
    hist = load_history()
    assert isinstance(hist, UKHistoricalReturns)
    assert len(hist) >= 140  # JST R6 provides 1871-2020 (150 years)
    assert hist.year[0] >= 1870 and hist.year[-1] >= 2015
    # Sanity: matches JST published moments (±0.5 pp) for equity.
    assert 0.07 < hist.equity.mean() < 0.13
    assert 0.15 < hist.equity.std() < 0.25


@pytest.mark.parametrize(
    "method",
    ["historical_bootstrap", "historical_block_bootstrap", "historical_sequential"],
)
def test_sampler_shape_and_values_in_history(method):
    rng = np.random.default_rng(123)
    eq, bond, infl, start_years = sample_historical_returns(
        method, n_sims=200, n_years=30, rng=rng
    )
    assert eq.shape == bond.shape == infl.shape == (200, 30)
    # Every sampled value must be a real historical observation.
    hist = load_history()
    assert np.isin(eq, hist.equity).all(), "equity sample outside history"
    assert np.isin(bond, hist.bond).all(), "bond sample outside history"
    assert np.isin(infl, hist.inflation).all(), "inflation sample outside history"
    # Start years only populated for sequential sampling.
    if method == "historical_sequential":
        assert start_years is not None
        assert start_years.shape == (200,)
        assert np.isin(start_years, hist.year).all()
    else:
        assert start_years is None


def test_bootstrap_moments_converge_to_history():
    rng = np.random.default_rng(7)
    eq, bond, infl, _ = sample_historical_returns(
        "historical_bootstrap", n_sims=5000, n_years=30, rng=rng
    )
    hist = load_history()
    # With 5000*30 = 150k draws, bootstrap mean must be within ~1pp of truth.
    assert abs(eq.mean() - hist.equity.mean()) < 0.01
    assert abs(bond.mean() - hist.bond.mean()) < 0.01
    assert abs(infl.mean() - hist.inflation.mean()) < 0.01


def test_sequential_sampling_is_contiguous_history():
    """Each path should be n_years contiguous historical observations
    (wrapping modulo len(history))."""
    rng = np.random.default_rng(0)
    eq, _, _, start_years = sample_historical_returns(
        "historical_sequential", n_sims=50, n_years=40, rng=rng
    )
    hist = load_history()
    n = len(hist)
    assert start_years is not None and start_years.shape == (50,)
    for path_idx in range(len(eq)):
        path = eq[path_idx]
        # Find a start index whose wrapped window matches
        matched = False
        for start in range(n):
            window = hist.equity[(np.arange(40) + start) % n]
            if np.allclose(window, path):
                matched = True
                break
        assert matched, f"sequential path {path_idx} isn't contiguous history"


def test_block_bootstrap_preserves_adjacency():
    """Within a 5-year block, successive years must be adjacent in history."""
    rng = np.random.default_rng(5)
    eq, _, _, _ = sample_historical_returns(
        "historical_block_bootstrap", n_sims=20, n_years=30, rng=rng
    )
    hist = load_history()
    n = len(hist)
    # Map each observed equity value back to its (possibly non-unique) history
    # index, then check that within each block of BLOCK_SIZE the indices
    # increase by exactly 1.
    for path_idx in range(len(eq)):
        path = eq[path_idx]
        block_count = len(path) // BLOCK_SIZE
        for block_idx in range(block_count):
            chunk = path[block_idx * BLOCK_SIZE : (block_idx + 1) * BLOCK_SIZE]
            # Find some start position matching the chunk
            match = False
            for start in range(n - BLOCK_SIZE + 1):
                if np.allclose(hist.equity[start : start + BLOCK_SIZE], chunk):
                    match = True
                    break
            assert match, (
                f"block at path {path_idx}, block {block_idx} isn't a contiguous "
                f"5-year slice of history"
            )


def test_sequential_start_year_matches_equity_path():
    """The start_years array should correspond to the actual first-year equity
    return of each path — i.e. a cohort that retires in 1973 has the 1973
    equity return as year 0."""
    rng = np.random.default_rng(42)
    eq, bond, infl, start_years = sample_historical_returns(
        "historical_sequential", n_sims=25, n_years=10, rng=rng
    )
    hist = load_history()
    year_to_idx = {int(y): i for i, y in enumerate(hist.year)}
    assert start_years is not None
    for path_idx in range(len(eq)):
        y = int(start_years[path_idx])
        hist_idx = year_to_idx[y]
        assert np.isclose(eq[path_idx, 0], hist.equity[hist_idx])
        assert np.isclose(bond[path_idx, 0], hist.bond[hist_idx])
        assert np.isclose(infl[path_idx, 0], hist.inflation[hist_idx])


def test_gaussian_method_raises():
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError):
        sample_historical_returns("gaussian", 10, 10, rng)
