# One-year US drawdown calculator

The calculator answers one question for one household in one tax year: if we
take this much from this account in 2026, what do we keep after taxes and any
benefits we lose? It also shows what the draw adds to the household's Medicare
premiums in 2028 and whether it covers each person's required minimum
distribution.

It covers a single filer or a married couple filing jointly, everyone 65 or
older by the end of 2026, drawing from a traditional IRA or 401(k), a Roth IRA,
taxable investments or cash. It runs at `/us-drawdown` in the app, through
`POST /core/simulate` and through the CLI, and all three return the same
`eggnest.core` envelope. `GET /programs` lists it as `us_drawdown_year`.

```bash
cd api
uv run eggnest core run scenario.yaml --engine us_drawdown_year --output-format envelope
```

```yaml
# scenario.yaml
state: NC
filing_status: single
you:
  birth_year: 1952
  social_security: 24000
  traditional_balance: 250000
cash_savings: 15000
draw_source: traditional
draw_amount: 30000
```

`api/eggnest/models_us_drawdown.py` documents every input and output. Every
amount of money comes in rounded to the cent, half a cent up, on the decimal
it prints as, which is what the page's fields show: 1.005 becomes $1.01 and
0.125 becomes 13 cents (`api/eggnest/money.py`).

## What decides each number

PolicyEngine-US computes every tax and benefit, and Eggnest holds no tax or
benefit formulas here. It changes one PolicyEngine-US parameter, SSI's unearned
income sources, for the reason the next section gives. `api/eggnest/us_year_engine.py` builds one
PolicyEngine-US household per draw amount in a single simulation and decides
what each household's inputs hold. `api/eggnest/drawdown_us.py` chooses the
draw amounts and reads the results.

| Draw | What PolicyEngine-US receives |
| --- | --- |
| Traditional IRA | The owner's `taxable_ira_distributions` |
| Traditional workplace plan, such as a 401(k) or 403(b) | The owner's `taxable_401k_distributions` |
| Roth IRA | The owner's `tax_exempt_ira_distributions`, which add no federal tax and no Medicare income |
| Taxable investments | `long_term_capital_gains` on the gain share of each sale; the rest returns what the household paid, and PolicyEngine-US never sees it |
| Cash | Nothing, since spending savings adds no income |

A traditional draw's `draw_account` says which kind of account it comes from,
`ira` (the default) or `workplace_plan`. Each person's other traditional
withdrawals have their own `other_withdrawals_account`, since they can come from
a different account than the draw; the calculator adds them to the same two
variables. PolicyEngine-US's rules treat 401(k) and 403(b) withdrawals alike, so
`taxable_401k_distributions` stands for both, and some states treat them unlike
IRA withdrawals: Maryland's pension subtraction (Md. Code Tax-Gen. 10-209) and
Rhode Island's retirement income subtraction (R.I. Gen. Laws 44-30-12(c)(9))
cover workplace plans but not IRAs.

The calculator counts each draw as spent evenly through the year and holds
savings at their January 1, 2026 balances for the whole year. So the resource
tests treat a withdrawal as still held, while money to spend counts it as
spent. SSI tests resources as of the first moment of each month and counts
money spent from the next month (20 CFR 416.1207(a); POMS SI 01110.600 B.2),
so a household that spends down below a limit could qualify for later months,
which the calculator doesn't show.

It puts each person's IRA and 401(k) balances into `ssi_countable_resources`,
since the owner can withdraw them (POMS SI 01120.210 B, D.2), along with the
household's cash and investments. SSA values a retirement fund at what the
owner could withdraw now, less any penalty for withdrawing early, with no
deduction for income tax (SI 01120.210 A.3). Everyone here is 65 or older, past
the IRS early-withdrawal tax (26 USC 72(t)(2)(A)(i)), and the calculator takes
no plan surrender charge, so it counts the whole balance. SSI's resource test
reads that figure, and so do PolicyEngine-US's asset tests for the Medicare
Savings Programs and Medicaid's senior and disability groups. SNAP's asset
test reads bank, stock and bond assets and leaves retirement accounts out.

A plan at a current employer that pays nothing until the owner leaves the job
is not a resource (POMS SI 01120.210 C.1). The calculator's traditional
balance doesn't tell such a plan apart, so it counts it; a caveat says so when
someone with a traditional balance has earnings.

For a married couple the calculator splits interest, dividends and the gain on
investments sold evenly between the spouses, as from accounts they hold
together. States that exclude retirement or investment income for each person,
such as Georgia's retirement exclusion (`ga_retirement_exclusion_person`, which
counts interest, dividends and capital gains), then apply each spouse's own
exclusion. Federal tax and SNAP read the couple's or household's total, so
the split leaves them as they were; SSI and the programs that follow its income
rules leave interest and dividends out (below). Cash and investment balances
sit with the first person. The SSI and Medicare Savings Program resource tests
add up the couple's resources, but two PolicyEngine-US tests read each
person's own `ssi_countable_resources`: Colorado's Old Age Pension
(`co_oap_eligible`) and Maryland's Public Assistance to Adults
(`md_paa_eligible`, only in a care facility). Colorado counts the couple's
resources together against its limit for a married client (9 CCR 2503-5
3.520.72 A), so for a Colorado couple with savings the page can show an Old
Age Pension that Colorado wouldn't pay; a caveat says so. Splitting the
savings evenly would make that worse, so they stay with the first person.

What someone receives for a resource is the resource in another form, not
income (20 CFR 416.1103(c), 416.1207(e); POMS SI 01110.600 B.4). Because SSI
counts retirement balances as resources, the calculator reads a withdrawal
from them the same way. That is Eggnest's reading: no regulation or POMS
section we found says it in words for an SSI claimant's own IRA or 401(k).
POMS says it for Trump Accounts, which it calls a type of traditional IRA (SI
01120.250 A): "Distributions of TA funds are not income, but a conversion of a
resource" (SI 01120.250 B.2). It says the same for a deemed spouse's or
parent's pension withdrawals (SI 01330.120 C.2, SI 01330.220 C.2).

SSI also leaves out interest and dividends earned on countable resources (42
USC 1382a(b)(23); 20 CFR 416.1124(c)(22); POMS SI 00830.500). The calculator
counts all the household's cash and investments as resources, so it leaves out
all the interest and dividends entered. A caveat asks for the savings behind
them when someone enters interest or dividends with no cash or investments.

PolicyEngine-US leaves retirement accounts out of SSI resources and counts
`retirement_distributions`, `interest_income` and `dividend_income` as SSI
unearned income. To follow the rules that go with counting the balances, the
calculator runs PolicyEngine-US with those three taken out of SSI's unearned
income sources (`gov.ssa.ssi.income.sources.unearned`) from 2026 on
(`us_year_engine.ssi_income_reform`). That is the one place Eggnest changes
PolicyEngine-US's rules. Every variable that reads `ssi_unearned_income`,
`ssi_marital_unearned_income` or `ssi_countable_income` follows it:

- SSI itself, including deeming between spouses;
- the Medicare Savings Programs (`msp_countable_income`), which use SSI's
  income method (42 USC 1396d(p)(1)(B));
- Medicaid's senior and disability groups
  (`medicaid_optional_senior_or_disabled_countable_income`) and its medically
  needy group (`is_medically_needy_for_medicaid`);
- state programs PolicyEngine-US builds on SSI's income: California's Cash
  Assistance Program for Immigrants, state supplement and 250 Percent Working
  Disabled Program; Colorado's Old Age Pension and state supplement;
  Connecticut's, Indiana's, Kentucky's and South Carolina's state
  supplementary payments; Florida's and Louisiana's optional state
  supplements; Idaho's Aid to the Aged, Blind and Disabled; Maryland's Public
  Assistance to Adults; Minnesota Supplemental Aid; and Missouri's
  supplementary payments.

SNAP keeps its own list of sources, which includes all three, so SNAP counts
withdrawals from both kinds of IRA, and interest and dividends, as unearned
income. SNAP also counts SSI payments, so it moves when the reform changes SSI.

SSA treats a plan that entitles its owner to periodic payments differently.
Periodic payments are those "which result from entitlement under a retirement
fund" (POMS SI 01120.210 A.2). The owner must apply for them and choose them
over a lump sum (SI 01120.210 E.1); the fund then "may not be a countable
resource" (SI 01120.210 B), and the payments are unearned income (20 CFR
416.1121(a); POMS SI 00830.160 B.1). Taking a lump sum when periodic payments
are available can make the owner ineligible for SSI for that month (POMS SI
00510.001 D.4). The calculator doesn't model that case; a caveat says so.
Whether required minimum distributions, or withdrawals an IRA owner schedules,
are periodic payments is not settled by any text we read.

PolicyEngine-US's `age`, `is_ssi_aged` and `is_medicare_eligible` are yearly,
while SSI is decided month by month (20 CFR 416.420) and counts someone as aged
once they are 65 (20 CFR 416.202(a)(1)). So someone born in 1961 counts as 65
for all of 2026, and SSI, Medicaid and Medicare Savings Program results for
them can include months before their birthday. A caveat says so.

The calculator takes every tax before refundable credits and counts those
credits once, among benefits:

- Federal income tax comes from `income_tax_before_refundable_credits`, which
  includes the net investment income tax and the alternative minimum tax.
  `federal_income_tax.citations` adds 26 USC 1411 or 26 USC 55 when the
  household pays either at the chosen draw or with no draw.
- State income tax comes from `state_income_tax_before_refundable_credits`.
  PolicyEngine-US's Wisconsin tax takes the lower of the usual tax after
  refundable credits and the tax on the retirement income exclusion path, which
  allows no credits. When the exclusion path wins, the calculator takes its tax
  from `state_income_tax`, counts no Wisconsin refundable credits, and cites
  `state_income_tax` and Wis. Stat. 71.05(6)(b)54m.a.
- Other taxes add employee payroll and self-employment tax to the rest of
  PolicyEngine-US's `household_tax_before_refundable_credits`: state use tax,
  local income tax and local occupational tax. In North Carolina, for example,
  PolicyEngine-US sets use tax from adjusted gross income, so a traditional draw
  raises it.
  `other_taxes.citations` names the ones the household pays at the chosen draw
  or with no draw.

Benefits start from PolicyEngine-US's `household_benefits`, leave out Social
Security, which the household enters as income, and health coverage, and add
refundable credits and the Alaska Permanent Fund Dividend. `benefits_by_program`
splits them by PolicyEngine-US variable, such as `snap` and `ssi`. The
calculator marks where PolicyEngine-US stops finding the household eligible for
Medicaid (`is_medicaid_eligible`) or a Medicare Savings Program (`msp`), and it
leaves the value of that coverage out of money to spend.

Money to spend adds the income the household enters, the draw and benefits,
and takes away taxes. It matches PolicyEngine-US's `household_net_income` plus
the cost of the investments the household sells and the cash it spends, which
PolicyEngine-US never sees as income, without health benefits or costs. The one
exception is Wisconsin's retirement income exclusion path: `household_net_income`
nets the usual tax, so when the path wins, money to spend exceeds that sum by
the tax the path saves. A Roth conversion adds tax but no money.

Social Security sets the income-related part of each person's 2028 Part B and
Part D premiums from their 2026 income (42 USC 1395r(i)(4)). The calculator
asks PolicyEngine-US for 2028:
each enrolled person's Part B premium less the base premium, plus
`income_adjusted_part_d_premium_surcharge`, against
`medicare_irmaa_magi_two_years_prior`, which adds tax-exempt interest to 2026
adjusted gross income. PolicyEngine-US holds the lines and amounts CMS
published up to its release and doesn't project them, so the calculator applies
the latest year it holds, now 2026, even after CMS publishes a later year's,
and `medicare_surcharge.rates_year` names that year.

Required minimum distributions come from the IRS Uniform Lifetime Table in
`api/eggnest/rmd.py`. From age 73, a person owes their traditional balance on
December 31, 2025 divided by the table's factor for their age at the end of
2026. The calculator figures one minimum on that whole balance and compares it
with their other traditional withdrawals plus any traditional draw from their
own account. That pooling holds among IRAs, whose minimums can come from any
of the owner's IRAs (26 CFR 1.408-8(e)); each 401(k) or other workplace plan
must pay out its own, and the page and caveats say so. Someone still working
for the employer whose plan they're in, owning 5% or less of it, can wait until
April 1 after the year they retire to take that plan's minimum
(26 USC 401(a)(9)(C)); a caveat names this whenever a person with a minimum has
earnings.

On a shortfall the person owes an excise tax of 25%, or 10% if they correct it
in time (26 USC 4974), due by December 31, 2026. The first minimum, for someone
who turns 73 in 2026, can wait until the required beginning date, April 1, 2027
(26 USC 401(a)(9)(C)(i)), and the excise tax on it falls in 2027
(26 CFR 54.4974-1(f)). For that person `first_year` is true, `due_by` is
2027-04-01 and the excise tax on a 2026 shortfall is nothing; they then take
both the 2026 and 2027 minimums in 2027. The calculator reports the excise tax
and leaves it out of taxes and money to spend.

## What each result holds

- `at_chosen_draw` and `with_no_draw`: the full year at the chosen draw and at
  none.
- `federal_income_tax`, `state_income_tax`, `other_taxes` and `benefits`: the
  chosen draw's amounts, each with the engine version and the law behind it.
- `coverage_at_chosen_draw` and `coverage_with_no_draw`: whether PolicyEngine-US
  finds the household eligible for Medicaid and a Medicare Savings Program.
- `sweep`: the same at every draw the calculator evaluates, from nothing to the
  larger of $250,000 and 125% of the draw, within what the account holds for
  the draw. A traditional draw can take the owner's balance less their other
  traditional withdrawals and Roth conversion, and `account_left` is what
  remains after all three. A grid of at
  most 400 round steps covers that range, with $250 steps up to $40,000, where
  benefits for older households end. The page reads between rows in a straight
  line, so it answers as the slider moves, and asks the API again 300 ms after
  the figures stop changing.
- `bands`: the ranges of draw where each extra dollar splits the same way
  between what the household keeps, pays in tax and loses in benefits. A second
  run cuts into 24 each grid interval that may hold a jump in a tax or benefit
  or a change of coverage, the one or two around each place the grid finds the
  rate changing, and each where a benefit reaches zero. A jump that shares an
  interval with a change of rate, or ends a phase-out, shows only on that
  closer look. Band edges then come from every draw evaluated, with each
  located jump cut out so no line runs through it. An edge that lands more
  than $1 from every draw evaluated gets a third run, and one closer moves to
  the nearest, so each band's rates come from the engine. A band with `jump`
  set is the 1/24 of an interval that holds a jump; its rates spread the jump
  over that width. Between that band's two rows the page reads the line on the
  nearer row's side of the jump, not a line through it, and dims its figures
  until the API answers for the draw, since the jump may fall either side. It
  dims them too for a draw past the sweep's top.
- `markers`: the draws where a benefit ends (`benefit_ends`), where Medicaid or
  a Medicare Savings Program ends (`coverage_ends`), where 2026 income crosses a
  Medicare line and the 2028 premium steps up (`medicare_surcharge_step`), and
  where a traditional draw covers its owner's required minimum
  (`required_minimum_reached`). The second run also evaluates the draws where
  the grid puts Medicare income at each line and halfway between neighbouring
  lines, so no interval of the sweep spans two lines and each
  `medicare_surcharge_step` carries its own line's step.
- `medicare_surcharge`: the lines for this filing status, the year they come
  from, the number of people on Medicare, and the yearly surcharge at the chosen
  draw and at none.
- `required_minimums`: each person's 2026 minimum, what they withdraw, any
  shortfall, whether 2026 is their first year with one, the day it's due and
  the excise tax on a shortfall.
- `next_1000`: where the next $1,000 of draw goes, a smaller step near the end
  of the account, and null once less than $1 is left, where rounding would
  swamp the rate, as it would a band's.

## What it leaves out

Filing statuses other than single and joint, anyone under 65 at the end of
2026, and any year but 2026. The calculator asks for no county, so
PolicyEngine-US places the household in its state's alphabetically first county
and applies that county's local taxes. It takes Social Security as entered,
without the retirement earnings test, and counts no value for Medicaid or the
Medicare Savings Programs. It treats every dividend as qualified, every gain as
long-term and every Roth withdrawal as a qualified distribution. The envelope's
`caveats` list these for each result, including the ones that depend on the
inputs.

SNAP agencies count a one-off lump sum as a resource rather than income
(7 CFR 273.9(c)(8)), so a single large withdrawal may count as savings where
the calculator counts it as income. Someone whose sole beneficiary is a spouse
more than 10 years younger uses the IRS Joint and Last Survivor Table, which
gives a smaller minimum than the Uniform Lifetime Table the calculator applies.

## Deployment

The calculator needs `policyengine-us`, which `api/pyproject.toml` requires at
2.15.16 or later and `api/uv.lock` pins at 2.15.16. The Modal image installs its
own list in `api/modal_app.py`, including `policyengine-us>=2.15.16`, on Python
3.11. The page calls the API at `NEXT_PUBLIC_API_URL`, tells search engines not
to index it, and no other page links to it.

## Invariants and tests

`api/tests/test_drawdown_us.py` states these properties at its top and tests
them with Hypothesis on a stand-in engine, whose kinks and cliffs sit where its
rules put them:

- Each band and the next $1,000 split into kept, tax and benefits that add to 1.
- Money to spend equals income entered plus the draw, less taxes, plus
  benefits, at every point of the sweep.
- Bands run from nothing to the top of the sweep, in order and without gaps.
- The chosen and no-draw outcomes fall on the sweep, and the account left
  equals what the source holds for the draw, less the draw. For a traditional
  draw, the owner's other traditional withdrawals and Roth conversion come out
  of the same balance first.
- Every marker lies inside the sweep.
- Each Medicare marker sits where Medicare income reaches its line and carries
  that line's step alone, so the steps add up to the surcharge at the top of
  the sweep.
- The same inputs give the same result.
- On a piecewise-linear series whose kinks sit four or more grid intervals
  apart, the grid's test for jumps never flags a change of rate. It flags any
  jump of $30 or more with no kink in its interval or the ones either side,
  and any two side by side of $60 or more.
- Over a whole run on such a series in the draw, changes of rate alone give no
  jump band, and each change of 5 cents a dollar or more lands on a band edge
  within $1 plus 25 cents divided by the change ($1.63 for 40 cents, $6 for 5
  cents), where the band's line misses the series by under the change times
  $1, plus 25 cents. The edge moves up to $1 to an evaluated draw, which takes
  the line up to the change times $1 off the series, so past a change of 75
  cents a dollar the line can miss by more than $1 (one case misses by $1.48
  at a change of $1.87), and a change too small for the bands to notice can
  tilt the line beside a larger one, which moves where the lines cross. A
  jump of $30 or more gets the one jump band, no wider than 1/24 of its grid
  interval, wherever it sits, unless it lies within 1/12 of an interval of a
  change of rate and is no larger than $25 plus that change times 1/24 of the
  interval. The reviewers' cases also hold: a change of rate keeps
  its own edge beside a jump or a change of coverage, kinks a $50,000 grid
  can't separate get their own edges, and a cliff where a phase-out ends gets
  its jump band.
- The band helpers both calculators share (`api/tests/test_drawdown_bands.py`),
  the search for jumps above included, place each change of rate that sits
  three or more grid intervals from the next within a cent.

`api/tests/test_drawdown_us_policyengine.py` runs the real engine. It checks
federal tax and taxable Social Security against hand calculations under 2026
law (Rev. Proc. 2025-32, 26 USC 86 and 151(d)(5)(C)), and the Medicare steps
against CMS's 2026 lines and amounts. It also ties money to spend to
`household_net_income`, checks that one simulation of many households gives
each the result it gets alone, and follows each kind of draw to the programs
that count it.

`app/src/lib/us-drawdown.test.ts` tests the page's arithmetic with fast-check
and checks it against runs recorded from the real engine, and
`app/e2e/us-drawdown.spec.ts` drives the page in a browser on one of those runs.
To refresh the recorded runs:

```bash
cd api
uv run python scripts/record_us_drawdown_fixture.py
```

Each recorded run also holds the engine's year at draws between the sweep's
rows, where the page reads its figures off a line, and the page's tests check
it there: within 2.5 cents, or half the step between the rows for benefits,
which the engine gives in whole dollars, and other taxes, which move in
whole-dollar steps over part of their range. `TestFrontendFixture` fails when
any part of the recorded runs, those draws included, drifts from the engine.
