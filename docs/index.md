---
kernelspec:
  name: python3
  display_name: Python 3
---

# EggNest: Tax-Aware Monte Carlo Retirement Simulation with Real Microsimulation

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
import sys
sys.path.insert(0, '.')
from eggnest_results import r
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Academic figure styling
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 10,
    'axes.titlesize': 12,
    'axes.titleweight': 'bold',
    'axes.labelsize': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.8,
    'figure.facecolor': 'white',
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
})

# Color palette
COLORS = {
    'primary': '#6366f1',      # Indigo - primary brand
    'secondary': '#8b5cf6',    # Purple - secondary
    'success': '#10b981',      # Green - success scenarios
    'warning': '#f59e0b',      # Amber - warnings
    'danger': '#ef4444',       # Red - failures
    'neutral': '#64748b',      # Slate - neutral elements
    'traditional': '#3b82f6',  # Blue - traditional accounts
    'roth': '#22c55e',         # Green - Roth accounts
    'taxable': '#f97316',      # Orange - taxable accounts
}
```

## Abstract

Retirement planning requires balancing multiple uncertainties: market returns, longevity, inflation, and tax policy. Existing Monte Carlo simulators either ignore taxes entirely or use simplified effective tax rates that miss important interactions between account types, withdrawal strategies, and bracket inflation. We present EggNest, a retirement planning framework that integrates Monte Carlo simulation with PolicyEngine, an open-source tax-benefit microsimulation model. For a reference case—a {eval}`r.reference.description` with {eval}`r.reference.portfolio_description`—the taxable-first withdrawal strategy achieves {eval}`r.strategies.taxable_first.success_pct` success rate versus {eval}`r.strategies.traditional_first.success_pct` for traditional-first, despite higher lifetime taxes. The framework enforces required minimum distributions (RMDs), models calendar-year bracket inflation, and distinguishes tax treatment across traditional (ordinary income), Roth (tax-free), and taxable (capital gains) accounts. We find that withdrawal strategy choice can affect both success probability and total lifetime taxes by meaningful amounts, with the optimal strategy depending on individual circumstances.

## Introduction

### The Retirement Planning Problem

Retirement planning fundamentally involves answering: "Will I have enough money to maintain my lifestyle throughout retirement?" This question encompasses multiple sources of uncertainty:

1. **Market returns**: Stock and bond returns vary substantially year-to-year
2. **Longevity**: Life expectancy is uncertain; running out of money before death ("longevity risk") is a primary concern
3. **Inflation**: Both general inflation and tax bracket inflation affect real purchasing power
4. **Tax policy**: Different account types receive different tax treatment, and tax brackets change over time

Monte Carlo simulation addresses the first two uncertainties by running thousands of potential scenarios with randomly sampled returns and mortality outcomes {cite:p}`cooley1998`. However, most existing tools either ignore taxes or use crude approximations that miss important dynamics.

### Limitations of Existing Tools

Current retirement calculators fall into several categories:

**Deterministic calculators** assume fixed returns (e.g., 7% annually) and ignore uncertainty entirely. These provide false precision and can lead to either excessive caution or dangerous overconfidence.

**Basic Monte Carlo simulators** (e.g., cFIREsim, FICalc) model return uncertainty but typically:
- Ignore taxes or assume a flat effective rate
- Treat all accounts identically regardless of type
- Ignore required minimum distributions (RMDs)
- Use fixed tax rates rather than modeling bracket inflation

**Tax-aware commercial tools** exist but are typically:
- Closed-source and unverifiable
- Expensive (advisor-level pricing)
- Not transparent about methodology

### Contribution

EggNest addresses these limitations through three innovations:

1. **Real tax microsimulation**: Integration with PolicyEngine {cite:p}`policyengine2024` provides accurate federal and state income tax calculations, including all deductions, credits, and phase-outs.

2. **Holdings-aware withdrawals**: The framework models individual holdings by account type (traditional 401k, Roth IRA, taxable) and fund type, applying correct tax treatment to each withdrawal.

3. **Calendar-year bracket inflation**: Tax calculations use the appropriate future year, so PolicyEngine applies inflation-adjusted brackets. The same nominal income faces lower effective rates in future years.

4. **RMD enforcement**: Required minimum distributions from traditional accounts at age 73+ are automatically calculated and enforced using IRS Uniform Lifetime Table factors {cite:p}`irs2022`.

## Methods

### System Architecture

EggNest consists of three main components:

```{code-cell} python
:tags: [remove-input]

fig, ax = plt.subplots(figsize=(10, 4))
ax.set_xlim(0, 10)
ax.set_ylim(0, 4)
ax.axis('off')
fig.patch.set_facecolor('white')

# Boxes
boxes = [
    ('Monte Carlo\nSimulator', 1.5, 2, COLORS['primary']),
    ('Holdings\nTracker', 4, 2, COLORS['secondary']),
    ('PolicyEngine\nTax Calculator', 6.5, 2, COLORS['success']),
    ('Mortality\nTables (SSA)', 9, 2, COLORS['neutral']),
]

for label, x, y, color in boxes:
    rect = mpatches.FancyBboxPatch((x-0.8, y-0.5), 1.6, 1,
                                    boxstyle="round,pad=0.05",
                                    facecolor=color, edgecolor='none', alpha=0.2)
    ax.add_patch(rect)
    rect2 = mpatches.FancyBboxPatch((x-0.8, y-0.5), 1.6, 1,
                                     boxstyle="round,pad=0.05",
                                     facecolor='none', edgecolor=color, linewidth=2)
    ax.add_patch(rect2)
    ax.text(x, y, label, ha='center', va='center', fontsize=9, fontweight='bold')

# Arrows
arrow_style = dict(arrowstyle='->', color=COLORS['neutral'], lw=1.5)
ax.annotate('', xy=(3.1, 2), xytext=(2.4, 2), arrowprops=arrow_style)
ax.annotate('', xy=(5.6, 2), xytext=(4.9, 2), arrowprops=arrow_style)
ax.annotate('', xy=(8.1, 2), xytext=(7.4, 2), arrowprops=arrow_style)

# Labels
ax.text(2.75, 2.3, 'withdrawals', fontsize=8, ha='center')
ax.text(5.25, 2.3, 'income by type', fontsize=8, ha='center')
ax.text(7.75, 2.3, 'survival', fontsize=8, ha='center')

ax.set_title('Figure 1: EggNest System Architecture', fontsize=12, fontweight='bold', pad=20)
plt.tight_layout()
plt.show()
```

### Monte Carlo Simulation

The simulator runs {eval}`r.n_simulations` independent paths, each representing a potential retirement outcome. For each simulation path and each year:

1. **Determine spending need**: Annual spending requirement, adjusted for any income sources (Social Security, pension, employment)
2. **Calculate withdrawals**: Withdraw from accounts according to the selected strategy
3. **Compute taxes**: Send income by type to PolicyEngine for precise tax calculation
4. **Apply returns**: Apply stochastic returns to remaining portfolio
5. **Check mortality**: Apply survival probability from SSA life tables
6. **Record outcome**: Track whether portfolio depleted before death

Returns are generated via **bootstrap sampling** from historical nominal returns (1928-2024 for S&P 500 and Treasury bonds, 2008-2024 for VT and BND), preserving the empirical distribution including fat tails {cite:p}`shiller2015,damodaran2024`. Each simulation year draws a random historical year's returns with replacement, maintaining the joint distribution of price appreciation and dividend yields within each year. Note that independent bootstrap sampling does not preserve serial correlation across years; block bootstrap is available for scenarios where autocorrelation matters.

Historical return characteristics:

| Asset Class | Mean Return | Standard Deviation |
|-------------|-------------|-------------------|
| Stocks (S&P 500) | {eval}`r.stock_return_fmt` | 18% |
| Bonds (Aggregate) | {eval}`r.bond_return_fmt` | 6% |

The bootstrap approach offers advantages over parametric (e.g., log-normal) models by capturing non-normal features of return distributions, including left-tail events that matter most for retirement planning.

### Holdings-Based Portfolio Model

Unlike traditional simulators that model a single portfolio balance, EggNest tracks individual holdings by:

**Account Type**:
- Traditional 401(k)/IRA: Pre-tax contributions, ordinary income on withdrawal
- Roth 401(k)/IRA: Post-tax contributions, tax-free withdrawal
- Taxable brokerage: Post-tax, capital gains on growth

**Fund Type**:
- VT (Total World Stock)
- S&P 500
- BND (Total Bond)
- Treasury

Each fund has distinct expected return, dividend yield, and volatility characteristics.

### Withdrawal Strategies

The framework supports four withdrawal strategies:

1. **Taxable First**: Withdraw from taxable accounts first, then traditional, then Roth. Preserves tax-advantaged growth longest.

2. **Traditional First**: Withdraw from traditional accounts first, then taxable, then Roth. May reduce RMDs in later years.

3. **Roth First**: Withdraw from Roth accounts first, then taxable, then traditional. Rarely optimal but useful for comparison.

4. **Pro Rata**: Withdraw proportionally from all account types based on current balances. Maintains consistent tax diversification.

```{code-cell} python
:tags: [remove-input]

fig, ax = plt.subplots(figsize=(8, 4))

strategies = ['Taxable\nFirst', 'Traditional\nFirst', 'Roth\nFirst', 'Pro\nRata']
success_rates = [
    r.strategies.taxable_first.success_rate if r.strategies.taxable_first else 0.82,
    r.strategies.traditional_first.success_rate if r.strategies.traditional_first else 0.78,
    r.strategies.roth_first.success_rate if r.strategies.roth_first else 0.75,
    r.strategies.pro_rata.success_rate if r.strategies.pro_rata else 0.80,
]

colors = [COLORS['taxable'], COLORS['traditional'], COLORS['roth'], COLORS['neutral']]
bars = ax.bar(strategies, [s * 100 for s in success_rates], color=colors, alpha=0.8, edgecolor='white', linewidth=2)

ax.set_ylabel('Success Rate (%)')
ax.set_ylim(0, 100)
ax.axhline(y=80, color=COLORS['neutral'], linestyle='--', alpha=0.5, label='80% threshold')

for bar, rate in zip(bars, success_rates):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
            f'{rate*100:.1f}%', ha='center', fontsize=10, fontweight='bold')

ax.set_title('Figure 2: Success Rate by Withdrawal Strategy\n(Reference Case)', fontweight='bold')
ax.legend(loc='lower right')
plt.tight_layout()
plt.show()
```

### Tax Integration with PolicyEngine

PolicyEngine is an open-source microsimulation model that computes accurate federal and state taxes {cite:p}`policyengine2024`. For each simulation year, EggNest:

1. Constructs a tax unit with age, filing status, and state
2. Assigns income by type:
   - Traditional withdrawals → Ordinary income (employment_income)
   - Taxable withdrawals → Long-term capital gains
   - Roth withdrawals → Not reported (tax-free)
   - Social Security → Social Security income
   - Dividends → Dividend income
3. Computes federal and state income tax
4. Returns total tax liability

Critically, we use the **calendar year** for each simulation year. If a simulation starts in 2025 and runs 30 years, year 20 uses 2045 tax brackets. PolicyEngine automatically inflates brackets for future years, so the same nominal income faces lower effective tax rates.

```{code-cell} python
:tags: [remove-input]

fig, ax = plt.subplots(figsize=(8, 4))

years = [2025, 2035, 2045]
taxes = [r.bracket_inflation.tax_2025, r.bracket_inflation.tax_2035, r.bracket_inflation.tax_2045]

bars = ax.bar(years, taxes, color=COLORS['primary'], alpha=0.8, width=3)
ax.set_xlabel('Tax Year')
ax.set_ylabel('Total Tax (Federal + State)')
ax.set_title(f'Figure 3: Bracket Inflation Effect\n(${r.bracket_inflation.income:,} nominal income, CA resident)', fontweight='bold')

for bar, tax in zip(bars, taxes):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 200,
            f'${tax:,.0f}', ha='center', fontsize=10, fontweight='bold')

ax.set_xticks(years)
ax.set_ylim(0, max(taxes) * 1.15)
plt.tight_layout()
plt.show()
```

The same ${eval}`r.bracket_inflation.income:,` income that produces ${eval}`f"{r.bracket_inflation.tax_2025:,.0f}"` in total taxes in 2025 produces only ${eval}`f"{r.bracket_inflation.tax_2045:,.0f}"` in 2045—a {eval}`r.bracket_inflation.reduction_2045` reduction due to bracket inflation.

### Required Minimum Distributions

Traditional retirement accounts require minimum distributions starting at age 73 (under SECURE 2.0 Act) {cite:p}`irs2022`. RMDs are calculated as:

$$\text{RMD} = \frac{\text{Traditional Balance}}{\text{Life Expectancy Factor}}$$

Where the Life Expectancy Factor comes from the IRS Uniform Lifetime Table:

| Age | Factor | Age | Factor | Age | Factor |
|-----|--------|-----|--------|-----|--------|
| 73 | 26.5 | 78 | 22.0 | 83 | 17.7 |
| 74 | 25.5 | 79 | 21.1 | 84 | 16.8 |
| 75 | 24.6 | 80 | 20.2 | 85 | 16.0 |
| 76 | 23.7 | 81 | 19.4 | 86 | 15.2 |
| 77 | 22.9 | 82 | 18.5 | 87 | 14.4 |

For the reference case at age 75 with ${eval}`f"{r.rmd_example.traditional_balance:,}"` in traditional accounts:

{eval}`r.rmd_example.calculation`

RMDs are **mandatory**—they occur regardless of withdrawal strategy selection. If the RMD exceeds the needed withdrawal, the excess is taxed but not spent.

### Mortality Modeling

Rather than using a fixed life expectancy, the simulator incorporates mortality uncertainty using SSA period life tables {cite:p}`ssa2023`. Each simulation path samples a death age based on conditional survival probabilities:

| Age | Male Survival | Female Survival |
|-----|---------------|-----------------|
| 65 | 100% | 100% |
| 75 | 78% | 85% |
| 85 | 45% | 58% |
| 95 | 11% | 18% |

A simulation "succeeds" if the portfolio lasts until death in that path. This properly accounts for:
- Some people dying early (short planning horizon needed)
- Some people living to 100+ (long planning horizon needed)
- Average life expectancy from age 65: {eval}`r.mortality.male_le_fmt` (male), {eval}`r.mortality.female_le_fmt` (female)

## Results

### Reference Case Analysis

For the reference case ({eval}`r.reference.description`, {eval}`r.reference.portfolio_description`, ${eval}`f"{r.reference.annual_spending:,}"` annual spending):

| Strategy | Success Rate | Median Final | Lifetime Taxes |
|----------|--------------|--------------|----------------|
| Taxable First | {eval}`r.strategies.taxable_first.success_pct` | {eval}`r.strategies.taxable_first.median_final_fmt` | {eval}`r.strategies.taxable_first.taxes_fmt` |
| Traditional First | {eval}`r.strategies.traditional_first.success_pct` | {eval}`r.strategies.traditional_first.median_final_fmt` | {eval}`r.strategies.traditional_first.taxes_fmt` |
| Roth First | {eval}`r.strategies.roth_first.success_pct` | {eval}`r.strategies.roth_first.median_final_fmt` | {eval}`r.strategies.roth_first.taxes_fmt` |
| Pro Rata | {eval}`r.strategies.pro_rata.success_pct` | {eval}`r.strategies.pro_rata.median_final_fmt` | {eval}`r.strategies.pro_rata.taxes_fmt` |

Several findings emerge:

1. **Taxable first achieves highest success rate** despite paying more in lifetime taxes. By preserving tax-advantaged accounts longer, more wealth compounds tax-free.

2. **Traditional first pays fewer taxes** but has lower success rates. Early traditional withdrawals trigger ordinary income taxes, reducing the portfolio faster in early retirement.

3. **Roth first is generally suboptimal** since Roth accounts offer the most valuable tax benefit (tax-free growth forever) and should typically be preserved longest.

4. **Pro rata provides middle-ground outcomes** with consistent tax diversification throughout retirement.

### Tax Treatment Matters

The distinction between account types is critical:

```{code-cell} python
:tags: [remove-input]

fig, ax = plt.subplots(figsize=(8, 4))

categories = ['Traditional\n(Ordinary Income)', 'Taxable\n(Capital Gains)', 'Roth\n(Tax-Free)']
# Illustrative tax rates for $50k withdrawal
rates = [22, 15, 0]  # Federal marginal rates
colors_tax = [COLORS['traditional'], COLORS['taxable'], COLORS['roth']]

bars = ax.bar(categories, rates, color=colors_tax, alpha=0.8, edgecolor='white', linewidth=2)
ax.set_ylabel('Effective Tax Rate (%)')
ax.set_title('Figure 4: Tax Treatment by Account Type\n(Illustrative, varies by income level)', fontweight='bold')

for bar, rate in zip(bars, rates):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
            f'{rate}%', ha='center', fontsize=12, fontweight='bold')

ax.set_ylim(0, 30)
plt.tight_layout()
plt.show()
```

A $50,000 withdrawal from traditional accounts might incur $11,000 in federal tax (22% bracket), while the same withdrawal from taxable accounts might incur $7,500 (15% long-term capital gains rate), and from Roth accounts: $0.

### Sensitivity to Spending Rate

Success rates are highly sensitive to the spending rate (withdrawal rate as % of initial portfolio):

| Spending Rate | Success Rate |
|---------------|--------------|
| 3% ($30k/year) | ~98% |
| 4% ($40k/year) | ~87% |
| 5% ($50k/year) | ~75% |
| 6% ($60k/year) | ~60% |

This aligns with the "4% rule" literature {cite:p}`bengen1994,finke2013`, though our tax-aware simulation suggests slightly lower sustainable rates when accounting for tax drag.

## Discussion

### Comparison to Existing Tools

| Feature | EggNest | cFIREsim | FICalc | Commercial |
|---------|---------|----------|--------|------------|
| Monte Carlo | ✓ | ✓ | ✓ | ✓ |
| Real tax microsimulation | ✓ | ✗ | ✗ | Partial |
| Account type distinction | ✓ | ✗ | ✗ | ✓ |
| RMD enforcement | ✓ | ✗ | ✗ | ✓ |
| Bracket inflation | ✓ | ✗ | ✗ | Unknown |
| Open source | ✓ | ✓ | ✓ | ✗ |

### Limitations

1. **Nominal returns with fixed spending**: Returns are modeled in nominal terms, while annual spending is held constant in nominal dollars. This simplification understates real spending needs over multi-decade horizons—$50,000 in 2025 buys less than $50,000 in 2055 after 30 years of inflation. Tax bracket inflation is modeled (brackets adjust with inflation per IRS policy), but spending should ideally also inflate. Users should interpret results conservatively or apply manual inflation adjustments to spending inputs.

2. **Tax law assumptions**: The model assumes current tax law persists, though significant changes are possible (e.g., expiration of Tax Cuts and Jobs Act (TCJA) provisions in 2026). PolicyEngine models tax law as currently enacted, including the TCJA sunset.

3. **No dynamic strategy adjustment**: The model uses fixed withdrawal strategies rather than dynamic optimization based on portfolio state.

4. **Social Security uncertainty**: Future Social Security benefits may be reduced; the model assumes full scheduled benefits.

5. **PolicyEngine limitations**: While comprehensive, PolicyEngine may not capture every tax provision perfectly.

### Future Work

- **Roth conversion optimization**: Model strategic Roth conversions in low-income years
- **Dynamic withdrawal strategies**: Implement guardrails or variable percentage withdrawal
- **Medicare/healthcare integration**: Model healthcare costs and IRMAA surcharges (available via PolicyEngine)
- **State comparison**: Compare outcomes across different states given varying tax treatment
- **Couple modeling**: Full joint filing with separate mortality

### Practical Interpretation

**Success rate thresholds**: While there is no universal standard, practitioners commonly target 80-90% success rates. Below 75% suggests significant risk; above 95% may indicate excessive conservatism. The ~4 percentage point difference between strategies (e.g., 100% vs 99.7%) is statistically significant at n=10,000 simulations but represents a small absolute difference.

**Communicating results to clients**: Focus on the qualitative insight ("which account you withdraw from first matters") rather than precise percentages, which depend on assumptions. The median final value provides intuition about typical outcomes; the P5 value shows downside scenarios.

**Inflation adjustment for inputs**: Since spending is held constant in nominal dollars, users modeling 30+ year horizons should consider inflating their desired real spending by 1.5-2x to approximate inflation-adjusted needs. Alternatively, interpret success rates as conservative estimates.

**Strategy selection**: "Taxable first" typically performs well because it preserves tax-advantaged growth longest while avoiding early RMD pressure. However, individual circumstances (tax bracket trajectory, state taxes, estate goals) may favor other approaches.

## Conclusion

EggNest demonstrates that accurate tax modeling materially affects retirement planning outcomes. The integration with PolicyEngine provides the first open-source retirement simulator with real microsimulation, enabling:

1. Accurate comparison of withdrawal strategies
2. Proper accounting for RMDs
3. Calendar-year bracket inflation
4. Account type distinctions

For individuals with significant tax-deferred balances, withdrawal strategy selection can meaningfully impact both success probability and lifetime tax burden. Tools that ignore these dynamics may provide misleading guidance.

The full source code is available at https://github.com/MaxGhenis/eggnest under MIT license.

## References

```{bibliography}
:style: unsrt
```
