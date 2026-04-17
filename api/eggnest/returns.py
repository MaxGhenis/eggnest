"""Historical return data and bootstrap sampling for Monte Carlo simulation.

Uses NOMINAL returns (not inflation-adjusted) for accurate tax calculations.
Data sources:
- S&P 500: slickcharts.com (price return + dividend return)
- 10-Year Treasury: NYU Stern Aswath Damodaran dataset
- VT: lazyportfolioetf.com (derived price + dividend)
- BND: Yahoo Finance (derived price + dividend)

Returns are stored as:
- Price returns: Capital gains component (taxed as capital gains)
- Dividend returns: Income component (taxed as qualified dividends)
"""

from typing import Literal

import numpy as np

# =============================================================================
# S&P 500 NOMINAL RETURNS (1928-2024)
# Source: slickcharts.com/sp500/returns/details
# =============================================================================

SP500_PRICE_RETURNS = {
    1928: 0.3788,
    1929: -0.1191,
    1930: -0.2848,
    1931: -0.4707,
    1932: -0.1478,
    1933: 0.4408,
    1934: -0.0471,
    1935: 0.4137,
    1936: 0.2792,
    1937: -0.3859,
    1938: 0.2455,
    1939: -0.0518,
    1940: -0.1509,
    1941: -0.1786,
    1942: 0.1243,
    1943: 0.1945,
    1944: 0.1380,
    1945: 0.3072,
    1946: -0.1187,
    1947: 0.0000,
    1948: -0.0065,
    1949: 0.1046,
    1950: 0.2168,
    1951: 0.1635,
    1952: 0.1178,
    1953: -0.0662,
    1954: 0.4502,
    1955: 0.2640,
    1956: 0.0262,
    1957: -0.1431,
    1958: 0.3806,
    1959: 0.0848,
    1960: -0.0297,
    1961: 0.2313,
    1962: -0.1181,
    1963: 0.1889,
    1964: 0.1297,
    1965: 0.0906,
    1966: -0.1309,
    1967: 0.2009,
    1968: 0.0766,
    1969: -0.1136,
    1970: 0.0010,
    1971: 0.1079,
    1972: 0.1563,
    1973: -0.1737,
    1974: -0.2972,
    1975: 0.3155,
    1976: 0.1915,
    1977: -0.1150,
    1978: 0.0106,
    1979: 0.1231,
    1980: 0.2577,
    1981: -0.0973,
    1982: 0.1476,
    1983: 0.1727,
    1984: 0.0140,
    1985: 0.2633,
    1986: 0.1462,
    1987: 0.0203,
    1988: 0.1240,
    1989: 0.2725,
    1990: -0.0656,
    1991: 0.2631,
    1992: 0.0446,
    1993: 0.0706,
    1994: -0.0154,
    1995: 0.3411,
    1996: 0.2026,
    1997: 0.3101,
    1998: 0.2667,
    1999: 0.1953,
    2000: -0.1014,
    2001: -0.1304,
    2002: -0.2337,
    2003: 0.2638,
    2004: 0.0899,
    2005: 0.0300,
    2006: 0.1362,
    2007: 0.0353,
    2008: -0.3849,
    2009: 0.2345,
    2010: 0.1278,
    2011: 0.0000,
    2012: 0.1341,
    2013: 0.2960,
    2014: 0.1139,
    2015: -0.0073,
    2016: 0.0954,
    2017: 0.1942,
    2018: -0.0624,
    2019: 0.2888,
    2020: 0.1626,
    2021: 0.2689,
    2022: -0.1944,
    2023: 0.2423,
    2024: 0.2331,
}

SP500_DIVIDEND_RETURNS = {
    1928: 0.0573,
    1929: 0.0349,
    1930: 0.0358,
    1931: 0.0373,
    1932: 0.0659,
    1933: 0.0991,
    1934: 0.0327,
    1935: 0.0630,
    1936: 0.0600,
    1937: 0.0356,
    1938: 0.0657,
    1939: 0.0477,
    1940: 0.0531,
    1941: 0.0627,
    1942: 0.0791,
    1943: 0.0645,
    1944: 0.0595,
    1945: 0.0572,
    1946: 0.0380,
    1947: 0.0571,
    1948: 0.0615,
    1949: 0.0833,
    1950: 0.1003,
    1951: 0.0767,
    1952: 0.0659,
    1953: 0.0563,
    1954: 0.0760,
    1955: 0.0516,
    1956: 0.0394,
    1957: 0.0353,
    1958: 0.0530,
    1959: 0.0348,
    1960: 0.0344,
    1961: 0.0376,
    1962: 0.0308,
    1963: 0.0391,
    1964: 0.0351,
    1965: 0.0339,
    1966: 0.0303,
    1967: 0.0389,
    1968: 0.0340,
    1969: 0.0286,
    1970: 0.0391,
    1971: 0.0352,
    1972: 0.0335,
    1973: 0.0271,
    1974: 0.0325,
    1975: 0.0565,
    1976: 0.0469,
    1977: 0.0432,
    1978: 0.0550,
    1979: 0.0613,
    1980: 0.0665,
    1981: 0.0482,
    1982: 0.0679,
    1983: 0.0529,
    1984: 0.0487,
    1985: 0.0540,
    1986: 0.0405,
    1987: 0.0322,
    1988: 0.0421,
    1989: 0.0444,
    1990: 0.0346,
    1991: 0.0416,
    1992: 0.0316,
    1993: 0.0302,
    1994: 0.0286,
    1995: 0.0347,
    1996: 0.0270,
    1997: 0.0235,
    1998: 0.0191,
    1999: 0.0151,
    2000: 0.0104,
    2001: 0.0115,
    2002: 0.0127,
    2003: 0.0230,
    2004: 0.0189,
    2005: 0.0191,
    2006: 0.0217,
    2007: 0.0196,
    2008: 0.0149,
    2009: 0.0301,
    2010: 0.0228,
    2011: 0.0211,
    2012: 0.0259,
    2013: 0.0279,
    2014: 0.0230,
    2015: 0.0211,
    2016: 0.0242,
    2017: 0.0241,
    2018: 0.0186,
    2019: 0.0261,
    2020: 0.0214,
    2021: 0.0182,
    2022: 0.0133,
    2023: 0.0206,
    2024: 0.0171,
}

# =============================================================================
# 10-YEAR TREASURY NOMINAL RETURNS (1928-2024)
# Source: NYU Stern Aswath Damodaran
# Note: Bond returns are essentially all "income" (coupon) for tax purposes
# =============================================================================

TREASURY_RETURNS = {
    1928: 0.0084,
    1929: 0.0342,
    1930: 0.0466,
    1931: -0.0531,
    1932: 0.1682,
    1933: -0.0007,
    1934: 0.1002,
    1935: 0.0498,
    1936: 0.0751,
    1937: 0.0023,
    1938: 0.0553,
    1939: 0.0594,
    1940: 0.0609,
    1941: 0.0093,
    1942: 0.0322,
    1943: 0.0208,
    1944: 0.0281,
    1945: 0.1073,
    1946: -0.0010,
    1947: -0.0262,
    1948: 0.0340,
    1949: 0.0645,
    1950: 0.0006,
    1951: -0.0394,
    1952: 0.0116,
    1953: 0.0363,
    1954: 0.0719,
    1955: -0.0129,
    1956: -0.0559,
    1957: 0.0745,
    1958: -0.0609,
    1959: -0.0226,
    1960: 0.1378,
    1961: 0.0097,
    1962: 0.0689,
    1963: 0.0121,
    1964: 0.0351,
    1965: 0.0071,
    1966: 0.0365,
    1967: -0.0919,
    1968: -0.0026,
    1969: -0.0508,
    1970: 0.1210,
    1971: 0.1324,
    1972: 0.0568,
    1973: -0.0111,
    1974: 0.0435,
    1975: 0.0919,
    1976: 0.1675,
    1977: -0.0067,
    1978: -0.0116,
    1979: -0.0122,
    1980: -0.0395,
    1981: 0.0185,
    1982: 0.4036,
    1983: 0.0065,
    1984: 0.1543,
    1985: 0.3097,
    1986: 0.2453,
    1987: -0.0274,
    1988: 0.0967,
    1989: 0.1803,
    1990: 0.0621,
    1991: 0.1930,
    1992: 0.0806,
    1993: 0.1821,
    1994: -0.0776,
    1995: 0.2352,
    1996: 0.0014,
    1997: 0.0999,
    1998: 0.1476,
    1999: -0.0825,
    2000: 0.1666,
    2001: 0.0535,
    2002: 0.1522,
    2003: 0.0138,
    2004: 0.0449,
    2005: 0.0287,
    2006: 0.0196,
    2007: 0.1000,
    2008: 0.2010,
    2009: -0.1112,
    2010: 0.0841,
    2011: 0.1604,
    2012: 0.0297,
    2013: -0.0778,
    2014: 0.1075,
    2015: 0.0155,
    2016: 0.0069,
    2017: 0.0275,
    2018: -0.0002,
    2019: 0.0892,
    2020: 0.1126,
    2021: -0.0439,
    2022: -0.1747,
    2023: 0.0396,
    2024: 0.0053,
}

# Treasury "dividend" yield (coupon income) - approximate based on prevailing rates
TREASURY_YIELDS = {
    1928: 0.0340,
    1929: 0.0360,
    1930: 0.0329,
    1931: 0.0393,
    1932: 0.0368,
    1933: 0.0331,
    1934: 0.0312,
    1935: 0.0279,
    1936: 0.0265,
    1937: 0.0268,
    1938: 0.0256,
    1939: 0.0236,
    1940: 0.0221,
    1941: 0.0195,
    1942: 0.0246,
    1943: 0.0247,
    1944: 0.0248,
    1945: 0.0237,
    1946: 0.0219,
    1947: 0.0225,
    1948: 0.0244,
    1949: 0.0231,
    1950: 0.0232,
    1951: 0.0257,
    1952: 0.0268,
    1953: 0.0294,
    1954: 0.0290,
    1955: 0.0284,
    1956: 0.0296,
    1957: 0.0346,
    1958: 0.0379,
    1959: 0.0402,
    1960: 0.0469,
    1961: 0.0438,
    1962: 0.0453,
    1963: 0.0400,
    1964: 0.0415,
    1965: 0.0413,
    1966: 0.0461,
    1967: 0.0451,
    1968: 0.0549,
    1969: 0.0610,
    1970: 0.0791,
    1971: 0.0674,
    1972: 0.0595,
    1973: 0.0630,
    1974: 0.0699,
    1975: 0.0799,
    1976: 0.0787,
    1977: 0.0742,
    1978: 0.0796,
    1979: 0.0925,
    1980: 0.1080,
    1981: 0.1384,
    1982: 0.1457,
    1983: 0.1146,
    1984: 0.1192,
    1985: 0.1162,
    1986: 0.0964,
    1987: 0.0783,
    1988: 0.0867,
    1989: 0.0884,
    1990: 0.0855,
    1991: 0.0886,
    1992: 0.0770,
    1993: 0.0687,
    1994: 0.0609,
    1995: 0.0757,
    1996: 0.0644,
    1997: 0.0635,
    1998: 0.0626,
    1999: 0.0544,
    2000: 0.0603,
    2001: 0.0516,
    2002: 0.0504,
    2003: 0.0401,
    2004: 0.0427,
    2005: 0.0422,
    2006: 0.0479,
    2007: 0.0463,
    2008: 0.0366,
    2009: 0.0326,
    2010: 0.0322,
    2011: 0.0278,
    2012: 0.0180,
    2013: 0.0235,
    2014: 0.0254,
    2015: 0.0214,
    2016: 0.0184,
    2017: 0.0233,
    2018: 0.0291,
    2019: 0.0214,
    2020: 0.0089,
    2021: 0.0152,
    2022: 0.0295,
    2023: 0.0396,
    2024: 0.0428,
}

# =============================================================================
# VT (VANGUARD TOTAL WORLD STOCK) NOMINAL RETURNS (2008-2024)
# Source: lazyportfolioetf.com, dividend yields from Vanguard
# =============================================================================

# Total returns from lazyportfolioetf.com (nominal)
VT_TOTAL_RETURNS = {
    2008: -0.4231,
    2009: 0.3265,
    2010: 0.1308,
    2011: -0.0750,
    2012: 0.1712,
    2013: 0.2295,
    2014: 0.0367,
    2015: -0.0186,
    2016: 0.0851,
    2017: 0.2449,
    2018: -0.0976,
    2019: 0.2682,
    2020: 0.1661,
    2021: 0.1827,
    2022: -0.1801,
    2023: 0.2203,
    2024: 0.1649,
}

# Dividend yields (approximate, based on Vanguard data ~2% average)
VT_DIVIDEND_YIELDS = {
    2008: 0.0280,
    2009: 0.0240,
    2010: 0.0210,
    2011: 0.0230,
    2012: 0.0250,
    2013: 0.0220,
    2014: 0.0230,
    2015: 0.0250,
    2016: 0.0240,
    2017: 0.0210,
    2018: 0.0220,
    2019: 0.0200,
    2020: 0.0180,
    2021: 0.0160,
    2022: 0.0190,
    2023: 0.0180,
    2024: 0.0195,
}

# Calculate price returns: price_return ≈ total_return - dividend_yield
VT_PRICE_RETURNS = {
    year: VT_TOTAL_RETURNS[year] - VT_DIVIDEND_YIELDS[year] for year in VT_TOTAL_RETURNS
}

# =============================================================================
# BND (VANGUARD TOTAL BOND MARKET) NOMINAL RETURNS (2008-2024)
# Source: Yahoo Finance, dividend yields from Vanguard (~3% average)
# =============================================================================

# Total returns (nominal)
BND_TOTAL_RETURNS = {
    2008: 0.0686,
    2009: 0.0363,
    2010: 0.0620,
    2011: 0.0792,
    2012: 0.0389,
    2013: -0.0210,
    2014: 0.0582,
    2015: 0.0056,
    2016: 0.0253,
    2017: 0.0357,
    2018: -0.0011,
    2019: 0.0884,
    2020: 0.0771,
    2021: -0.0186,
    2022: -0.1311,
    2023: 0.0566,
    2024: 0.0138,
}

# Dividend yields (bond fund yields are higher, ~3-4% average)
BND_DIVIDEND_YIELDS = {
    2008: 0.0450,
    2009: 0.0380,
    2010: 0.0350,
    2011: 0.0320,
    2012: 0.0280,
    2013: 0.0260,
    2014: 0.0250,
    2015: 0.0240,
    2016: 0.0250,
    2017: 0.0260,
    2018: 0.0290,
    2019: 0.0280,
    2020: 0.0220,
    2021: 0.0180,
    2022: 0.0250,
    2023: 0.0340,
    2024: 0.0386,
}

# Calculate price returns
BND_PRICE_RETURNS = {
    year: BND_TOTAL_RETURNS[year] - BND_DIVIDEND_YIELDS[year]
    for year in BND_TOTAL_RETURNS
}

# =============================================================================
# US CPI INFLATION (DECEMBER-TO-DECEMBER, 1928-2024)
# Source: Federal Reserve FRED CPIAUCNS series, converted to annual Dec/Dec rates
# =============================================================================

CPI_INFLATION = {
    1928: -0.0116,
    1929: 0.0058,
    1930: -0.0640,
    1931: -0.0932,
    1932: -0.1027,
    1933: 0.0076,
    1934: 0.0152,
    1935: 0.0299,
    1936: 0.0145,
    1937: 0.0286,
    1938: -0.0278,
    1939: 0.0000,
    1940: 0.0071,
    1941: 0.0993,
    1942: 0.0903,
    1943: 0.0296,
    1944: 0.0230,
    1945: 0.0225,
    1946: 0.1813,
    1947: 0.0884,
    1948: 0.0299,
    1949: -0.0207,
    1950: 0.0593,
    1951: 0.0600,
    1952: 0.0075,
    1953: 0.0075,
    1954: -0.0074,
    1955: 0.0037,
    1956: 0.0299,
    1957: 0.0290,
    1958: 0.0176,
    1959: 0.0173,
    1960: 0.0136,
    1961: 0.0067,
    1962: 0.0133,
    1963: 0.0164,
    1964: 0.0097,
    1965: 0.0192,
    1966: 0.0346,
    1967: 0.0304,
    1968: 0.0472,
    1969: 0.0620,
    1970: 0.0557,
    1971: 0.0327,
    1972: 0.0341,
    1973: 0.0871,
    1974: 0.1234,
    1975: 0.0694,
    1976: 0.0486,
    1977: 0.0670,
    1978: 0.0902,
    1979: 0.1329,
    1980: 0.1252,
    1981: 0.0892,
    1982: 0.0383,
    1983: 0.0379,
    1984: 0.0395,
    1985: 0.0380,
    1986: 0.0110,
    1987: 0.0443,
    1988: 0.0442,
    1989: 0.0465,
    1990: 0.0611,
    1991: 0.0306,
    1992: 0.0290,
    1993: 0.0275,
    1994: 0.0267,
    1995: 0.0254,
    1996: 0.0332,
    1997: 0.0170,
    1998: 0.0161,
    1999: 0.0268,
    2000: 0.0339,
    2001: 0.0155,
    2002: 0.0238,
    2003: 0.0188,
    2004: 0.0326,
    2005: 0.0342,
    2006: 0.0254,
    2007: 0.0408,
    2008: 0.0009,
    2009: 0.0272,
    2010: 0.0150,
    2011: 0.0296,
    2012: 0.0174,
    2013: 0.0150,
    2014: 0.0076,
    2015: 0.0073,
    2016: 0.0207,
    2017: 0.0211,
    2018: 0.0191,
    2019: 0.0229,
    2020: 0.0136,
    2021: 0.0704,
    2022: 0.0645,
    2023: 0.0335,
    2024: 0.0289,
}

# =============================================================================
# NUMPY ARRAYS FOR EFFICIENT SIMULATION
# =============================================================================

# S&P 500
SP500_PRICE_ARRAY = np.array(list(SP500_PRICE_RETURNS.values()))
SP500_DIVIDEND_ARRAY = np.array(list(SP500_DIVIDEND_RETURNS.values()))
SP500_YEARS = np.array(list(SP500_PRICE_RETURNS.keys()))

# Treasury
TREASURY_PRICE_ARRAY = np.array(list(TREASURY_RETURNS.values()))
TREASURY_YIELD_ARRAY = np.array(list(TREASURY_YIELDS.values()))
TREASURY_YEARS = np.array(list(TREASURY_RETURNS.keys()))

# VT
VT_PRICE_ARRAY = np.array(list(VT_PRICE_RETURNS.values()))
VT_DIVIDEND_ARRAY = np.array(list(VT_DIVIDEND_YIELDS.values()))
VT_YEARS = np.array(list(VT_PRICE_RETURNS.keys()))

# BND
BND_PRICE_ARRAY = np.array(list(BND_PRICE_RETURNS.values()))
BND_DIVIDEND_ARRAY = np.array(list(BND_DIVIDEND_YIELDS.values()))
BND_YEARS = np.array(list(BND_PRICE_RETURNS.keys()))

# Inflation
INFLATION_ARRAY = np.array(list(CPI_INFLATION.values()))
INFLATION_YEARS = np.array(list(CPI_INFLATION.keys()))

# Legacy aliases for backward compatibility
RETURNS_ARRAY = SP500_PRICE_ARRAY + SP500_DIVIDEND_ARRAY  # Total returns
RETURNS_YEARS = SP500_YEARS
HISTORICAL_REAL_RETURNS = SP500_PRICE_RETURNS  # Legacy name
BOND_RETURNS_ARRAY = TREASURY_PRICE_ARRAY  # Legacy name

# Fund arrays lookup
FUND_ARRAYS = {
    "vt": (VT_PRICE_ARRAY, VT_DIVIDEND_ARRAY),
    "sp500": (SP500_PRICE_ARRAY, SP500_DIVIDEND_ARRAY),
    "bnd": (BND_PRICE_ARRAY, BND_DIVIDEND_ARRAY),
    "treasury": (TREASURY_PRICE_ARRAY, TREASURY_YIELD_ARRAY),
}
FUND_HISTORIES = {
    "vt": (VT_YEARS, VT_PRICE_ARRAY, VT_DIVIDEND_ARRAY),
    "sp500": (SP500_YEARS, SP500_PRICE_ARRAY, SP500_DIVIDEND_ARRAY),
    "bnd": (BND_YEARS, BND_PRICE_ARRAY, BND_DIVIDEND_ARRAY),
    "treasury": (TREASURY_YEARS, TREASURY_PRICE_ARRAY, TREASURY_YIELD_ARRAY),
}


def _generate_sample_indices(
    n_simulations: int,
    n_years: int,
    n_historical: int,
    method: Literal["bootstrap", "block_bootstrap", "historical"],
    block_size: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate shared historical indices for a Monte Carlo run."""
    if method == "bootstrap":
        return rng.integers(0, n_historical, size=(n_simulations, n_years))

    if method == "historical":
        start_indices = rng.integers(0, n_historical, size=n_simulations)
        offsets = np.arange(n_years)
        return (start_indices[:, None] + offsets[None, :]) % n_historical

    if method == "block_bootstrap":
        if block_size > n_historical:
            raise ValueError(
                f"block_size {block_size} exceeds history length {n_historical}"
            )

        indices = np.zeros((n_simulations, n_years), dtype=int)
        n_blocks = (n_years + block_size - 1) // block_size

        for sim in range(n_simulations):
            year_idx = 0
            for _ in range(n_blocks):
                start = rng.integers(0, n_historical - block_size + 1)
                end_idx = min(year_idx + block_size, n_years)
                block_len = end_idx - year_idx
                indices[sim, year_idx:end_idx] = np.arange(start, start + block_len)
                year_idx = end_idx

        return indices

    raise ValueError(f"Unknown method: {method}")


def _inflate_years_to_rates(sampled_years: np.ndarray) -> np.ndarray:
    """Map sampled historical years to annual inflation rates."""
    lookup = {
        int(year): float(rate)
        for year, rate in zip(INFLATION_YEARS, INFLATION_ARRAY, strict=True)
    }
    inflation = np.zeros_like(sampled_years, dtype=float)
    for year, rate in lookup.items():
        inflation = np.where(sampled_years == year, rate, inflation)

    if np.any(~np.isin(sampled_years, INFLATION_YEARS)):
        raise ValueError("Sampled years are outside the available inflation history")
    return inflation


def get_aligned_fund_arrays(
    funds: list[Literal["vt", "sp500", "bnd", "treasury"]]
    | tuple[Literal["vt", "sp500", "bnd", "treasury"], ...],
) -> tuple[np.ndarray, dict[str, tuple[np.ndarray, np.ndarray]]]:
    """
    Align selected funds to their common overlapping year range.

    Returns:
        Tuple of (common_years, aligned price/dividend arrays by fund).
    """
    unique_funds = list(dict.fromkeys(funds))
    if not unique_funds:
        raise ValueError("At least one fund is required")

    start_year = max(int(FUND_HISTORIES[fund][0][0]) for fund in unique_funds)
    end_year = min(int(FUND_HISTORIES[fund][0][-1]) for fund in unique_funds)
    if start_year > end_year:
        raise ValueError("Selected funds do not share an overlapping history")

    common_years: np.ndarray | None = None
    aligned: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for fund in unique_funds:
        years, price_array, div_array = FUND_HISTORIES[fund]
        mask = (years >= start_year) & (years <= end_year)
        fund_years = years[mask]
        if common_years is None:
            common_years = fund_years
        elif not np.array_equal(common_years, fund_years):
            raise ValueError("Selected funds do not align to a shared yearly history")
        aligned[fund] = (price_array[mask], div_array[mask])

    return common_years, aligned


def build_historical_year_matrix(
    available_years: np.ndarray,
    n_years: int,
    start_years: list[int] | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build exact year indices for historical cohort backtests.

    Returns:
        Tuple of (index_matrix, sampled_years, valid_start_years).
    """
    if n_years <= 0:
        raise ValueError("n_years must be positive")

    max_start_count = len(available_years) - n_years + 1
    if max_start_count <= 0:
        raise ValueError("Requested horizon exceeds available historical data")

    valid_start_years = available_years[:max_start_count]

    if start_years is None:
        selected_start_years = valid_start_years
        start_indices = np.arange(max_start_count, dtype=int)
    else:
        selected_start_years = np.asarray(start_years, dtype=int)
        if selected_start_years.size == 0:
            raise ValueError("At least one start year is required")
        start_lookup = {int(year): index for index, year in enumerate(valid_start_years)}
        missing_years = [
            int(year) for year in selected_start_years if int(year) not in start_lookup
        ]
        if missing_years:
            raise ValueError(
                "Start years are outside the valid historical range: "
                + ", ".join(str(year) for year in missing_years)
            )
        start_indices = np.array(
            [start_lookup[int(year)] for year in selected_start_years], dtype=int
        )

    offsets = np.arange(n_years, dtype=int)
    index_matrix = start_indices[:, None] + offsets[None, :]
    sampled_years = available_years[index_matrix]
    return index_matrix, sampled_years, valid_start_years


def generate_historical_blended_return_paths(
    n_years: int,
    stock_allocation: float = 1.0,
    stock_index: Literal["sp500", "vt"] = "sp500",
    bond_index: Literal["treasury", "bnd"] = "treasury",
    start_years: list[int] | np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate exact historical blended return paths for chosen cohort start years.

    Returns:
        Tuple of (price_growth, dividend_yields, sampled_years, valid_start_years).
    """
    common_years, aligned = get_aligned_fund_arrays([stock_index, bond_index])
    stock_price, stock_div = aligned[stock_index]
    bond_price, bond_div = aligned[bond_index]
    index_matrix, sampled_years, valid_start_years = build_historical_year_matrix(
        common_years, n_years, start_years
    )
    bond_allocation = 1.0 - stock_allocation
    blended_price = (
        stock_allocation * stock_price[index_matrix]
        + bond_allocation * bond_price[index_matrix]
    )
    blended_div = (
        stock_allocation * stock_div[index_matrix]
        + bond_allocation * bond_div[index_matrix]
    )
    return blended_price, blended_div, sampled_years, valid_start_years


def generate_historical_fund_return_paths(
    funds: list[Literal["vt", "sp500", "bnd", "treasury"]]
    | tuple[Literal["vt", "sp500", "bnd", "treasury"], ...],
    n_years: int,
    start_years: list[int] | np.ndarray | None = None,
) -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], np.ndarray, np.ndarray]:
    """
    Generate exact historical fund return paths for chosen cohort start years.

    Returns:
        Tuple of (fund returns, sampled years, valid start years).
    """
    common_years, aligned_funds = get_aligned_fund_arrays(funds)
    index_matrix, sampled_years, valid_start_years = build_historical_year_matrix(
        common_years, n_years, start_years
    )
    fund_returns: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for fund, (price_array, div_array) in aligned_funds.items():
        fund_returns[fund] = (price_array[index_matrix], div_array[index_matrix])
    return fund_returns, sampled_years, valid_start_years


def generate_fund_returns(
    fund: Literal["vt", "sp500", "bnd", "treasury"],
    n_simulations: int,
    n_years: int,
    method: Literal["bootstrap", "block_bootstrap", "historical"] = "bootstrap",
    block_size: int = 5,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate returns for a specific fund using bootstrap sampling.

    Args:
        fund: Fund type (vt, sp500, bnd, treasury)
        n_simulations: Number of Monte Carlo simulations
        n_years: Number of years to simulate
        method: Bootstrap method
        block_size: Block size for block bootstrap
        rng: Random number generator

    Returns:
        (price_growth, dividend_yields) arrays of shape (n_simulations, n_years)
    """
    correlated = generate_correlated_fund_returns(
        funds=[fund],
        n_simulations=n_simulations,
        n_years=n_years,
        method=method,
        block_size=block_size,
        rng=rng,
    )
    return correlated[fund]


def generate_correlated_fund_returns(
    funds: list[Literal["vt", "sp500", "bnd", "treasury"]]
    | tuple[Literal["vt", "sp500", "bnd", "treasury"], ...],
    n_simulations: int,
    n_years: int,
    method: Literal["bootstrap", "block_bootstrap", "historical"] = "bootstrap",
    block_size: int = 5,
    rng: np.random.Generator | None = None,
    return_sampled_years: bool = False,
) -> (
    dict[str, tuple[np.ndarray, np.ndarray]]
    | tuple[dict[str, tuple[np.ndarray, np.ndarray]], np.ndarray]
):
    """
    Generate fund returns with shared historical sampling across selected funds.

    This preserves same-year cross-fund relationships within the funds' common
    overlapping history window.
    """
    if rng is None:
        rng = np.random.default_rng()

    common_years, aligned_funds = get_aligned_fund_arrays(funds)
    sample_fund = next(iter(aligned_funds))
    n_historical = len(aligned_funds[sample_fund][0])
    indices = _generate_sample_indices(
        n_simulations=n_simulations,
        n_years=n_years,
        n_historical=n_historical,
        method=method,
        block_size=block_size,
        rng=rng,
    )

    correlated_returns: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for fund, (price_array, div_array) in aligned_funds.items():
        correlated_returns[fund] = (price_array[indices], div_array[indices])

    if return_sampled_years:
        return correlated_returns, common_years[indices]
    return correlated_returns


def generate_inflation_paths(
    n_simulations: int,
    n_years: int,
    model: Literal["historical", "constant"] = "historical",
    inflation_rate: float = 0.025,
    method: Literal["bootstrap", "block_bootstrap", "historical", "normal"] = "bootstrap",
    block_size: int = 5,
    sampled_years: np.ndarray | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Generate annual inflation paths for the simulation horizon."""
    if rng is None:
        rng = np.random.default_rng()

    if model == "constant":
        return np.full((n_simulations, n_years), inflation_rate, dtype=float)

    if sampled_years is not None:
        if sampled_years.shape != (n_simulations, n_years):
            raise ValueError(
                "sampled_years must have shape (n_simulations, n_years)"
            )
        return _inflate_years_to_rates(sampled_years)

    if model != "historical":
        raise ValueError(f"Unknown inflation model: {model}")

    if method == "normal":
        sample_method: Literal["bootstrap", "block_bootstrap", "historical"] = "bootstrap"
    else:
        sample_method = method

    indices = _generate_sample_indices(
        n_simulations=n_simulations,
        n_years=n_years,
        n_historical=len(INFLATION_ARRAY),
        method=sample_method,
        block_size=block_size,
        rng=rng,
    )
    return INFLATION_ARRAY[indices]


def get_historical_stats() -> dict:
    """Get summary statistics for historical returns."""
    sp500_total = SP500_PRICE_ARRAY + SP500_DIVIDEND_ARRAY
    vt_total = VT_PRICE_ARRAY + VT_DIVIDEND_ARRAY
    treasury_total = TREASURY_PRICE_ARRAY + TREASURY_YIELD_ARRAY
    bnd_total = BND_PRICE_ARRAY + BND_DIVIDEND_ARRAY

    return {
        # S&P 500 stats
        "sp500_price_mean": float(np.mean(SP500_PRICE_ARRAY)),
        "sp500_dividend_mean": float(np.mean(SP500_DIVIDEND_ARRAY)),
        "sp500_total_mean": float(np.mean(sp500_total)),
        "sp500_std": float(np.std(sp500_total)),
        "sp500_min": float(np.min(sp500_total)),
        "sp500_max": float(np.max(sp500_total)),
        "sp500_n_years": len(SP500_PRICE_ARRAY),
        # VT stats
        "vt_price_mean": float(np.mean(VT_PRICE_ARRAY)),
        "vt_dividend_mean": float(np.mean(VT_DIVIDEND_ARRAY)),
        "vt_total_mean": float(np.mean(vt_total)),
        "vt_std": float(np.std(vt_total)),
        "vt_n_years": len(VT_PRICE_ARRAY),
        # Treasury stats
        "treasury_mean": float(np.mean(treasury_total)),
        "treasury_std": float(np.std(treasury_total)),
        # BND stats
        "bnd_total_mean": float(np.mean(bnd_total)),
        "bnd_std": float(np.std(bnd_total)),
        # Inflation stats
        "inflation_mean": float(np.mean(INFLATION_ARRAY)),
        "inflation_std": float(np.std(INFLATION_ARRAY)),
        # Legacy aliases (used by main.py allocation endpoint)
        # Default to the long-history S&P 500 / Treasury baseline.
        "stock_mean": float(np.mean(sp500_total)),
        "stock_std": float(np.std(sp500_total)),
        "bond_mean": float(np.mean(treasury_total)),
        "bond_std": float(np.std(treasury_total)),
    }


def get_return_arrays(
    stock_index: Literal["sp500", "vt"] = "sp500",
    bond_index: Literal["treasury", "bnd"] = "treasury",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Get price and dividend arrays for the specified indexes.

    Returns:
        (stock_price, stock_dividend, bond_price, bond_dividend)
    """
    _, aligned = get_aligned_fund_arrays([stock_index, bond_index])
    stock_price, stock_div = aligned[stock_index]
    bond_price, bond_div = aligned[bond_index]
    return stock_price, stock_div, bond_price, bond_div


def generate_returns(
    n_simulations: int,
    n_years: int,
    method: Literal[
        "bootstrap", "block_bootstrap", "historical", "normal"
    ] = "bootstrap",
    block_size: int = 5,
    expected_return: float = 0.10,
    volatility: float = 0.16,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Generate stock price returns and dividend yields.

    Returns:
        (price_growth, dividend_yields) arrays of shape (n_simulations, n_years)
    """
    if rng is None:
        rng = np.random.default_rng()

    price_array = SP500_PRICE_ARRAY
    div_array = SP500_DIVIDEND_ARRAY
    n_historical = len(price_array)

    if method == "bootstrap":
        indices = rng.integers(0, n_historical, size=(n_simulations, n_years))
        return price_array[indices], div_array[indices]

    elif method == "block_bootstrap":
        n_blocks = (n_years + block_size - 1) // block_size
        price_growth = np.zeros((n_simulations, n_years))
        div_returns = np.zeros((n_simulations, n_years))

        for sim in range(n_simulations):
            year_idx = 0
            for _ in range(n_blocks):
                start = rng.integers(0, n_historical - block_size + 1)
                end_idx = min(year_idx + block_size, n_years)
                block_len = end_idx - year_idx
                price_growth[sim, year_idx:end_idx] = price_array[
                    start : start + block_len
                ]
                div_returns[sim, year_idx:end_idx] = div_array[
                    start : start + block_len
                ]
                year_idx = end_idx
        return price_growth, div_returns

    elif method == "historical":
        price_growth = np.zeros((n_simulations, n_years))
        div_returns = np.zeros((n_simulations, n_years))
        start_indices = rng.integers(0, n_historical, size=n_simulations)

        for sim in range(n_simulations):
            for year in range(n_years):
                idx = (start_indices[sim] + year) % n_historical
                price_growth[sim, year] = price_array[idx]
                div_returns[sim, year] = div_array[idx]
        return price_growth, div_returns

    elif method == "normal":
        # For normal, use expected values
        avg_div = float(np.mean(div_array))
        price_growth = rng.normal(
            expected_return - avg_div, volatility, size=(n_simulations, n_years)
        )
        div_returns = np.full((n_simulations, n_years), avg_div)
        return price_growth, div_returns

    else:
        raise ValueError(f"Unknown method: {method}")


def generate_blended_returns(
    n_simulations: int,
    n_years: int,
    stock_allocation: float = 1.0,
    method: Literal[
        "bootstrap", "block_bootstrap", "historical", "normal"
    ] = "bootstrap",
    block_size: int = 5,
    expected_stock_return: float = 0.10,
    stock_volatility: float = 0.16,
    expected_bond_return: float = 0.04,
    bond_volatility: float = 0.08,
    stock_index: Literal["sp500", "vt"] = "sp500",
    bond_index: Literal["treasury", "bnd"] = "treasury",
    rng: np.random.Generator | None = None,
    return_sampled_years: bool = False,
) -> (
    tuple[np.ndarray, np.ndarray]
    | tuple[np.ndarray, np.ndarray, np.ndarray | None]
):
    """
    Generate blended stock/bond returns with separate price and dividend components.

    Returns:
        (price_growth, dividend_yields) - blended based on allocation
    """
    if not 0 <= stock_allocation <= 1:
        raise ValueError(
            f"stock_allocation must be between 0 and 1, got {stock_allocation}"
        )

    if rng is None:
        rng = np.random.default_rng()

    # Get the appropriate return arrays
    common_years, aligned = get_aligned_fund_arrays([stock_index, bond_index])
    stock_price, stock_div = aligned[stock_index]
    bond_price, bond_div = aligned[bond_index]

    n_historical = len(stock_price)
    bond_allocation = 1.0 - stock_allocation
    sampled_years: np.ndarray | None = None

    if method in {"bootstrap", "block_bootstrap", "historical"}:
        indices = _generate_sample_indices(
            n_simulations=n_simulations,
            n_years=n_years,
            n_historical=n_historical,
            method=method,
            block_size=block_size,
            rng=rng,
        )
        sampled_years = common_years[indices]
        blended_price = (
            stock_allocation * stock_price[indices]
            + bond_allocation * bond_price[indices]
        )
        blended_div = (
            stock_allocation * stock_div[indices] + bond_allocation * bond_div[indices]
        )

    elif method == "normal":
        avg_stock_div = float(np.mean(stock_div))
        avg_bond_div = float(np.mean(bond_div))

        stock_price_ret = rng.normal(
            expected_stock_return - avg_stock_div,
            stock_volatility,
            size=(n_simulations, n_years),
        )
        bond_price_ret = rng.normal(
            expected_bond_return - avg_bond_div,
            bond_volatility,
            size=(n_simulations, n_years),
        )

        blended_price = (
            stock_allocation * stock_price_ret + bond_allocation * bond_price_ret
        )
        blended_div = np.full(
            (n_simulations, n_years),
            stock_allocation * avg_stock_div + bond_allocation * avg_bond_div,
        )

    else:
        raise ValueError(f"Unknown method: {method}")

    if return_sampled_years:
        return blended_price, blended_div, sampled_years
    return blended_price, blended_div
