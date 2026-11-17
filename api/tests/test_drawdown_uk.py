"""Tests for the one-year UK drawdown calculator, without the rules engine.

Stand-in tax and Pension Credit rules replace the Axiom engine, so these check
what the calculator gives each rule and how it reports the answers. The real
rules run in test_drawdown_uk_axiom.py.

Invariants, for every input:
- Every sweep row accounts for every pound: money to spend equals the State
  Pension paid in the year plus other income, the draw and Pension Credit,
  less income tax and NI.
- State Pension paid is the yearly rate times the share of the tax year from
  State Pension age, and nothing while deferred. Pension Credit counts the
  weekly rate in each eligible week, claimed or deferred (reg 18(1)).
- Each band and next_1000 splits the pound in full: kept + tax + Pension
  Credit == 1. Bands run from 0 to the top of the sweep without gaps, and
  their rates add back up to the sweep's total change.
- A pot's sweep runs to its balance, or until taxable income passes £125,140,
  where the real rules charge the additional rate on every further pound
  (ITA 2007 ss.10(3A), (5A), 35(2)), tax-free cash taken first included.
- 0 <= Pension Credit <= eligible weeks x minimum guarantee; tax >= 0;
  taxable part of the draw <= draw.
- Pension Credit takes off the engine's tax on non-savings income plus NI
  (reg 17(10)), never more than the year's tax. Interest and dividends sit on
  top (ITA 2007 s.16) but taper the allowance (s.35(2)), so on the real rules
  they can raise it (test_drawdown_uk_axiom.py); these stand-ins don't taper.
- Regular pot draws: tax never falls as the draw rises. Pension Credit never
  falls below its no-draw level up to the pot's annuity income, and never
  rises beyond it. Without interest or dividends, money to spend never falls.
- ISA, GIA and cash draws leave tax unchanged and never lower Pension Credit.
- One-off draws taking tax-free cash first: the taxable part is the draw less
  the smaller of a quarter of the pot and the Lump Sum Allowance left.
- The same input gives the same output; the chosen draw equals its sweep row.
- A pot that turns 55 after the tax year can pay nothing in it (Finance Act
  2004 s.165 pension rule 1, Sch 29 paras 1(1)(d) and 4A(1)(c), s.279), so its
  sweep holds only the zero draw, with no bands, markers or next_1000.
  Otherwise next_1000 is missing only when the source is empty after the draw.
- On a coarse grid, band_edges places each kink of a piecewise-linear series
  within £1. A whole run places each turning point within 2p on these
  stand-in rules (two credit kinks £200 or more apart included).
- On the stepped stand-in (stand_in_stepped_tax: the Personal Savings
  Allowance of ITA 2007 ss.12A-12B and the allowance rounded up to the pound
  of s.35(3), in pence), each fall in the Personal Savings Allowance gets a
  band one penny wide with jump set, tax moves £1 or more across every jump
  band, and every other band charges 0p to 62p a pound and stays within £1
  of the straight line between its ends, so no step of £2 or more hides in
  it. That holds where a change of rate sits within a 24th of a grid
  interval of a jump too, since a run then looks again at the pieces around
  the jump: on the 20 examples CI runs and on HYPOTHESIS_PROFILE=thorough
  with 150 examples (two seeds) and 500, with interest from £600, so each
  jump is £20 or more and the change £100 or more of taxable income past it.
  (A jump under the £5 a piece must move beyond its neighbours' rates, as
  from £520 of interest, can go unfound.) The taper's band runs from the
  last penny before its first 40p step to the penny of its last, even where
  the grid samples each step at the same point (4% or 16% tax free). A run
  evaluates the year seven times at most: the grid, a closer look, one more
  only where a jump has a band beside it too short to judge, three placing
  changes to the penny, and one more only where a band is still not
  straight. test_drawdown_uk_axiom.py checks the reviewers' cases on the
  real engine.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import eggnest.core.uk_drawdown_year as envelope
from eggnest import axiom_uk, drawdown_bands, drawdown_uk
from eggnest.citations import Citation
from eggnest.cli import main as cli
from eggnest.core.router import run_core_scenario
from eggnest.core.uk_drawdown_year import (
    OUTPUT_KEY,
    build_uk_drawdown_year_scenario,
    caveats_for,
    extract_uk_drawdown_year_result,
)
from eggnest.drawdown_uk import (
    DrawdownEngines,
    DrawdownEngineUnavailable,
    age_on,
    band_breaks,
    band_edges,
    crossing_point,
    gad_annuity_income_per_1000,
    run_uk_drawdown_year,
)
from eggnest.models_uk_drawdown import (
    LUMP_SUM_ALLOWANCE,
    UKDrawdownYearInput,
    UKDrawdownYearResult,
    pot_locked_all_year,
)
from eggnest.programs import list_programs
from eggnest.tax_uk import AXIOM_UK_TAX_ENGINE, UKYearInputs, UKYearResults
from main import app

client = TestClient(app)

MINIMUM_GUARANTEE = 238.0
# On the real rules, income past the higher rate limit pays the additional rate
# and leaves no Personal Allowance (ITA 2007 ss.10(3A), (5A), 35(2)).
ADDITIONAL_RATE_INCOME = 125_140.0
PAST_QUALIFYING_AGE = date(1958, 6, 15)  # 67 on 6 April 2026
UNDER_QUALIFYING_AGE = date(1966, 6, 15)  # 59 on 6 April 2026


def stand_in_band_tax(income: np.ndarray) -> np.ndarray:
    taxable = np.maximum(income - 12_570.0, 0.0)
    return (
        0.20 * np.minimum(taxable, 37_700.0)
        + 0.40 * np.clip(taxable - 37_700.0, 0.0, 87_440.0)
        + 0.45 * np.maximum(taxable - 125_140.0, 0.0)
    )


def stand_in_tax(inputs: UKYearInputs) -> UKYearResults:
    """Banded tax in the shape of the real rules; not the real rules.

    No allowance taper, so savings and dividends on top leave the tax on
    non-savings income as it would be without them.
    """
    non_savings = (
        inputs.state_pension + inputs.private_pension_income + inputs.employment_income
    )
    income = non_savings + inputs.savings_interest + inputs.dividend_income
    income_tax = stand_in_band_tax(income)
    share_under_spa = 1.0 - (inputs.share_of_year_over_spa or 0.0)
    ni = 0.08 * np.maximum(inputs.employment_income - 12_570.0, 0.0) * share_under_spa
    return UKYearResults(
        net_income=income - income_tax - ni,
        total_tax=income_tax + ni,
        income_tax=income_tax,
        employee_ni=ni,
        non_savings_income_tax=stand_in_band_tax(non_savings),
    )


def stand_in_credit(*, year, weekly_income, capital) -> dict:
    """Guarantee credit in the shape of the real rule; not the real rule."""
    deemed = np.ceil(np.maximum(capital - 10_000.0, 0.0) / 500.0)
    return {
        "weekly_deemed_income": deemed,
        "annual_amount": np.maximum(MINIMUM_GUARANTEE - weekly_income - deemed, 0.0)
        * 52.0,
        "weekly_minimum_guarantee": MINIMUM_GUARANTEE,
        "citations": [Citation(id="stand-in credit", url="https://example.test/c")],
    }


STAND_INS = DrawdownEngines(
    tax=stand_in_tax,
    pension_credit=stand_in_credit,
    tax_citations=lambda year: [
        Citation(id="stand-in tax", url="https://example.test/t")
    ],
)


def run(inputs: UKDrawdownYearInput) -> UKDrawdownYearResult:
    return run_uk_drawdown_year(inputs, STAND_INS)


def _taxed_in_bands(taxable: np.ndarray) -> np.ndarray:
    """ITA 2007 s.10's rates on taxable income stacked from nothing."""
    return (
        0.20 * np.minimum(taxable, 37_700.0)
        + 0.40 * np.clip(taxable - 37_700.0, 0.0, 87_440.0)
        + 0.45 * np.maximum(taxable - 125_140.0, 0.0)
    )


def stand_in_stepped_tax(inputs: UKYearInputs) -> UKYearResults:
    """Banded tax with the two steps of the real rules; not the real rules.

    The allowance falls £1 for every £2 of income over £100,000, rounded up to
    the pound (ITA 2007 s.35(2)-(3)), so tax moves 40p at a time through the
    taper. Interest stacks on top, and its nil-rate slice, which still fills
    the bands, is £1,000, or £500 once any income reaches the higher rate,
    or nothing at the additional rate (ss.12A-12B), so tax jumps there.
    Figures round to the penny.
    """
    non_savings = (
        inputs.state_pension
        + inputs.private_pension_income
        + inputs.employment_income
        + inputs.dividend_income
    )
    savings = inputs.savings_interest
    # In whole pence, rounded down, so £100,002 of income is £100,002.
    income = np.floor(np.round((non_savings + savings) * 100, 6)) / 100
    allowance = np.ceil(
        np.maximum(12_570.0 - np.maximum(income - 100_000.0, 0.0) / 2, 0.0)
    )
    taxable_non_savings = np.maximum(non_savings - allowance, 0.0)
    taxable_savings = np.maximum(
        savings - np.maximum(allowance - non_savings, 0.0), 0.0
    )
    taxable = taxable_non_savings + taxable_savings
    savings_allowance = np.where(
        taxable > 125_140.0, 0.0, np.where(taxable > 37_700.0, 500.0, 1_000.0)
    )
    nil = np.minimum(savings_allowance, taxable_savings)
    income_tax = np.round(
        _taxed_in_bands(taxable)
        - (
            _taxed_in_bands(taxable_non_savings + nil)
            - _taxed_in_bands(taxable_non_savings)
        ),
        2,
    )
    ni = np.zeros_like(income_tax)
    return UKYearResults(
        net_income=income - income_tax,
        total_tax=income_tax,
        income_tax=income_tax,
        employee_ni=ni,
        non_savings_income_tax=np.round(_taxed_in_bands(taxable_non_savings), 2),
    )


STEPPED = DrawdownEngines(
    tax=stand_in_stepped_tax,
    pension_credit=stand_in_credit,
    tax_citations=STAND_INS.tax_citations,
)


def person(**overrides) -> UKDrawdownYearInput:
    """Past the qualifying age, with a provider's annuity rate of £50 per £1,000."""
    base = {
        "birth_date": PAST_QUALIFYING_AGE,
        "state_pension": 9_360.0,
        "annuity_income_per_1000": 50.0,
    }
    return UKDrawdownYearInput(**{**base, **overrides})


pounds = st.floats(
    min_value=0.0, max_value=300_000.0, allow_nan=False, allow_infinity=False
).map(lambda value: round(value, 2))


@st.composite
def scenarios(draw, sources=("sipp", "isa", "gia", "cash"), investment_income=True):
    source = draw(st.sampled_from(sources))
    balances = {
        "sipp_balance": draw(pounds),
        "isa_balance": draw(pounds),
        "gia_balance": draw(pounds),
        "cash_savings": draw(pounds),
    }
    key = "cash_savings" if source == "cash" else f"{source}_balance"
    share = draw(st.floats(min_value=0.0, max_value=1.0))
    income = pounds if investment_income else st.just(0.0)
    pattern = draw(st.sampled_from(["regular", "one_off"]))
    fraction = draw(st.sampled_from([0.0, 0.25]))
    cash_first = (
        source == "sipp"
        and pattern == "one_off"
        and fraction == 0.25
        and draw(st.booleans())
    )
    return UKDrawdownYearInput(
        birth_date=draw(st.dates(date(1935, 1, 1), date(1972, 4, 5))),
        state_pension=draw(pounds),
        state_pension_deferred=draw(st.booleans()),
        other_pension_income=draw(pounds),
        employment_income=draw(pounds),
        savings_interest=draw(income),
        dividend_income=draw(income),
        draw_source=source,
        draw_amount=round(balances[key] * share * 0.999, 2),
        sipp_draw_pattern=pattern,
        sipp_tax_free_fraction=fraction,
        sipp_tax_free_cash_first=cash_first,
        gilt_yield_percent=draw(st.floats(min_value=0.0, max_value=12.0)),
        **balances,
    )


@st.composite
def pot_draws(draw):
    """Pot draws up to £2 million beside modest income, where the top of the
    sweep matters most."""
    modest = st.floats(min_value=0.0, max_value=20_000.0).map(
        lambda value: round(value, 2)
    )
    pot = draw(
        st.floats(min_value=0.0, max_value=2_000_000.0).map(
            lambda value: round(value, 2)
        )
    )
    # Half take the tax-free cash first, which the general strategy rarely
    # pairs with a large pot and modest income.
    cash_first = draw(st.booleans())
    pattern = "one_off" if cash_first else draw(st.sampled_from(["regular", "one_off"]))
    fraction = 0.25 if cash_first else draw(st.sampled_from([0.0, 0.25]))
    return UKDrawdownYearInput(
        birth_date=draw(st.dates(date(1935, 1, 1), date(1972, 4, 5))),
        state_pension=draw(modest),
        other_pension_income=draw(modest),
        employment_income=draw(modest),
        savings_interest=draw(modest),
        dividend_income=draw(modest),
        sipp_balance=pot,
        draw_amount=round(pot * draw(st.floats(0.0, 0.5)), 2),
        sipp_draw_pattern=pattern,
        sipp_tax_free_fraction=fraction,
        sipp_tax_free_cash_first=cash_first,
        lump_sum_allowance_remaining=draw(
            st.one_of(
                st.just(LUMP_SUM_ALLOWANCE),
                st.floats(min_value=0.0, max_value=LUMP_SUM_ALLOWANCE).map(
                    lambda value: round(value, 2)
                ),
            )
        ),
    )


class TestAccounting:
    @given(scenarios())
    def test_every_row_accounts_for_every_pound(self, inputs):
        result = run(inputs)
        income = (
            result.state_pension_paid
            + inputs.other_pension_income
            + inputs.employment_income
            + inputs.savings_interest
            + inputs.dividend_income
        )
        for row in result.sweep:
            expected = (
                income
                + row.draw
                + row.pension_credit
                - row.income_tax
                - row.employee_ni
            )
            assert row.money_to_spend == pytest.approx(expected, abs=0.04)

    @given(scenarios())
    def test_bands_split_each_pound_in_full_and_cover_the_range(self, inputs):
        result = run(inputs)
        if len(result.sweep) == 1:
            assert result.bands == []
            return
        assert result.bands[0].draw_from == 0.0
        assert result.bands[-1].draw_to == result.sweep[-1].draw
        for left, right in zip(result.bands, result.bands[1:], strict=False):
            assert left.draw_to == right.draw_from
        for band in result.bands:
            assert band.draw_to > band.draw_from
            assert band.kept + band.to_tax + band.to_pension_credit == pytest.approx(
                1.0, abs=1e-6
            )

    @given(scenarios())
    def test_band_rates_add_back_up_to_the_total_change(self, inputs):
        result = run(inputs)
        if not result.bands:
            return
        added = sum((b.draw_to - b.draw_from) * b.kept for b in result.bands)
        total = result.sweep[-1].money_to_spend - result.sweep[0].money_to_spend
        assert added == pytest.approx(total, abs=0.1)

    @given(pot_draws())
    def test_the_sweep_reaches_the_pot_or_the_additional_rate(self, inputs):
        result = run(inputs)
        last = result.sweep[-1]
        other_income = (
            result.state_pension_paid
            + inputs.other_pension_income
            + inputs.employment_income
            + inputs.savings_interest
            + inputs.dividend_income
        )
        assert (
            last.draw >= inputs.sipp_balance - 0.005
            or last.taxable_draw + other_income > ADDITIONAL_RATE_INCOME
        )

    @given(scenarios())
    def test_next_1000_splits_the_pound_and_matches_the_money(self, inputs):
        result = run(inputs)
        step = result.next_1000
        if step is None:
            assert result.pot_left == 0.0 or pot_locked_all_year(inputs)
            return
        assert step.draw_from == result.at_chosen_draw.draw
        assert step.kept + step.to_tax + step.to_pension_credit == pytest.approx(
            1.0, abs=1e-6
        )

    @given(scenarios())
    def test_amounts_stay_within_their_limits(self, inputs):
        result = run(inputs)
        most_credit = result.pension_credit_working.eligible_weeks * MINIMUM_GUARANTEE
        for row in result.sweep:
            assert 0.0 <= row.pension_credit <= most_credit + 0.01
            assert row.income_tax >= 0.0
            assert row.employee_ni >= 0.0
            assert 0.0 <= row.taxable_draw <= row.draw + 0.005

    @given(scenarios())
    def test_chosen_draw_is_its_own_sweep_row(self, inputs):
        result = run(inputs)
        matches = [r for r in result.sweep if r.draw == result.at_chosen_draw.draw]
        assert matches == [result.at_chosen_draw]
        assert result.with_no_draw == result.sweep[0]

    @given(scenarios())
    def test_the_same_input_gives_the_same_result(self, inputs):
        assert run(inputs) == run(inputs)

    @given(scenarios())
    def test_headline_figures_match_the_chosen_row(self, inputs):
        result = run(inputs)
        assert result.income_tax.amount == result.at_chosen_draw.income_tax
        assert result.employee_ni.amount == result.at_chosen_draw.employee_ni
        assert result.pension_credit.amount == result.at_chosen_draw.pension_credit
        assert result.money_to_spend == result.at_chosen_draw.money_to_spend


def regular_inputs(**kwargs):
    return scenarios(sources=("sipp",), **kwargs).map(
        lambda inputs: inputs.model_copy(update={"sipp_draw_pattern": "regular"})
    )


class TestRegularPotDraws:
    @given(regular_inputs())
    def test_tax_never_falls_as_the_draw_rises(self, inputs):
        result = run(inputs)
        direct = [r.income_tax + r.employee_ni for r in result.sweep]
        assert all(b >= a - 0.02 for a, b in zip(direct, direct[1:], strict=False))

    @given(regular_inputs())
    def test_drawing_up_to_the_annuity_income_never_lowers_credit(self, inputs):
        result = run(inputs)
        annuity = (
            inputs.sipp_balance
            * (result.pension_credit_working.annuity_income_per_1000 or 0.0)
            / 1_000
        )
        for row in result.sweep:
            if row.draw <= annuity:
                assert row.pension_credit >= result.with_no_draw.pension_credit - 0.01

    @given(regular_inputs())
    def test_credit_never_rises_past_the_annuity_income(self, inputs):
        result = run(inputs)
        annuity = (
            inputs.sipp_balance
            * (result.pension_credit_working.annuity_income_per_1000 or 0.0)
            / 1_000
        )
        above = [r.pension_credit for r in result.sweep if r.draw >= annuity]
        assert all(b <= a + 0.01 for a, b in zip(above, above[1:], strict=False))

    # Interest and dividends sit outside the Pension Credit test, so tax
    # charged on them isn't deducted from counted income. With them, money to
    # spend can dip while credit tapers; that violation is intended.
    @given(regular_inputs(investment_income=False))
    def test_money_never_falls_without_investment_income(self, inputs):
        money = [r.money_to_spend for r in run(inputs).sweep]
        assert all(b >= a - 0.03 for a, b in zip(money, money[1:], strict=False))


class TestSavingsDraws:
    @given(scenarios(sources=("isa", "gia", "cash")))
    def test_tax_stays_put_and_credit_never_falls(self, inputs):
        result = run(inputs)
        for row in result.sweep:
            assert row.income_tax == result.with_no_draw.income_tax
            assert row.employee_ni == result.with_no_draw.employee_ni
            assert row.taxable_draw == 0.0
            assert row.pension_credit >= result.with_no_draw.pension_credit - 0.01


class TestPensionCreditCounting:
    """Hand calculations at DWP's own annuity rate of £50 per £1,000."""

    def test_undrawn_pot_counts_at_the_annuity_rate(self):
        # DMG 85460: £50,000 pot, £2,500 a year, £48.07 a week.
        working = run(person(sipp_balance=50_000.0)).pension_credit_working
        assert working.annual_annuity_income == 2_500.0
        assert working.notional_pot_income == pytest.approx(48.07, abs=0.01)
        assert working.regular_pot_income == 0.0

    def test_partial_withdrawal_tops_up_to_the_annuity_rate(self):
        # DMG 85460: some income drawn, the difference counts.
        working = run(
            person(sipp_balance=50_000.0, draw_amount=1_300.0)
        ).pension_credit_working
        assert working.regular_pot_income == 25.0
        assert working.notional_pot_income == pytest.approx(23.08, abs=0.01)

    def test_withdrawal_above_the_annuity_rate_replaces_notional_income(self):
        # DMG 85460: actual income of £50 a week beats notional income of £48.07.
        working = run(
            person(sipp_balance=50_000.0, draw_amount=2_600.0)
        ).pension_credit_working
        assert working.regular_pot_income == 50.0
        assert working.notional_pot_income == 0.0

    def test_one_off_withdrawal_reduces_the_pot_valued(self):
        # DMG 85458: £40,000 pot, £8,000 taken as capital, reassessed on £32,000.
        working = run(
            person(
                sipp_balance=40_000.0, draw_amount=8_000.0, sipp_draw_pattern="one_off"
            )
        ).pension_credit_working
        assert working.annual_annuity_income == 1_600.0
        assert working.notional_pot_income == pytest.approx(30.77, abs=0.01)
        assert working.regular_pot_income == 0.0

    def test_pot_draw_of_nothing_credit_by_hand(self):
        # 238 - (180 state pension + 48.0769 notional) = 9.9231 a week.
        result = run(person(sipp_balance=50_000.0))
        assert result.with_no_draw.pension_credit == pytest.approx(516.0, abs=0.01)

    def test_regular_draw_counts_the_tax_free_part_as_income(self):
        # DMG 85476: withdrawn income counts in full.
        working = run(
            person(
                sipp_balance=52_000.0, draw_amount=5_200.0, sipp_tax_free_fraction=0.25
            )
        ).pension_credit_working
        assert working.regular_pot_income == 100.0

    def test_one_off_draw_counts_as_capital_after_tax(self):
        inputs = person(
            sipp_balance=100_000.0,
            draw_amount=40_000.0,
            sipp_draw_pattern="one_off",
            state_pension=12_570.0,
        )
        result = run(inputs)
        taxable = 30_000.0
        expected_tax = 0.20 * taxable
        assert result.income_tax.amount == pytest.approx(expected_tax, abs=0.01)
        working = result.pension_credit_working
        assert working.capital_first_week == pytest.approx(
            (40_000.0 - expected_tax) * (1 - 0.5 / 52), abs=0.01
        )
        assert working.capital_last_week == pytest.approx(
            (40_000.0 - expected_tax) * (0.5 / 52), abs=0.01
        )
        # Reg 17(10) deducts tax on income; this draw is capital.
        assert working.tax_deducted == 0.0

    def test_savings_fall_week_by_week_as_money_is_spent(self):
        working = run(
            person(isa_balance=30_000.0, draw_source="isa", draw_amount=15_600.0)
        ).pension_credit_working
        assert working.capital_first_week == pytest.approx(30_000 - 150.0, abs=0.01)
        assert working.capital_last_week == pytest.approx(30_000 - 15_450.0, abs=0.01)
        assert working.deemed_income_first_week == 40.0
        assert (
            working.deemed_income_last_week == 10.0
        )  # £4,550 over: 9 steps and a part

    def test_tax_on_regular_income_comes_off_counted_income(self):
        result = run(person(sipp_balance=100_000.0, draw_amount=20_000.0))
        # Taxable income 9,360 + 15,000 = 24,360; tax 20% of 11,790.
        assert result.pension_credit_working.tax_deducted == pytest.approx(
            2_358.0 / 52, abs=0.01
        )

    def test_interest_and_dividends_stay_out_of_counted_tax(self):
        plain = run(person(sipp_balance=100_000.0, draw_amount=20_000.0))
        investing = run(
            person(
                sipp_balance=100_000.0,
                draw_amount=20_000.0,
                savings_interest=5_000.0,
                dividend_income=5_000.0,
            )
        )
        assert (
            investing.pension_credit_working.tax_deducted
            == plain.pension_credit_working.tax_deducted
        )
        assert investing.income_tax.amount > plain.income_tax.amount

    @given(scenarios())
    def test_tax_deducted_never_exceeds_the_tax_charged(self, inputs):
        # Reg 17(10) takes off tax payable on counted income, part of the
        # year's tax; a penny a week of rounding aside.
        result = run(inputs)
        deducted = result.pension_credit_working.tax_deducted * 52
        charged = result.income_tax.amount + result.employee_ni.amount
        assert deducted <= charged + 0.27

    def test_an_engine_without_non_savings_tax_is_refused(self):
        def total_only(inputs: UKYearInputs) -> UKYearResults:
            tax = stand_in_tax(inputs)
            tax.non_savings_income_tax = None
            return tax

        engines = DrawdownEngines(
            tax=total_only,
            pension_credit=stand_in_credit,
            tax_citations=STAND_INS.tax_citations,
        )
        with pytest.raises(DrawdownEngineUnavailable, match="non-savings"):
            run_uk_drawdown_year(person(), engines)

    def test_earnings_count_after_the_five_pound_disregard(self):
        working = run(person(employment_income=5_200.0)).pension_credit_working
        assert working.earnings_counted == 95.0

    def test_under_the_qualifying_age_no_credit_at_all(self):
        result = run(
            person(
                birth_date=UNDER_QUALIFYING_AGE,
                sipp_balance=50_000.0,
                state_pension=0.0,
            )
        )
        working = result.pension_credit_working
        assert working.status == "under_qualifying_age"
        assert working.eligible_weeks == 0
        assert working.weekly_minimum_guarantee is None
        assert all(r.pension_credit == 0.0 for r in result.sweep)

    def test_qualifying_after_the_last_week_assessed_counts_no_weeks(self):
        # Pension Credit age on Tuesday 30 March 2027, inside the tax year but
        # after the last Monday week assessed, which starts 29 March.
        result = run(person(birth_date=date(1960, 9, 30), state_pension=0.0))
        working = result.pension_credit_working
        assert working.qualifying_date == date(2027, 3, 30)
        assert working.eligible_weeks == 0
        assert working.status == "under_qualifying_age"
        assert result.pension_credit.amount == 0.0

    def test_reaching_the_qualifying_age_during_the_year(self):
        # 66th birthday on 15 June 2026.
        result = run(person(birth_date=date(1960, 6, 15), state_pension=0.0))
        working = result.pension_credit_working
        assert working.status == "calculated"
        assert working.qualifying_date > date(2026, 4, 6)
        assert 0 < working.eligible_weeks < 52
        assert result.with_no_draw.pension_credit == pytest.approx(
            working.eligible_weeks * MINIMUM_GUARANTEE, abs=0.01
        )


class TestStatePension:
    # Born 15 July 1960: State Pension age 66 years 4 months, 15 November 2026
    # (Pensions Act 2014 s.26), 142 of the year's 365 days.
    REACHES_SPA_IN_YEAR = date(1960, 7, 15)
    FULL_RATE = 12_547.60

    def test_paid_from_state_pension_age_for_the_rest_of_the_year(self):
        result = run(
            person(birth_date=self.REACHES_SPA_IN_YEAR, state_pension=self.FULL_RATE)
        )
        assert result.state_pension_age_date == date(2026, 11, 15)
        assert result.state_pension_paid == pytest.approx(
            self.FULL_RATE * 142 / 365, abs=0.01
        )
        assert result.money_to_spend == pytest.approx(
            result.state_pension_paid, abs=0.01
        )

    def test_pension_credit_counts_the_weekly_rate_in_each_eligible_week(self):
        # £241.30 a week of State Pension clears the £238 minimum guarantee in
        # each of the 20 weeks from 15 November, so no credit is due.
        result = run(
            person(birth_date=self.REACHES_SPA_IN_YEAR, state_pension=self.FULL_RATE)
        )
        working = result.pension_credit_working
        assert working.eligible_weeks == 20
        assert working.state_pension == pytest.approx(self.FULL_RATE / 52, abs=0.01)
        assert result.pension_credit.amount == 0.0

    def test_a_lower_rate_earns_credit_only_in_eligible_weeks(self):
        result = run(person(birth_date=self.REACHES_SPA_IN_YEAR, state_pension=9_360.0))
        assert result.pension_credit.amount == pytest.approx(20 * (238 - 180), abs=0.01)

    def test_under_state_pension_age_all_year_nothing_is_paid(self):
        result = run(person(birth_date=UNDER_QUALIFYING_AGE, state_pension=9_360.0))
        assert result.state_pension_paid == 0.0
        assert result.money_to_spend == 0.0

    def test_deferred_state_pension_is_not_paid_but_counts_for_credit(self):
        # SI 2002/1792 reg 18(1): a State Pension not claimed counts as
        # notional income from State Pension age.
        claimed = run(person(state_pension=9_360.0))
        deferred = run(person(state_pension=9_360.0, state_pension_deferred=True))
        assert deferred.state_pension_paid == 0.0
        assert claimed.state_pension_paid == 9_360.0
        assert deferred.pension_credit == claimed.pension_credit
        assert deferred.money_to_spend == pytest.approx(
            claimed.money_to_spend - 9_360.0, abs=0.01
        )

    @pytest.mark.parametrize("year_of_birth", [2004, 2005, 2006, 2007, 2008])
    def test_young_adults_with_a_pot_need_no_annuity_rate(self, year_of_birth):
        # Aged 18 to 22, past no qualifying age: the GAD table is never read.
        result = run(
            UKDrawdownYearInput(
                birth_date=date(year_of_birth, 1, 1),
                sipp_balance=10_000.0,
                isa_balance=5_000.0,
                draw_source="isa",
                draw_amount=1_000.0,
            )
        )
        working = result.pension_credit_working
        assert working.eligible_weeks == 0
        assert working.annuity_age is None
        assert working.annuity_income_per_1000 is None
        assert result.money_to_spend == 1_000.0


class TestTaxFreeCash:
    def test_a_quarter_of_each_withdrawal_is_tax_free(self):
        result = run(person(sipp_balance=100_000.0, draw_amount=40_000.0))
        assert result.at_chosen_draw.taxable_draw == 30_000.0

    def test_no_tax_free_cash_after_crystallising(self):
        result = run(
            person(
                sipp_balance=100_000.0, draw_amount=40_000.0, sipp_tax_free_fraction=0.0
            )
        )
        assert result.at_chosen_draw.taxable_draw == 40_000.0

    def test_lump_sum_allowance_caps_tax_free_cash(self):
        result = run(
            person(
                sipp_balance=100_000.0,
                draw_amount=40_000.0,
                lump_sum_allowance_remaining=4_000.0,
            )
        )
        assert result.at_chosen_draw.taxable_draw == 36_000.0

    def test_savings_are_never_taxable_draws(self):
        result = run(
            person(gia_balance=10_000.0, draw_source="gia", draw_amount=5_000.0)
        )
        assert result.at_chosen_draw.taxable_draw == 0.0
        assert result.assumptions.tax_free_fraction_applied == 0.0


class TestTaxFreeCashFirst:
    @staticmethod
    def one_off(**overrides) -> UKDrawdownYearInput:
        return person(
            sipp_balance=100_000.0,
            sipp_draw_pattern="one_off",
            sipp_tax_free_cash_first=True,
            **overrides,
        )

    def test_a_quarter_of_the_pot_comes_out_tax_free(self):
        result = run(self.one_off(draw_amount=25_000.0))
        assert result.at_chosen_draw.taxable_draw == 0.0
        assert result.assumptions.tax_free_cash_first

    def test_what_is_drawn_past_the_quarter_is_taxable(self):
        result = run(self.one_off(draw_amount=40_000.0))
        assert result.at_chosen_draw.taxable_draw == 15_000.0

    def test_the_lump_sum_allowance_caps_the_tax_free_cash(self):
        result = run(
            self.one_off(draw_amount=25_000.0, lump_sum_allowance_remaining=4_000.0)
        )
        assert result.at_chosen_draw.taxable_draw == 21_000.0

    def test_the_band_edge_sits_where_the_tax_free_cash_runs_out(self):
        # A State Pension that fills the personal allowance: every taxable
        # pound pays basic rate.
        result = run(self.one_off(draw_amount=25_000.0, state_pension=12_570.0))
        assert result.bands[0].draw_to == 25_000.0
        assert result.bands[0].to_tax == 0.0
        assert result.bands[1].to_tax == pytest.approx(0.2, abs=1e-6)

    def test_the_sweep_passes_the_additional_rate_threshold(self):
        # Past the tax-free cash every pound is taxable, so the stand-in's 45%
        # rate starts at a draw of £100,000 + £137,710 - £9,360 = £228,350.
        result = run(
            person(
                sipp_balance=400_000.0,
                draw_amount=25_000.0,
                sipp_draw_pattern="one_off",
                sipp_tax_free_cash_first=True,
            )
        )
        assert result.sweep[-1].draw > 228_350.0
        assert result.bands[-1].to_tax == pytest.approx(0.45, abs=1e-6)

    @given(scenarios(sources=("sipp",)))
    def test_taxable_part_is_what_passes_the_tax_free_cash(self, inputs):
        if not inputs.sipp_tax_free_cash_first:
            return
        cap = min(inputs.sipp_balance * 0.25, inputs.lump_sum_allowance_remaining)
        for row in run(inputs).sweep:
            assert row.taxable_draw == pytest.approx(max(row.draw - cap, 0.0), abs=0.01)


class TestBandEdges:
    @staticmethod
    def grid() -> np.ndarray:
        return np.unique(
            np.concatenate(
                [
                    [0.0, 1.0],
                    np.arange(0.0, 20_250.0, 250.0),
                    np.arange(0.0, 81_000.0, 1_000.0),
                ]
            )
        )

    @staticmethod
    def line(draws, kinks, rates) -> np.ndarray:
        edges = np.concatenate([[0.0], kinks, [draws[-1]]])
        pieces = np.clip(draws[:, None] - edges[:-1], 0.0, np.diff(edges))
        return pieces @ np.asarray(rates)

    @given(
        st.lists(
            st.floats(min_value=1_500.0, max_value=70_000.0),
            min_size=1,
            max_size=3,
            unique=True,
        ).filter(
            lambda values: all(
                b - a >= 4_000.0
                for a, b in zip(sorted(values), sorted(values)[1:], strict=False)
            )
        ),
        st.lists(st.sampled_from([0.0, 0.15, 0.3, 0.45, 0.6]), min_size=4, max_size=4),
    )
    def test_edges_land_on_each_true_kink(self, kinks, rates):
        kinks = sorted(kinks)
        rates = rates[: len(kinks) + 1]
        # Only a change of rate is a kink.
        real = [k for k, a, b in zip(kinks, rates, rates[1:], strict=False) if a != b]
        draws = self.grid()
        edges = band_edges(draws, self.line(draws, kinks, rates), np.zeros_like(draws))
        assert len(edges) == len(real) + 2
        for kink, edge in zip(real, edges[1:-1], strict=False):
            assert edge == pytest.approx(kink, abs=1.0)

    def test_a_kink_in_the_first_interval_is_placed(self):
        draws = self.grid()
        edges = band_edges(
            draws, self.line(draws, [30.0], [0.0, 0.15]), np.zeros_like(draws)
        )
        assert edges == pytest.approx([0.0, 30.0, draws[-1]], abs=0.01)

    def test_credit_kinks_are_placed_when_tax_runs_straight(self):
        draws = self.grid()
        credit = 1_416.0 - self.line(draws, [1_600.0, 3_016.0], [0.0, 1.0, 0.0])
        edges = band_edges(draws, np.zeros_like(draws), credit)
        assert edges == pytest.approx([0.0, 1_600.0, 3_016.0, draws[-1]], abs=0.01)

    def test_two_credit_kinks_inside_neighbouring_spans_are_both_placed(self):
        # uk-law-3: credit flat to £3,100, falls £1 per £1 to £3,376, then
        # tax from £4,760. The second kink sits inside the span the first
        # kink's crossing used to read.
        draws = np.unique(
            np.concatenate(
                [
                    [0.0, 1.0],
                    np.arange(0.0, 20_100.0, 100.0),
                    np.arange(0.0, 20_250.0, 250.0),
                ]
            )
        )
        credit = np.clip(276.0 - np.maximum(draws - 3_100.0, 0.0), 0.0, None)
        tax = 0.15 * np.maximum(draws - 4_760.0, 0.0)
        edges = band_edges(draws, tax, credit)
        assert edges == pytest.approx(
            [0.0, 3_100.0, 3_376.0, 4_760.0, 20_000.0], abs=0.01
        )

    def test_steps_in_deemed_income_do_not_fragment_bands(self):
        draws = np.arange(0.0, 20_250.0, 50.0)
        # 52 weeks of a £1 step per £500, spread as capital falls.
        spent = (np.arange(52) + 0.5) / 52
        capital = 30_000.0 - np.outer(draws, spent)
        credit = (40.0 - np.ceil((capital - 10_000.0) / 500.0)).sum(axis=1)
        edges = band_edges(draws, np.zeros_like(draws), credit)
        assert len(edges) == 2

    def test_straight_series_has_no_interior_edges(self):
        draws = self.grid()
        assert band_edges(draws, draws * 0.2, draws * 0.1).tolist() == [0.0, draws[-1]]

    def test_a_single_point_has_a_single_edge(self):
        assert band_edges(np.zeros(1), np.zeros(1), np.zeros(1)).tolist() == [0.0]

    def test_breaks_respect_each_series_tolerance(self):
        draws = np.arange(0.0, 1_001.0, 100.0)
        wiggle = np.where(draws == 500.0, 2.0, 0.0)
        assert band_breaks(draws, [(wiggle, 5.0)]) == [0, 10]
        assert 5 in band_breaks(draws, [(wiggle, 1.0)])

    def test_crossing_needs_two_lines_that_differ(self):
        draws = np.array([0.0, 100.0, 200.0, 300.0])
        straight = draws * 0.2
        assert crossing_point(draws, straight, (0, 1), (2, 3)) is None
        assert crossing_point(draws, straight, (1, 1), (2, 3)) is None

    def test_crossing_rejects_a_point_outside_the_gap(self):
        draws = np.array([0.0, 100.0, 200.0, 300.0])
        # Lines cross at 400, past the gap between grid points 1 and 2.
        values = np.array([0.0, 40.0, 40.0, 60.0])
        assert crossing_point(draws, values, (0, 1), (2, 3)) is None


class TestBandsAndMarkersOnWholeRuns:
    def test_regular_draw_bands_at_each_turning_point(self):
        # Annuity income £1,000; credit gone at £3,016; tax from £4,280.
        result = run(person(sipp_balance=20_000.0, draw_amount=2_500.0))
        edges = [round(b.draw_from) for b in result.bands] + [
            round(result.bands[-1].draw_to)
        ]
        assert edges == [0, 1_000, 3_016, 4_280, 20_000]
        assert [round(b.kept, 2) for b in result.bands] == [1.0, 0.0, 1.0, 0.85]
        assert [m.kind for m in result.markers] == [
            "pot_income_covered",
            "guarantee_credit_ends",
        ]
        assert [m.draw for m in result.markers] == pytest.approx(
            [1_000.0, 3_016.0], abs=1
        )

    def test_two_credit_kinks_276_apart_get_their_own_band(self):
        # uk-law-3's counterexample: aged 90, GAD factor 155, so a £20,000 pot
        # has £3,100 of annuity income; credit of £276 runs out at £3,376.
        result = run(
            UKDrawdownYearInput(
                birth_date=date(1936, 1, 10),
                state_pension=9_000.0,
                sipp_balance=20_000.0,
            )
        )
        edges = [band.draw_from for band in result.bands] + [result.bands[-1].draw_to]
        assert edges == pytest.approx(
            [0.0, 3_100.0, 3_376.0, 4_760.0, 20_000.0], abs=0.01
        )
        middle = result.bands[1]
        assert middle.to_pension_credit == pytest.approx(1.0, abs=1e-6)
        assert middle.kept == pytest.approx(0.0, abs=1e-6)

    @given(
        state_pension=st.floats(min_value=6_000.0, max_value=11_500.0).map(
            lambda value: round(value, 2)
        ),
        pot=st.floats(min_value=2_000.0, max_value=40_000.0).map(
            lambda value: round(value, 2)
        ),
    )
    def test_each_turning_point_of_a_regular_draw_is_an_edge(self, state_pension, pot):
        # Aged 90 at £155 per £1,000: credit is flat to the annuity income,
        # falls a pound per pound to 12,376 - State Pension, and tax starts
        # where three quarters of the draw fills the personal allowance.
        annuity = pot * 0.155
        credit_ends = 12_376.0 - state_pension
        if credit_ends - annuity < 200.0:
            return
        result = run(
            UKDrawdownYearInput(
                birth_date=date(1936, 1, 10),
                state_pension=state_pension,
                sipp_balance=pot,
            )
        )
        tax_starts = (12_570.0 - state_pension) / 0.75
        turns = [annuity, credit_ends, tax_starts]
        expected = [0.0, *(turn for turn in turns if turn < pot), pot]
        edges = [band.draw_from for band in result.bands] + [result.bands[-1].draw_to]
        assert edges == pytest.approx(expected, abs=0.02)

    def test_savings_draw_earns_credit_on_each_pound_spent(self):
        result = run(
            person(
                state_pension=9_360.0,
                isa_balance=30_000.0,
                draw_source="isa",
                draw_amount=15_000.0,
            )
        )
        assert result.next_1000 is not None
        assert result.next_1000.kept > 1.0
        assert result.next_1000.to_pension_credit < 0.0
        assert result.bands[0].kept == pytest.approx(1.05, abs=0.01)

    def test_no_pot_no_movement(self):
        result = run(person())
        assert [r.draw for r in result.sweep] == [0.0]
        assert result.bands == []
        assert result.next_1000 is None
        assert result.markers == []

    def test_last_pounds_of_the_pot_use_a_shorter_step(self):
        result = run(person(sipp_balance=1_500.0, draw_amount=1_000.0))
        assert result.next_1000 is not None
        assert result.next_1000.draw_to == 1_500.0

    def test_empty_pot_has_no_next_step(self):
        result = run(person(sipp_balance=1_500.0, draw_amount=1_500.0))
        assert result.next_1000 is None
        assert result.pot_left == 0.0

    def test_no_marker_for_covering_annuity_income_without_any_credit(self):
        result = run(
            person(
                state_pension=12_547.60, sipp_balance=400_000.0, draw_amount=30_000.0
            )
        )
        assert result.with_no_draw.pension_credit == 0.0
        assert result.markers == []

    def test_markers_skip_someone_under_the_qualifying_age(self):
        result = run(person(birth_date=UNDER_QUALIFYING_AGE, sipp_balance=20_000.0))
        assert result.markers == []

    def test_sweep_reaches_past_a_large_draw(self):
        result = run(
            person(
                sipp_balance=900_000.0,
                draw_amount=400_000.0,
                sipp_tax_free_fraction=0.0,
            )
        )
        assert result.sweep[-1].draw == 500_000.0
        assert 400_000.0 in {r.draw for r in result.sweep}

    def test_sweep_reaches_past_the_end_of_the_lump_sum_allowance(self):
        # A quarter of each draw is tax free until £268,275 of tax-free cash
        # is used, at a draw of £1,073,100; the sweep runs a quarter past it.
        result = run(person(sipp_balance=2_000_000.0, draw_amount=10_000.0))
        assert result.sweep[-1].draw == pytest.approx(1_073_100.0 * 1.25)
        assert 1_073_100.0 in {r.draw for r in result.sweep}
        last = result.bands[-1]
        assert last.draw_from == pytest.approx(1_073_100.0)
        assert last.to_tax == pytest.approx(0.45, abs=1e-6)

    def test_sweep_stops_at_the_balance_when_the_allowance_outlasts_it(self):
        result = run(person(sipp_balance=900_000.0, draw_amount=400_000.0))
        assert result.sweep[-1].draw == 900_000.0


def _stepped_tax(inputs: UKDrawdownYearInput, draws) -> np.ndarray:
    """The stepped stand-in's income tax at each draw."""
    calculation = drawdown_uk._Calculation(inputs, STEPPED)
    return calculation.evaluate(np.asarray(draws, dtype=float)).income_tax


def _assert_no_band_hides_a_step(
    inputs: UKDrawdownYearInput, result: UKDrawdownYearResult
) -> None:
    """Every band without ``jump`` stays within £1 of the straight line
    between its ends on the stepped stand-in and charges 0p to 62p a pound;
    every jump band is one penny across which tax moves £1 or more."""
    for band in result.bands:
        if band.jump:
            assert round(band.draw_to - band.draw_from, 2) == 0.01, band
            assert abs(band.to_tax) * 0.01 >= 1.0, band
            continue
        assert -1e-6 <= band.to_tax <= 0.62, band
        inside = np.round(np.linspace(band.draw_from, band.draw_to, 66), 2)
        tax = _stepped_tax(inputs, inside)
        chord = np.interp(inside, [inside[0], inside[-1]], [tax[0], tax[-1]])
        assert np.max(np.abs(tax - chord)) <= 1.0, (band.draw_from, band.draw_to)


def _jump_sizes(result: UKDrawdownYearResult) -> list[tuple[float, float]]:
    rows = {row.draw: row for row in result.sweep}
    return [
        (
            band.draw_from,
            round(rows[band.draw_to].income_tax - rows[band.draw_from].income_tax, 2),
        )
        for band in result.bands
        if band.jump
    ]


class TestStepsInIncomeTax:
    """R3 and R7 (2026-11-16 review) on the stepped stand-in."""

    # R3's probe: £48,000 of other pension and £1,500 of interest; a draw of
    # £770 takes income to the higher rate, and one of £75,640 to the
    # additional rate.
    PROBE = {
        "birth_date": PAST_QUALIFYING_AGE,
        "state_pension": 0.0,
        "other_pension_income": 48_000.0,
        "savings_interest": 1_500.0,
        "sipp_balance": 100_000.0,
        "sipp_tax_free_fraction": 0.0,
        "draw_amount": 770.0,
    }

    def test_each_savings_allowance_step_is_a_one_penny_jump(self):
        # £500 of interest goes from nil to 20% at £770.01, and the last £500
        # from nil to 40% at £75,640.01: £100 and £200.
        result = run_uk_drawdown_year(UKDrawdownYearInput(**self.PROBE), STEPPED)
        assert _jump_sizes(result) == [(770.0, 100.0), (75_640.0, 200.0)]
        jumps = [band for band in result.bands if band.jump]
        assert [round(b.draw_to - b.draw_from, 2) for b in jumps] == [0.01, 0.01]
        rates = [(b.draw_from, round(b.to_tax, 4)) for b in result.bands if not b.jump]
        assert rates == [
            (0.0, 0.2),
            (770.01, 0.4),
            (1_770.0, 0.2),
            (2_270.0, 0.4),
            (50_501.99, 0.6),
            (75_640.01, 0.45),
        ]

    @pytest.mark.parametrize(
        ("state_pension", "tax_free", "first_step", "last_step"),
        [
            # (1 - tax free) D + State Pension reaches £100,002 (the
            # allowance's first pound gone) and £125,140 (its last).
            (12_547.60, 0.25, 116_605.87, 150_123.20),
            (9_410.70, 0.25, 120_788.40, 154_305.74),
            # With 4% or 16% tax free, the grid and its 24ths sample the 40p
            # steps at the same point of each, so they look straight there.
            (12_547.60, 0.04, 91_098.34, 117_283.75),
            (9_410.70, 0.16, 107_846.79, 137_772.98),
        ],
    )
    def test_the_taper_ends_sit_on_its_first_and_last_steps(
        self, state_pension, tax_free, first_step, last_step
    ):
        # R7: a £2 million pot, so a £10,000 grid.
        inputs = person(
            state_pension=state_pension,
            sipp_balance=2_000_000.0,
            draw_amount=10_000.0,
            sipp_tax_free_fraction=tax_free,
        )
        before, at = _stepped_tax(inputs, [first_step - 0.01, first_step])
        assert at - before == pytest.approx(0.4 + 0.003, abs=0.011)
        result = run_uk_drawdown_year(inputs, STEPPED)
        starts = [band.draw_from for band in result.bands]
        assert round(first_step - 0.01, 2) in starts
        assert last_step in starts
        inside = [b for b in result.bands if 100_000.0 < b.draw_from < 1_073_100.0]
        assert all(b.draw_to - b.draw_from >= 1_000.0 for b in inside)
        assert not any(b.jump for b in result.bands)

    @given(
        pot_draws(),
        st.floats(600.0, 20_000.0).map(lambda value: round(value, 2)),
        st.one_of(st.none(), st.floats(0.0, 0.25).map(lambda value: round(value, 2))),
    )
    def test_no_band_hides_a_step(self, inputs, interest, tax_free):
        """Every band without ``jump`` stays within £1 of a straight line, so
        no step of £2 or more hides in it, and it charges between 0p and
        62p a pound; every jump band is one penny across which tax moves £1
        or more."""
        update = {"savings_interest": interest}
        if tax_free is not None and not inputs.sipp_tax_free_cash_first:
            update["sipp_tax_free_fraction"] = tax_free
        inputs = inputs.model_copy(update=update)
        _assert_no_band_hides_a_step(inputs, run_uk_drawdown_year(inputs, STEPPED))

    # Hypothesis found these with 150 examples. Each draws a £400,000.50
    # lump sum from a pot of £800,001, so the grid runs in £5,000 steps and
    # its 24ths are £208.33 apart. Past the jump where the Personal Savings
    # Allowance falls to £500 (ITA 2007 s.12B), tax rises 40p a pound until
    # the allowance's slice reaches the higher rate, then 20p until all the
    # non-savings income has, then 40p: the 40p stretch is £219 of draw in
    # the first case and £440 in the second, about one 24th and two.
    CROWDED = {
        "birth_date": date(1972, 1, 1),
        "sipp_balance": 800_001.0,
        "draw_amount": 400_000.50,
        "sipp_draw_pattern": "one_off",
        "sipp_tax_free_fraction": 0.25,
        "sipp_tax_free_cash_first": True,
    }

    CROWDED_CASES = [
        # £32 of Lump Sum Allowance left and £719 of interest: the change
        # at £49,802 sat on the 24th at £49,791.67, so the band above it
        # charged 21p and strayed £1.97 from straight.
        (
            {"lump_sum_allowance_remaining": 32.0, "savings_interest": 719.0},
            49_583.00,
            43.80,
            (49_802.00, 50_302.00),
        ),
        # £1,255 of dividends and £940 of interest: the jump kept its
        # 24th, £208.33 wide, as its jump band.
        (
            {"dividend_income": 1_255.0, "savings_interest": 940.0},
            248_075.25,
            88.00,
            (248_515.25, 249_015.25),
        ),
    ]

    @pytest.mark.parametrize(("overrides", "jump", "size", "kinks"), CROWDED_CASES)
    def test_a_change_of_rate_close_to_a_jump_gets_its_own_band(
        self, overrides, jump, size, kinks
    ):
        inputs = UKDrawdownYearInput(**{**self.CROWDED, **overrides})
        result = run_uk_drawdown_year(inputs, STEPPED)
        _assert_no_band_hides_a_step(inputs, result)
        assert (jump, size) in _jump_sizes(result)
        near = [
            (band.draw_from, round(band.to_tax, 4), band.jump)
            for band in result.bands
            if jump - 1_000.0 < band.draw_to and band.draw_from < kinks[1] + 1_000.0
        ]
        assert [is_jump for _, _, is_jump in near] == [False, True, False, False, False]
        assert [rate for _, rate, is_jump in near if not is_jump] == [
            0.2,
            0.4,
            0.2,
            0.4,
        ]
        # Changes of rate of 20p: within a cent plus half a penny over 20p.
        assert near[3][0] == pytest.approx(kinks[0], abs=0.01 + 0.005 / 0.2)
        assert near[4][0] == pytest.approx(kinks[1], abs=0.01 + 0.005 / 0.2)

    # Hypothesis found this one: the grid's piece after the £42.80 jump at
    # the higher rate holds 30p a pound to £66,360 and 15p after it (the
    # Personal Savings Allowance's £500 slice still fills the basic rate),
    # and it passed for a second jump.
    BESIDE_A_JUMP = {
        "birth_date": date(1972, 1, 1),
        "savings_interest": 714.0,
        "sipp_balance": 799_884.0,
        "draw_amount": 399_942.0,
        "sipp_draw_pattern": "one_off",
    }

    def test_a_change_of_rate_beside_a_jump_keeps_its_edge(self):
        result = run_uk_drawdown_year(
            UKDrawdownYearInput(**self.BESIDE_A_JUMP), STEPPED
        )
        near = [
            (band.draw_from, round(band.to_tax, 4), band.jump)
            for band in result.bands
            if 66_000.0 < band.draw_to and band.draw_from < 67_100.0
        ]
        assert [jump for _, _, jump in near] == [False, True, False, False, False]
        assert _jump_sizes(result)[0][1] == 42.80
        assert near[2][0] == pytest.approx(near[1][0] + 0.01, abs=1e-9)
        # Changes of rate of 15p: within a cent plus half a penny over 15p.
        assert near[3][0] == pytest.approx(66_360.0, abs=0.01 + 0.005 / 0.15)
        assert near[4][0] == pytest.approx(67_026.6667, abs=0.01 + 0.005 / 0.15)
        assert [rate for _, rate, _ in near[2:]] == [0.3, 0.15, 0.3]

    def test_a_run_evaluates_the_year_at_most_seven_times(self, monkeypatch):
        # The grid; a closer look; one more only where a located jump has a
        # band beside it too short to judge a line; three rounds placing
        # changes in income tax to the penny (the first with any edge no run
        # has evaluated); and one more only where a band is not straight.
        calls = []
        evaluate = drawdown_uk._Calculation.evaluate

        def counted(self, draws):
            calls.append(len(draws))
            return evaluate(self, draws)

        crowded = []
        find = drawdown_bands.crowded_jumps

        def found(*args):
            crowded.append(find(*args))
            return crowded[-1]

        monkeypatch.setattr(drawdown_uk._Calculation, "evaluate", counted)
        monkeypatch.setattr(drawdown_bands, "crowded_jumps", found)
        cases = [
            (self.PROBE, False),
            (self.BESIDE_A_JUMP, True),
            *(({**self.CROWDED, **case[0]}, True) for case in self.CROWDED_CASES),
        ]
        for case, looks_closer in cases:
            calls.clear()
            crowded.clear()
            run_uk_drawdown_year(UKDrawdownYearInput(**case), STEPPED)
            assert bool(crowded[0]) is looks_closer
            assert len(calls) <= (7 if looks_closer else 6)


class TestPotLockedAllYear:
    """A pot whose owner turns 55 after 5 April 2027 pays nothing in 2026/27."""

    def test_only_the_zero_draw_is_costed(self):
        inputs = person(
            birth_date=date(1980, 1, 10),
            state_pension=0.0,
            sipp_balance=10_000.0,
            draw_amount=0.0,
        )
        result = run(inputs)
        assert [row.draw for row in result.sweep] == [0.0]
        assert result.next_1000 is None
        assert result.bands == []
        assert result.markers == []
        assert result.minimum_pension_age_date == date(2035, 1, 10)
        caveats = caveats_for(inputs)
        assert not any("take this draw on or after" in c for c in caveats)
        locked = [c for c in caveats if "after this tax year ends" in c]
        assert len(locked) == 1
        assert "10 January 2035" in locked[0]
        assert "Sch 29" in locked[0]

    def test_the_lock_starts_with_births_from_6_april_1972(self):
        locked = run(
            person(birth_date=date(1972, 4, 6), sipp_balance=10_000.0, draw_amount=0.0)
        )
        assert [row.draw for row in locked.sweep] == [0.0]
        assert locked.next_1000 is None
        # 55 on 5 April 2027, the last day of the tax year.
        open_pot = run(
            person(birth_date=date(1972, 4, 5), sipp_balance=10_000.0, draw_amount=0.0)
        )
        assert open_pot.sweep[-1].draw == 10_000.0
        assert open_pot.next_1000 is not None

    def test_savings_sweep_as_usual_before_55(self):
        result = run(
            person(
                birth_date=date(1980, 1, 10),
                isa_balance=10_000.0,
                draw_source="isa",
                draw_amount=0.0,
            )
        )
        assert result.sweep[-1].draw == 10_000.0
        assert result.next_1000 is not None

    @given(
        birth_date=st.dates(date(1972, 4, 6), date(2008, 4, 6)),
        pot=pounds,
        income=pounds,
    )
    def test_a_locked_pot_costs_no_draw_but_zero(self, birth_date, pot, income):
        inputs = UKDrawdownYearInput(
            birth_date=birth_date,
            state_pension=0.0,
            employment_income=income,
            sipp_balance=pot,
            draw_amount=0.0,
        )
        assert pot_locked_all_year(inputs)
        result = run(inputs)
        assert [row.draw for row in result.sweep] == [0.0]
        assert result.next_1000 is None
        assert result.bands == []
        assert result.markers == []


class TestGadTable:
    def test_table_values(self):
        assert gad_annuity_income_per_1000(68, 5.25) == 82.0
        assert gad_annuity_income_per_1000(85, 5.25) == 155.0

    def test_ages_past_the_table_use_its_last_row(self):
        assert gad_annuity_income_per_1000(95, 5.25) == 155.0

    def test_yield_rounds_down_to_the_next_quarter_point(self):
        at_5_25 = gad_annuity_income_per_1000(68, 5.25)
        assert gad_annuity_income_per_1000(68, 5.49) == at_5_25
        assert gad_annuity_income_per_1000(68, 5.5) != at_5_25

    def test_yields_past_the_table_use_its_ends(self):
        assert gad_annuity_income_per_1000(68, 9.3) == gad_annuity_income_per_1000(
            68, 8.0
        )

    def test_the_default_assumption_reads_the_table(self):
        working = run(
            person_with_table := UKDrawdownYearInput(
                birth_date=PAST_QUALIFYING_AGE, sipp_balance=20_000.0
            )
        ).pension_credit_working
        assert person_with_table.annuity_income_per_1000 is None
        assert working.annuity_age == 67
        assert working.annuity_income_per_1000 == gad_annuity_income_per_1000(67, 5.25)

    def test_a_provider_figure_replaces_the_table(self):
        result = run(person(sipp_balance=20_000.0))
        assert result.pension_credit_working.annuity_income_per_1000 == 50.0
        assert result.assumptions.gilt_yield_percent_used is None

    @given(st.dates(date(1900, 1, 1), date(2010, 12, 31)))
    def test_age_counts_complete_years(self, birth_date):
        on = date(2026, 4, 6)
        age = age_on(birth_date, on)
        assert date(birth_date.year + age, birth_date.month, 1) <= on
        assert (birth_date.year + age + 1, birth_date.month, birth_date.day) > (
            on.year,
            on.month,
            on.day,
        )


class TestInputRules:
    def test_cannot_draw_more_than_the_pot_holds(self):
        with pytest.raises(ValidationError, match="exceeds"):
            person(sipp_balance=1_000.0, draw_amount=1_000.01)

    def test_cannot_draw_from_an_empty_source(self):
        with pytest.raises(ValidationError, match="exceeds"):
            person(sipp_balance=1_000.0, draw_source="isa", draw_amount=1.0)

    def test_pension_pot_locked_before_minimum_pension_age(self):
        with pytest.raises(ValidationError, match="before age 55"):
            person(birth_date=date(1975, 1, 1), sipp_balance=1_000.0, draw_amount=1.0)

    def test_pot_can_be_drawn_by_someone_turning_55_during_the_year(self):
        inputs = person(
            birth_date=date(1971, 8, 1), sipp_balance=1_000.0, draw_amount=1.0
        )
        assert run(inputs).minimum_pension_age_date == date(2026, 8, 1)

    def test_the_year_ends_on_5_april_2027(self):
        assert person(
            birth_date=date(1972, 4, 5), sipp_balance=1_000.0, draw_amount=1.0
        )
        with pytest.raises(ValidationError, match="before age 55"):
            person(birth_date=date(1972, 4, 6), sipp_balance=1_000.0, draw_amount=1.0)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"sipp_draw_pattern": "regular"},
            {"sipp_draw_pattern": "one_off", "sipp_tax_free_fraction": 0.0},
            {
                "sipp_draw_pattern": "one_off",
                "draw_source": "isa",
                "isa_balance": 1_000.0,
            },
        ],
    )
    def test_tax_free_cash_first_needs_a_one_off_pot_draw(self, overrides):
        with pytest.raises(ValidationError, match="sipp_tax_free_cash_first"):
            person(sipp_balance=1_000.0, sipp_tax_free_cash_first=True, **overrides)

    def test_savings_can_be_drawn_before_minimum_pension_age(self):
        assert person(
            birth_date=date(1975, 1, 1),
            isa_balance=1_000.0,
            draw_source="isa",
            draw_amount=1.0,
        )

    def test_scotland_is_refused(self):
        with pytest.raises(ValidationError):
            person(region="Scotland")

    def test_only_2026_is_offered(self):
        with pytest.raises(ValidationError):
            person(tax_year=2027)

    @pytest.mark.parametrize("birth_date", [date(1900, 1, 1), date(2015, 1, 1)])
    def test_age_must_be_adult_and_plausible(self, birth_date):
        with pytest.raises(ValidationError, match="age from 18 to 120"):
            person(birth_date=birth_date)

    def test_tax_free_share_cannot_pass_a_quarter(self):
        with pytest.raises(ValidationError):
            person(sipp_tax_free_fraction=0.26)


@pytest.fixture
def stand_in_engine(monkeypatch):
    monkeypatch.setattr(drawdown_uk, "default_engines", lambda: STAND_INS)
    monkeypatch.setattr(
        envelope.axiom_uk,
        "versions",
        lambda: {"axiom-rules-engine": "stand-in", "rulespec-uk": "stand-in"},
    )


class TestEnvelope:
    def test_scenario_round_trip_through_the_router(self, stand_in_engine):
        inputs = person(sipp_balance=20_000.0, draw_amount=2_500.0)
        scenario = build_uk_drawdown_year_scenario(inputs, tags={"fixture": "drawdown"})
        result = run_core_scenario(scenario)
        assert result.schema_version == "eggnest.result.v1"
        assert result.engine == "uk_drawdown_year"
        assert result.country == "GBR"
        assert OUTPUT_KEY in result.outputs
        assert result.assumptions["currency"] == "GBP"
        assert extract_uk_drawdown_year_result(result) == run(inputs)

    def test_every_figure_names_its_engine_and_law(self, stand_in_engine):
        result = extract_uk_drawdown_year_result(
            run_core_scenario(
                build_uk_drawdown_year_scenario(person(sipp_balance=20_000.0))
            )
        )
        for figure in (result.income_tax, result.employee_ni, result.pension_credit):
            assert figure.engine == AXIOM_UK_TAX_ENGINE
            assert figure.citations

    def test_pension_credit_cites_the_rules_applied_by_hand(self, stand_in_engine):
        result = extract_uk_drawdown_year_result(
            run_core_scenario(
                build_uk_drawdown_year_scenario(person(sipp_balance=20_000.0))
            )
        )
        ids = " ".join(ref.id for ref in result.pension_credit.citations)
        assert "reg 18" in ids
        assert "DWP Decision Makers Guide" in ids
        assert "GAD drawdown pension tables" in ids

    def test_envelope_lists_sources_and_versions(self, stand_in_engine):
        result = run_core_scenario(
            build_uk_drawdown_year_scenario(person(sipp_balance=20_000.0))
        )
        assert {s.name for s in result.sources} == {
            "Axiom rules engine",
            "rulespec-uk",
            "GAD drawdown pension tables",
        }
        assert result.reproducibility.tax_engine_versions["rulespec-uk"] == "stand-in"
        assert result.citations

    def test_annuity_source_follows_the_input(self, stand_in_engine):
        table = run_core_scenario(
            build_uk_drawdown_year_scenario(
                UKDrawdownYearInput(
                    birth_date=PAST_QUALIFYING_AGE, sipp_balance=1_000.0
                )
            )
        )
        provider = run_core_scenario(
            build_uk_drawdown_year_scenario(person(sipp_balance=1_000.0))
        )
        assert "GAD" in table.assumptions["annuity_rate_source"]
        assert "provider" in provider.assumptions["annuity_rate_source"]


class TestCaveats:
    @staticmethod
    def text(inputs) -> str:
        return " ".join(caveats_for(inputs))

    def test_always_names_what_it_leaves_out(self):
        text = self.text(person())
        for needed in (
            "not financial",
            "Housing Benefit",
            "Council Tax Reduction",
            "Scottish",
            "Savings Credit",
        ):
            assert needed in text

    def test_flags_capital_gains_only_with_a_gia(self):
        assert "Capital Gains" not in self.text(person())
        assert "Capital Gains" in self.text(person(gia_balance=1_000.0))

    def test_flags_northern_ireland_regulations(self):
        assert "Northern Ireland" not in self.text(person())
        assert "SR 2003 No. 28" in self.text(person(region="Northern Ireland"))

    def test_flags_savings_credit_for_older_claimants(self):
        older = self.text(person(birth_date=date(1945, 1, 1)))
        assert "Savings Credit (State Pension Credit Act" in older
        assert "men born before 6 April 1951" in older
        assert "Savings Credit (State Pension Credit Act" not in self.text(person())

    def test_names_the_state_pension_age_reached_in_the_year(self):
        text = self.text(person(birth_date=date(1960, 7, 15)))
        assert "State Pension age on 15 November 2026" in text

    def test_says_no_state_pension_is_counted_before_state_pension_age(self):
        text = self.text(person(birth_date=UNDER_QUALIFYING_AGE))
        assert "after this tax year, so we count no State Pension" in text

    def test_explains_a_deferred_state_pension(self):
        text = self.text(person(state_pension_deferred=True))
        assert "reg 18(1)" in text
        assert "reg 18(1)" not in self.text(person())

    def test_an_older_deferred_state_pension_counts_the_pension_not_the_lump_sum(
        self,
    ):
        # SI 2002/1792 reg 18(1B): after 12 months' deferral of a pre-2016
        # State Pension, DWP counts the pension payable if the lump sum were
        # chosen, without the extra pension for deferring (DMG 85445-85446).
        text = self.text(
            person(
                birth_date=date(1945, 1, 1),
                state_pension=5_200.0,
                state_pension_deferred=True,
            )
        )
        assert "counts the lump sum" not in text
        assert "reg 18(1B)" in text
        assert "if you chose the lump sum" in text
        # The new State Pension (s.16(1)(za)) is outside reg 18(1B).
        assert "18(1B)" not in self.text(person(state_pension_deferred=True))

    def test_discloses_how_dwp_times_pension_credit(self):
        # Claims and Payments Regs (SI 1987/1968) reg 16A: payable from the
        # first full benefit week, which ends on the payday; reg 26BA: paid in
        # arrears on a day set by the NI number. Neither is an input, so the
        # 52 Monday weeks from 6 April are an approximation the caveat names.
        inputs = UKDrawdownYearInput(birth_date=date(1960, 4, 12), state_pension=0)
        caveats = caveats_for(inputs)
        assert not any("every eligible week" in c for c in caveats)
        timing = [c for c in caveats if "52 weeks" in c and "payday" in c]
        assert len(timing) == 1
        assert "16A" in timing[0] and "26BA" in timing[0]
        assert "a week’s worth more or less" in timing[0]
        assert "Monday 6 April 2026" in timing[0]
        # The count itself stays: Mondays from 18 May 2026 to 29 March 2027.
        result = run(inputs)
        assert result.pension_credit_working.qualifying_date == date(2026, 5, 12)
        assert result.pension_credit_working.eligible_weeks == 46
        assert result.pension_credit.amount == pytest.approx(46 * 238.0, abs=0.01)

    def test_names_the_day_someone_turns_55(self):
        inputs = person(
            birth_date=date(1971, 8, 1), sipp_balance=1_000.0, draw_amount=1.0
        )
        assert "You turn 55 on 1 August 2026" in self.text(inputs)
        assert "You turn 55" not in self.text(person(sipp_balance=1_000.0))

    def test_flags_the_sale_deduction_on_shares_only_with_a_gia(self):
        assert "DMG 84763" not in self.text(person())
        assert "DMG 84763" in self.text(person(gia_balance=1_000.0))

    def test_flags_the_dmg_85472_reading_of_tax_free_cash(self):
        assert "DMG 85472" in self.text(person())

    @pytest.mark.parametrize(
        ("region", "needed", "absent"),
        [
            ("England", "SI 2012/2885", "help with rates"),
            ("Wales", "Wales sets its own", "SI 2012/2885"),
            ("Northern Ireland", "help with rates", "SI 2006/214"),
        ],
    )
    def test_local_help_is_worded_for_each_nation(self, region, needed, absent):
        text = self.text(person(region=region))
        assert needed in text
        assert absent not in text


class TestApi:
    @staticmethod
    def body(**overrides) -> dict:
        return build_uk_drawdown_year_scenario(
            person(sipp_balance=20_000.0, draw_amount=2_500.0, **overrides)
        ).model_dump(mode="json")

    def test_simulate_returns_the_envelope(self, stand_in_engine):
        response = client.post("/core/simulate", json=self.body())
        assert response.status_code == 200
        data = response.json()
        assert data["engine"] == "uk_drawdown_year"
        # 9,360 state pension + 2,500 draw + 52 x (238 - 180 - 48.08) credit.
        assert data["outputs"][OUTPUT_KEY]["money_to_spend"] == 12_376.0

    def test_invalid_inputs_are_rejected_before_any_rule_runs(self, stand_in_engine):
        body = self.body()
        body["inputs"]["draw_amount"] = 999_999.0
        response = client.post("/core/simulate", json=body)
        assert response.status_code == 422

    def test_missing_engine_is_a_service_error(self, monkeypatch):
        monkeypatch.setattr(axiom_uk, "available", lambda: False)
        response = client.post("/core/simulate", json=self.body())
        assert response.status_code == 503
        assert "Axiom rules engine" in response.json()["detail"]

    def test_programs_lists_the_calculator(self):
        program = {p.id: p for p in list_programs()}["uk_drawdown_year"]
        assert program.engine == "uk_drawdown_year"
        assert program.jurisdiction == "uk"
        assert program.outputs


class TestDefaultEngines:
    def test_refuses_to_run_without_the_axiom_engine(self, monkeypatch):
        monkeypatch.setattr(axiom_uk, "available", lambda: False)
        with pytest.raises(DrawdownEngineUnavailable, match="Axiom rules engine"):
            run_uk_drawdown_year(person())


class TestCli:
    def test_schema_describes_the_inputs(self):
        result = CliRunner().invoke(cli, ["core", "schema", "uk-drawdown-input"])
        assert result.exit_code == 0
        assert "draw_amount" in json.loads(result.output)["properties"]

    def test_run_accepts_raw_inputs(self, stand_in_engine, tmp_path):
        path = tmp_path / "scenario.json"
        path.write_text(
            person(sipp_balance=20_000.0, draw_amount=2_500.0).model_dump_json()
        )
        result = CliRunner().invoke(
            cli,
            [
                "core",
                "run",
                str(path),
                "--engine",
                "uk_drawdown_year",
                "--output-format",
                "envelope",
            ],
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["engine"] == "uk_drawdown_year"
