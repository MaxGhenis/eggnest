"""One-shot extractor for UK historical asset returns.

Pulls the Jorda-Schularick-Taylor Macrohistory Database (R6), selects the UK
series, and writes a clean CSV to ``api/eggnest/data/uk_historical_returns.csv``.

Source: https://www.macrohistory.net/database/

Run:

    uv run python scripts/build_uk_historical_data.py

Re-run whenever a newer JST release is published.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import pandas as pd

JST_URL = "https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.dta"
CACHE_PATH = Path("/tmp/jst_uk_historical.dta")
OUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "eggnest"
    / "data"
    / "uk_historical_returns.csv"
)


def _download(url: str, dest: Path) -> None:
    if dest.exists():
        return
    print(f"Downloading {url} -> {dest}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
        out.write(resp.read())


def main() -> None:
    _download(JST_URL, CACHE_PATH)
    df = pd.read_stata(CACHE_PATH)
    uk = df[df["iso"] == "GBR"].copy()
    uk = uk.sort_values("year").reset_index(drop=True)

    # CPI in JST is a price level; convert to annual percent change.
    uk["cpi_return"] = uk["cpi"].pct_change()

    out = uk[["year", "eq_tr", "bond_tr", "cpi_return"]].rename(
        columns={
            "eq_tr": "equity_return_nominal",
            "bond_tr": "bond_return_nominal",
            "cpi_return": "cpi_inflation",
        }
    )
    out = out.dropna(
        subset=["equity_return_nominal", "bond_return_nominal", "cpi_inflation"]
    )
    out["year"] = out["year"].astype(int)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False, float_format="%.6f")

    print(
        f"Wrote {len(out)} years ({out['year'].min()}-{out['year'].max()}) "
        f"to {OUT_PATH}",
        file=sys.stderr,
    )
    print(out.describe().to_string(), file=sys.stderr)


if __name__ == "__main__":
    main()
