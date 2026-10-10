# EggNest

Agent-callable household finance calculators with real tax calculations.

**[eggnest.co](https://eggnest.co)**

## What is EggNest?

EggNest exposes household finance calculations that AI agents and chat interfaces can call directly. Retirement simulations are one surface; the broader contract is deterministic, source-backed taxes, credits, benefits, and resource comparisons under explicit assumptions. The calculators are educational tools and avoid financial-advice language.

## Product Surfaces

- **US simulator**: Portfolio, Social Security, spouse, annuity, state-tax, and asset-allocation comparisons using PolicyEngine-US.
- **UK simulator**: ISA/SIPP/GIA retirement simulation using historical UK returns, stochastic earnings, mortality, and PolicyEngine UK compiled tax calculations.
- **Life event calculator**: Household tax and benefit deltas for common US life events.
- **Household resources**: Agent-facing annual US taxes, refundable credits, selected benefits, and net-resource comparisons across earnings.
- **Marketing/thesis pages**: Public product and market context in the same Next.js app.

## Architecture

```text
eggnest/
├── app/                     # Next.js app, simulator UI, marketing pages, tests
│   └── src/
│       ├── app/             # App Router routes
│       ├── components/      # Shared UI components
│       └── lib/             # API clients and utilities
├── api/                     # Python FastAPI backend
│   └── eggnest/
│       ├── core/            # Versioned scenario/result engine boundary
│       ├── simulation.py    # US Monte Carlo simulator
│       ├── simulation_uk.py # UK Monte Carlo simulator
│       ├── tax.py           # PolicyEngine-US integration
│       ├── tax_uk.py        # PolicyEngine UK compiled integration
│       └── models*.py       # Pydantic models
└── supabase/                # Database migrations
```

## Development

### Backend

```bash
cd api
uv venv
uv pip install -e ".[dev]"
uv run uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd app
bun install
bun run dev
```

The frontend runs on port `5174` and expects the API at `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set.

## Engine Contract

New calculation surfaces should call the core engine envelope instead of importing UI/API-specific simulator code directly. The stable HTTP entry point is:

```bash
POST /core/simulate
```

with a versioned scenario envelope:

```json
{
  "schema_version": "eggnest.scenario.v1",
  "engine": "us_retirement",
  "country": "USA",
  "inputs": {
    "current_age": 65,
    "max_age": 95,
    "initial_capital": 500000,
    "annual_spending": 40000,
    "state": "CA",
    "filing_status": "single"
  }
}
```

Long-running agent calls should use the pollable job endpoint instead of
holding one HTTP request open:

```bash
# Start a core engine job.
curl -sS -X POST https://policyengine--eggnest-api-fastapi-app.modal.run/core/jobs \
  -H "Content-Type: application/json" \
  --data @scenario.json

# Poll until status is "succeeded" or "failed"; succeeded responses include
# result: { schema_version: "eggnest.result.v1", outputs: ... }.
curl -sS https://policyengine--eggnest-api-fastapi-app.modal.run/core/jobs/JOB_ID
```

Supported core engines are currently `us_household_resources`, `us_retirement`, and `uk_retirement`. The response wraps numerical outputs with assumptions, FinBot-style `citations: [{id, url}]`, sources, caveats, and reproducibility metadata. Household resource payloads also include `output_citations` keyed by fields such as `benefits.snap`. Legacy endpoints such as `/simulate`, `/simulate-uk`, and `/calculate-household` keep their existing response shape while delegating to shared calculation logic where available.

## Agent and CLI Calls

Chat interfaces and MCP-style wrappers should prefer machine-readable CLI calls over parsing rich terminal output:

```bash
cd api

# Print the stable scenario envelope schema.
uv run eggnest core schema scenario

# Discover agent-callable programs and their primary outputs.
uv run eggnest programs list --jurisdiction us

# Run a scenario locally from YAML/JSON and return the full core envelope.
uv run eggnest core run scenario.yaml --output-format envelope

# Read raw US inputs from stdin and return only the legacy simulator payload.
cat scenario.yaml | uv run eggnest core run - --engine us_retirement --output-format legacy

# Keep the friendly simulate command, but emit JSON for tools.
uv run eggnest simulate scenario.yaml --local --output-format result

# Use the remote pollable job API for long-running simulations.
uv run eggnest simulate scenario.yaml --job --output-format envelope

# Compare account withdrawal orders without adding tax-policy logic to EggNest.
uv run eggnest compare withdrawal-strategies scenario.yaml

# Compare historical market cohorts with contiguous, non-wrapping return paths.
uv run eggnest compare historical-cohorts scenario.yaml --start-year 1966 --start-year 1973

# Validate partial household intake and get next questions for an agent.
uv run eggnest household validate household.yaml

# Run US household resources. Federal tax is before refundable credits;
# refundable credits and SNAP are counted in benefits. The envelope includes
# flat citations plus per-field output_citations for agent UIs.
uv run eggnest household run household.yaml --output-format envelope

# Find earnings ranges where higher earnings reduce modeled net resources.
uv run eggnest compare earnings-grid household.yaml --income-min 0 --income-max 80000 --step 1000
```

Use `--output FILE` when a tool prefers file artifacts. `eggnest core run` accepts either a full `eggnest.scenario.v1` envelope or raw engine inputs. Policy logic belongs in PolicyEngine; EggNest orchestrates schemas, validation, comparisons, and stable CLI/API contracts.

## Test Commands

```bash
cd api
uv run ruff check .
uv run black --check .
uv run pytest -n auto  # parallel; drop -n auto for serial runs

cd ../app
bun run lint
bun run test:run
bun run build
bun run test:e2e -- --project=chromium
```

## Stack

- **Frontend**: Next.js, React 19, TypeScript, Tailwind CSS, Plotly/Recharts
- **Backend**: FastAPI, NumPy, pandas, Pydantic
- **Tax engines**: PolicyEngine-US and PolicyEngine UK compiled
- **Database/auth**: Supabase
- **Hosting**: Vercel frontend, Python API deployment

## License

MIT
