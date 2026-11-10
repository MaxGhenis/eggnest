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

`api/eggnest/models_us_drawdown.py` documents every input and output.

## What decides each number

PolicyEngine-US computes every tax and benefit, and EggNest holds no tax or
benefit formulas here. `api/eggnest/us_year_engine.py` builds one
PolicyEngine-US household per draw amount in a single simulation and decides
what each household's inputs hold. `api/eggnest/drawdown_us.py` chooses the
draw amounts and reads the results.

| Draw | What PolicyEngine-US receives |
| --- | --- |
| Traditional IRA or 401(k) | The owner's `taxable_ira_distributions`, on top of their other traditional withdrawals |
| Roth IRA | The owner's `tax_exempt_ira_distributions`, which add no federal tax and no Medicare income |
| Taxable investments | `long_term_capital_gains` on the gain share of each sale; the rest returns what the household paid, and PolicyEngine-US never sees it |
| Cash | Nothing, since spending savings adds no income |

SNAP and SSI count withdrawals from both kinds of IRA as unearned income,
through PolicyEngine-US's `retirement_distributions`. The calculator counts
each draw as spent evenly through the year and holds savings at their
January 1, 2026 balances for the whole year. It puts each person's IRA and
401(k) balances into `ssi_countable_resources` in full, since the owner can
withdraw them (POMS SI 01120.210 B), along with the household's cash and
investments. SSI's resource test reads that figure, and so do PolicyEngine-US's
asset tests for the Medicare Savings Programs and Medicaid's senior and
disability groups. SNAP's asset test reads bank, stock and bond assets and
leaves retirement accounts out. The calculator assigns interest, dividends, cash
and investments to the first person.

The calculator takes every tax before refundable credits and counts those
credits once, among benefits:

- Federal income tax comes from `income_tax_before_refundable_credits`.
- State income tax comes from `state_income_tax_before_refundable_credits`.
  PolicyEngine-US's Wisconsin tax takes the lower of the usual tax after
  refundable credits and the tax on the retirement income exclusion path, which
  allows no credits. When the exclusion path wins, the calculator takes its tax
  and counts no Wisconsin refundable credits.
- Other taxes add employee payroll and self-employment tax to the rest of
  PolicyEngine-US's `household_tax_before_refundable_credits`: state use tax,
  local income tax and local occupational tax. In North Carolina, for example,
  PolicyEngine-US sets use tax from adjusted gross income, so a traditional draw
  raises it.

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
PolicyEngine-US never sees as income, without health benefits or costs. A Roth
conversion adds tax but no money.

Social Security sets the income-related part of each person's 2028 Part B and
Part D premiums from their 2026 income (42 USC 1395r(i)(4)). The calculator
asks PolicyEngine-US for 2028:
each enrolled person's Part B premium less the base premium, plus
`income_adjusted_part_d_premium_surcharge`, against
`medicare_irmaa_magi_two_years_prior`, which adds tax-exempt interest to 2026
adjusted gross income. PolicyEngine-US holds the lines and amounts CMS has
published and doesn't project them, so the calculator applies the latest year
it holds, now 2026, and `medicare_surcharge.rates_year` names that year.

Required minimum distributions come from the IRS Uniform Lifetime Table in
`api/eggnest/rmd.py`. From age 73, a person owes their traditional balance on
December 31, 2025 divided by the table's factor for their age at the end of
2026. The calculator compares that minimum with their other traditional
withdrawals plus any traditional draw from their own account. On any shortfall
the person owes an excise tax of 25%, or 10% if they correct it in time
(26 USC 4974). The calculator reports that tax and leaves it out of taxes and
money to spend.

## What each result holds

- `at_chosen_draw` and `with_no_draw`: the full year at the chosen draw and at
  none.
- `federal_income_tax`, `state_income_tax`, `other_taxes` and `benefits`: the
  chosen draw's amounts, each with the engine version and the law behind it.
- `coverage_at_chosen_draw` and `coverage_with_no_draw`: whether PolicyEngine-US
  finds the household eligible for Medicaid and a Medicare Savings Program.
- `sweep`: the same at every draw the calculator evaluates, from nothing to the
  larger of $250,000 and 125% of the draw, within the account. A grid of at
  most 400 round steps covers that range, with $250 steps up to $40,000, where
  benefits for older households end. The page reads between rows in a straight
  line, so it answers as the slider moves, and asks the API again 300 ms after
  the figures stop changing.
- `bands`: the ranges of draw where each extra dollar splits the same way
  between what the household keeps, pays in tax and loses in benefits. A second
  run evaluates each place the grid finds the rate changing, so edges land on
  the dollar. It also cuts into 24 each grid interval where a tax or benefit
  jumps, which places the jump within 1/24 of that interval.
- `markers`: the draws where a benefit ends (`benefit_ends`), where Medicaid or
  a Medicare Savings Program ends (`coverage_ends`), where 2026 income crosses a
  Medicare line and the 2028 premium steps up (`medicare_surcharge_step`), and
  where a traditional draw covers its owner's required minimum
  (`required_minimum_reached`).
- `medicare_surcharge`: the lines for this filing status, the year they come
  from, the number of people on Medicare, and the yearly surcharge at the chosen
  draw and at none.
- `required_minimums`: each person's 2026 minimum, what they withdraw, any
  shortfall and the excise tax on it.
- `next_1000`: where the next $1,000 of draw goes, a smaller step near the end
  of the account, and null at a draw that empties it.

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
  equals the balance less the draw.
- Every marker lies inside the sweep.
- The same inputs give the same result.
- On piecewise-linear series whose kinks sit apart, the search for jumps never
  takes a change of rate for one. It finds any jump of $30 or more, and any two
  side by side of $60 or more.

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

`TestFrontendFixture` fails when the recorded runs drift from the engine.
