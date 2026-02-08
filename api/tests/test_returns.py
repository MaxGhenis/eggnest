"""Tests for returns module with separate price and dividend returns."""

import numpy as np

from eggnest.returns import (
    SP500_DIVIDEND_ARRAY,
    SP500_PRICE_ARRAY,
    generate_blended_returns,
    get_return_arrays,
)


def test_generate_blended_returns_returns_tuple():
    """generate_blended_returns should return (price_growth, dividend_yields)."""
    price_ret, div_ret = generate_blended_returns(
        n_simulations=100,
        n_years=10,
        stock_allocation=0.8,
    )
    assert isinstance(price_ret, np.ndarray)
    assert isinstance(div_ret, np.ndarray)
    assert price_ret.shape == (100, 10)
    assert div_ret.shape == (100, 10)


def test_price_and_dividend_separate():
    """Price returns and dividends should be separate, not double-counted."""
    price_ret, div_ret = generate_blended_returns(
        n_simulations=1000,
        n_years=30,
        stock_allocation=1.0,
        stock_index="sp500",
    )

    # Price returns can be negative
    assert np.any(price_ret < 0)

    # Dividend returns should always be positive (or at least non-negative)
    assert np.all(div_ret >= 0)

    # Mean dividend yield should be around 2-5% historically
    mean_div = np.mean(div_ret)
    assert 0.01 < mean_div < 0.10


def test_vt_bnd_indexes():
    """VT and BND indexes should work."""
    price_ret, div_ret = generate_blended_returns(
        n_simulations=100,
        n_years=10,
        stock_allocation=0.6,
        stock_index="vt",
        bond_index="bnd",
    )
    assert price_ret.shape == (100, 10)
    assert div_ret.shape == (100, 10)


def test_get_return_arrays_alignment():
    """Return arrays should be aligned to same length when mixing indexes."""
    stock_price, stock_div, bond_price, bond_div = get_return_arrays(
        stock_index="vt",
        bond_index="bnd",
    )

    # All should have same length
    assert len(stock_price) == len(stock_div)
    assert len(stock_price) == len(bond_price)
    assert len(stock_price) == len(bond_div)


def test_nominal_returns_not_inflation_adjusted():
    """S&P 500 nominal returns should include years with >30% returns."""
    # In nominal terms, 1954 had ~52% total return
    total_returns = SP500_PRICE_ARRAY + SP500_DIVIDEND_ARRAY
    assert np.max(total_returns) > 0.40  # Should have some very high nominal years
