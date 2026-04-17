"""Golden regression tests for deterministic simulator cases."""

import pytest

from tests.simulation_goldens import (
    generate_simulation_goldens,
    get_simulation_golden_cases,
    load_simulation_golden_fixture,
)


@pytest.fixture(scope="module")
def simulation_golden_fixture() -> dict[str, dict]:
    """Load the checked-in simulator goldens once for the module."""
    return load_simulation_golden_fixture()


def test_simulation_golden_fixture_covers_all_cases(
    simulation_golden_fixture: dict[str, dict],
):
    """The fixture should map exactly to the declared deterministic cases."""
    expected_cases = {case.name for case in get_simulation_golden_cases()}
    assert set(simulation_golden_fixture) == expected_cases


def test_simulation_goldens_match_fixture(
    simulation_golden_fixture: dict[str, dict],
):
    """Seeded simulator outputs should stay pinned to the checked-in goldens."""
    assert generate_simulation_goldens() == simulation_golden_fixture
