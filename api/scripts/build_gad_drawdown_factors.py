"""Build data/gad_drawdown_factors.json from GOV.UK's drawdown pension tables.

The factors give the annual income, per £1,000 of fund, that a lifetime
annuity could pay at a given age and 15-year gilt yield. DWP's Pension Credit
guidance (DMG 85470) uses these tables to value an undrawn pension pot.

Usage:
    uv run --with odfpy --with pandas python scripts/build_gad_drawdown_factors.py
"""

from __future__ import annotations

import json
import re
import tempfile
import urllib.request
from pathlib import Path

import pandas as pd

SOURCE_PAGE = "https://www.gov.uk/government/publications/drawdown-pension-tables"
SOURCE_FILE = (
    "https://assets.publishing.service.gov.uk/media/67e2b60a5698d84e39cfdac9/"
    "Drawdown_factors_effective_1_September_2025.ods"
)
SHEET = "Pensioner_aged_23_or_over"
OUTPUT = Path(__file__).parents[1] / "eggnest" / "data" / "gad_drawdown_factors.json"


def _parse_age(label: object) -> list[int]:
    """Ages a row covers: '23, 24 or 25' and '85 or over' span several."""
    text = str(label)
    ages = [int(value) for value in re.findall(r"\d+", text)]
    if not ages:
        return []
    if "over" in text:
        return [ages[0]]
    return ages


def main() -> None:
    request = urllib.request.Request(
        SOURCE_FILE, headers={"User-Agent": "eggnest-data-build/0.1"}
    )
    with tempfile.NamedTemporaryFile(suffix=".ods") as handle:
        with urllib.request.urlopen(request, timeout=60) as response:
            handle.write(response.read())
        handle.flush()
        table = pd.read_excel(handle.name, engine="odf", sheet_name=SHEET, header=None)

    yields = [
        float(re.match(r"([\d.]+)%", str(label)).group(1))
        for label in table.iloc[0, 1:]
    ]
    factors: dict[str, list[float]] = {}
    for _, row in table.iloc[1:].iterrows():
        for age in _parse_age(row.iloc[0]):
            factors[str(age)] = [float(value) for value in row.iloc[1:]]

    payload = {
        "source_page": SOURCE_PAGE,
        "source_file": SOURCE_FILE,
        "table": "Table 1, pensioner aged 23 or over",
        "effective_from": "2025-09-01",
        "unit": "GBP of annual income per GBP 1,000 of fund",
        "gilt_yields_percent": yields,
        "last_age_means_that_age_or_over": max(int(age) for age in factors),
        "factors_by_age": factors,
    }
    OUTPUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"Wrote {OUTPUT} ({len(factors)} ages, {len(yields)} yields)")


if __name__ == "__main__":
    main()
