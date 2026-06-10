# UK Axiom rules engine integration

The UK simulator can compute taxes and benefits from statute encodings via
the [Axiom rules engine](https://github.com/TheAxiomFoundation/axiom-rules-engine)
and [rulespec-uk](https://github.com/TheAxiomFoundation/rulespec-uk). Every
number produced this way carries a citation to the legislation that defines
it (via the engine's explain traces).

## Enabling

```bash
export EGGNEST_AXIOM_ENGINE_BIN=/path/to/axiom-rules-engine   # release build
export EGGNEST_RULESPEC_UK_ROOT=/path/to/rulespec-uk
export EGGNEST_UK_TAX_ENGINE=axiom   # optional: switch the tax backend
```

With the first two variables set, the simulator computes the Pension Credit
guarantee-credit screen along the median path regardless of which tax
backend is selected. The tax backend itself defaults to
policyengine-uk-compiled until the parity gap list (below) is closed.

## What is statute-encoded today

- Income tax bands and band tax (ITA 2007 s.10)
- Dividend rates and stacking (ITA 2007 s.13)
- Personal allowance with the £100k taper (ITA 2007 s.35)
- Class 1 employee NI percentages, with the s.6(3) pensionable-age
  exemption applied (SSCBA 1992 ss.1/8)
- Guarantee credit (State Pension Credit Act 2002 s.2; SI 2002/1792 reg 6)

Band limits, rates, and NI thresholds are still runtime inputs in
rulespec-uk; interim values with per-value legal sources live in
`api/eggnest/data/axiom_uk_parameters.yaml`.

## Parity status

`api/scripts/uk_engine_parity.py` compares both backends across a 72-case
grid and classifies every difference. Current status: zero unexplained
differences. The remaining encoding gaps, in priority order for
rulespec-uk:

1. ITA 2007 s.13A — dividend nil rate (£500): Axiom overstates dividend
   tax by up to £43.75 at the ordinary rate.
2. ITA 2007 ss.12–12B — starting rate for savings and personal savings
   allowance: Axiom taxes savings interest as non-savings income.
3. Scottish and Welsh rates: the region input is ignored by the Axiom
   backend.

The parity work also surfaced two policyengine-uk-compiled issues worth
filing upstream: employee NI charged over pensionable age, and State
Pension re-uprating/imputation for over-SPA records even when the caller
supplies its own SP series.

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
