"""Social Security timing calculations.

This module calculates adjusted Social Security benefits based on claiming age.
Uses SSA rules for:
- Full Retirement Age (FRA) by birth year
- Early retirement reduction (5/9 of 1% per month for first 36 months,
  5/12 of 1% per month for additional months)
- Delayed retirement credits (8% per year for those born 1943+, up to age 70)

Sources:
- https://www.ssa.gov/benefits/retirement/planner/agereduction.html
- https://www.ssa.gov/oact/quickcalc/early_late.html
"""


def get_full_retirement_age(birth_year: int) -> float:
    """Get Full Retirement Age (FRA) based on birth year.

    Args:
        birth_year: Year of birth

    Returns:
        FRA in years (e.g., 67.0 or 66.5)
    """
    if birth_year <= 1937:
        return 65.0
    elif birth_year == 1938:
        return 65 + 2 / 12
    elif birth_year == 1939:
        return 65 + 4 / 12
    elif birth_year == 1940:
        return 65 + 6 / 12
    elif birth_year == 1941:
        return 65 + 8 / 12
    elif birth_year == 1942:
        return 65 + 10 / 12
    elif 1943 <= birth_year <= 1954:
        return 66.0
    elif birth_year == 1955:
        return 66 + 2 / 12
    elif birth_year == 1956:
        return 66 + 4 / 12
    elif birth_year == 1957:
        return 66 + 6 / 12
    elif birth_year == 1958:
        return 66 + 8 / 12
    elif birth_year == 1959:
        return 66 + 10 / 12
    else:  # 1960 or later
        return 67.0


def get_early_reduction_factor(birth_year: int, claiming_age: float) -> float:
    """Calculate early retirement reduction factor.

    Per SSA:
    - 5/9 of 1% per month for the first 36 months before FRA
    - 5/12 of 1% per month for additional months beyond 36

    Args:
        birth_year: Year of birth (determines FRA)
        claiming_age: Age at which benefits are claimed

    Returns:
        Reduction factor (1.0 = no reduction, 0.7 = 30% reduction)
    """
    fra = get_full_retirement_age(birth_year)

    # If claiming at or after FRA, no reduction
    if claiming_age >= fra:
        return 1.0

    # Calculate months early
    months_early = int(round((fra - claiming_age) * 12))

    # Apply reduction formula
    if months_early <= 36:
        # 5/9 of 1% per month
        reduction = months_early * (5 / 9) * 0.01
    else:
        # First 36 months at 5/9 of 1%
        reduction_first_36 = 36 * (5 / 9) * 0.01
        # Additional months at 5/12 of 1%
        additional_months = months_early - 36
        reduction_additional = additional_months * (5 / 12) * 0.01
        reduction = reduction_first_36 + reduction_additional

    return 1.0 - reduction


def get_delayed_retirement_credit(birth_year: int, claiming_age: float) -> float:
    """Calculate delayed retirement credit factor.

    For those born 1943 or later, the DRC is 8% per year of delay after FRA
    (2/3 of 1% per month), up to age 70.

    Args:
        birth_year: Year of birth (determines FRA)
        claiming_age: Age at which benefits are claimed

    Returns:
        Credit factor (1.0 = no credit, 1.24 = 24% increase)
    """
    fra = get_full_retirement_age(birth_year)

    # If claiming at or before FRA, no credit
    if claiming_age <= fra:
        return 1.0

    # Cap at age 70 (no additional credit beyond 70)
    effective_claiming_age = min(claiming_age, 70.0)

    # Calculate years of delay
    years_delayed = effective_claiming_age - fra

    # DRC is 8% per year for those born 1943+
    # (Earlier birth years had lower rates, but those folks are already 80+)
    credit_per_year = 0.08

    return 1.0 + (years_delayed * credit_per_year)


def calculate_adjusted_benefit(
    pia_monthly: float, birth_year: int, claiming_age: float
) -> float:
    """Calculate adjusted monthly benefit based on claiming age.

    The Primary Insurance Amount (PIA) is the benefit at Full Retirement Age.
    This function adjusts for early claiming (reduction) or delayed claiming (credit).

    Args:
        pia_monthly: Primary Insurance Amount (monthly benefit at FRA)
        birth_year: Year of birth
        claiming_age: Age at which benefits are claimed

    Returns:
        Adjusted monthly benefit amount

    Raises:
        ValueError: If claiming_age < 62 or pia_monthly < 0
    """
    if pia_monthly < 0:
        raise ValueError("PIA must be positive or zero")

    if pia_monthly == 0:
        return 0.0

    if claiming_age < 62:
        raise ValueError("Cannot claim Social Security before age 62")

    fra = get_full_retirement_age(birth_year)

    if claiming_age < fra:
        # Early claiming - apply reduction
        factor = get_early_reduction_factor(birth_year, claiming_age)
    elif claiming_age > fra:
        # Delayed claiming - apply credit
        factor = get_delayed_retirement_credit(birth_year, claiming_age)
    else:
        # Claiming at FRA
        factor = 1.0

    return pia_monthly * factor
