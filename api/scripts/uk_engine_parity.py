"""Parity report: Axiom rules engine vs policyengine-uk-compiled.

Runs a scenario grid through both UK tax backends and classifies every
difference as either a known encoding gap (with the statute that closes
it) or an unexplained discrepancy. Exits non-zero on unexplained
discrepancies so this can run as a gate once the gap list is empty.

Usage:
    EGGNEST_AXIOM_ENGINE_BIN=... EGGNEST_RULESPEC_UK_ROOT=... \
        uv run python scripts/uk_engine_parity.py [--output report.md]
"""

from __future__ import annotations

import argparse
import itertools
import sys

import numpy as np

from eggnest import axiom_uk
from eggnest.tax_uk import UKYearInputs, calculate_uk_tax

TOLERANCE = 1.0  # pounds; rounding differences below this are a match

AGES = [45, 60, 70]
EMPLOYMENT = [0.0, 30_000.0, 60_000.0]
PENSION = [0.0, 15_000.0, 45_000.0, 110_000.0]
DIVIDENDS = [0.0, 5_000.0]
SAVINGS = [0.0, 2_000.0]
STATE_PENSION_AT_70 = 11_502.0
YEAR = 2025


def classify(case: dict, delta: float) -> str | None:
    """Attribute a PE-vs-Axiom delta to a known gap, if one applies."""
    if abs(delta) <= TOLERANCE:
        return None
    reasons = []
    if case["dividends"] > 0:
        reasons.append("dividend nil rate not encoded (ITA 2007 s.13A)")
    if case["savings"] > 0:
        reasons.append(
            "savings allowance/starting rate not encoded (ITA 2007 ss.12-12B)"
        )
    if case["age"] >= 66 and case["employment"] > 0:
        reasons.append(
            "policyengine-uk-compiled charges employee NI over pensionable age "
            "(SSCBA 1992 s.6(3) exempts; Axiom is statutory here)"
        )
    if case["age"] >= 66:
        reasons.append(
            "policyengine-uk-compiled re-uprates/imputes State Pension for "
            "over-SPA records; the simulator supplies its own SP series"
        )
    return "; ".join(reasons) if reasons else "UNEXPLAINED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None, help="write a markdown report here")
    args = parser.parse_args()

    if not axiom_uk.available():
        print(
            "Axiom engine unavailable: set EGGNEST_AXIOM_ENGINE_BIN and "
            "EGGNEST_RULESPEC_UK_ROOT",
            file=sys.stderr,
        )
        return 2

    rows = []
    unexplained = 0
    for age, employment, pension, dividends, savings in itertools.product(
        AGES, EMPLOYMENT, PENSION, DIVIDENDS, SAVINGS
    ):
        if employment > 0 and pension > 0:
            continue  # keep the grid focused
        state_pension = STATE_PENSION_AT_70 if age >= 66 else 0.0
        case = {
            "age": age,
            "employment": employment,
            "pension": pension,
            "dividends": dividends,
            "savings": savings,
            "state_pension": state_pension,
        }
        inputs = UKYearInputs(
            age=age,
            year=YEAR,
            state_pension=np.array([state_pension]),
            private_pension_income=np.array([pension]),
            savings_interest=np.array([savings]),
            dividend_income=np.array([dividends]),
            employment_income=np.array([employment]),
        )
        axiom = float(axiom_uk.calculate_uk_tax_axiom(inputs).total_tax[0])
        pe = float(calculate_uk_tax(inputs).total_tax[0])
        delta = pe - axiom
        reason = classify(case, delta)
        if reason == "UNEXPLAINED":
            unexplained += 1
        rows.append(
            {
                **case,
                "axiom": axiom,
                "policyengine": pe,
                "delta": delta,
                "reason": reason,
            }
        )

    matched = sum(1 for row in rows if row["reason"] is None)
    lines = [
        "# UK tax engine parity: Axiom vs policyengine-uk-compiled",
        "",
        f"Tax year {YEAR}/{YEAR + 1}. {len(rows)} scenarios; "
        f"{matched} exact within £{TOLERANCE:.0f}; "
        f"{len(rows) - matched} differ ({unexplained} unexplained).",
        "",
        "| age | employment | pension | dividends | savings | Axiom | PolicyEngine | delta | classification |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['age']} | {row['employment']:,.0f} | {row['pension']:,.0f} "
            f"| {row['dividends']:,.0f} | {row['savings']:,.0f} "
            f"| {row['axiom']:,.2f} | {row['policyengine']:,.2f} "
            f"| {row['delta']:+,.2f} | {row['reason'] or 'match'} |"
        )
    report = "\n".join(lines)
    if args.output:
        with open(args.output, "w") as handle:
            handle.write(report + "\n")
    print(report)
    return 1 if unexplained else 0


if __name__ == "__main__":
    sys.exit(main())
