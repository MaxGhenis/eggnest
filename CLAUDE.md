# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EggNest is a retirement and financial planning simulator that uses Monte Carlo simulation with real tax calculations via PolicyEngine-US. The project uses a unified Next.js frontend with a Python FastAPI backend.

## Development Commands

### Backend (Python/FastAPI)
```bash
cd api
uv venv && uv pip install -e ".[dev]"
uv run uvicorn main:app --reload --port 8000

# Run tests
uv run pytest tests/
uv run pytest tests/test_simulation.py -v  # Single test file

# Linting
uv run black .
uv run ruff check .
```

### Frontend (Next.js 15 + Tailwind v4)
```bash
cd app
bun install
bun run dev              # Runs on port 5174
bun run build            # Next.js build
bun run lint             # ESLint via next lint
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
│       ├── simulation.py    # MonteCarloSimulator (vectorized NumPy)
│       ├── tax.py           # PolicyEngine-US integration
│       ├── mortality.py     # SSA mortality tables
│       └── models.py        # Pydantic request/response models
├── app/                     # Next.js 15 frontend (unified)
│   └── src/
│       ├── app/             # Next.js App Router pages
│       │   ├── (marketing)/ # Landing page & thesis (route group)
│       │   ├── simulator/   # Monte Carlo simulator
│       │   └── life-event/  # Tax & benefits calculator
│       ├── lib/api.ts       # API client with SSE streaming
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
- `POST /simulate` - Run simulation, returns full result
- `POST /simulate/stream` - SSE streaming with progress events
- `GET /mortality/{gender}` - Mortality rates and survival curves
- `POST /compare-annuity` - Compare investment vs annuity option

### Frontend API Client (`app/src/lib/api.ts`)
- `runSimulation()` - Standard POST request
- `runSimulationWithProgress()` - AsyncGenerator for SSE events
- TypeScript interfaces mirror Pydantic models

## Conventions

- Backend uses Pydantic v2 models with `Field()` validators
- Frontend uses Next.js 15 (App Router) with React 19, TypeScript, and Tailwind CSS v4
- Styling uses Tailwind utility classes plus CSS custom properties defined in `globals.css`
- Tests use pytest (backend) and Vitest (frontend)
- `app/` is the unified frontend (marketing pages, simulator, and tools)
