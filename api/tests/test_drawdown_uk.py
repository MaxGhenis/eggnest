"""Tests for the one-year UK drawdown calculator, without the rules engine.

Stand-in tax and Pension Credit rules replace the Axiom engine, so these check
what the calculator gives each rule and how it reports the answers. The real
rules run in test_drawdown_uk_axiom.py.

Invariants, for every input:
- Every sweep row accounts for every pound: money to spend equals all income
  plus the draw plus Pension Credit, less income tax and NI.
- Each band and next_1000 splits the pound in full: kept + tax + Pension
  Credit == 1. Bands run from 0 to the top of the sweep without gaps, and
  their rates add back up to the sweep's total change.
- 0 <= Pension Credit <= eligible weeks x minimum guarantee; tax >= 0;
  taxable part of the draw <= draw.
- Regular pot draws: tax never falls as the draw rises. Pension Credit never
  falls below its no-draw level up to the pot's annuity income, and never
  rises beyond it. Without interest or dividends, money to spend never falls.
- ISA, GIA and cash draws leave tax unchanged and never lower Pension Credit.
- The same input gives the same output; the chosen draw equals its sweep row.
- Band edges land within £1 of the true kink of a piecewise-linear function.
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
from eggnest import axiom_uk, drawdown_uk
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
from eggnest.models_uk_drawdown import UKDrawdownYearInput, UKDrawdownYearResult
from eggnest.programs import list_programs
from eggnest.tax_uk import AXIOM_UK_TAX_ENGINE, UKYearInputs, UKYearResults
from main import app

client = TestClient(app)

MINIMUM_GUARANTEE = 238.0
PAST_QUALIFYING_AGE = date(1958, 6, 15)  # 67 on 6 April 2026
UNDER_QUALIFYING_AGE = date(1966, 6, 15)  # 59 on 6 April 2026


def stand_in_tax(inputs: UKYearInputs) -> UKYearResults:
    """Banded tax in the shape of the real rules; not the real rules."""
    income = (
        inputs.state_pension
        + inputs.private_pension_income
        + inputs.employment_income
        + inputs.savings_interest
        + inputs.dividend_income
    )
    taxable = np.maximum(income - 12_570.0, 0.0)
    income_tax = (
        0.20 * np.minimum(taxable, 37_700.0)
        + 0.40 * np.clip(taxable - 37_700.0, 0.0, 87_440.0)
        + 0.45 * np.maximum(taxable - 125_140.0, 0.0)
    )
    share_under_spa = 1.0 - (inputs.share_of_year_over_spa or 0.0)
    ni = 0.08 * np.maximum(inputs.employment_income - 12_570.0, 0.0) * share_under_spa
    return UKYearResults(
        net_income=income - income_tax - ni,
        total_tax=income_tax + ni,
        income_tax=income_tax,
        employee_ni=ni,
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
    return UKDrawdownYearInput(
        birth_date=draw(st.dates(date(1935, 1, 1), date(1971, 4, 5))),
        state_pension=draw(pounds),
        other_pension_income=draw(pounds),
        employment_income=draw(pounds),
        savings_interest=draw(income),
        dividend_income=draw(income),
        draw_source=source,
        draw_amount=round(balances[key] * share * 0.999, 2),
        sipp_draw_pattern=draw(st.sampled_from(["regular", "one_off"])),
        sipp_tax_free_fraction=draw(st.sampled_from([0.0, 0.25])),
        gilt_yield_percent=draw(st.floats(min_value=0.0, max_value=12.0)),
        **balances,
    )


class TestAccounting:
    @given(scenarios())
    def test_every_row_accounts_for_every_pound(self, inputs):
        result = run(inputs)
        income = (
            inputs.state_pension
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

    @given(scenarios())
    def test_next_1000_splits_the_pound_and_matches_the_money(self, inputs):
        result = run(inputs)
        step = result.next_1000
        if step is None:
            assert result.pot_left == 0.0
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
            * result.pension_credit_working.annuity_income_per_1000
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
            * result.pension_credit_working.annuity_income_per_1000
            / 1_000
        )
        above = [r.pension_credit for r in result.sweep if r.draw >= annuity]
        assert all(b <= a + 0.01 for a, b in zip(above, above[1:], strict=False))

    # Interest and dividends sit outside the Pension Credit test, so tax they
    # cause isn't deducted from counted income. With them, money to spend can
    # dip while credit tapers; that violation is intended.
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

    def test_markers_skip_someone_under_the_qualifying_age(self):
        result = run(person(birth_date=UNDER_QUALIFYING_AGE, sipp_balance=20_000.0))
        assert result.markers == []

    def test_sweep_reaches_past_a_large_draw(self):
        result = run(person(sipp_balance=900_000.0, draw_amount=400_000.0))
        assert result.sweep[-1].draw == 500_000.0
        assert 400_000.0 in {r.draw for r in result.sweep}


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
        assert "may be too low" in self.text(person(birth_date=date(1945, 1, 1)))
        assert "may be too low" not in self.text(person())


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
