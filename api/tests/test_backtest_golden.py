"""Golden regression tests for deterministic historical backtests."""

import pytest

from tests.backtest_goldens import (
    generate_backtest_goldens,
    get_backtest_golden_cases,
    load_backtest_golden_fixture,
)


@pytest.fixture(scope="module")
def backtest_golden_fixture() -> dict[str, dict]:
    """Load the checked-in historical backtest goldens once for the module."""
    return load_backtest_golden_fixture()


def test_backtest_golden_fixture_covers_all_cases(
    backtest_golden_fixture: dict[str, dict],
):
    """The fixture should map exactly to the declared historical backtest cases."""
    expected_cases = {case.name for case in get_backtest_golden_cases()}
    assert set(backtest_golden_fixture) == expected_cases


def test_backtest_goldens_match_fixture(
    backtest_golden_fixture: dict[str, dict],
):
    """Seeded historical backtests should stay pinned to the checked-in goldens."""
    assert generate_backtest_goldens() == backtest_golden_fixture
