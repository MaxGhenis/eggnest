# EggNest Business Plan

## Executive Summary

EggNest is the **financial simulation engine for life decisions**. Starting with retirement planning, we're building a platform that answers "what if?" for every major financial decision—job changes, relocations, home purchases, having children, and more.

**Model**: B2C freemium SaaS, open source core
**Wedge**: Monte Carlo retirement simulator with real tax calculations
**Vision**: The simulation layer for all life decisions

---

## The Big Idea

### Personal Finances Are Opaque—Right Now, Not Just in Retirement

The tax-and-benefits system is impossibly complex. People can't answer basic questions about their **current** financial situation:

| Question | Why It's Hard |
|----------|---------------|
| "What's my actual marginal tax rate?" | Federal + state + FICA + phase-outs of credits |
| "If I earn $5K more, how much do I keep?" | Might lose ACA subsidies, EITC, SNAP—could be negative |
| "Should I take this job offer?" | Different state taxes, benefits, 401k match, health insurance |
| "Can I afford to move?" | Property taxes, SALT cap, state income tax, cost of living |
| "What happens if we have a baby?" | CTC, CDCTC, EITC changes, Medicaid eligibility, childcare costs |
| "Should I work more hours?" | Benefit cliffs can mean effective 80%+ marginal tax rates |

### The Benefits Cliff Problem

For low and middle-income households, the interaction of taxes AND benefits creates perverse incentives:

```
Earn $1 more → Lose $3 in benefits → Net: -$2

This happens at:
- SNAP eligibility cliffs
- Medicaid → ACA transition
- EITC phase-out
- CTC phase-out
- ACA subsidy cliffs
- Housing assistance limits
- Childcare subsidy cliffs
```

**Nobody shows people these cliffs before they fall off them.**

### The Full Picture: Taxes + Benefits + Decisions

PolicyEngine models BOTH sides:
- **Taxes**: Federal, state, local, FICA, credits, deductions
- **Benefits**: SNAP, Medicaid, ACA subsidies, EITC, CTC, housing assistance, childcare subsidies, SSI, TANF

**This means**: We can show a family their TRUE marginal rate—including benefit loss—and help them make decisions with full information.

### Who This Helps

| Income Level | Pain Points |
|--------------|-------------|
| **Low income** | Benefit cliffs, EITC optimization, Medicaid vs ACA |
| **Middle income** | Phase-outs, SALT caps, ACA subsidy cliffs, childcare credits |
| **High income** | AMT, capital gains planning, retirement optimization |
| **Everyone** | "What if I take this job / move / have a kid / work more hours?" |

**The problem**: People make life decisions blind to the tax-and-benefit implications. They deserve to see the full picture.

---

## Product Vision

### Phase 1: Retirement Simulator (Now)
The wedge. Prove the model with the highest-stakes, most calculable decision.

- Monte Carlo simulation
- Real federal + state taxes via PolicyEngine
- Social Security optimization
- Annuity comparison

### Phase 2: Life Event Simulator (Year 2)
Expand to adjacent decisions that share the same engine.

**Job Change Simulator**
- Compare total compensation (salary, bonus, equity, benefits)
- Model tax implications across states
- 401k/pension comparison
- Health insurance cost differences

**Relocation Simulator**
- State income tax comparison
- Property tax + SALT cap impact
- Cost of living adjustment
- Commute cost changes

**Home Purchase Simulator**
- Mortgage interest deduction (with SALT cap reality)
- Property tax implications
- PMI, HOA, maintenance modeling
- Rent vs. buy Monte Carlo

### Phase 3: Family Planning Simulator (Year 3)
High emotional stakes, high financial complexity.

**Child Cost Simulator**
- Childcare costs by location
- Tax credits (CTC, CDCTC, EITC)
- Health insurance changes
- Education savings (529) modeling
- Long-term income impact

**Education Decision Simulator**
- College ROI by major/school
- Student loan modeling
- Grad school break-even analysis
- Trade school vs. college comparison

### Phase 4: Full Life Simulator (Year 4+)
The everything engine.

- Career path modeling
- Business formation (LLC vs S-corp vs sole prop)
- Divorce financial planning
- Inheritance/estate planning
- Healthcare cost projection (pre-Medicare)
- Long-term care insurance decisions

---

## Why This Works

### PolicyEngine is the Unlock

Most "what if" tools fail because taxes are too complex. PolicyEngine solves this:

- Actual tax law, not estimates
- Federal + state + local
- All credits and deductions
- Benefit program interactions (SNAP, Medicaid, ACA subsidies)
- Updated as laws change

**This means**: We can accurately model decisions that span tax jurisdictions, income levels, and family structures.

### Monte Carlo is the Right Framework

Life is uncertain. Single-point estimates are misleading.

- Job: "What if I get laid off in year 2?"
- House: "What if interest rates change?"
- Retirement: "What if markets crash early?"
- Child: "What if childcare costs rise faster than inflation?"

**Monte Carlo shows the distribution of outcomes**, not just the expected case.

### Open Source Builds Trust

Financial decisions are high-stakes. People don't trust black boxes.

- Users can verify the math
- Community catches errors
- No hidden agenda (we're not selling products)
- Transparent methodology

---

## Market Opportunity

### TAM by Decision Type

| Decision | Annual US Occurrences | Willingness to Pay | TAM |
|----------|----------------------|-------------------|-----|
| Retirement planning | 4M retiring/year | High ($100+) | $400M+ |
| Job changes | 50M/year | Medium ($20-50) | $1B+ |
| Home purchases | 5M/year | High ($50-100) | $500M+ |
| Relocations | 30M/year | Medium ($20-50) | $600M+ |
| New children | 3.6M/year | Medium ($30-50) | $150M+ |
| **Total addressable** | | | **$3B+** |

### Why People Will Pay

| Tier | Price | Features |
|------|-------|----------|
| **Free** | $0 | Single scenario, basic inputs |
| **Pro** | $12/mo or $99/yr | Save scenarios, compare side-by-side, PDF export |
| **Family** | $20/mo or $179/yr | Multiple life events, shared household planning |

---

## Competitive Landscape

### No One Does This Well

| Competitor | What They Do | Gap |
|------------|--------------|-----|
| **Retirement calculators** | Single decision, no real taxes | Limited scope |
| **Tax software** | Backward-looking, no simulation | No "what if" |
| **Salary comparison** (Levels.fyi) | Comp data, no tax modeling | No net impact |
| **Cost of living** (Numbeo) | Rough estimates | No personalization |
| **Budgeting apps** (Mint, YNAB) | Track spending | No future modeling |
| **Robo-advisors** | Investment management | Not decision simulation |

**EggNest's position**: The simulation layer that none of these provide.

### Moat

1. **PolicyEngine integration**: Years of tax law encoded, continuously updated
2. **Open source trust**: Competitors can't replicate transparency
3. **Data network effects**: More users → better assumptions → better simulations
4. **Brand**: "EggNest it" becomes the verb for life decision simulation

---

## Business Model

### Revenue Streams

**1. Consumer Subscriptions (Primary)**
- Free tier drives awareness
- Pro/Family tiers for power users
- Target: 1-2% conversion, $100 ARPU

**2. API Access (Year 2+)**
- HR platforms: "See your net pay in any state"
- Real estate: "Calculate true cost of ownership"
- Fintech: "Add life simulation to your app"
- Pricing: Usage-based, $0.10-1.00/simulation

**3. Embedded Partnerships (Year 3+)**
- Employers: "Help employees evaluate relocation packages"
- Universities: "Show students ROI of degrees"
- Benefits platforms: "Compare health plan true costs"

### Revenue Projections

| Year | Users | Subscribers | API Revenue | Total ARR |
|------|-------|-------------|-------------|-----------|
| 1 | 100K | 1K | $0 | $100K |
| 2 | 500K | 7.5K | $100K | $850K |
| 3 | 2M | 30K | $500K | $3.5M |
| 4 | 5M | 100K | $2M | $12M |
| 5 | 15M | 300K | $10M | $40M |

---

## Go-to-Market

### Phase 1: Retirement Community (Now)
- Launch on HN, Reddit (r/financialindependence, r/Fire)
- SEO: "Monte Carlo retirement calculator"
- Build credibility with FIRE community

### Phase 2: Job/Relocation (Year 2)
- Target: Tech workers evaluating offers
- Channels: Blind, Levels.fyi, LinkedIn
- SEO: "Job offer comparison calculator", "Cost of living calculator"
- Partner with salary transparency sites

### Phase 3: Home/Family (Year 3)
- Target: First-time homebuyers, new parents
- Channels: Real estate content, parenting communities
- SEO: "Rent vs buy calculator", "Cost of raising a child calculator"
- Partner with real estate platforms

### Phase 4: Platform (Year 4+)
- API launches
- Embedded partnerships
- B2B sales team

---

## Technology

### Core Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    EggNest Platform                      │
├─────────────────────────────────────────────────────────┤
│  Retirement │ Job Change │ Relocation │ Home │ Family   │
│  Simulator  │ Simulator  │ Simulator  │ Sim  │ Sim      │
├─────────────────────────────────────────────────────────┤
│                 Shared Simulation Engine                 │
│         (Monte Carlo, scenario comparison, etc.)         │
├─────────────────────────────────────────────────────────┤
│                    PolicyEngine                          │
│     (Federal tax, state tax, benefits, credits)          │
├─────────────────────────────────────────────────────────┤
│                     Data Layer                           │
│   (Cost of living, childcare costs, salary data, etc.)   │
└─────────────────────────────────────────────────────────┘
```

### Stack
- **Frontend**: React + TypeScript
- **Backend**: Python + FastAPI
- **Tax Engine**: PolicyEngine-US
- **Database**: Supabase
- **Hosting**: Vercel + Cloud Run

### Data Sources (to build/acquire)
- Cost of living by metro
- Childcare costs by location
- Health insurance premiums
- Property tax rates
- Salary benchmarks by role/location

---

## Growth Path to $1B

### The Platform Play

| Phase | Product | Users | ARR | Valuation |
|-------|---------|-------|-----|-----------|
| 1 | Retirement sim | 100K | $100K | $1M |
| 2 | + Job/Relocation | 2M | $3.5M | $35M |
| 3 | + Home/Family | 10M | $15M | $150M |
| 4 | + API/Platform | 30M | $50M | $500M |
| 5 | Full life sim | 100M | $150M | $1.5B |

### Why This Can Be Huge

1. **Universal need**: Everyone makes life decisions
2. **Recurring**: Life keeps happening (new job, new house, new kid)
3. **High stakes**: People pay for important decisions
4. **Network effects**: Shared scenarios, community benchmarks
5. **Data moat**: Aggregated decision data improves recommendations

### Comparable Exits

| Company | Category | Exit |
|---------|----------|------|
| Credit Karma | Financial decisions | $7B (Intuit) |
| Mint | Budgeting | $170M (Intuit) |
| Personal Capital | Wealth planning | $1B (Empower) |
| NerdWallet | Financial comparison | $5B (IPO) |

EggNest's category: **Life decision simulation**. Bigger than any single vertical.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Complexity of multi-domain simulation | Start with retirement, prove model, expand carefully |
| Data acquisition costs | Partner with data providers, crowdsource benchmarks |
| PolicyEngine dependency | Deep partnership, contribute upstream, potential acquisition |
| Big tech competition | Open source moat, move fast, niche expertise |
| User trust in financial AI | Transparency, show methodology, no product recommendations |

---

## Team Needs

### Now
- Technical founder (have)

### Year 1
- Growth marketer
- Part-time designer

### Year 2
- 2 engineers (simulation engine, API)
- Data scientist (model improvement)
- Content marketer

### Year 3+
- Sales (API/partnerships)
- Customer success
- Additional engineers

---

## Summary

**Starting point**: Monte Carlo retirement calculator with real taxes.

**Vision**: The simulation engine for every major life decision.

**Why now**:
- PolicyEngine makes real tax calculation possible
- Open source builds trust in financial tools
- People are increasingly making decisions without advisors

**Path to $1B**:
1. Win retirement planning
2. Expand to job/relocation decisions
3. Add home/family planning
4. Become the platform (API + partnerships)
5. "EggNest it" becomes how people evaluate life decisions

The nest isn't just for retirement. It's where you go to see all your possible futures.

---

*Last updated: December 2024*
