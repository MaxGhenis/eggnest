# EggNest

Monte Carlo financial planning with real tax and benefit calculations.

**[eggnest.co](https://eggnest.co)** | **[app.eggnest.co](https://app.eggnest.co)**

## What is EggNest?

EggNest is a financial modeling engine and simulator for major household decisions under uncertainty. It runs thousands of Monte Carlo simulations to show the distribution of possible outcomes, not just a single "expected" result. Unlike most calculators, EggNest uses PolicyEngine to calculate actual federal and state taxes and household rules, so you can compare scenarios using real after-tax math.

## Features

- **Monte Carlo Simulation**: 10,000+ scenarios showing the range of possible outcomes
- **Historical Backtests**: Replay the same plan logic across exact historical retirement cohorts
- **Real Tax + Benefit Calculations**: Federal and state rules via PolicyEngine-US, not rough estimates
- **Life-Event Comparisons**: Explore raises, marriage, children, relocation, and retirement
- **Household Planning**: Model couples, dependents, and multiple income sources together
- **Retirement Workflow**: Social Security timing, annuity comparisons, and long-run spending paths
- **Withdrawal Strategy Lab**: Compare tax-aware drawdown sequences on the same plan
- **Roth Conversion Lab**: Search fixed-dollar and bracket-fill Roth conversion scenarios with tax and Medicare premium effects
- **What-If Scenarios**: Quickly compare before/after household situations
- **Engine Access**: Use the same model through Python, CLI, FastAPI, or MCP

## Interfaces

- **Python package**: `from eggnest import get_engine`
- **CLI**: `eggnest simulate`, `eggnest backtest`, `eggnest compare-strategies`, `eggnest optimize-roth-conversions`
- **MCP server**: `eggnest-mcp` or `eggnest mcp`
- **Web app**: [eggnest.co/simulator](https://eggnest.co/simulator)
- **FastAPI**: existing HTTP endpoints for the app and external clients

## Architecture

```
eggnest/
├── app/                     # Next.js frontend (eggnest.co)
│   └── src/
│       ├── components/      # Simulator + life-event UI
│       ├── app/             # Marketing, simulator, life-event routes
│       └── lib/api.ts       # API client with SSE streaming
├── api/                     # Python FastAPI backend
│   └── eggnest/
│       ├── engine.py        # Stable local Python interface
│       ├── cli.py           # CLI entrypoint
│       ├── mcp_server.py    # Local stdio MCP server
│       ├── simulation.py    # MonteCarloSimulator (vectorized NumPy)
│       ├── backtest.py      # Deterministic historical cohort runner
│       ├── tax.py           # PolicyEngine-US integration
│       ├── household.py     # Household tax/benefit calculations
│       └── models.py        # Pydantic models
└── supabase/                # Database migrations
```

## Development

### Backend (Python/FastAPI)
```bash
cd api
uv venv && uv pip install -e ".[dev]"
uv run uvicorn main:app --reload --port 8000
```

### Python Package
```bash
cd api
uv run python - <<'PY'
from eggnest import get_engine

engine = get_engine()
result = engine.simulate({
    "initial_capital": 1_000_000,
    "annual_spending": 60_000,
    "current_age": 60,
    "max_age": 95,
    "gender": "male",
    "has_spouse": False,
    "has_annuity": False,
})
print(result.success_rate)
PY
```

### CLI
```bash
cd api
uv run eggnest init
uv run eggnest simulate
uv run eggnest backtest --format json
uv run eggnest compare-strategies
uv run eggnest compare-roth-conversions
uv run eggnest optimize-roth-conversions --format report-json
```

### MCP
```bash
cd api
uv run eggnest-mcp
```

This runs EggNest as a local stdio MCP server so AI clients can call the same engine directly.

## Canonical Roth Optimization Example

This example uses the same detailed-holdings plan through Python, CLI, and MCP. The output is a calculator artifact, not financial advice: it reports modeled leaders, deltas, and cliff years under the supplied assumptions.

Create `api/scenarios/roth-demo.yaml`:

```yaml
name: Roth demo
annual_spending: 90000
current_age: 60
max_age: 95
gender: female
state: CA
filing_status: single
has_spouse: false
has_annuity: false
n_simulations: 500
random_seed: 20260409
holdings:
  - account_type: taxable
    fund: sp500
    balance: 350000
    cost_basis: 260000
  - account_type: traditional_401k
    fund: treasury
    balance: 850000
  - account_type: roth_ira
    fund: sp500
    balance: 100000
```

Run the CLI report artifact:

```bash
cd api
uv run eggnest optimize-roth-conversions scenarios/roth-demo.yaml \
  --annual-amount 0 \
  --annual-amount 25000 \
  --annual-amount 50000 \
  --candidate-start-age 60 \
  --candidate-start-age 62 \
  --window-length 5 \
  --window-length 10 \
  --format report-json > roth-report.json
```

Call the same engine from Python:

```python
from pathlib import Path

import yaml

from eggnest import get_engine
from eggnest.models import RothOptimizationInput, SimulationInput

scenario = yaml.safe_load(Path("scenarios/roth-demo.yaml").read_text())
request = RothOptimizationInput(
    base_input=SimulationInput.model_validate(scenario),
    annual_conversion_amounts=[0, 25_000, 50_000],
    candidate_start_ages=[60, 62],
    window_lengths=[5, 10],
)

report = get_engine().optimize_roth_conversions_report(request)
print(report.artifact_type)
print(report.leaders.score_leader)
print(report.baseline_scenario_label)
```

MCP clients can call `optimize_roth_conversions_report` with the same inputs:

```json
{
  "base_input": {
    "annual_spending": 90000,
    "current_age": 60,
    "max_age": 95,
    "gender": "female",
    "state": "CA",
    "filing_status": "single",
    "has_spouse": false,
    "has_annuity": false,
    "n_simulations": 500,
    "random_seed": 20260409,
    "holdings": [
      {"account_type": "taxable", "fund": "sp500", "balance": 350000, "cost_basis": 260000},
      {"account_type": "traditional_401k", "fund": "treasury", "balance": 850000},
      {"account_type": "roth_ira", "fund": "sp500", "balance": 100000}
    ]
  },
  "annual_conversion_amounts": [0, 25000, 50000],
  "candidate_start_ages": [60, 62],
  "window_lengths": [5, 10]
}
```

How to read the report:

- `baseline_scenario_label` names the scenario used for all delta columns.
- `leaders` gives the score, tax, Medicare premium, real-wealth, and historical-cohort leaders under the modeled objective.
- `Tax Δ` is the modeled lifetime tax difference versus the baseline.
- `Medicare Δ` includes modeled Part B premiums plus Part D IRMAA surcharge effects where available.
- `representative_cliff_ledger` shows year-level bracket room, marginal federal rate, IRMAA band, and Medicare-premium changes for the score-leading scenario.

### Frontend (Next.js)
```bash
cd app
npm install
npm run dev
```

### Documentation Results Artifact
```bash
cd api
EGGNEST_REGENERATE_RESULTS=1 uv run python ../docs/eggnest_results.py
```

This writes `docs/eggnest_results.json`, which the paper/docs import directly instead of recomputing simulation outputs during docs builds.

## Stack

- **Frontend**: Next.js 16 + TypeScript + Tailwind + Plotly
- **Backend**: Python + FastAPI + NumPy + PolicyEngine-US
- **Engine Access**: Python package + Click CLI + MCP
- **Database**: Supabase (Postgres + Auth)
- **Hosting**: Vercel (frontend) + Modal (API)
- **Tax Engine**: [PolicyEngine-US](https://github.com/PolicyEngine/policyengine-us)

## License

MIT
