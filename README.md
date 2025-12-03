# FinSim

Retirement and financial planning simulator.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│                      finsim.app                          │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  Supabase (Auth + DB)                    │
│              - User accounts & settings                  │
│              - Saved simulations                         │
│              - Usage tracking                            │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│               Backend (Python/FastAPI)                   │
│                  Cloud Run or Modal                      │
│              - Monte Carlo simulation                    │
│              - Portfolio modeling                        │
│              - Tax calculations (PolicyEngine-US)        │
└─────────────────────────────────────────────────────────┘
```

## Features

- **Retirement Planning**: Monte Carlo simulation of portfolio outcomes
- **Annuity Comparison**: Compare annuities vs. index fund investing
- **Tax-Aware Withdrawals**: Accurate federal + state taxes via PolicyEngine-US
- **Social Security**: Project benefits with COLA adjustments
- **Mortality-Adjusted Returns**: IRR calculations with survival weighting

## Development

```bash
# Backend
cd api
uv venv && uv pip install -e ".[dev]"
uv run uvicorn main:app --reload

# Frontend
cd web
npm install
npm run dev
```

## Configuration

### Backend (.env)
```bash
cp api/.env.example api/.env
# Edit with your Supabase credentials
```

### Frontend (.env)
```bash
cp web/.env.example web/.env
# Edit with your Supabase and API URLs
```

### Supabase Setup

1. Create a Supabase project at supabase.com
2. Link: `supabase link --project-ref YOUR_PROJECT_REF`
3. Run migrations: `supabase db push`

## Stack

- **Frontend**: React + Vite + TypeScript + Recharts
- **Backend**: Python + FastAPI + Pydantic + PolicyEngine-US
- **Database**: Supabase (Postgres + Auth)
- **Compute**: Cloud Run or Modal (for heavy simulation)
- **Tax Engine**: PolicyEngine-US (accurate federal + state taxes)
