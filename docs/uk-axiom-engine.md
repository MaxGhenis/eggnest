# UK Axiom rules engine integration

The UK simulator can compute taxes and benefits from statute encodings via
the [Axiom rules engine](https://github.com/TheAxiomFoundation/axiom-rules-engine)
and [rulespec-uk](https://github.com/TheAxiomFoundation/rulespec-uk). Every
number produced this way carries a citation to the legislation that defines
it (via the engine's explain traces).

## Enabling

```bash
export EGGNEST_AXIOM_ENGINE_BIN=/path/to/axiom-rules-engine   # release build from main
export EGGNEST_RULESPEC_UK_ROOT=/path/to/rulespec-uk
export EGGNEST_UK_TAX_ENGINE=axiom   # optional: switch the tax backend
```

The adapter compiles the rule modules once per process (setting
`AXIOM_RULESPEC_REPO_ROOTS` for cross-module import resolution). With the
first two variables set, the simulator computes the Pension Credit
guarantee-credit screen along the median path regardless of which tax
backend is selected.

## What is statute-encoded today

- Income tax bands and band tax, with the basic rate limit as an encoded
  parameter and the higher rate limit derived per s.10(5A) (ITA 2007 s.10;
  FA 2021/FA 2023 imports)
- Personal allowance with the £100k taper (ITA 2007 s.35)
- Starting rate for savings (ITA 2007 s.12) and the personal savings
  allowance with its higher/additional-rate tiers (ITA 2007 ss.12A-12B)
- Dividend stacking and rates structure (ITA 2007 s.13) with the dividend
  nil rate and its per-band split (ITA 2007 s.13A)
- Class 1 employee NI percentages, with the s.6(3) pensionable-age
  exemption applied (SSCBA 1992 ss.1/8)
- Guarantee credit (State Pension Credit Act 2002 s.2; SI 2002/1792 reg 6)

Values still supplied as cited runtime inputs from
`api/eggnest/data/axiom_uk_parameters.yaml`: the income tax rates (20/40/45,
ITA s.6 stub has no values yet), the 2025/26 dividend rates (see upstream
issues), the 0% starting rate for savings, and the NI weekly thresholds
(kept as an explicit annual-equivalence convention; the statutory weekly
values are encoded in SI 2001/1004 reg 10).

## Parity status

`api/scripts/uk_engine_parity.py` compares both backends across a 72-case
grid and classifies every difference, with each classification bounded by
the delta it can actually produce. Current status: **49/72 exact to the
pound, zero unexplained**. All remaining differences are documented
policyengine-uk-compiled deviations from the statutory encodings:

1. Employee NI charged over pensionable age (SSCBA 1992 s.6(3) exempts).
2. State Pension re-uprated/imputed for over-SPA records even when the
   caller supplies its own SP series.
3. Dividend nil rate relieved against the top slice; ITA 2007 s.13A nil-rates
   the *first* £500, so the engines differ when the nil rate straddles a
   band edge.
4. Personal savings allowance sized before dividend stacking; s.12B(3)
   counts income charged at the dividend upper/additional rates.

The former encoding gaps (dividend nil rate, savings allowances) closed
with rulespec-uk PR #48. Remaining encoding gap: Scottish and Welsh rates
(the region input is ignored by the Axiom backend).

Upstream issues to track: rulespec-uk's ITA s.8 encoding dates the Finance
Act 2026 dividend rates (10.75%/35.75%) from 2024-04-06, so eggnest feeds
the 2025/26 rates from its cited values file until the effective-dating is
corrected.

## WASM feasibility

The engine core compiles cleanly for `wasm32-unknown-unknown`
(`cargo check --target wasm32-unknown-unknown --lib`; verified 2026-06-10,
all dependencies are pure Rust). A client-side UK calculator — engine plus
compiled rulespec artifacts shipped to the browser, no backend on the
consumer path — is architecturally viable and would eliminate cold starts
and server cost for the UK simulator. Remaining work is a wasm-bindgen
interface and artifact bundling.

## Deployment note

The Modal image does not yet include the engine binary or rulespec-uk, so
production serves `pension_credit: null` and the PolicyEngine tax backend
until the image adds them (build the release binary in the image, or pull
a prebuilt artifact).
