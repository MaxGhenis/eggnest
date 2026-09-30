# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EggNest is an agent-callable household finance calculator suite with real tax calculations via PolicyEngine-US and PolicyEngine UK. Retirement simulation is one product surface; the emerging core is stable CLI/API contracts for AI agents to compute household resources, compare scenarios, and cite assumptions without putting policy logic outside PolicyEngine. The project uses a unified Next.js frontend with a Python FastAPI backend.

## Development Commands

### Backend (Python/FastAPI)
```bash
cd api
uv sync --all-extras  # dev extra: pytest, pytest-xdist, Hypothesis
uv run uvicorn main:app --reload --port 8000

# Run tests
uv run pytest tests/ -n 4 --dist loadfile
uv run pytest tests/test_simulation.py -v  # Single test file
HYPOTHESIS_PROFILE=thorough uv run pytest tests/test_household_net_income.py  # 400 examples per property

# After changing uv.lock, regenerate the Modal image requirements (CI checks this)
uv export --frozen --no-dev --no-emit-project --no-hashes --no-header -o requirements-modal.txt

# Linting
uv run black .
uv run ruff check .
```

### Frontend (Next.js + Tailwind v4)
```bash
cd app
bun install
bun run dev              # Runs on port 5174
bun run build            # Next.js build
bun run lint             # ESLint flat config
bun run test             # Vitest watch mode
bun run test:run         # Vitest single run
```

### Environment Setup
Backend requires `api/.env` with Supabase credentials. Frontend uses `NEXT_PUBLIC_API_URL` to point to the API (defaults to `http://localhost:8000`).

## Architecture

```
eggnest/
├── api/                     # Python FastAPI backend
│   ├── main.py              # FastAPI app with endpoints
│   └── eggnest/             # Core simulation package
│       ├── core/            # Versioned scenario/result engine boundary
│       ├── simulation.py    # US MonteCarloSimulator (vectorized NumPy)
│       ├── simulation_uk.py # UK Monte Carlo simulator
│       ├── tax.py           # PolicyEngine-US integration
│       ├── tax_uk.py        # PolicyEngine UK compiled integration
│       ├── mortality.py     # SSA mortality tables
│       └── models.py        # Pydantic request/response models
├── app/                     # Next.js frontend (unified)
│   └── src/
│       ├── app/             # Next.js App Router pages
│       │   ├── (marketing)/ # Landing page & thesis (route group)
│       │   ├── simulator/   # US Monte Carlo simulator
│       │   ├── life-event/  # Tax & benefits calculator
│       │   └── uk-simulator/# UK simulator
│       ├── lib/api.ts       # US API client with SSE streaming
│       ├── lib/api-uk.ts    # UK API client
│       ├── hooks/           # Custom React hooks
│       └── components/      # UI components
└── supabase/                # Database migrations
```

## Key Technical Details

### Simulation Engine (`api/eggnest/simulation.py`)
- Vectorized NumPy for performance across 10,000+ Monte Carlo paths
- Year-by-year processing with mortality masks and income calculations
- Supports SSE streaming via `run_with_progress()` generator
- Tax-aware withdrawals using PolicyEngine-US microsimulation

### Tax Integration (`api/eggnest/tax.py`)
- Uses `policyengine_us.Microsimulation` with custom `MonteCarloDataset`
- Batches all scenarios into a single PolicyEngine run per simulation year
- Calculates federal + state income tax on capital gains, SS, dividends, employment income

### API Endpoints
- `GET /programs` - List agent-callable programs, primary outputs, caveats, and CLI entry points
- `POST /core/simulate` - Run a versioned core scenario envelope (`us_household_resources`, `us_retirement`, `uk_retirement`)
- `POST /simulate` - Run US simulation, returns legacy result shape via the core engine
- `POST /simulate/stream` - SSE streaming with progress events
- `GET /mortality/{gender}` - Mortality rates and survival curves
- `POST /household/validate` - Validate partial household intake and return missing fields plus next questions
- `POST /household/resources` - Calculate annual US taxes, refundable credits, benefits, and net resources
- `POST /compare-earnings-grid` - Compare household resources over an annual earnings grid and flag cliffs
- `POST /compare-annuity` - Compare portfolio withdrawals vs annuity cash flows
- `POST /compare-withdrawal-strategies` - Compare holdings withdrawal orders under shared market/tax assumptions
- `POST /compare-historical-cohorts` - Compare contiguous historical market cohorts under shared tax assumptions
- `POST /simulate-uk` - Run UK simulation

### Frontend API Client (`app/src/lib/api.ts`)
- `runSimulation()` - Standard POST request
- `runSimulationWithProgress()` - AsyncGenerator for SSE events
- TypeScript interfaces mirror Pydantic models

## Conventions

- Backend uses Pydantic v2 models with `Field()` validators
- New product surfaces should use `eggnest.core` scenario/result envelopes before adding API- or UI-specific contracts
- CLI/MCP-style callers should prefer `GET /programs`, `POST /core/simulate`, or `uv run eggnest core run ... --output-format envelope`; legacy product endpoints are compatibility shims
- For low- and middle-income household work, use `eggnest household validate`, `eggnest household run`, and `eggnest compare earnings-grid`; do not add tax or benefit policy formulas to EggNest
- Household resources follow PolicyEngine-US `household_net_income` with health coverage excluded: `net_income = total_income - total_taxes + total_benefits`. Taxes are before refundable credits (federal income tax after non-refundable credits, state income tax before state refundable credits, payroll including state payroll such as CA SDI, self-employment tax, `other_taxes` for state use and local taxes). Refundable credits and benefits are counted once, in `total_benefits`. The marginal tax rate is `1 - Δnet_income / $1,000` of extra wages for the primary earner (the non-dependent person with the highest earnings)
- Household `benefits`, `tax_breakdown` and `non_refundable_credit_breakdown` keys are PolicyEngine-US variable names (`refundable_ctc`, `eitc`, `snap`, `ssi`, ...); `benefits` sums to `total_benefits` and `tax_breakdown` sums to `total_taxes`
- Agent-facing household outputs expose FinBot-style citations as `citations: [{id, url}]`; `HouseholdResult.output_citations` maps fields like `benefits.snap` to supporting sources
- Frontend uses Next.js App Router with React 19, TypeScript, and Tailwind CSS v4
- Styling uses Tailwind utility classes plus CSS custom properties defined in `globals.css`
- Tests use pytest (backend) and Vitest (frontend)
- `app/` is the unified frontend (marketing pages, simulator, and tools)
