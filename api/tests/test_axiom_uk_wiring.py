"""Engine-free tests of the Axiom backend's wiring and the Pension Credit
screen's assembly. They run everywhere; test_axiom_uk.py covers the rules
engine itself."""

from __future__ import annotations

import json
import math
import stat
from datetime import date, timedelta

import numpy as np
import pytest

from eggnest import axiom_uk, simulation_uk
from eggnest.core.uk_retirement import run_uk_retirement
from eggnest.models_uk import UKSimulationInput
from eggnest.simulation_uk import (
    _pension_credit_screen,
    _PensionCreditYear,
    run_uk_simulation,
)
from eggnest.state_pension_age import anniversary, pension_credit_qualifying_date
from eggnest.tax_uk import (
    UKYearInputs,
    calculate_uk_tax,
    get_uk_tax_calculator,
    share_of_year_over_state_pension_age,
)

WEEKLY_GUARANTEE = 238.0


def fake_screen(*, year, weekly_income, capital):
    """Pure-Python stand-in for the engine: reg 15(6) and s.2 by hand."""
    tariff = np.ceil(np.maximum(np.asarray(capital) - 10_000.0, 0.0) / 500.0)
    credit = np.maximum(WEEKLY_GUARANTEE - (np.asarray(weekly_income) + tariff), 0)
    return {
        "weekly_deemed_income": tariff,
        "annual_amount": credit * 52.0,
        "weekly_minimum_guarantee": WEEKLY_GUARANTEE,
        "citations": [],
    }


@pytest.fixture
def fake_engine(monkeypatch):
    calls = []

    def screen(**kwargs):
        calls.append(kwargs)
        return fake_screen(**kwargs)

    monkeypatch.setattr(axiom_uk, "available", lambda: True)
    monkeypatch.setattr(axiom_uk, "pension_credit_screen", screen)
    return calls


# --- backend selection -------------------------------------------------------


def test_default_backend_is_policyengine(monkeypatch):
    monkeypatch.delenv("EGGNEST_UK_TAX_ENGINE", raising=False)
    assert get_uk_tax_calculator() is calculate_uk_tax


def test_axiom_backend_selected_when_available(monkeypatch):
    monkeypatch.setenv("EGGNEST_UK_TAX_ENGINE", "axiom")
    monkeypatch.setattr(axiom_uk, "available", lambda: True)
    assert get_uk_tax_calculator() is axiom_uk.calculate_uk_tax_axiom


def test_axiom_selected_but_unavailable_falls_back(monkeypatch):
    monkeypatch.setenv("EGGNEST_UK_TAX_ENGINE", "axiom")
    monkeypatch.setattr(axiom_uk, "available", lambda: False)
    assert get_uk_tax_calculator() is calculate_uk_tax


def test_no_screen_without_the_engine(monkeypatch):
    monkeypatch.setattr(axiom_uk, "available", lambda: False)
    result = run_uk_simulation(
        UKSimulationInput(
            current_age=70, max_age=72, annual_spending=10_000, n_simulations=100
        )
    )
    assert result.pension_credit is None


def test_rule_citation_url_handles_short_paths():
    # Act-level or non-statute rule ids must not crash citation building.
    assert (
        axiom_uk._rule_citation_url("uk:statutes/ukpga/2007/3#whole_act")
        == "https://www.legislation.gov.uk/ukpga/2007/3"
    )
    assert axiom_uk._rule_citation_url(
        "uk:policies/govuk/pension-credit#rule"
    ).startswith("https://www.legislation.gov.uk/")


# --- engine discovery (axiom-rules-engine v0.2.x rules) ----------------------


def _fake_engine_binary(tmp_path, capabilities: dict):
    binary = tmp_path / "axiom-rules-engine"
    binary.write_text(
        "#!/bin/sh\n" f"echo '{json.dumps(capabilities)}'\n",
    )
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
    return binary


def _rulespec_root(tmp_path, name="rulespec-uk"):
    root = tmp_path / name
    (root / "uk").mkdir(parents=True)
    return root


@pytest.fixture
def clear_capabilities_cache():
    axiom_uk._engine_capabilities.cache_clear()
    yield
    axiom_uk._engine_capabilities.cache_clear()


@pytest.mark.usefixtures("clear_capabilities_cache")
def test_available_with_a_supported_engine_and_checkout(tmp_path, monkeypatch):
    binary = _fake_engine_binary(
        tmp_path, {"artifact_format_version": 2, "engine_version": "0.2.2"}
    )
    monkeypatch.setenv("EGGNEST_AXIOM_ENGINE_BIN", str(binary))
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(_rulespec_root(tmp_path)))
    assert axiom_uk.available()


@pytest.mark.usefixtures("clear_capabilities_cache")
@pytest.mark.parametrize(
    "capabilities",
    [
        {"artifact_format_version": 1, "engine_version": "0.1.9"},
        {"artifact_format_version": 2, "engine_version": "0.3.0"},
        {},
    ],
)
def test_unsupported_engine_is_unavailable(tmp_path, monkeypatch, capabilities):
    binary = _fake_engine_binary(tmp_path, capabilities)
    monkeypatch.setenv("EGGNEST_AXIOM_ENGINE_BIN", str(binary))
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(_rulespec_root(tmp_path)))
    assert not axiom_uk.available()


def test_rulespec_root_must_be_a_real_rulespec_uk_checkout(tmp_path, monkeypatch):
    good = _rulespec_root(tmp_path)
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(good))
    assert axiom_uk.rulespec_uk_root() == good.resolve()

    # A symlink resolves to the canonical path the engine requires.
    link = tmp_path / "link-to-rulespec"
    link.symlink_to(good)
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(link))
    assert axiom_uk.rulespec_uk_root() == good.resolve()

    # The engine rejects any other directory name ...
    wrong_name = _rulespec_root(tmp_path, "rulespec-uk-main")
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(wrong_name))
    assert axiom_uk.rulespec_uk_root() is None

    # ... and content directories at the top level (a stale checkout).
    (good / "legislation").mkdir()
    monkeypatch.setenv("EGGNEST_RULESPEC_UK_ROOT", str(good))
    assert axiom_uk.rulespec_uk_root() is None


# --- employee NI past State Pension age (SSCBA 1992 s.6(3)) ------------------


def _tax_inputs(**overrides) -> UKYearInputs:
    fields = {
        "age": 66,
        "year": 2026,
        "state_pension": np.zeros(1),
        "private_pension_income": np.zeros(1),
        "savings_interest": np.zeros(1),
        "dividend_income": np.zeros(1),
        "employment_income": np.array([40_000.0]),
    }
    fields.update(overrides)
    return UKYearInputs(**fields)


def test_no_employee_ni_on_earnings_after_state_pension_age():
    # Born 1 Jan 1959: State Pension age 66 on 1 Jan 2025, before this year.
    over = calculate_uk_tax(_tax_inputs(age=67, birth_date=date(1959, 1, 1)))
    assert over.employee_ni[0] == 0.0
    # Without a birth date the engine's own NI stands.
    unknown = calculate_uk_tax(_tax_inputs(age=67))
    assert unknown.employee_ni[0] == pytest.approx(2_194.40, abs=0.01)


def test_employee_ni_prorated_in_the_year_state_pension_age_falls():
    # Born 6 Oct 1960: State Pension age 66y7m, reached 6 May 2027, part-way
    # through the year from the 66th birthday (6 Oct 2026) to the 67th.
    birth = date(1960, 10, 6)
    inputs = _tax_inputs(age=66, birth_date=birth)
    share = share_of_year_over_state_pension_age(inputs)
    start, end = anniversary(birth, 66), anniversary(birth, 67)
    reached = pension_credit_qualifying_date(birth)
    assert reached == date(2027, 5, 6)
    assert share == pytest.approx((end - reached).days / (end - start).days)
    ni = calculate_uk_tax(inputs).employee_ni[0]
    assert ni == pytest.approx(2_194.40 * (1 - share), abs=0.01)


# --- Pension Credit screen assembly ------------------------------------------


def _years(birth, ages, weekly_income, capital, alive=None):
    n = len(weekly_income)
    alive = np.ones(n, dtype=bool) if alive is None else np.asarray(alive)
    return [
        _PensionCreditYear(
            age=age,
            alive=alive,
            weekly_income=np.asarray(weekly_income, dtype=float),
            capital=np.asarray(capital, dtype=float),
        )
        for age in ages
    ]


def test_under_qualifying_age_is_its_own_status(fake_engine):
    birth = date(1986, 9, 29)  # State Pension age 68
    screen = _pension_credit_screen(
        _years(birth, range(40, 61), [0.0], [0.0]), birth, date(2026, 9, 29)
    )
    assert screen.status == "under_qualifying_age"
    assert (screen.qualifying_age_years, screen.qualifying_age_months) == (68, 0)
    assert screen.weekly_minimum_guarantee is None
    assert screen.ages == []
    assert fake_engine == []  # nothing to screen, so no engine call
    assert any("Sch 4" in citation.id for citation in screen.citations)


def test_credit_is_pro_rata_in_the_qualifying_year(fake_engine):
    birth = date(1960, 10, 6)  # qualifies 6 May 2027, during the age-66 year
    screen = _pension_credit_screen(
        _years(birth, [65, 66, 67], [100.0], [0.0]), birth, date(2025, 10, 6)
    )
    assert screen.status == "screened"
    assert (screen.qualifying_age_years, screen.qualifying_age_months) == (66, 7)
    assert screen.ages == [66, 67]  # the age-65 year is before qualifying
    full_year = (WEEKLY_GUARANTEE - 100.0) * 52
    start, end = anniversary(birth, 66), anniversary(birth, 67)
    share = (end - date(2027, 5, 6)).days / (end - start).days
    assert screen.median_annual_amount_by_age == pytest.approx(
        [round(full_year * share, 2), full_year], abs=0.01
    )
    assert screen.first_age_indicated == 66


def test_only_living_paths_count(fake_engine):
    birth = date(1955, 1, 1)
    screen = _pension_credit_screen(
        _years(birth, [71, 72], [100.0, 100.0, 500.0], [0.0] * 3, alive=[1, 0, 1]),
        birth,
        date(2026, 1, 1),
    )
    # Two living paths each year: one low-income (indicated), one not.
    assert screen.share_indicated_by_age == [0.5, 0.5]
    # The dead low-income path never counts as indicated.
    assert screen.share_of_paths_indicated == pytest.approx(1 / 3)


def test_savings_count_as_capital_not_their_income(fake_engine):
    """GIA dividends are not income for Pension Credit (Sch IV para 18); the
    GIA counts through the reg 15(6) tariff instead, so a pensioner living
    off a £60,000 GIA's dividends on a small State Pension is screened on
    State Pension + £100/week deemed income."""
    result = run_uk_simulation(
        UKSimulationInput(
            current_age=70,
            max_age=70,
            annual_spending=8_000,
            state_pension_annual=6_000,
            state_pension_start_age=66,
            gia_balance=60_000,
            dividend_yield=0.05,
            return_source="gaussian",
            return_volatility=0.0,
            inflation_rate=0.0,
            n_simulations=100,
            include_mortality=False,
        )
    )
    call = fake_engine[0]
    tax = calculate_uk_tax(
        UKYearInputs(
            age=70,
            year=date.today().year,
            state_pension=np.full(1, 6_000.0),
            private_pension_income=np.zeros(1),
            savings_interest=np.zeros(1),
            dividend_income=np.full(1, 3_000.0),
            employment_income=np.zeros(1),
        )
    ).total_tax[0]
    assert call["weekly_income"] == pytest.approx((6_000 - tax) / 52)
    assert call["capital"] == pytest.approx(60_000)
    credit = (WEEKLY_GUARANTEE - ((6_000 - tax) / 52 + 100)) * 52
    assert result.pension_credit.median_annual_amount_by_age == pytest.approx(
        [credit], abs=0.01
    )


def test_pension_drawdown_counts_in_full_and_earnings_after_disregards(
    fake_engine,
):
    """Drawdown counts gross, tax-free cash included (SPC Act s.16(1)(f));
    earnings count after half of pension contributions and £5 a week."""
    run_uk_simulation(
        UKSimulationInput(
            current_age=70,
            max_age=70,
            annual_spending=15_000,
            state_pension_annual=0,
            sipp_balance=200_000,
            employment_income=10_000,
            retirement_age=75,
            savings_rate=0.1,
            sipp_contribution_share=1.0,
            return_source="gaussian",
            return_volatility=0.0,
            inflation_rate=0.0,
            n_simulations=100,
            include_mortality=False,
        )
    )
    flows = next(
        simulation_uk.iterate_uk_year_flows(
            UKSimulationInput(
                current_age=70,
                max_age=70,
                annual_spending=15_000,
                state_pension_annual=0,
                sipp_balance=200_000,
                employment_income=10_000,
                retirement_age=75,
                savings_rate=0.1,
                sipp_contribution_share=1.0,
                return_source="gaussian",
                return_volatility=0.0,
                inflation_rate=0.0,
                n_simulations=100,
                include_mortality=False,
            )
        )
    )
    draw = flows.withdrawal_sipp[0]
    assert draw > 0
    earnings = 10_000 - 0.5 * 1_000 - 5 * 52
    expected = (draw + earnings - flows.total_tax[0]) / 52
    assert fake_engine[0]["weekly_income"][0] == pytest.approx(expected)


def test_screen_samples_at_most_500_paths(fake_engine):
    result = run_uk_simulation(
        UKSimulationInput(
            current_age=70,
            max_age=70,
            annual_spending=10_000,
            n_simulations=1_200,
            include_mortality=False,
        )
    )
    assert result.pension_credit.paths_screened == 500
    assert len(fake_engine[0]["weekly_income"]) == 500


def test_core_envelope_carries_screen_citations(fake_engine, monkeypatch):
    from eggnest.core.uk_retirement import extract_uk_simulation_result

    envelope = run_uk_retirement(
        UKSimulationInput(
            current_age=70,
            max_age=71,
            annual_spending=10_000,
            n_simulations=100,
            include_mortality=False,
        )
    )
    screen = extract_uk_simulation_result(envelope).pension_credit
    ids = {citation.id for citation in envelope.citations}
    assert {citation.id for citation in screen.citations} <= ids
    assert any("Sch 4" in citation_id for citation_id in ids)


def test_qualifying_age_is_state_pension_age_for_recent_births():
    for birth in (date(1960, 4, 5), date(1961, 3, 6), date(1978, 4, 6)):
        start = anniversary(birth, 60)
        assert pension_credit_qualifying_date(birth) > start
    assert math.isclose(
        (pension_credit_qualifying_date(date(1961, 3, 6)) - date(1961, 3, 6))
        / timedelta(days=365.25),
        67,
        abs_tol=0.01,
    )
