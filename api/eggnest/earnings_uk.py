"""Stochastic UK earnings-process sampler for pre-retirement paths.

Models log-earnings as a deterministic age profile plus a persistent AR(1)
shock plus a transitory iid shock, following the Meghir-Pistaferri /
Blundell-Pistaferri-Preston style::

    log y_{i, t} = α(age_{i, t}) + p_{i, t} + ε_{i, t}
    p_{i, t}     = ρ · p_{i, t-1} + η_{i, t}
    η_{i, t} ~ N(0, σ_η²)
    ε_{i, t} ~ N(0, σ_ε²)

Defaults are calibrated to UK estimates (BHPS/UKHLS literature):

    σ_η ≈ 0.10   persistent innovation stdev
    σ_ε ≈ 0.20   transitory shock stdev
    ρ   ≈ 0.97   persistence
    peak-growth Δlog ≈ 0.40   entry-to-peak

Country-specific calibration (e.g. US/PSID) is done by scaling the input
parameters rather than forking the model — see the `earnings_*` fields on
``UKSimulationInput``.

References
----------
- Meghir, C. & Pistaferri, L. (2011), "Earnings, Consumption and Life Cycle
  Choices," Handbook of Labor Economics Vol 4B. [PSID σ_η ≈ 0.14, σ_ε ≈ 0.25]
- Blundell, Pistaferri & Preston (2008), "Consumption Inequality and Partial
  Insurance," AER. [BHPS σ_η ≈ 0.10, σ_ε ≈ 0.20]
- Guvenen (2009), "An Empirical Investigation of Labor Income Processes."
"""

from __future__ import annotations

import numpy as np

PEAK_AGE = 52.0  # age at which the log-earnings profile is highest


def _deterministic_log_profile(
    ages: np.ndarray, entry_age: float, peak_growth: float
) -> np.ndarray:
    """Log-earnings profile anchored at 0 at entry, peaking at ``peak_growth``.

    Quadratic in age centred on PEAK_AGE; the profile is symmetric around the
    peak and declines after. For retirement planning we only care about the
    working-age range (22-70).
    """
    # Width chosen so that log-earnings at entry_age = 0.
    span = PEAK_AGE - entry_age
    if span <= 0:
        return np.zeros_like(ages, dtype=np.float64)
    # quadratic: f(a) = peak_growth * (1 - ((a - PEAK_AGE) / span) ** 2)
    normalized = (ages - PEAK_AGE) / span
    return peak_growth * (1.0 - normalized**2)


def sample_earnings_paths(
    n_sims: int,
    ages: np.ndarray,
    starting_earnings: float,
    retirement_age: int,
    model: str,
    persistent_sigma: float,
    transitory_sigma: float,
    persistence: float,
    peak_growth: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Draw (n_sims, n_years) gross earnings in nominal £.

    ``ages[t]`` is the person's age in simulation year ``t``. Earnings are
    zero for every age ``>= retirement_age``. The year-0 level is pinned to
    ``starting_earnings`` for every path so the user input remains meaningful.

    Parameters match the Meghir-Pistaferri-style process described at module
    level. Setting ``model='flat'`` returns the input repeated (pre-retirement)
    for parity with the legacy behaviour.
    """
    n_years = len(ages)
    output = np.zeros((n_sims, n_years), dtype=np.float64)
    working_mask = ages < retirement_age
    if not working_mask.any() or starting_earnings <= 0:
        return output

    entry_age = float(ages[0])

    if model == "flat":
        output[:, working_mask] = starting_earnings
        return output

    # Deterministic log-profile shared across all paths, normalised so that
    # its year-0 value equals log(starting_earnings).
    det_profile = _deterministic_log_profile(
        ages.astype(np.float64), entry_age, peak_growth
    )
    det_log = np.log(starting_earnings) + det_profile

    if model == "deterministic":
        output[:, working_mask] = np.exp(det_log[working_mask])
        return output

    # Stochastic: add persistent AR(1) + transitory iid shocks. Pin year 0
    # to zero shock so every path starts at the user's stated level.
    persistent = np.zeros((n_sims, n_years), dtype=np.float64)
    innovations = rng.normal(0.0, persistent_sigma, size=(n_sims, n_years))
    innovations[:, 0] = 0.0
    for t in range(1, n_years):
        persistent[:, t] = persistence * persistent[:, t - 1] + innovations[:, t]
    transitory = rng.normal(0.0, transitory_sigma, size=(n_sims, n_years))
    transitory[:, 0] = 0.0

    log_earnings = det_log[None, :] + persistent + transitory
    # Guard against pathological negative earnings via the lognormal floor.
    earnings = np.exp(log_earnings)
    output[:, working_mask] = earnings[:, working_mask]
    return output
