# Technical Appendix

## A. Return Engines and Data

EggNest stores **nominal annual price returns** and **nominal annual dividend yields** separately. This lets the simulator:

- treat dividends as distributed income rather than implicit reinvestment
- pass taxable withdrawals and dividend income to PolicyEngine in separate buckets
- track realized gains separately from taxable sale proceeds when cost basis is available
- support both simple total-capital mode and holdings-by-fund mode

### Supported return models

| Model | Description | Default |
|-------|-------------|---------|
| `bootstrap` | Sample individual historical years with replacement | Yes |
| `block_bootstrap` | Sample contiguous blocks of historical years | No |
| `historical` | Replay a contiguous historical sequence from a random start year | No |
| `normal` | Draw from user-supplied mean/volatility assumptions | No |

### Data windows

| Series | Approximate range |
|--------|-------------------|
| S&P 500 | 1928-2024 |
| 10-Year Treasury | 1928-2024 |
| VT | 2008-2024 |
| BND | 2007-2024 |

The default baseline uses **S&P 500 + 10-Year Treasury** because that pair provides the longest continuous history in the dataset. VT and BND remain available, but selecting either shortens the overlapping window to the ETF era.

Inflation is modeled separately from returns using annual US CPI changes (December-to-December). The live default is `inflation_model="historical"`. When the return engine uses historical/bootstrap/block sampling, EggNest applies inflation from the same sampled historical years so market and inflation shocks stay paired within a path.

In holdings mode, fund-level return generation currently supports `bootstrap` and `block_bootstrap`. Other requested methods fall back to bootstrap so that each holding can still draw from its own fund history.

When multiple funds appear in the same holdings-based simulation, EggNest first aligns them to their common overlapping year range and then applies a shared sampled year/block index across all selected funds. This preserves same-period stock/bond co-movement within the available overlap window instead of sampling each fund independently.

## B. Complete RMD Table

IRS Uniform Lifetime Table (2024):

| Age | Factor | Age | Factor | Age | Factor |
|-----|--------|-----|--------|-----|--------|
| 72 | 27.4 | 82 | 18.5 | 92 | 10.2 |
| 73 | 26.5 | 83 | 17.7 | 93 | 9.6 |
| 74 | 25.5 | 84 | 16.8 | 94 | 9.1 |
| 75 | 24.6 | 85 | 16.0 | 95 | 8.6 |
| 76 | 23.7 | 86 | 15.2 | 96 | 8.1 |
| 77 | 22.9 | 87 | 14.4 | 97 | 7.6 |
| 78 | 22.0 | 88 | 13.7 | 98 | 7.1 |
| 79 | 21.1 | 89 | 12.9 | 99 | 6.7 |
| 80 | 20.2 | 90 | 12.2 | 100 | 6.3 |
| 81 | 19.4 | 91 | 11.5 | 101+ | 5.9 |

## C. SSA Life Table Extract

Period life table for 2021 (most recent SSA publication):

### Male

| Age | q(x) | l(x) | e(x) |
|-----|------|------|------|
| 65 | 0.0148 | 79,537 | 18.2 |
| 70 | 0.0222 | 73,182 | 14.6 |
| 75 | 0.0345 | 64,721 | 11.3 |
| 80 | 0.0548 | 53,736 | 8.4 |
| 85 | 0.0886 | 40,276 | 6.0 |
| 90 | 0.1419 | 25,656 | 4.1 |
| 95 | 0.2088 | 12,814 | 2.9 |

### Female

| Age | q(x) | l(x) | e(x) |
|-----|------|------|------|
| 65 | 0.0100 | 86,272 | 20.8 |
| 70 | 0.0151 | 82,013 | 16.7 |
| 75 | 0.0238 | 76,170 | 12.9 |
| 80 | 0.0390 | 67,897 | 9.5 |
| 85 | 0.0655 | 56,409 | 6.6 |
| 90 | 0.1097 | 41,225 | 4.4 |
| 95 | 0.1721 | 24,362 | 2.9 |

Where:
- q(x) = probability of dying within one year at age x
- l(x) = number surviving to age x out of 100,000 births
- e(x) = remaining life expectancy at age x

## D. Tax Integration Details

### PolicyEngine Integration

EggNest uses PolicyEngine-US via `Microsimulation` with a custom `Dataset` class:

```python
class MonteCarloDataset(Dataset):
    """Custom dataset for batch tax calculations."""

    def generate(self) -> None:
        data = {
            "age": {self.year: self.ages},
            "long_term_capital_gains": {self.year: self.capital_gains},
            "social_security": {self.year: self.social_security},
            "employment_income": {self.year: self.employment_income},
            "filing_status": {self.year: filing_status_values},
            "household_state_fips": {self.year: state_codes},
            # ... entity relationships
        }
        self.save_dataset(data)
```

### Income Classification

| Source | PolicyEngine Variable | Tax Treatment |
|--------|----------------------|---------------|
| Traditional withdrawal | employment_income | Ordinary rates |
| Realized gains from taxable sales | long_term_capital_gains | LTCG rates |
| Taxable cash reserve withdrawal | (not reported) | Already after-tax cash |
| Roth withdrawal | (not reported) | Tax-free |
| Social Security | social_security | Partially taxable |
| Dividends | dividend_income | Qualified rates |

### Supported States

All 50 US states plus DC are supported via PolicyEngine's state tax modules. States without income tax (FL, TX, WA, NV, etc.) correctly return zero state tax.

## E. Simulation Algorithm

Pseudocode for the core simulation loop:

```
function simulate(params, n_simulations):
    paths = zeros(n_simulations, n_years + 1)
    paths[:, 0] = initial_capital

    for sim in range(n_simulations):
        for year in range(n_years):
            age = current_age + year
            calendar_year = START_YEAR + year

            if household_is_dead_or_depleted:
                paths[sim, year + 1] = paths[sim, year]
                continue

            inflation_factor = cumulative_inflation(sim, year)
            inflation_rate = sampled_inflation(sim, year)

            # Calculate income and nominal spending target
            spending_need = (
                annual_spending * inflation_factor
                if spending_mode == "real"
                else annual_spending
            )
            social_security = (
                social_security_base * inflation_factor
                if social_security_inflation_adjusted
                else social_security_base
            )
            pension = pension_base * (1 + pension_cola_rate) ** year
            annuity = annuity_base * (1 + annuity_cola_rate) ** year
            guaranteed_income = social_security + pension + employment + annuity
            dividends = portfolio_dividends(year)
            cash_before_withdrawals = guaranteed_income + dividends
            pre_tax_gap = max(0, spending_need - cash_before_withdrawals)

            # Calculate RMD if applicable
            if age >= 73:
                rmd = traditional_balance / rmd_factor(age)
                rmd = min(rmd, traditional_balance)

            # Determine withdrawals by strategy, including mandatory RMDs
            withdrawals = withdraw_by_strategy(pre_tax_gap, rmd, strategy, balances)

            # Gross up iteratively for taxes
            while True:
                taxes = calculate_taxes(
                    traditional=withdrawals.traditional + withdrawals.traditional_rmd,
                    taxable_gains=withdrawals.taxable_capital_gains,
                    taxable_cash=withdrawals.taxable_cash,
                    social_security=ss_income,
                    dividends=dividends,
                    year=calendar_year,
                )
                portfolio_cash_needed = max(
                    0, spending_need + taxes - cash_before_withdrawals
                )
                shortfall = portfolio_cash_needed - withdrawals.total
                if shortfall <= tolerance:
                    break
                withdrawals += withdraw_by_strategy(shortfall, 0, strategy, balances)

            # Re-deposit any excess RMD cash into taxable cash
            surplus_cash = max(0, withdrawals.total - portfolio_cash_needed)
            taxable_cash_balance += surplus_cash

            # Apply returns
            returns = sample_returns(year)
            new_balance = grow_remaining_portfolio(balance, returns)

            paths[sim, year + 1] = new_balance

    return compute_statistics(paths)
```

## F. Validation

### Tax Calculation Validation

We validated PolicyEngine tax calculations against:
1. IRS Tax Tables (exact match for simple cases)
2. TurboTax calculations (within rounding error)
3. Manual calculations for edge cases

### Withdrawal Logic Validation

Unit tests verify:
- RMD calculations match IRS table exactly
- Withdrawal order follows specified strategy
- Pro-rata proportions are correct
- Cascading to next account when depleted

### Monte Carlo Convergence

The production API defaults to 10,000 simulations per run. At that scale:
- Success rate standard error: ~0.5%
- Median final value standard error: ~2%

Results stabilize after approximately 5,000 simulations for most statistics.

The documentation artifact (`docs/eggnest_results.json`) intentionally uses a smaller seeded run so that results can be regenerated in a reasonable amount of time from the API environment. The artifact stores both `n_simulations` and `random_seed`, and docs imports read the JSON artifact rather than silently recomputing it.

## G. API Reference

### SimulationInput Model

```python
class SimulationInput(BaseModel):
    # Portfolio
    initial_capital: float = None  # Legacy mode
    holdings: list[Holding] = None  # Holdings mode

    # Demographics
    current_age: int
    retirement_age: int
    max_age: int = 95
    gender: Literal["male", "female"]

    # Income
    annual_spending: float
    spending_mode: Literal["real", "nominal"] = "real"
    inflation_model: Literal["historical", "constant"] = "historical"
    inflation_rate: float = 0.025
    social_security_monthly: float = 0
    social_security_start_age: int = 67
    social_security_inflation_adjusted: bool = True
    pension_annual: float = 0
    pension_cola_rate: float = 0
    employment_income: float = 0
    annuity_cola_rate: float = 0

    # Tax
    state: str = "CA"
    filing_status: str = "single"

    # Strategy
    withdrawal_strategy: str = "taxable_first"
    stock_allocation: float = 0.6
    stock_index: str = "sp500"
    bond_index: str = "treasury"
    return_model: str = "bootstrap"

    # Simulation
    n_simulations: int = 10000
    random_seed: int | None = None
```

### Holding Model

```python
class Holding(BaseModel):
    account_type: Literal[
        "traditional_401k", "traditional_ira",
        "roth_401k", "roth_ira", "taxable"
    ]
    fund: Literal["vt", "sp500", "bnd", "treasury"]
    balance: float
    cost_basis: float | None = None  # Optional; taxable holdings only
```

### SimulationResult Model

```python
class SimulationResult(BaseModel):
    success_rate: float
    median_final_value: float
    median_final_value_real: float
    mean_final_value: float
    mean_final_value_real: float
    percentiles_real: dict[str, float]
    total_withdrawn_median: float
    total_taxes_median: float
    median_depletion_age: int | None
    percentile_paths: PercentilePaths
    year_breakdown: list[YearBreakdown]
```
