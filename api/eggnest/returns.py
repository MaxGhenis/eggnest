"""Historical return data and bootstrap sampling for Monte Carlo simulation.

Uses real S&P 500 total returns (with dividends) adjusted for inflation.
Data sources:
- Robert Shiller's dataset (1871-present)
- NYU Stern Aswath Damodaran dataset (stocks, bonds, bills 1928-2024)
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

# 10-Year Treasury Bond Real Returns by Year (inflation-adjusted)
# Source: NYU Stern Aswath Damodaran dataset (1928-2024)
# These are REAL returns (after inflation), matching the stock return data above.
# Data from: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html

HISTORICAL_BOND_RETURNS = {
    # 1928-1939 (Great Depression era - bonds did well during deflation)
    1928: 0.0201,
    1929: 0.0360,
    1930: 0.1168,
    1931: 0.0745,
    1932: 0.2125,
    1933: 0.0108,
    1934: 0.0635,
    1935: 0.0144,
    1936: 0.0352,
    1937: -0.0144,
    1938: 0.0719,
    1939: 0.0441,
    # 1940s (WWII and post-war inflation hurt bonds)
    1940: 0.0465,
    1941: -0.1087,
    1942: -0.0618,
    1943: -0.0046,
    1944: 0.0027,
    1945: 0.0152,
    1946: -0.1270,
    1947: -0.0727,
    1948: -0.0101,
    1949: 0.0688,
    # 1950s (Post-war boom, rising rates hurt bonds)
    1950: -0.0519,
    1951: -0.0594,
    1952: 0.0150,
    1953: 0.0337,
    1954: 0.0406,
    1955: -0.0170,
    1956: -0.0509,
    1957: 0.0379,
    1958: -0.0379,
    1959: -0.0430,
    # 1960s
    1960: 0.1014,
    1961: 0.0138,
    1962: 0.0430,
    1963: 0.0004,
    1964: 0.0273,
    1965: -0.0118,
    1966: -0.0053,
    1967: -0.0448,
    1968: -0.0138,
    1969: -0.1056,
    # 1970s (Stagflation - terrible for bonds)
    1970: 0.1059,
    1971: 0.0631,
    1972: -0.0057,
    1973: -0.0464,
    1974: -0.0921,
    1975: -0.0312,
    1976: 0.1060,
    1977: -0.0507,
    1978: -0.0899,
    1979: -0.1114,
    # 1980s (High rates, then bond bull market)
    1980: -0.1378,
    1981: -0.0066,
    1982: 0.2792,
    1983: -0.0057,
    1984: 0.0941,
    1985: 0.2111,
    1986: 0.2293,
    1987: -0.0900,
    1988: 0.0364,
    1989: 0.1247,
    # 1990s (Bond bull market continues)
    1990: 0.0012,
    1991: 0.1159,
    1992: 0.0628,
    1993: 0.1116,
    1994: -0.1043,
    1995: 0.2042,
    1996: -0.0183,
    1997: 0.0810,
    1998: 0.1310,
    1999: -0.1065,
    # 2000s (Flight to safety, financial crisis)
    2000: 0.1283,
    2001: 0.0396,
    2002: 0.1244,
    2003: -0.0148,
    2004: 0.0120,
    2005: -0.0053,
    2006: -0.0057,
    2007: 0.0589,
    2008: 0.1999,
    2009: -0.1347,
    # 2010s (Low rates, QE)
    2010: 0.0686,
    2011: 0.1270,
    2012: 0.0121,
    2013: -0.1045,
    2014: 0.0991,
    2015: 0.0055,
    2016: -0.0136,
    2017: 0.0068,
    2018: -0.0189,
    2019: 0.0719,
    # 2020s (Pandemic, inflation)
    2020: 0.0984,
    2021: -0.1070,
    2022: -0.2281,
    2023: 0.0051,
    2024: -0.0427,
}

# VT (Vanguard Total World Stock ETF) Real Returns
# Source: lazyportfolioetf.com, inflation-adjusted using CPI
# VT launched June 2008, tracks FTSE Global All Cap Index
# Nominal returns adjusted by annual CPI inflation
VT_REAL_RETURNS = {
    2008: -0.4440,  # -42.31% nominal, 3.8% inflation
    2009: 0.3318,   # 32.65% nominal, -0.4% inflation
    2010: 0.1130,   # 13.08% nominal, 1.6% inflation
    2011: -0.1038,  # -7.50% nominal, 3.2% inflation
    2012: 0.1471,   # 17.12% nominal, 2.1% inflation
    2013: 0.2113,   # 22.95% nominal, 1.5% inflation
    2014: 0.0204,   # 3.67% nominal, 1.6% inflation
    2015: -0.0196,  # -1.86% nominal, 0.1% inflation
    2016: 0.0711,   # 8.51% nominal, 1.3% inflation
    2017: 0.2192,   # 24.49% nominal, 2.1% inflation
    2018: -0.1186,  # -9.76% nominal, 2.4% inflation
    2019: 0.2458,   # 26.82% nominal, 1.8% inflation
    2020: 0.1523,   # 16.61% nominal, 1.2% inflation
    2021: 0.1296,   # 18.27% nominal, 4.7% inflation
    2022: -0.2408,  # -18.01% nominal, 8.0% inflation
    2023: 0.1723,   # 22.03% nominal, 4.1% inflation
    2024: 0.1320,   # 16.49% nominal, 2.9% inflation
}

# BND (Vanguard Total Bond Market ETF) Real Returns
# Source: Yahoo Finance/lazyportfolioetf.com, inflation-adjusted using CPI
# BND launched April 2007, tracks Bloomberg US Aggregate Bond Index
# Nominal returns adjusted by annual CPI inflation
BND_REAL_RETURNS = {
    2007: 0.0408,   # 6.93% nominal, 2.8% inflation
    2008: 0.0295,   # 6.86% nominal, 3.8% inflation
    2009: 0.0405,   # 3.63% nominal, -0.4% inflation
    2010: 0.0453,   # 6.20% nominal, 1.6% inflation
    2011: 0.0457,   # 7.92% nominal, 3.2% inflation
    2012: 0.0175,   # 3.89% nominal, 2.1% inflation
    2013: -0.0355,  # -2.10% nominal, 1.5% inflation
    2014: 0.0415,   # 5.82% nominal, 1.6% inflation
    2015: 0.0046,   # 0.56% nominal, 0.1% inflation
    2016: 0.0121,   # 2.53% nominal, 1.3% inflation
    2017: 0.0143,   # 3.57% nominal, 2.1% inflation
    2018: -0.0245,  # -0.11% nominal, 2.4% inflation
    2019: 0.0692,   # 8.84% nominal, 1.8% inflation
    2020: 0.0643,   # 7.71% nominal, 1.2% inflation
    2021: -0.0626,  # -1.86% nominal, 4.7% inflation
    2022: -0.1955,  # -13.11% nominal, 8.0% inflation
    2023: 0.0150,   # 5.66% nominal, 4.1% inflation
    2024: -0.0147,  # 1.38% nominal, 2.9% inflation
}

# Convert to numpy arrays
VT_RETURNS_ARRAY = np.array(list(VT_REAL_RETURNS.values()))
BND_RETURNS_ARRAY = np.array(list(BND_REAL_RETURNS.values()))

# Convert bond returns to numpy array
BOND_RETURNS_ARRAY = np.array(list(HISTORICAL_BOND_RETURNS.values()))


def get_historical_stats() -> dict:
    """Get summary statistics for historical returns (stocks and bonds)."""
    stock_returns = RETURNS_ARRAY
    bond_returns = BOND_RETURNS_ARRAY
    return {
        # Stock stats
        "stock_mean": float(np.mean(stock_returns)),
        "stock_median": float(np.median(stock_returns)),
        "stock_std": float(np.std(stock_returns)),
        "stock_min": float(np.min(stock_returns)),
        "stock_max": float(np.max(stock_returns)),
        "stock_min_year": int(RETURNS_YEARS[np.argmin(stock_returns)]),
        "stock_max_year": int(RETURNS_YEARS[np.argmax(stock_returns)]),
        # Bond stats
        "bond_mean": float(np.mean(bond_returns)),
        "bond_median": float(np.median(bond_returns)),
        "bond_std": float(np.std(bond_returns)),
        "bond_min": float(np.min(bond_returns)),
        "bond_max": float(np.max(bond_returns)),
        # Legacy fields for backward compatibility
        "mean": float(np.mean(stock_returns)),
        "median": float(np.median(stock_returns)),
        "std": float(np.std(stock_returns)),
        "min": float(np.min(stock_returns)),
        "max": float(np.max(stock_returns)),
        "min_year": int(RETURNS_YEARS[np.argmin(stock_returns)]),
        "max_year": int(RETURNS_YEARS[np.argmax(stock_returns)]),
        # Common fields
        "n_years": len(stock_returns),
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


def generate_blended_returns(
    n_simulations: int,
    n_years: int,
    stock_allocation: float = 1.0,
    method: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = "bootstrap",
    block_size: int = 5,
    expected_stock_return: float = 0.07,
    stock_volatility: float = 0.16,
    expected_bond_return: float = 0.02,
    bond_volatility: float = 0.08,
    stock_index: Literal["sp500", "vt"] = "vt",
    bond_index: Literal["treasury", "bnd"] = "bnd",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """
    Generate blended stock/bond returns based on allocation.

    Args:
        n_simulations: Number of simulation paths.
        n_years: Number of years per path.
        stock_allocation: Fraction of portfolio in stocks (0.0 to 1.0).
                         1.0 = 100% stocks, 0.0 = 100% bonds.
        method: Return generation method (same as generate_returns).
        block_size: Block size for block_bootstrap method.
        expected_stock_return: Mean stock return for normal method.
        stock_volatility: Stock volatility for normal method.
        expected_bond_return: Mean bond return for normal method.
        bond_volatility: Bond volatility for normal method.
        stock_index: 'sp500' (S&P 500, 1928-2024) or 'vt' (Total World, 2008-2024).
        bond_index: 'treasury' (10-Year, 1928-2024) or 'bnd' (Total Bond Market, 2007-2024).
        rng: NumPy random generator.

    Returns:
        Array of shape (n_simulations, n_years) with blended annual returns.

    Raises:
        ValueError: If stock_allocation is not between 0 and 1.
    """
    if not 0 <= stock_allocation <= 1:
        raise ValueError(f"stock_allocation must be between 0 and 1, got {stock_allocation}")

    # Select the appropriate return arrays based on index choice
    if stock_index == "vt":
        stock_returns_array = VT_RETURNS_ARRAY
    else:  # sp500
        stock_returns_array = RETURNS_ARRAY

    if bond_index == "bnd":
        bond_returns_array = BND_RETURNS_ARRAY
    else:  # treasury
        bond_returns_array = BOND_RETURNS_ARRAY

    # For VT+BND, we need to use the overlapping years (2008-2024)
    # For now, use whichever has fewer years as the constraint
    n_stock_years = len(stock_returns_array)
    n_bond_years = len(bond_returns_array)
    n_historical = min(n_stock_years, n_bond_years)

    # If using mismatched indexes, trim to overlapping period
    if stock_index == "vt" and bond_index == "bnd":
        # Both have 2008+ data, use VT length (17 years: 2008-2024)
        # BND has 2007-2024 (18 years), trim first year
        bond_returns_array = bond_returns_array[1:]  # Skip 2007
        n_historical = len(stock_returns_array)
    elif stock_index == "vt":
        # VT with treasury: use VT years (17), sample from last 17 treasury years
        bond_returns_array = BOND_RETURNS_ARRAY[-n_stock_years:]
        n_historical = n_stock_years
    elif bond_index == "bnd":
        # S&P500 with BND: use BND years (18), sample from last 18 S&P years
        stock_returns_array = RETURNS_ARRAY[-n_bond_years:]
        n_historical = n_bond_years

    # If 100% stocks, use stock returns directly
    if stock_allocation == 1.0:
        if rng is None:
            rng = np.random.default_rng()

        if method == "bootstrap":
            indices = rng.integers(0, n_historical, size=(n_simulations, n_years))
            return stock_returns_array[indices]
        elif method == "normal":
            return rng.normal(expected_stock_return, stock_volatility, size=(n_simulations, n_years))
        else:
            # Fall through to general implementation
            pass

    bond_allocation = 1.0 - stock_allocation

    if rng is None:
        rng = np.random.default_rng()

    if method == "bootstrap":
        # Sample same indices for both stock and bond to maintain correlation structure
        indices = rng.integers(0, n_historical, size=(n_simulations, n_years))
        stock_returns = stock_returns_array[indices]
        bond_returns = bond_returns_array[indices]

    elif method == "block_bootstrap":
        # Block bootstrap for both asset classes
        n_blocks = (n_years + block_size - 1) // block_size
        stock_returns = np.zeros((n_simulations, n_years))
        bond_returns = np.zeros((n_simulations, n_years))

        for sim in range(n_simulations):
            year_idx = 0
            for _ in range(n_blocks):
                start = rng.integers(0, n_historical - block_size + 1)
                end_idx = min(year_idx + block_size, n_years)
                block_len = end_idx - year_idx

                stock_returns[sim, year_idx:end_idx] = stock_returns_array[start : start + block_len]
                bond_returns[sim, year_idx:end_idx] = bond_returns_array[start : start + block_len]
                year_idx = end_idx

    elif method == "historical":
        # Walk through historical sequences
        stock_returns = np.zeros((n_simulations, n_years))
        bond_returns = np.zeros((n_simulations, n_years))

        start_indices = rng.integers(0, n_historical, size=n_simulations)

        for sim in range(n_simulations):
            for year in range(n_years):
                idx = (start_indices[sim] + year) % n_historical
                stock_returns[sim, year] = stock_returns_array[idx]
                bond_returns[sim, year] = bond_returns_array[idx]

    elif method == "normal":
        # Generate independent normal returns
        stock_returns = rng.normal(expected_stock_return, stock_volatility, size=(n_simulations, n_years))
        bond_returns = rng.normal(expected_bond_return, bond_volatility, size=(n_simulations, n_years))

    else:
        raise ValueError(f"Unknown method: {method}")

    # Blend returns based on allocation
    blended_returns = stock_allocation * stock_returns + bond_allocation * bond_returns

    return blended_returns
