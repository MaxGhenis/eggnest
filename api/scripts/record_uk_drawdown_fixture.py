"""Record real-engine drawdown results for the frontend's tests.

The frontend reads amounts off the API's sweep. Its tests run against these
recorded results, and tests/test_drawdown_uk_axiom.py fails when they drift
from what the engine now produces.

Each scenario also records the engine's answers at draws between the sweep's
rows ("probes"), where the page reads its figures off a line, so the
frontend's tests can check what it shows there against the engine.

Run from api/ with the Axiom engine configured:

    uv run python scripts/record_uk_drawdown_fixture.py
"""

from __future__ import annotations

import bisect
import json
from pathlib import Path
from typing import Any

import numpy as np

from eggnest.core.uk_drawdown_year import run_uk_drawdown_year_scenario
from eggnest.drawdown_uk import _Calculation, default_engines
from eggnest.models_uk_drawdown import UKDrawdownYearInput

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "src"
    / "test"
    / "fixtures"
    / "uk-drawdown-recorded.json"
)

# The figures the page opens with: EXAMPLE_INPUTS in app/src/lib/uk-drawdown.ts.
EXAMPLE: dict[str, Any] = {
    "birth_date": "1958-06-15",
    "region": "England",
    "tax_year": 2026,
    "state_pension": 9360.0,
    "state_pension_deferred": False,
    "other_pension_income": 0.0,
    "employment_income": 0.0,
    "savings_interest": 0.0,
    "dividend_income": 0.0,
    "sipp_balance": 10000.0,
    "isa_balance": 0.0,
    "gia_balance": 0.0,
    "cash_savings": 0.0,
    "draw_source": "sipp",
    "draw_amount": 2500.0,
    "sipp_draw_pattern": "regular",
    "sipp_tax_free_fraction": 0.25,
    "sipp_tax_free_cash_first": False,
    "lump_sum_allowance_remaining": 268275.0,
    "gilt_yield_percent": 5.25,
    "annuity_income_per_1000": None,
}

SCENARIOS: dict[str, dict[str, Any]] = {
    "example": EXAMPLE,
    "one_off": {**EXAMPLE, "sipp_draw_pattern": "one_off"},
    "isa_with_deemed_income": {
        **EXAMPLE,
        "sipp_balance": 0.0,
        "isa_balance": 30000.0,
        "draw_source": "isa",
        "draw_amount": 15000.0,
    },
    "large_pot": {**EXAMPLE, "sipp_balance": 400000.0, "draw_amount": 30000.0},
    # State Pension age on 15 November 2026, part way through the year.
    "reaches_state_pension_age": {
        **EXAMPLE,
        "birth_date": "1960-07-15",
        "state_pension": 12547.6,
    },
    # Pension Credit age on Tuesday 30 March 2027: in the tax year, but after
    # the last counted week starts on 29 March, so no week counts.
    "pension_credit_age_in_last_days": {**EXAMPLE, "birth_date": "1960-09-30"},
    # 55 on 10 January 2035, after the tax year: the pot can pay nothing.
    "locked_pot": {
        **EXAMPLE,
        "birth_date": "1980-01-10",
        "state_pension": 0.0,
        "draw_amount": 0.0,
    },
    "tax_free_cash_first": {
        **EXAMPLE,
        "state_pension": 12547.6,
        "sipp_balance": 100000.0,
        "draw_amount": 25000.0,
        "sipp_draw_pattern": "one_off",
        "sipp_tax_free_cash_first": True,
    },
    # The Personal Savings Allowance falls from £1,000 to £500 at the higher
    # rate and to nothing at the additional rate (ITA 2007 s.12B), so income
    # tax jumps £100 at a draw of £770.00 and £200 at £75,640.00.
    "savings_allowance_steps": {
        **EXAMPLE,
        "state_pension": 0.0,
        "other_pension_income": 48000.0,
        "savings_interest": 1500.0,
        "sipp_balance": 100000.0,
        "sipp_tax_free_fraction": 0.0,
        "draw_amount": 30000.0,
    },
}


def probe_draws(result: dict[str, Any]) -> list[float]:
    """Draws off the sweep where the page reads its figures off a line: the
    middle of each band's first, middle and last interval between rows."""
    draws = [row["draw"] for row in result["sweep"]]
    picked: set[float] = set()
    for band in result["bands"]:
        low = bisect.bisect_left(draws, band["draw_from"])
        high = bisect.bisect_right(draws, band["draw_to"])
        inside = draws[low:high]
        gaps = list(zip(inside, inside[1:], strict=False))
        for start, end in {gaps[0], gaps[len(gaps) // 2], gaps[-1]} if gaps else ():
            middle = round((start + end) / 2, 2)
            if start < middle < end:
                picked.add(middle)
    return sorted(picked)


def probes(inputs: dict[str, Any], draws: list[float]) -> list[dict[str, Any]]:
    """The engine's year at each draw, as the API reports a chosen draw."""
    if not draws:
        return []
    calculation = _Calculation(UKDrawdownYearInput(**inputs), default_engines())
    evaluated = calculation.evaluate(np.asarray(draws, dtype=float))
    return [
        json.loads(evaluated.outcome(index).model_dump_json())
        for index in range(len(evaluated.draws))
    ]


def record_one(inputs: dict[str, Any]) -> dict[str, Any]:
    envelope = json.loads(run_uk_drawdown_year_scenario(inputs).model_dump_json())
    result = envelope["outputs"]["uk_drawdown_year_result"]
    return {
        "inputs": inputs,
        "envelope": envelope,
        "probes": probes(inputs, probe_draws(result)),
    }


def record() -> dict[str, Any]:
    """Run every scenario and return what the frontend's tests read."""
    return {name: record_one(inputs) for name, inputs in SCENARIOS.items()}


def main() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(record(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(f"Wrote {FIXTURE}")


if __name__ == "__main__":
    main()
