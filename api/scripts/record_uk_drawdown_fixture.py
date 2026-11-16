"""Record real-engine drawdown results for the frontend's tests.

The frontend reads amounts off the API's sweep. Its tests run against these
recorded results, and tests/test_drawdown_uk_axiom.py fails when they drift
from what the engine now produces.

Run from api/ with the Axiom engine configured:

    uv run python scripts/record_uk_drawdown_fixture.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eggnest.core.uk_drawdown_year import run_uk_drawdown_year_scenario

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
    "tax_free_cash_first": {
        **EXAMPLE,
        "state_pension": 12547.6,
        "sipp_balance": 100000.0,
        "draw_amount": 25000.0,
        "sipp_draw_pattern": "one_off",
        "sipp_tax_free_cash_first": True,
    },
}


def record() -> dict[str, Any]:
    """Run every scenario and return what the frontend's tests read."""
    return {
        name: {
            "inputs": inputs,
            "envelope": json.loads(
                run_uk_drawdown_year_scenario(inputs).model_dump_json()
            ),
        }
        for name, inputs in SCENARIOS.items()
    }


def main() -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(record(), sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(f"Wrote {FIXTURE}")


if __name__ == "__main__":
    main()
