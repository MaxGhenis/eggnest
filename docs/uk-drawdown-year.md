# One-year UK drawdown calculator

The calculator answers one question for one person in one tax year: if I take
this much from this pot in 2026/27, what do I keep after income tax, National
Insurance and any change in Pension Credit?

It runs at `/uk-drawdown` in the app, through `POST /core/simulate` and through
the CLI, and all three return the same `eggnest.core` envelope. `GET /programs`
lists it as `uk_drawdown_year`.

```bash
cd api
uv run eggnest core run scenario.yaml --engine uk_drawdown_year --output-format envelope
```

```yaml
# scenario.yaml
birth_date: 1958-06-15
state_pension: 9360
sipp_balance: 10000
draw_source: sipp
draw_amount: 2500
```

`api/eggnest/models_uk_drawdown.py` documents every input and output.

## What decides each number

The [Axiom rules engine](uk-axiom-engine.md) computes income tax, employee
National Insurance and guarantee credit from rulespec-uk. Eggnest holds no tax
or benefit formulas here. `api/eggnest/drawdown_uk.py` decides what each rule
receives, and each decision follows a cited provision.

Income tax sees the State Pension, other pensions, earnings, interest,
dividends and the taxable part of a pension draw. A quarter of each pot
withdrawal comes tax free unless someone has already taken their tax-free cash,
up to the Lump Sum Allowance. ISA, investment and cash draws add no taxable
income; the calculator leaves out Capital Gains Tax.

Pension Credit assesses each of the 52 weeks separately:

| Money | How DWP counts it | Authority |
| --- | --- | --- |
| State Pension | In full, claimed or not, from the qualifying age | SI 2002/1792 reg 18(1) |
| Other pensions | In full | SPCA 2002 s.16(1)(f) |
| Regular withdrawals from a pot | In full as income, tax-free part included | DMG 85456, 85476 |
| One-off withdrawals from a pot | As capital, and DWP values what's left again | DMG 85457-85458 |
| An undrawn pot | The annuity it could buy, less regular withdrawals | Reg 18(2)-(3); DMG 85460 |
| Earnings | Above £5 a week | Sch VI para 5(a) |
| Tax on counted income | Taken off that income | Reg 17(10) |
| Savings over £10,000 | £1 a week per £500 or part | Reg 15(6) |
| Actual interest and dividends | Not counted | Sch IV para 18 |
| The pot itself | Not capital | Sch V para 22 |

The calculator assumes someone spends each draw evenly through the year, so ISA,
investment and cash balances fall week by week and a one-off draw from a pot
sits in savings until spent.

The annuity rate comes from the Government Actuary's drawdown tables, which
providers use for the figure they give DWP (DMG 85470). The calculator reads
Table 1 by age and a 15-year gilt yield rounded down to the next 0.25%, and
accepts a provider's own figure in its place. `gad_drawdown_factors.json`
carries the table, and `api/scripts/build_gad_drawdown_factors.py` rebuilds it.

## What each result holds

- `at_chosen_draw` and `with_no_draw`: the full year at the chosen draw and at
  none.
- `sweep`: the same at every draw on a grid up to the pot, or at least far
  enough to pass the additional-rate threshold. The page reads between rows in
  a straight line, so it answers as the slider moves and refreshes from the API
  when the slider stops.
- `bands`: the ranges of draw where each extra pound splits the same way, with
  edges placed to the penny where the rate changes.
- `markers`: the draw where a pot's regular withdrawals pass its annuity income,
  so Pension Credit starts to fall, and the draw where guarantee credit ends.
- `pension_credit_working`: the weekly amounts behind the result.
- `next_1000`: where the next £1,000 of draw goes, or a smaller step near the
  end of the pot.

## What it leaves out

Couples, Scottish taxpayers, Savings Credit, additional amounts for severe
disability or caring, Housing Benefit, Council Tax Reduction and any year but
2026/27. The envelope's `caveats` list these for each result, including the
ones that depend on the inputs.

The Scottish rates need a 2026/27 encoding that neither tax engine holds. Most
of what Housing Benefit and Council Tax Reduction need for pensioners remains
unencoded in rulespec-uk, so the page warns when a draw ends guarantee credit,
which passports people to both.

## Deployment

The calculator has no fallback engine. Without `EGGNEST_AXIOM_ENGINE_BIN` and
`EGGNEST_RULESPEC_UK_ROOT`, the API answers 503.

## Invariants and tests

`api/tests/test_drawdown_uk.py` states these properties at its top and tests
them with stand-in rules and Hypothesis:

- Money to spend equals all income, plus the draw, plus Pension Credit, less
  income tax and National Insurance.
- Each pound of draw goes somewhere: kept, tax and lost credit sum to 1.
- For regular pot draws, tax never falls as the draw rises, and Pension Credit
  never falls below its no-draw level up to the pot's annuity income and never
  rises beyond it.
- ISA, investment and cash draws leave tax unchanged and never lower Pension
  Credit.
- Bands run from nothing to the top of the sweep without gaps.

`api/tests/test_drawdown_uk_axiom.py` runs the real engine against scenarios
worked by hand from the legislation, and compares its tax with
`policyengine-uk-compiled`. The two engines differ where interest straddles the
higher-rate or additional-rate threshold, and the Axiom result follows
ITA 2007 s.12B(8).

`app/src/lib/uk-drawdown.test.ts` tests the page's arithmetic with fast-check
and checks it against runs recorded from the real engine. To refresh those
recorded runs:

```bash
cd api
uv run python scripts/record_uk_drawdown_fixture.py
```

`TestFrontendFixture` fails when the recorded runs drift from the engine.
