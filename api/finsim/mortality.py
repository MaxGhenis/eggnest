"""Mortality tables and survival calculations from SSA Period Life Tables."""

import numpy as np
from typing import Literal

# SSA Period Life Table 2021 - Probability of death within one year
# Source: https://www.ssa.gov/oact/STATS/table4c6.html
MALE_MORTALITY = {
    0: 0.00546, 1: 0.00038, 2: 0.00025, 3: 0.00020, 4: 0.00016,
    5: 0.00014, 10: 0.00009, 15: 0.00033, 20: 0.00102, 25: 0.00127,
    30: 0.00141, 35: 0.00169, 40: 0.00220, 45: 0.00321, 50: 0.00475,
    55: 0.00721, 60: 0.01069, 65: 0.01564, 70: 0.02268, 75: 0.03374,
    80: 0.05204, 85: 0.08211, 90: 0.12889, 95: 0.19447, 100: 0.27750,
    105: 0.36798, 110: 0.46452, 115: 0.50000, 119: 1.00000
}

FEMALE_MORTALITY = {
    0: 0.00455, 1: 0.00031, 2: 0.00019, 3: 0.00015, 4: 0.00012,
    5: 0.00011, 10: 0.00008, 15: 0.00019, 20: 0.00038, 25: 0.00049,
    30: 0.00060, 35: 0.00080, 40: 0.00117, 45: 0.00177, 50: 0.00275,
    55: 0.00418, 60: 0.00631, 65: 0.00964, 70: 0.01477, 75: 0.02304,
    80: 0.03797, 85: 0.06374, 90: 0.10792, 95: 0.17501, 100: 0.26326,
    105: 0.36142, 110: 0.45842, 115: 0.50000, 119: 1.00000
}


def get_mortality_rates(gender: Literal["male", "female"]) -> dict[int, float]:
    """Get mortality rates by age for given gender."""
    return MALE_MORTALITY if gender == "male" else FEMALE_MORTALITY


def interpolate_mortality_rate(age: int, gender: Literal["male", "female"]) -> float:
    """Get interpolated mortality rate for a specific age."""
    mortality_rates = get_mortality_rates(gender)
    ages = sorted(mortality_rates.keys())
    rates = [mortality_rates[a] for a in ages]
    return float(np.interp(age, ages, rates))


def calculate_survival_curve(
    start_age: int,
    end_age: int,
    gender: Literal["male", "female"]
) -> list[float]:
    """Calculate cumulative survival probability from start_age to each age."""
    survival = [1.0]  # Probability of surviving to start_age is 1
    cumulative = 1.0

    for age in range(start_age, end_age):
        mort_rate = interpolate_mortality_rate(age, gender)
        cumulative *= (1 - mort_rate)
        survival.append(cumulative)

    return survival


def generate_alive_mask(
    n_simulations: int,
    n_years: int,
    current_age: int,
    gender: Literal["male", "female"],
    rng: np.random.Generator
) -> np.ndarray:
    """
    Generate a boolean mask indicating if the person is alive at each year.

    Returns:
        Array of shape (n_simulations, n_years + 1) where True means alive.
    """
    alive_mask = np.ones((n_simulations, n_years + 1), dtype=bool)

    for year in range(n_years):
        age = current_age + year
        mort_rate = interpolate_mortality_rate(age, gender)

        # Generate random deaths
        deaths = rng.random(n_simulations) < mort_rate

        # Once dead, stay dead
        alive_mask[deaths, year + 1:] = False

    return alive_mask


def generate_joint_alive_mask(
    n_simulations: int,
    n_years: int,
    primary_age: int,
    primary_gender: Literal["male", "female"],
    spouse_age: int,
    spouse_gender: Literal["male", "female"],
    rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Generate alive masks for a couple.

    Returns:
        Tuple of (primary_alive, spouse_alive, either_alive) arrays.
        Each array has shape (n_simulations, n_years + 1).
    """
    primary_alive = generate_alive_mask(n_simulations, n_years, primary_age, primary_gender, rng)
    spouse_alive = generate_alive_mask(n_simulations, n_years, spouse_age, spouse_gender, rng)
    either_alive = primary_alive | spouse_alive

    return primary_alive, spouse_alive, either_alive
