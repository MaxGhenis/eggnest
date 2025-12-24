"""Required Minimum Distribution (RMD) calculations.

RMDs are required withdrawals from tax-deferred retirement accounts
(Traditional IRA, 401k) starting at age 73 (SECURE 2.0 Act).

Formula: RMD = Account Balance / Distribution Period

The distribution period comes from IRS Uniform Lifetime Table.
"""

# IRS Uniform Lifetime Table (2024)
# Used when spouse is not sole beneficiary or spouse is less than 10 years younger
# Source: https://www.irs.gov/publications/p590b
UNIFORM_LIFETIME_TABLE = {
    72: 27.4,
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22.0,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16.0,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
    95: 8.9,
    96: 8.4,
    97: 7.8,
    98: 7.3,
    99: 6.8,
    100: 6.4,
    101: 6.0,
    102: 5.6,
    103: 5.2,
    104: 4.9,
    105: 4.6,
    106: 4.3,
    107: 4.1,
    108: 3.9,
    109: 3.7,
    110: 3.5,
    111: 3.4,
    112: 3.3,
    113: 3.1,
    114: 3.0,
    115: 2.9,
    116: 2.8,
    117: 2.7,
    118: 2.5,
    119: 2.3,
    120: 2.0,
}

# RMD starting age (SECURE 2.0 Act)
RMD_START_AGE = 73


def calculate_rmd(account_balance: float, age: int) -> float:
    """
    Calculate Required Minimum Distribution for a given age.

    Args:
        account_balance: Total balance in traditional (tax-deferred) accounts
        age: Current age of the account holder

    Returns:
        Required minimum distribution amount. Returns 0 if under RMD age.
    """
    if age < RMD_START_AGE:
        return 0.0

    if account_balance <= 0:
        return 0.0

    # Get distribution period, use max age if beyond table
    distribution_period = UNIFORM_LIFETIME_TABLE.get(age, UNIFORM_LIFETIME_TABLE[120])

    return account_balance / distribution_period


def get_rmd_factor(age: int) -> float:
    """
    Get the RMD withdrawal factor (1 / distribution period) for an age.

    Args:
        age: Current age

    Returns:
        Factor to multiply by account balance to get RMD.
        Returns 0 if under RMD age.
    """
    if age < RMD_START_AGE:
        return 0.0

    distribution_period = UNIFORM_LIFETIME_TABLE.get(age, UNIFORM_LIFETIME_TABLE[120])
    return 1.0 / distribution_period
