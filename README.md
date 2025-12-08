# EggNest

Monte Carlo retirement simulation with real tax calculations.

**[eggnest.co](https://eggnest.co)** | **[app.eggnest.co](https://app.eggnest.co)**

## What is EggNest?

EggNest is a retirement planning simulator that runs thousands of Monte Carlo simulations to show you the probability distribution of outcomes—not just a single "expected" result. Unlike other calculators, EggNest uses PolicyEngine to calculate actual federal and state taxes, giving you accurate after-tax projections.

## Features

- **Monte Carlo Simulation**: 10,000+ scenarios showing the range of possible outcomes
- **Real Tax Calculations**: Federal + state income tax via PolicyEngine-US (not estimates)
- **Social Security Optimization**: Model different claiming ages (62-70)
- **Spouse Support**: Joint simulation with mortality modeling
- **Annuity Comparison**: Compare guaranteed income vs. portfolio withdrawals
- **What-If Scenarios**: Quickly explore spending and savings changes

## Architecture

```
eggnest/
├── app/                     # React frontend (app.eggnest.co)
│   └── src/
│       ├── components/      # Wizard, SimulationProgress
│       ├── pages/           # SimulatorPage
│       └── lib/api.ts       # API client with SSE streaming
├── web/                     # Landing page (eggnest.co)
│   └── src/pages/           # HomePage, ThesisPage
├── api/                     # Python FastAPI backend
│   └── eggnest/
│       ├── simulation.py    # MonteCarloSimulator (vectorized NumPy)
│       ├── tax.py           # PolicyEngine-US integration
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

### Frontend (React/Vite)
```bash
cd app
npm install
npm run dev  # Runs on port 5174
```

### Landing Page
```bash
cd web
npm install
npm run dev  # Runs on port 5173
```

## Stack

- **Frontend**: React 19 + Vite + TypeScript + Plotly
- **Backend**: Python + FastAPI + NumPy + PolicyEngine-US
- **Database**: Supabase (Postgres + Auth)
- **Hosting**: Vercel (frontend) + Modal (API)
- **Tax Engine**: [PolicyEngine-US](https://github.com/PolicyEngine/policyengine-us)

## License

MIT
