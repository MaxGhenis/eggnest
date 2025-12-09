"""Historical return data and bootstrap sampling for Monte Carlo simulation.

Uses real S&P 500 total returns (with dividends) adjusted for inflation.
Data sources:
- Robert Shiller's dataset (1871-present)
- Official CPI data for inflation adjustment

This provides more realistic simulations than normal distribution assumptions
because it preserves:
- Fat tails (extreme events)
- Natural return distributions
- Historical volatility patterns
"""

import numpy as np
from typing import Literal

# S&P 500 Real Total Returns by Year (inflation-adjusted, with dividends)
# Source: Robert Shiller dataset, CPI-adjusted
# Format: {year: real_total_return}
# These are REAL returns (after inflation), so they can be used directly
# in simulations without further inflation adjustment.

HISTORICAL_REAL_RETURNS = {
    # 1928-1939 (Great Depression era)
    1928: 0.3788,
    1929: -0.1466,
    1930: -0.2590,
    1931: -0.3812,
    1932: -0.1221,
    1933: 0.4698,
    1934: 0.0203,
    1935: 0.4391,
    1936: 0.3172,
    1937: -0.3534,
    1938: 0.2541,
    1939: 0.0341,
    # 1940s (WWII and post-war)
    1940: -0.1524,
    1941: -0.1963,
    1942: 0.1080,
    1943: 0.2282,
    1944: 0.1680,
    1945: 0.3445,
    1946: -0.2610,
    1947: -0.0455,
    1948: -0.0177,
    1949: 0.1888,
    # 1950s (Post-war boom)
    1950: 0.2416,
    1951: 0.1334,
    1952: 0.1181,
    1953: 0.0053,
    1954: 0.5256,
    1955: 0.2618,
    1956: 0.0376,
    1957: -0.1392,
    1958: 0.4161,
    1959: 0.0892,
    # 1960s
    1960: 0.0148,
    1961: 0.2563,
    1962: -0.1010,
    1963: 0.2046,
    1964: 0.1502,
    1965: 0.1024,
    1966: -0.1309,
    1967: 0.2009,
    1968: 0.0611,
    1969: -0.1411,
    # 1970s (Stagflation)
    1970: -0.0112,
    1971: 0.0984,
    1972: 0.1537,
    1973: -0.2359,
    1974: -0.3649,
    1975: 0.2831,
    1976: 0.1881,
    1977: -0.1167,
    1978: -0.0175,
    1979: 0.0539,
    # 1980s (Bull market begins)
    1980: 0.1867,
    1981: -0.1437,
    1982: 0.1476,
    1983: 0.1899,
    1984: 0.0181,
    1985: 0.2633,
    1986: 0.1462,
    1987: 0.0203,
    1988: 0.1194,
    1989: 0.2689,
    # 1990s (Tech boom)
    1990: -0.0921,
    1991: 0.2631,
    1992: 0.0450,
    1993: 0.0726,
    1994: -0.0154,
    1995: 0.3417,
    1996: 0.1932,
    1997: 0.3101,
    1998: 0.2667,
    1999: 0.1853,
    # 2000s (Dot-com crash, financial crisis)
    2000: -0.1214,
    2001: -0.1311,
    2002: -0.2336,
    2003: 0.2638,
    2004: 0.0769,
    2005: 0.0149,
    2006: 0.1324,
    2007: 0.0141,
    2008: -0.3849,
    2009: 0.2345,
    # 2010s (Recovery and bull run)
    2010: 0.1278,
    2011: -0.0124,
    2012: 0.1426,
    2013: 0.3017,
    2014: 0.1139,
    2015: -0.0073,
    2016: 0.0954,
    2017: 0.1942,
    2018: -0.0624,
    2019: 0.2880,
    # 2020s
    2020: 0.1612,
    2021: 0.2147,
    2022: -0.2512,
    2023: 0.2256,
    2024: 0.2310,  # Preliminary estimate
}

# Convert to numpy array for efficient sampling
RETURNS_ARRAY = np.array(list(HISTORICAL_REAL_RETURNS.values()))
RETURNS_YEARS = np.array(list(HISTORICAL_REAL_RETURNS.keys()))


def get_historical_stats() -> dict:
    """Get summary statistics for historical returns."""
    returns = RETURNS_ARRAY
    return {
        "mean": float(np.mean(returns)),
        "median": float(np.median(returns)),
        "std": float(np.std(returns)),
        "min": float(np.min(returns)),
        "max": float(np.max(returns)),
        "min_year": int(RETURNS_YEARS[np.argmin(returns)]),
        "max_year": int(RETURNS_YEARS[np.argmax(returns)]),
        "n_years": len(returns),
        "start_year": int(RETURNS_YEARS[0]),
        "end_year": int(RETURNS_YEARS[-1]),
    }


class ReturnGenerator:
    """Generate simulated returns using various methods."""

    def __init__(self, rng: np.random.Generator | None = None):
        """
        Initialize return generator.

        Args:
            rng: NumPy random generator. If None, creates a new one.
        """
        self._rng = rng or np.random.default_rng()

    def bootstrap(
        self,
        n_simulations: int,
        n_years: int,
        block_size: int = 1,
    ) -> np.ndarray:
        """
        Generate returns by bootstrapping from historical data.

        Args:
            n_simulations: Number of simulation paths to generate.
            n_years: Number of years per path.
            block_size: Size of blocks for block bootstrap.
                        1 = standard bootstrap (i.i.d. sampling)
                        >1 = block bootstrap (preserves some autocorrelation)

        Returns:
            Array of shape (n_simulations, n_years) with annual returns.
        """
        n_historical = len(RETURNS_ARRAY)

        if block_size == 1:
            # Standard bootstrap: sample years independently
            indices = self._rng.integers(0, n_historical, size=(n_simulations, n_years))
            return RETURNS_ARRAY[indices]
        else:
            # Block bootstrap: sample contiguous blocks
            # This preserves some autocorrelation structure
            n_blocks = (n_years + block_size - 1) // block_size
            returns = np.zeros((n_simulations, n_years))

            for sim in range(n_simulations):
                year_idx = 0
                for _ in range(n_blocks):
                    # Pick a random starting point
                    start = self._rng.integers(0, n_historical - block_size + 1)
                    block = RETURNS_ARRAY[start : start + block_size]

                    # Copy block to returns (may truncate last block)
                    end_idx = min(year_idx + block_size, n_years)
                    returns[sim, year_idx:end_idx] = block[: end_idx - year_idx]
                    year_idx = end_idx

            return returns

    def normal(
        self,
        n_simulations: int,
        n_years: int,
        mean: float = 0.07,
        std: float = 0.16,
    ) -> np.ndarray:
        """
        Generate returns from normal distribution (legacy method).

        Args:
            n_simulations: Number of simulation paths.
            n_years: Number of years per path.
            mean: Expected annual return.
            std: Annual volatility (standard deviation).

        Returns:
            Array of shape (n_simulations, n_years) with annual returns.
        """
        return self._rng.normal(mean, std, size=(n_simulations, n_years))

    def historical_sequence(
        self,
        n_simulations: int,
        n_years: int,
    ) -> np.ndarray:
        """
        Generate returns by walking through historical sequences.

        Each simulation starts at a random year and walks forward,
        wrapping around if necessary. This preserves exact historical
        sequences and their autocorrelation.

        This is similar to what cFIREsim uses.

        Args:
            n_simulations: Number of simulation paths.
            n_years: Number of years per path.

        Returns:
            Array of shape (n_simulations, n_years) with annual returns.
        """
        n_historical = len(RETURNS_ARRAY)
        returns = np.zeros((n_simulations, n_years))

        # Pick random starting years for each simulation
        start_indices = self._rng.integers(0, n_historical, size=n_simulations)

        for sim in range(n_simulations):
            for year in range(n_years):
                idx = (start_indices[sim] + year) % n_historical
                returns[sim, year] = RETURNS_ARRAY[idx]

        return returns


def generate_returns(
    n_simulations: int,
    n_years: int,
    method: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = "bootstrap",
    block_size: int = 5,
    expected_return: float = 0.07,
    volatility: float = 0.16,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Generate simulated annual returns.

    Args:
        n_simulations: Number of simulation paths.
        n_years: Number of years per path.
        method: Return generation method:
            - "bootstrap": Random sampling from historical years (default)
            - "block_bootstrap": Sample contiguous blocks (preserves autocorrelation)
            - "historical": Walk through actual historical sequences
            - "normal": Normal distribution (legacy, less realistic)
        block_size: Block size for block_bootstrap method.
        expected_return: Mean return for normal method.
        volatility: Std dev for normal method.
        rng: NumPy random generator.

    Returns:
        Array of shape (n_simulations, n_years) with annual returns.
    """
    generator = ReturnGenerator(rng)

    if method == "bootstrap":
        return generator.bootstrap(n_simulations, n_years, block_size=1)
    elif method == "block_bootstrap":
        return generator.bootstrap(n_simulations, n_years, block_size=block_size)
    elif method == "historical":
        return generator.historical_sequence(n_simulations, n_years)
    elif method == "normal":
        return generator.normal(n_simulations, n_years, expected_return, volatility)
    else:
        raise ValueError(f"Unknown method: {method}")
