"""Experimental UK tax and benefits backend via the Axiom rules engine.

Evaluates rulespec-uk statute encodings (Income Tax Act 2007 ss.10/13/35,
SSCBA 1992 s.8, State Pension Credit Act 2002 s.2, SI 2002/1792 reg 6)
through the Axiom rules engine binary. Each computed amount carries a
statute-level citation harvested from the engine's explain traces.

This backend is opt-in (EGGNEST_UK_TAX_ENGINE=axiom) and degrades to
unavailable when the engine binary or the rulespec-uk checkout is absent.

Known gaps versus policyengine-uk-compiled, asserted in tests and reported
by scripts/uk_engine_parity.py — all conservative (overstate tax):
- no savings allowance or starting rate for savings (ITA ss.12-12B not yet
  encoded): savings interest is taxed as non-savings income;
- no dividend nil rate (ITA s.13A not yet encoded);
- no Scottish or Welsh rates: the region input is ignored.

Statutory values that rulespec-uk still takes as runtime inputs (band
limits, rates, NI thresholds) come from data/axiom_uk_parameters.yaml with
per-value legal sources.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml

from .citations import Citation
from .tax_uk import UKYearInputs, UKYearResults

_TAX_YEAR_START = "-04-06"
_TAX_YEAR_END = "-04-05"

# Rule modules evaluated by this backend, relative to the rulespec-uk root.
_ARTIFACT_SOURCES = {
    "ita_s10": "statutes/ukpga/2007/3/10.yaml",
    "ita_s13": "statutes/ukpga/2007/3/13.yaml",
    "ita_s35": "statutes/ukpga/2007/3/35.yaml",
    "sscba_s8": "statutes/ukpga/1992/4/8.yaml",
    "spca_s2": "statutes/ukpga/2002/16/2.yaml",
    "spc_regs_6": "regulations/uksi/2002/1792/6.yaml",
}

_REF_PREFIXES = {
    "ita_s10": "uk:statutes/ukpga/2007/3/10#",
    "ita_s13": "uk:statutes/ukpga/2007/3/13#",
    "ita_s35": "uk:statutes/ukpga/2007/3/35#",
    "sscba_s8": "uk:statutes/ukpga/1992/4/8#",
    "spca_s2": "uk:statutes/ukpga/2002/16/2#",
    "spc_regs_6": "uk:regulations/uksi/2002/1792/6#",
}

_PARAMS_PATH = Path(__file__).parent / "data" / "axiom_uk_parameters.yaml"


def engine_binary() -> Path | None:
    """Locate the Axiom rules engine binary, if configured or on PATH."""
    configured = os.environ.get("EGGNEST_AXIOM_ENGINE_BIN")
    if configured:
        path = Path(configured)
        return path if path.exists() else None
    found = shutil.which("axiom-rules-engine")
    return Path(found) if found else None


def rulespec_uk_root() -> Path | None:
    """Locate the rulespec-uk checkout, if configured or in a known spot."""
    configured = os.environ.get("EGGNEST_RULESPEC_UK_ROOT")
    if configured:
        path = Path(configured)
        return path if path.exists() else None
    return None


def available() -> bool:
    """Whether the Axiom backend can run in this environment."""
    return engine_binary() is not None and rulespec_uk_root() is not None


@lru_cache(maxsize=1)
def _statutory_inputs() -> dict:
    """Cited statutory values supplied as runtime inputs (see module doc)."""
    raw = yaml.safe_load(_PARAMS_PATH.read_text())
    return {
        group: {name: entry["value"] for name, entry in entries.items()}
        for group, entries in raw.items()
    }


@lru_cache(maxsize=1)
def statutory_input_citations() -> list[Citation]:
    """Citations for the interim statutory input values."""
    raw = yaml.safe_load(_PARAMS_PATH.read_text())
    citations: list[Citation] = []
    for entries in raw.values():
        for name, entry in entries.items():
            citations.append(Citation(id=f"statutory-input:{name}", url=entry["url"]))
    return _dedupe_citations(citations)


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, str]] = set()
    unique: list[Citation] = []
    for citation in citations:
        key = (citation.id, citation.url)
        if key not in seen:
            seen.add(key)
            unique.append(citation)
    return unique


@dataclass(frozen=True)
class _Artifacts:
    """Compiled engine artifacts for one process lifetime."""

    directory: Path
    paths: dict[str, Path]


@lru_cache(maxsize=1)
def _artifacts() -> _Artifacts:
    binary = engine_binary()
    root = rulespec_uk_root()
    if binary is None or root is None:
        raise RuntimeError(
            "Axiom backend unavailable: set EGGNEST_AXIOM_ENGINE_BIN and "
            "EGGNEST_RULESPEC_UK_ROOT"
        )
    directory = Path(tempfile.mkdtemp(prefix="eggnest-axiom-uk-"))
    paths: dict[str, Path] = {}
    for key, relative in _ARTIFACT_SOURCES.items():
        output = directory / f"{key}.compiled.json"
        process = subprocess.run(
            [
                str(binary),
                "compile",
                "--program",
                str(root / relative),
                "--output",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"Axiom compile failed for {relative}: {process.stderr.strip()}"
            )
        paths[key] = output
    return _Artifacts(directory=directory, paths=paths)


def _tax_year_period(year: int) -> dict:
    return {
        "period_kind": "tax_year",
        "start": f"{year}{_TAX_YEAR_START}",
        "end": f"{year + 1}{_TAX_YEAR_END}",
    }


def _scalar(value: float | bool) -> dict:
    if isinstance(value, bool):
        return {"kind": "bool", "value": value}
    return {"kind": "decimal", "value": f"{float(value):.6f}"}


def _execute(
    artifact_key: str,
    *,
    year: int,
    per_entity_inputs: dict[str, np.ndarray],
    shared_inputs: dict[str, float | bool],
    outputs: list[str],
    mode: str = "fast",
    n: int | None = None,
) -> dict[str, np.ndarray] | tuple[dict[str, np.ndarray], list[dict]]:
    """Run one rule module for a batch of entities (one per Monte Carlo path)."""
    artifacts = _artifacts()
    prefix = _REF_PREFIXES[artifact_key]
    period = _tax_year_period(year)
    interval = {"start": period["start"], "end": period["end"]}

    if n is None:
        n = len(next(iter(per_entity_inputs.values())))
    records = []
    for name, values in per_entity_inputs.items():
        ref = prefix + "input." + name
        for index in range(n):
            records.append(
                {
                    "name": ref,
                    "entity": "Person",
                    "entity_id": f"p{index}",
                    "interval": interval,
                    "value": _scalar(float(values[index])),
                }
            )
    for name, value in shared_inputs.items():
        ref = prefix + "input." + name
        for index in range(n):
            records.append(
                {
                    "name": ref,
                    "entity": "Person",
                    "entity_id": f"p{index}",
                    "interval": interval,
                    "value": _scalar(value),
                }
            )

    request = {
        "mode": mode,
        "dataset": {"inputs": records, "relations": []},
        "queries": [
            {
                "entity_id": f"p{index}",
                "period": period,
                "outputs": [prefix + output for output in outputs],
            }
            for index in range(n)
        ],
    }
    process = subprocess.run(
        [
            str(engine_binary()),
            "run-compiled",
            "--artifact",
            str(artifacts.paths[artifact_key]),
        ],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"Axiom execution failed for {artifact_key}: {process.stderr.strip()}"
        )
    response = json.loads(process.stdout)

    results: dict[str, np.ndarray] = {
        output: np.zeros(n, dtype=float) for output in outputs
    }
    by_entity = {result["entity_id"]: result for result in response["results"]}
    for index in range(n):
        result = by_entity[f"p{index}"]
        for output in outputs:
            value = result["outputs"][prefix + output]["value"]["value"]
            results[output][index] = float(value)

    if mode == "explain":
        traces = [result.get("trace", {}) for result in response["results"]]
        return results, traces
    return results


def _rule_citation_url(rule_id: str) -> str:
    """Map an engine rule id to its legislation.gov.uk URL."""
    # e.g. uk:statutes/ukpga/2007/3/10#income_tax_on_section_10_income
    path = rule_id.split(":", 1)[1].split("#", 1)[0]
    parts = path.split("/")
    if parts[0] == "statutes":
        _, kind, year, chapter, section = parts[:5]
        return (
            f"https://www.legislation.gov.uk/{kind}/{year}/{chapter}/section/{section}"
        )
    if parts[0] == "regulations":
        _, kind, year, number, regulation = parts[:5]
        return f"https://www.legislation.gov.uk/{kind}/{year}/{number}/regulation/{regulation}"
    return f"https://www.legislation.gov.uk/{path}"


def _trace_citations(traces: list[dict]) -> list[Citation]:
    citations: list[Citation] = []
    for trace in traces:
        for rule_id, node in trace.items():
            url = node.get("source_url") or _rule_citation_url(rule_id)
            citations.append(Citation(id=rule_id, url=url))
    return _dedupe_citations(citations)


def calculate_uk_tax_axiom(inputs: UKYearInputs) -> UKYearResults:
    """UK tax for one simulated year via the Axiom rules engine.

    Mirrors the ITA 2007 s.23 calculation steps, with each computed step
    delegated to the statute encodings; only income classification and the
    s.25(2) allowance-ordering glue live here.
    """
    params = _statutory_inputs()
    it = params["income_tax"]
    div = params["dividend_tax"]
    ni = params["national_insurance"]
    year = inputs.year

    employment = inputs.employment_income.astype(float)
    # Gap (ITA ss.12-12B not yet encoded): savings interest is taxed as
    # non-savings income, with no personal savings allowance.
    non_savings = (
        employment
        + inputs.state_pension.astype(float)
        + inputs.private_pension_income.astype(float)
        + inputs.savings_interest.astype(float)
    )
    dividends = inputs.dividend_income.astype(float)
    total_income = non_savings + dividends

    # ITA 2007 s.35: personal allowance with the adjusted-net-income taper.
    pa = _execute(
        "ita_s35",
        year=year,
        per_entity_inputs={"adjusted_net_income": total_income},
        shared_inputs={
            "individual_makes_claim": True,
            "individual_meets_requirements_under_section_56": True,
        },
        outputs=["personal_allowance"],
    )["personal_allowance"]

    # ITA 2007 s.25(2) ordering: allowance against non-savings income first,
    # any remainder against dividend income.
    pa_non_savings = np.minimum(pa, non_savings)
    pa_dividends = np.minimum(pa - pa_non_savings, dividends)
    taxable_non_savings = non_savings - pa_non_savings
    taxable_dividends = dividends - pa_dividends

    # ITA 2007 s.10: band placement and tax on non-dividend income.
    s10 = _execute(
        "ita_s10",
        year=year,
        per_entity_inputs={"income_charged_under_section_10": taxable_non_savings},
        shared_inputs={
            "basic_rate_limit": it["basic_rate_limit"],
            "higher_rate_limit": it["higher_rate_limit"],
            "basic_rate": it["basic_rate"],
            "higher_rate": it["higher_rate"],
            "additional_rate": it["additional_rate"],
        },
        outputs=["income_tax_on_section_10_income"],
    )
    non_savings_tax = s10["income_tax_on_section_10_income"]

    # ITA 2007 s.13: dividend income stacks above other income (s.16) and
    # is charged at the dividend rates. Gap: no s.13A dividend nil rate.
    s13 = _execute(
        "ita_s13",
        year=year,
        per_entity_inputs={
            "dividend_income_subject_to_section_13_rates": taxable_dividends,
            "income_already_charged_before_section_13_dividend_income": (
                taxable_non_savings
            ),
        },
        shared_inputs={
            "basic_rate_limit": it["basic_rate_limit"],
            "higher_rate_limit": it["higher_rate_limit"],
            "dividend_ordinary_rate": div["dividend_ordinary_rate"],
            "dividend_upper_rate": div["dividend_upper_rate"],
            "dividend_additional_rate": div["dividend_additional_rate"],
        },
        outputs=["income_tax_on_section_13_dividend_income"],
    )
    dividend_tax = s13["income_tax_on_section_13_dividend_income"]

    # SSCBA 1992 s.8: primary Class 1 contributions on employment earnings,
    # weekly basis. s.6(3): no primary contributions over pensionable age.
    if inputs.age < ni["state_pension_age"] and bool(np.any(employment > 0)):
        s8 = _execute(
            "sscba_s8",
            year=year,
            per_entity_inputs={
                "earnings_paid_in_tax_week_in_respect_of_employment": employment / 52.0
            },
            shared_inputs={
                "current_primary_threshold_or_prescribed_equivalent": (
                    ni["weekly_primary_threshold"]
                ),
                "current_upper_earnings_limit_or_prescribed_equivalent": (
                    ni["weekly_upper_earnings_limit"]
                ),
                "primary_class_1_contribution_payable_as_mentioned_in_section_6_1_a": True,
                "regulations_under_section_6_6_do_not_displace_calculation": True,
                "regulations_under_sections_116_to_120_do_not_displace_calculation": True,
            },
            outputs=["primary_class_1_contribution"],
        )
        national_insurance = s8["primary_class_1_contribution"] * 52.0
    else:
        national_insurance = np.zeros_like(employment)

    total_tax = non_savings_tax + dividend_tax + national_insurance
    return UKYearResults(
        net_income=total_income - total_tax,
        total_tax=total_tax,
    )


def pension_credit_screen(
    *,
    year: int,
    ages: np.ndarray,
    annual_income: np.ndarray,
) -> dict:
    """Screen guarantee credit entitlement across simulated years.

    Evaluates SPC Act 2002 s.2 with the standard minimum guarantee from
    SI 2002/1792 reg 6, one entity per simulated year. This is a modeled
    screening estimate: the full income-assessment rules (capital tariff
    income, housing additions) are not yet encoded, so the simulator's
    modeled income stands in for SPC Act s.15 income.

    Returns annual amounts plus the statute citations backing them.
    """
    ages = np.asarray(ages)
    annual_income = np.asarray(annual_income, dtype=float)
    n = len(annual_income)
    qualifying_age = int(_statutory_inputs()["national_insurance"]["state_pension_age"])
    entitled = ages >= qualifying_age
    if not bool(np.any(entitled)):
        return {
            "annual_amount": np.zeros(n, dtype=float),
            "weekly_minimum_guarantee": 0.0,
            "citations": [],
        }

    # SI 2002/1792 reg 6: weekly standard minimum guarantee (single person,
    # none of the nil-amount paragraph 3 cases applying).
    reg6, reg6_traces = _execute(
        "spc_regs_6",
        year=year,
        per_entity_inputs={},
        n=1,
        shared_inputs={
            "claimant_has_partner": False,
            "claimant_is_prisoner": False,
            "member_of_religious_order_fully_maintained_by_order": False,
            "detained_in_custody_on_remand_pending_trial": False,
            "detained_pending_sentence_upon_conviction": False,
            "detained_pending_trial_or_sentence_following_conviction_by_court": False,
            "detained_for_period_not_exceeding_52_weeks": False,
            "detained_in_custody_for_more_than_52_weeks": False,
            "awarded_tax_credit_under_tax_credits_act": False,
        },
        outputs=["standard_minimum_guarantee"],
        mode="explain",
    )
    weekly_guarantee = float(reg6["standard_minimum_guarantee"][0])
    annual_guarantee = weekly_guarantee * 52.0

    s2, s2_traces = _execute(
        "spca_s2",
        year=year,
        per_entity_inputs={"claimant_income": annual_income},
        shared_inputs={
            "claimant_is_entitled_to_guarantee_credit": True,
            "standard_minimum_guarantee": annual_guarantee,
            "prescribed_additional_amounts_applicable": 0.0,
        },
        outputs=["guarantee_credit"],
        mode="explain",
    )

    citations = _trace_citations(reg6_traces + s2_traces)
    return {
        "annual_amount": np.where(
            entitled, np.maximum(0.0, s2["guarantee_credit"]), 0.0
        ),
        "weekly_minimum_guarantee": weekly_guarantee,
        "citations": citations,
    }


def tax_citations(year: int) -> list[Citation]:
    """Statute citations for the tax rules this backend evaluates."""
    _, traces = _execute(
        "ita_s35",
        year=year,
        per_entity_inputs={"adjusted_net_income": np.array([30_000.0])},
        shared_inputs={
            "individual_makes_claim": True,
            "individual_meets_requirements_under_section_56": True,
        },
        outputs=["personal_allowance"],
        mode="explain",
    )
    citations = _trace_citations(traces)
    for key in ("ita_s10", "ita_s13", "sscba_s8"):
        prefix = _REF_PREFIXES[key]
        rule_id = prefix.rstrip("#")
        citations.append(Citation(id=rule_id, url=_rule_citation_url(rule_id + "#x")))
    return _dedupe_citations(citations + statutory_input_citations())
