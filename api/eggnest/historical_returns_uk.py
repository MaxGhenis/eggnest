"""UK historical asset-return sampling for Monte Carlo simulation.

Loads the bundled JST macrohistory UK series (equity total return, bond total
return, CPI inflation, 1871-2020) and offers three sampling strategies:

* ``bootstrap``       — iid resample years with replacement. Fast; loses
                        serial correlation.
* ``block_bootstrap`` — resample contiguous 5-year blocks with replacement.
                        Preserves short-run autocorrelation (e.g. 1974-1975
                        stay together).
* ``sequential``      — each path picks a random start year and walks
                        forward ``n_years`` in history (wrapping if needed).
                        Each path is a real historical retirement outcome.

All samplers return a tuple of three arrays each shaped ``(n_sims, n_years)``::

    (equity_return, bond_return, inflation)

Nominal annual returns as decimal fractions (0.10 = +10 %).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent / "data" / "uk_historical_returns.csv"

UKReturnSource = Literal[
    "gaussian",
    "historical_bootstrap",
    "historical_block_bootstrap",
    "historical_sequential",
]

BLOCK_SIZE = 5  # 5-year blocks for block-bootstrap


@dataclass(frozen=True)
class UKHistoricalReturns:
    """Immutable view over the bundled UK historical return series."""

    year: np.ndarray
    equity: np.ndarray  # nominal total return (decimal)
    bond: np.ndarray  # nominal total return (decimal)
    inflation: np.ndarray  # CPI pct change (decimal)

    def __len__(self) -> int:
        return len(self.year)


@lru_cache(maxsize=1)
def load_history() -> UKHistoricalReturns:
    """Load the bundled UK historical series (cached)."""
    df = pd.read_csv(DATA_PATH)
    return UKHistoricalReturns(
        year=df["year"].to_numpy(),
        equity=df["equity_return_nominal"].to_numpy(dtype=np.float64),
        bond=df["bond_return_nominal"].to_numpy(dtype=np.float64),
        inflation=df["cpi_inflation"].to_numpy(dtype=np.float64),
    )


def _bootstrap_indices(
    n_sims: int, n_years: int, n_history: int, rng: np.random.Generator
) -> np.ndarray:
    return rng.integers(0, n_history, size=(n_sims, n_years))


def _block_bootstrap_indices(
    n_sims: int, n_years: int, n_history: int, rng: np.random.Generator
) -> np.ndarray:
    """Moving-block bootstrap: concatenate random contiguous blocks."""
    n_blocks = (n_years + BLOCK_SIZE - 1) // BLOCK_SIZE
    block_starts = rng.integers(0, n_history - BLOCK_SIZE + 1, size=(n_sims, n_blocks))
    offsets = np.arange(BLOCK_SIZE)
    # Shape (n_sims, n_blocks, BLOCK_SIZE)
    idx = block_starts[:, :, None] + offsets[None, None, :]
    idx = idx.reshape(n_sims, n_blocks * BLOCK_SIZE)[:, :n_years]
    return idx


def _sequential_indices(
    n_sims: int, n_years: int, n_history: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Each path picks a random start year and walks forward (wrapping).

    Returns ``(indices, start_positions)`` where ``indices`` is the usual
    ``(n_sims, n_years)`` window matrix and ``start_positions`` is the
    ``(n_sims,)`` array of per-path history indices for the starting year.
    Callers that want calendar years (1871-2020) should look up
    ``load_history().year[start_positions]``.
    """
    starts = rng.integers(0, n_history, size=n_sims)
    offsets = np.arange(n_years)
    idx = (starts[:, None] + offsets[None, :]) % n_history
    return idx, starts


_SAMPLER_DISPATCH = {
    "historical_bootstrap": _bootstrap_indices,
    "historical_block_bootstrap": _block_bootstrap_indices,
    "historical_sequential": _sequential_indices,
}


def sample_historical_returns(
    method: UKReturnSource,
    n_sims: int,
    n_years: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Draw historical (equity, bond, inflation) return paths.

    Returns three ``(n_sims, n_years)`` arrays of nominal annual returns plus
    a fourth ``start_years`` array shaped ``(n_sims,)`` with the calendar-year
    cohort each path started from. ``start_years`` is ``None`` unless
    ``method == "historical_sequential"`` — shuffled / block bootstraps have
    no single interpretable start year.

    Raises ``ValueError`` for ``method == "gaussian"`` (caller handles Gaussian).
    """
    if method == "gaussian":
        raise ValueError("Gaussian returns are not handled by the historical sampler.")
    sampler = _SAMPLER_DISPATCH[method]
    hist = load_history()
    if method == "historical_sequential":
        idx, starts = sampler(n_sims, n_years, len(hist), rng)
        start_years = hist.year[starts].astype(int)
    else:
        idx = sampler(n_sims, n_years, len(hist), rng)
        start_years = None
    return hist.equity[idx], hist.bond[idx], hist.inflation[idx], start_years
