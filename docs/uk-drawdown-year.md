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

`api/eggnest/models_uk_drawdown.py` documents every input and output. Every
amount of money comes in rounded to the penny, half a penny up, on the decimal
it prints as, which is what the page's fields show: 1.005 becomes £1.01 and
0.125 becomes 13p (`api/eggnest/money.py`).

## What decides each number

The [Axiom rules engine](uk-axiom-engine.md) computes income tax, employee
National Insurance and guarantee credit from rulespec-uk. rulespec-uk doesn't
yet encode how DWP counts pension pots and savings, when the State Pension
starts, or how pension tax-free cash works, so `api/eggnest/drawdown_uk.py`
applies those rules by hand before the engine runs, each with a cited
provision: which money counts as income or capital for Pension Credit, notional
income from an undrawn pot, the £5 earnings disregard, tax off counted income,
the State Pension from State Pension age, the tax-free part of a pot draw and
the minimum pension age. Each is a capability rulespec-uk lacks today.

Income tax sees the State Pension paid in the year, other pensions, earnings,
interest, dividends and the taxable part of a pension draw. The State Pension
paid is the yearly rate for the share of the tax year from State Pension age,
and nothing while someone defers it.

A quarter of each pot withdrawal comes tax free unless someone has already
taken their tax-free cash, up to the Lump Sum Allowance. A one-off withdrawal
can instead take the tax-free cash first, as a pension commencement lump sum:
up to a quarter of the pot, within the Lump Sum Allowance left, comes tax free
and the rest is taxable (Finance Act 2004 s.166 and Sch 29 paras 1-3). A pot
pays out from age 55 (s.165 pension rule 1, Sch 29 paras 1(1)(d) and 4A(1)(c),
and s.279), so the calculator draws from it for anyone 55 by 5 April 2027 and
names the day they turn 55. For anyone younger the pot can pay nothing in the
year, so the calculator costs only a draw of nothing from it. ISA,
investment and cash draws add no taxable income; the calculator leaves out
Capital Gains Tax.

The calculator assesses Pension Credit in each of 52 weeks from 6 April 2026
separately, counting a week when it starts on or after the qualifying date.
That approximates DWP's timing. DWP pays from the first full benefit week, which
turns on the claimant's payday, unless they move straight from Universal Credit
or another benefit reg 16A(2) names (SI 1987/1968 reg 16A). For people reaching
pensionable age from 6 April 2010, the National Insurance number sets the
payday unless DWP arranges another, and DWP pays in arrears, weekly,
fortnightly or every four weeks (reg 26BA). The tax year has 52 weeks and a day, and neither the payday nor an
earlier benefit is an input, so DWP's count can be about a week more or less;
the caveats say so. The last week starts on 29 March 2027, so a qualifying date
from 30 March to 5 April 2027 leaves no week counted, and the page says so
rather than calling the date after the tax year.

In each week it counts:

| Money | How DWP counts it | Authority |
| --- | --- | --- |
| State Pension | At its weekly rate in each week from the qualifying age, claimed or deferred | SI 2002/1792 regs 17(1), 18(1) |
| Other pensions | In full | SPCA 2002 s.16(1)(f) |
| Regular withdrawals from a pot | In full as income, tax-free part included | DMG 85456, 85476 |
| One-off withdrawals from a pot | As capital, and DWP values what's left again | DMG 85457-85458 |
| An undrawn pot | The annuity it could buy at the age of the first eligible week, less regular withdrawals | Reg 18(2)-(3); DMG 85460 |
| Earnings | Above £5 a week | Sch VI para 5(a) |
| Tax on counted income | Taken off that income: income tax on non-savings income, with whatever allowance interest and dividends leave, and NI; a one-off draw's tax comes off the capital instead | Reg 17(10); ITA 2007 ss.16, 25(3A), 35(2) |
| Savings over £10,000 | £1 a week per £500 or part, at full value (DWP takes 10% off shares; the calculator doesn't) | Regs 15(6), 19 |
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
  enough to pass the additional-rate threshold and the draw where the tax-free
  cash runs out, so the last band's rate holds to the pot. With the tax-free
  cash taken first, every pound past the cash is taxable, so the grid runs
  £180,000 past it. The page reads between rows in a straight line, so it
  answers as the slider moves and refreshes from the API when the slider stops.
  Between the two rows of a band with `jump` set it reads the nearer row's
  side of the jump instead: the nearer row, carried to the draw at the rate
  of a line beside the jump. It takes that rate from rows £1 or more apart,
  since the API places a change of rate between rows a penny apart and rounds
  each figure to the penny, and two rows a penny apart can put a rate up to
  £1 a pound out. Since such a pair brackets a change of rate, the pound out
  can cross one; the line then carries the rate beyond the change, and the
  figures can miss by up to the change of rate times the distance carried.
  Where the nearer row's side holds no row £1 away, at either end of the
  sweep or beside another jump, it takes the other side's rate, or the wider
  side's where neither does. Either way it dims those figures until
  the API answers for the draw, since the jump may fall either side. The
  ladder says where each jump falls ("At £770" for one placed to the penny,
  "Between" its ends for one the API leaves in a wider piece), and inside a
  jump band the chart's tooltip says the same and what changes, with no
  figure for the draw. The page's fields and slider give whole pennies, which
  a penny band can't hold, so only a wider band shows these. For a draw past
  the sweep's top it dims its figures until the API answers.
- `bands`: the ranges of draw where each extra pound splits the same way. A
  second run cuts into 24 pieces each grid interval that may hold a jump in
  income tax, the intervals around each change of rate and those where Pension
  Credit reaches zero. A change of rate a piece or two from a jump leaves
  pieces between them that look like jumps too, so where a jump has fewer
  than five draws on either side before the next change, one more run cuts
  the pieces from the jump to just past that change into up to 24, none
  narrower than £5, and looks for the jumps again. Up to three more runs then
  place each change in income tax to the penny, and one more runs only where
  a band's tax still strays more than £1 from straight: seven runs at most. A
  band with `jump` set is the one penny where income tax jumps, as where a
  draw takes income into the higher or additional rate and the Personal
  Savings Allowance falls to £500 or to nothing (ITA 2007 s.12B); its rates
  spread the jump over that penny.
- `state_pension_paid`, `state_pension_age_date` and
  `minimum_pension_age_date`: the State Pension counted for tax, and the days
  behind it and behind a pot draw.
- `markers`: the draw where a pot's regular withdrawals pass its annuity income,
  so Pension Credit starts to fall, and the draw where guarantee credit ends.
- `pension_credit_working`: the weekly amounts behind the result.
- `next_1000`: where the next £1,000 of draw goes, or a smaller step near the
  end of the pot; none at the end of the pot or for a pot that can't pay out
  this year.

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

- Money to spend equals the State Pension paid, other income, the draw and
  Pension Credit, less income tax and National Insurance.
- Pension Credit counts the State Pension's weekly rate in each eligible week,
  claimed or deferred; tax and money to spend count only what is paid.
- Each pound of draw goes somewhere: kept, tax and lost credit sum to 1.
- For regular pot draws, tax never falls as the draw rises, and Pension Credit
  never falls below its no-draw level up to the pot's annuity income and never
  rises beyond it.
- ISA, investment and cash draws leave tax unchanged and never lower Pension
  Credit.
- Bands run from nothing to the top of the sweep without gaps.
- On stand-in rules with the real rules' steps, each fall in the Personal
  Savings Allowance (ITA 2007 s.12B) gets a band one penny wide with `jump`
  set, and income tax moves £1 or more across every such band. No other band
  charges more than 62p a pound or strays more than £1 from a straight line,
  so none hides a step of £2 or more, including where a change of rate sits
  within a 24th of a grid interval of the jump. The stand-in rounds tax to
  the penny, so on it a band under £1, which only a sweep under £1 or a gap
  between two jumps leaves, can charge a penny of rounding over the 62p: a
  pot of one penny can show 100p a pound to tax. The tests check this on 20
  examples; with `HYPOTHESIS_PROFILE=thorough` it held on 150 (two seeds)
  and on 500. At the higher rate the jump is 20% of the interest over £500,
  up to £100, so the tests' £600 to £20,000 of interest makes each jump £20
  or more and the next change of rate £100 or more of taxable income past
  it. The law's jump can be smaller, £1 at £505 of interest, and pin_changes
  counts a move of £1 in a penny as one. A jump under £5 can go unfound,
  since a piece of draw must move £5 beyond its neighbours' rates to count
  as one: at the higher rate that is under £525 of interest.
- Where the Personal Allowance tapers, it rounds up to the pound (s.35(3)), so
  tax rises in 40p steps; the taper's band runs from the last penny before its
  first step to the penny of its last, even where the grid samples each step
  at the same point (4% or 16% of the draw tax free). A run evaluates the
  year seven times at most.
- The shared band helpers (`api/tests/test_drawdown_bands.py`) place a jump at
  a change of rate on its penny, and a change of rate alone, on figures
  rounded to the penny, within a cent plus half a penny over the change of
  rate, with no second edge within £1 of it. A jump a 24th of a grid interval
  from a change of rate keeps its penny once its pieces are cut finer, and the
  change gets its own edge. Where tax gives a jump back, as past the Personal
  Savings Allowance's fall, no edge lands within £1 of the jump's ends, so no
  band but a jump's is narrower than £1.

`api/tests/test_drawdown_uk_axiom.py` runs the real engine against scenarios
worked by hand from the legislation, and compares its tax with
`policyengine-uk-compiled`. The two engines differ where interest straddles the
higher-rate or additional-rate threshold, and the Axiom result follows
ITA 2007 s.12B(8). It also checks the reviewers' cases: the Personal Savings
Allowance's £100 and £200 jumps and the taper's first and last 40p steps to
the penny, and each change of rate beside a jump within a cent plus half a
penny over the change of rate.

`app/src/lib/uk-drawdown.test.ts` tests the page's arithmetic with fast-check
and checks it against runs recorded from the real engine. To refresh those
recorded runs:

```bash
cd api
uv run python scripts/record_uk_drawdown_fixture.py
```

Each recorded run also holds the engine's year at draws between the sweep's
rows, where the page reads its figures off a line, and the page's tests check
it there: within 2p, except income tax, within 22p because the tapering
Personal Allowance moves it in 40p steps, and Pension Credit on a draw from
savings, within half the step between the rows because its tariff income moves
£1 a week for each £500 or part.
`TestFrontendFixture` fails when any part of the recorded runs, those draws
included, drifts from the engine.
