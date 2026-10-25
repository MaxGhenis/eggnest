"""Shared pytest configuration."""

import os

from hypothesis import HealthCheck, settings

# Property-based tests run a fixed, derandomized set of examples by default so
# CI is reproducible. HYPOTHESIS_PROFILE=thorough explores 400 random examples
# per property (override with HYPOTHESIS_MAX_EXAMPLES).
settings.register_profile(
    "ci",
    max_examples=20,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "thorough",
    max_examples=int(os.environ.get("HYPOTHESIS_MAX_EXAMPLES", "400")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "ci"))
