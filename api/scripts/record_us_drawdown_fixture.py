"""Record real-engine US drawdown results for the frontend's tests.

The frontend reads amounts off the API's sweep. Its tests run against these
recorded results, and tests/test_drawdown_us_policyengine.py fails when they
drift from what PolicyEngine-US now produces.

Each scenario also records PolicyEngine-US's answers at draws between the
sweep's rows ("probes"), where the page reads its figures off a line, so the
frontend's tests can check what it shows there against the engine.

Run from api/:

    uv run python scripts/record_us_drawdown_fixture.py
"""

from __future__ import annotations

import bisect
import json
from pathlib import Path
from typing import Any

import numpy as np

from eggnest.core.us_drawdown_year import run_us_drawdown_year_scenario
from eggnest.drawdown_us import _evaluate, default_engine
from eggnest.models_us_drawdown import USDrawdownYearInput

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "src"
    / "test"
    / "fixtures"
    / "us-drawdown-recorded.json"
)

_NOBODY: dict[str, Any] = {
    "social_security": 0.0,
    "pension_income": 0.0,
    "government_pension_income": 0.0,
    "earnings": 0.0,
    "traditional_balance": 0.0,
    "roth_balance": 0.0,
    "other_traditional_withdrawals": 0.0,
    "other_withdrawals_account": "ira",
    "roth_conversion": 0.0,
}

# The figures the page opens with: EXAMPLE_INPUTS in app/src/lib/us-drawdown.ts.
EXAMPLE: dict[str, Any] = {
    "tax_year": 2026,
    "state": "NC",
    "filing_status": "single",
    "you": {
        **_NOBODY,
        "birth_year": 1952,
        "social_security": 24000.0,
        "traditional_balance": 250000.0,
    },
    "spouse": None,
    "taxable_interest": 0.0,
    "tax_exempt_interest": 0.0,
    "dividends": 0.0,
    "taxable_balance": 0.0,
    "taxable_gain_share": 0.5,
    "cash_savings": 15000.0,
    "draw_source": "traditional",
    "draw_owner": "you",
    "draw_account": "ira",
    "draw_amount": 30000.0,
}

SCENARIOS: dict[str, dict[str, Any]] = {
    "example": EXAMPLE,
    # Social Security of $12,000 and small savings in California: SNAP, a
    # Medicare Savings Program and Medi-Cal, each with an end.
    "low_income": {
        **EXAMPLE,
        "state": "CA",
        "you": {
            **_NOBODY,
            "birth_year": 1958,
            "social_security": 12000.0,
            "traditional_balance": 20000.0,
        },
        "cash_savings": 500.0,
        "draw_amount": 3000.0,
    },
    "roth": {
        **EXAMPLE,
        "you": {**EXAMPLE["you"], "roth_balance": 100000.0},
        "draw_source": "roth",
        "draw_amount": 20000.0,
    },
    # A couple on Medicare who both pay the income-related premiums.
    "couple": {
        **EXAMPLE,
        "state": "FL",
        "filing_status": "married_filing_jointly",
        "you": {
            **_NOBODY,
            "birth_year": 1954,
            "social_security": 40000.0,
            "traditional_balance": 2000000.0,
        },
        "spouse": {**_NOBODY, "birth_year": 1956, "social_security": 25000.0},
        "dividends": 20000.0,
        "draw_amount": 150000.0,
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
    """PolicyEngine-US's year at each draw, as the API reports a chosen draw."""
    if not draws:
        return []
    model = USDrawdownYearInput(**inputs)
    evaluated = _evaluate(
        default_engine(), model, np.asarray(draws, dtype=float)
    ).evaluated
    return [
        json.loads(evaluated.outcome(index).model_dump_json())
        for index in range(len(evaluated.draws))
    ]


def record_one(inputs: dict[str, Any]) -> dict[str, Any]:
    envelope = json.loads(run_us_drawdown_year_scenario(inputs).model_dump_json())
    result = envelope["outputs"]["us_drawdown_year_result"]
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
