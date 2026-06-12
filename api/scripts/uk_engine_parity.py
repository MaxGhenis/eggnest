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


def _expected_gap_bound(case: dict) -> tuple[float, list[str]]:
    """Maximum |delta| the known policyengine-uk-compiled quirks can explain.

    Each entry excuses only the delta it can actually produce, so a genuine
    bug cannot hide behind a known difference. The former encoding gaps
    (dividend nil rate, savings allowances) closed with rulespec-uk PR #48,
    so dividends/savings cases must now match exactly. NI percentages are
    read from the SSCBA 1992 s.8 encoding; the remaining magnitudes come
    from the cited values file.
    """
    params = axiom_uk._statutory_inputs()
    gaps = params["parity_gap_bounds"]
    income_tax = params["income_tax_rates"]
    ni = params["national_insurance"]

    bound = 0.0
    reasons = []
    if case["dividends"] > 0:
        # Both engines apply the s.13A nil rate, but they place it in
        # different bands when it straddles a boundary: the encoding follows
        # the statutory "first £500" (bottom-up); policyengine-uk-compiled
        # relieves the top slice. The difference is bounded by the nil-rate
        # amount at the spread between the highest and lowest dividend rates.
        nil_amount = axiom_uk._artifact_parameter(
            "ita_s13A", "dividend_nil_rate_allowance", YEAR
        )
        dividend_rates = params["dividend_tax"]
        bound += min(case["dividends"], nil_amount) * (
            dividend_rates["dividend_additional_rate"]
            - dividend_rates["dividend_ordinary_rate"]
        )
        reasons.append(
            "dividend nil-rate band placement: encoding nil-rates the first "
            "slice (ITA 2007 s.13A); policyengine-uk-compiled relieves the "
            "top slice"
        )
    if case["savings"] > 0 and case["dividends"] > 0:
        # s.12B(3) sizes the savings allowance counting income charged at the
        # dividend upper/additional rates (the encoding's reading);
        # policyengine-uk-compiled sizes it before dividend stacking, so the
        # tiers can differ by one step. Bound: one tier step at the highest
        # rate the displaced savings could bear.
        tier_step = axiom_uk._artifact_parameter(
            "ita_s12B", "savings_allowance_higher_rate_amount", YEAR
        )
        bound += tier_step * income_tax["additional_rate"]
        reasons.append(
            "savings allowance sizing: ITA 2007 s.12B(3) counts dividend-band "
            "income (encoding); policyengine-uk-compiled sizes the allowance "
            "before dividend stacking"
        )
    if case["age"] >= ni["state_pension_age"] and case["employment"] > 0:
        # PE charges employee NI over pensionable age; bound = the NI it adds.
        main_rate = axiom_uk._artifact_parameter(
            "sscba_s8", "main_primary_percentage", YEAR
        )
        additional_rate = axiom_uk._artifact_parameter(
            "sscba_s8", "additional_primary_percentage", YEAR
        )
        weekly = case["employment"] / 52.0
        main_band = max(
            min(weekly, ni["weekly_upper_earnings_limit"])
            - ni["weekly_primary_threshold"],
            0.0,
        )
        upper_band = max(weekly - ni["weekly_upper_earnings_limit"], 0.0)
        bound += (main_band * main_rate + upper_band * additional_rate) * 52.0
        reasons.append(
            "policyengine-uk-compiled charges employee NI over pensionable age "
            "(SSCBA 1992 s.6(3) exempts; Axiom is statutory here)"
        )
    if case["age"] >= ni["state_pension_age"]:
        # PE re-uprates/imputes State Pension for over-SPA records: bound the
        # excused income tax at a full new State Pension at the top rate.
        bound += gaps["full_new_state_pension_ceiling"] * (
            income_tax["additional_rate"]
        )
        reasons.append(
            "policyengine-uk-compiled re-uprates/imputes State Pension for "
            "over-SPA records; the simulator supplies its own SP series"
        )
    return bound, reasons


def classify(case: dict, delta: float) -> str | None:
    """Attribute a PE-vs-Axiom delta to a known gap, if one can explain it."""
    if abs(delta) <= TOLERANCE:
        return None
    bound, reasons = _expected_gap_bound(case)
    if reasons and abs(delta) <= bound + TOLERANCE:
        return "; ".join(reasons)
    return "UNEXPLAINED"


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
