# UK Axiom rules engine integration

The UK simulator can compute UK income tax and National Insurance, and a
Pension Credit screen, from statute encodings via the
[Axiom rules engine](https://github.com/TheAxiomFoundation/axiom-rules-engine)
and [rulespec-uk](https://github.com/TheAxiomFoundation/rulespec-uk). The
Pension Credit screen carries citations to the legislation behind it (from
the engine's explain traces); the tax backend's numbers do not yet carry
per-number citations in the API response.

## Enabling

The backend targets axiom-rules-engine **v0.2.x** (CI pins v0.2.2) and a
rulespec-uk checkout (CI pins `932390f`):

```bash
export EGGNEST_AXIOM_ENGINE_BIN=/path/to/axiom-rules-engine   # v0.2.x release binary
export EGGNEST_RULESPEC_UK_ROOT=/path/to/rulespec-uk          # directory named rulespec-uk
export EGGNEST_UK_TAX_ENGINE=axiom   # optional: switch the tax backend
```

The engine is strict about the checkout: the path must be the canonical,
absolute path to a real directory named exactly `rulespec-uk` (no symlink,
no macOS `/tmp` alias), with no `legislation/`, `statutes/` or similar
directories at its top level. `axiom_uk.rulespec_uk_root()` resolves the
path and reports the backend unavailable otherwise, and `available()` also
asks the engine for its capabilities (artifact format 2, version 0.2.x).
The adapter compiles each rule module once per process with
`compile --program <root>/uk/<module> --rulespec-root <root>`.

With the first two variables set, every UK simulation carries a Pension
Credit screen, whichever tax backend is selected. `.github/workflows/ci.yml`
installs the pinned engine release (checking its SHA-256) and rulespec-uk
commit and sets `EGGNEST_REQUIRE_AXIOM=1`, which makes `test_axiom_uk.py`
fail rather than skip if the engine is missing.

## What the engine computes

Tax (with `EGGNEST_UK_TAX_ENGINE=axiom`):

- Income tax bands and band tax, with the basic rate limit as an encoded
  parameter and the higher rate limit derived per s.10(5A) (ITA 2007 s.10)
- Personal allowance with the £100k taper (ITA 2007 s.35)
- Starting rate for savings (ITA 2007 s.12) and the personal savings
  allowance tiers (ITA 2007 s.12B)
- Dividend stacking and rates structure with the dividend nil rate
  (ITA 2007 ss.13, 13A)
- Class 1 employee NI (SSCBA 1992 s.8)

Pension Credit (always, when the engine is configured):

- Standard minimum guarantee for a single claimant (SI 2002/1792 reg 6)
- Income deemed from capital: £1 a week for each £500, or part, above
  £10,000 (SI 2002/1792 reg 15(6))
- Guarantee credit (State Pension Credit Act 2002 s.2)

Values still supplied as cited runtime inputs from
`api/eggnest/data/axiom_uk_parameters.yaml`: the income tax rates (ITA s.6
in rulespec-uk is still deferred), the dividend rates (see the upstream
issue below), the 0% starting rate for savings, and the NI weekly
thresholds (an explicit annual-equivalence convention).

Computed in eggnest, with citations, because rulespec-uk has no encoding:

- State Pension age, from Pensions Act 1995 Sch 4 Pt I para 1 as amended
  (`api/eggnest/state_pension_age.py`, schedule in
  `api/eggnest/data/state_pension_age.json`, checked against the
  legislation.gov.uk text of 2026-09-29; the tests compare it with every
  enacted table row). It sets the Pension Credit qualifying age (SPC Act
  2002 s.1(6)) and ends employee NI on earnings after it (SSCBA 1992
  s.6(3)) in both tax backends. The simulator knows only a whole-year age,
  so it takes the person's birthday to be the run date.

## The Pension Credit screen

For up to 500 evenly spaced simulated paths, in every year a path is alive
from the qualifying age (pro rata in the year it is reached), the screen
counts income as State Pension Credit does and asks the engine for the
guarantee credit:

- **Counted:** State Pension and pension drawdown in full, tax-free cash
  included (SPC Act s.16(1)(f)); earnings less half of pension
  contributions (reg 17A(4A)) and £5 a week (Sch VI para 5(a)); less the
  income tax and NI payable (reg 17(10)); plus reg 15(6) deemed income on
  ISA and GIA balances at the start of the year.
- **Not counted:** actual dividends and interest on savings, which Sch IV
  para 18 disregards (the savings count as capital instead), and the SIPP
  pot, which is not capital (Sch V para 22).
- **Not modeled:** notional income from an undrawn pension pot (reg 18),
  savings credit, housing costs, couples. The screen can overstate
  entitlement where a SIPP sits undrawn.

The result reports the share of screened paths with credit indicated
(overall and by age), the median credit where indicated, the median first
age, and the qualifying age. A plan that ends before the qualifying age
returns `status: "under_qualifying_age"`. The screen is never added to
spendable income or to success rates.

## Parity status

`api/scripts/uk_engine_parity.py` compares the Axiom and PolicyEngine tax
backends across a 72-case grid and classifies every difference, each
classification bounded by the delta it can actually produce. With engine
v0.2.2 and rulespec-uk `932390f`: **68/72 exact to the pound, 4 differ,
zero unexplained**. The four differences come from two documented
policyengine-uk-compiled deviations from the statutory encodings:

1. Dividend nil rate relieved against the top slice; ITA 2007 s.13A
   nil-rates the *first* £500, so the engines differ when the nil rate
   straddles a band edge.
2. Personal savings allowance sized before dividend stacking; s.12B(3)
   counts income charged at the dividend upper/additional rates.

Two former deviations are gone: the simulator now switches off
policyengine-uk-compiled's imputed State Pension, and both backends stop
employee NI at State Pension age. Remaining encoding gap: Scottish and
Welsh rates (the Axiom backend ignores region).

Upstream issue to track: rulespec-uk's ITA s.8 encoding dates the Finance
Act 2026 dividend rates (10.75%/35.75%) from 2024-04-06, so eggnest feeds
the 2025/26 rates from its cited values file for every year until the
effective-dating is corrected.

## WASM feasibility

The engine core compiled for `wasm32-unknown-unknown`
(`cargo check --target wasm32-unknown-unknown --lib`) when checked on
2026-06-10; not re-checked on v0.2.x. A client-side UK calculator (engine
plus compiled rulespec artifacts shipped to the browser) would remove cold
starts and server cost for the UK simulator; the remaining work is a
wasm-bindgen interface and artifact bundling.

## Deployment note

Production (eggnest.co and its Modal API) runs the
`fix/uk-outcome-layout-20260919` line, which has none of this backend, and
the Modal image has neither the engine nor rulespec-uk. Production
therefore serves the PolicyEngine tax backend and no `pension_credit`
field, so the homepage does not mention Pension Credit screening. To serve
the screen: add the pinned engine binary and a rulespec-uk checkout to the
API image, set the two environment variables, deploy this code, and then
name the screen in the homepage's UK line.
