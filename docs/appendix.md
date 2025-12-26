# Technical Appendix

## A. Return Distribution Parameters

Historical return distributions are calibrated from Shiller's data (1928-2024) and Damodaran's annual updates.

### Stock Returns (S&P 500)

| Statistic | Value |
|-----------|-------|
| Arithmetic Mean | 11.7% |
| Geometric Mean | 9.8% |
| Standard Deviation | 19.8% |
| Simulation Mean | 7.0% |
| Simulation Std | 18.0% |

We use conservative estimates (7% mean) to account for potential lower future returns compared to historical averages.

### Bond Returns (10-Year Treasury)

| Statistic | Value |
|-----------|-------|
| Arithmetic Mean | 5.2% |
| Geometric Mean | 5.0% |
| Standard Deviation | 7.8% |
| Simulation Mean | 3.0% |
| Simulation Std | 6.0% |

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
| Taxable withdrawal | long_term_capital_gains | LTCG rates |
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

            # Calculate income
            spending_need = annual_spending
            other_income = social_security + pension + employment
            net_need = max(0, spending_need - other_income)

            # Calculate RMD if applicable
            if age >= 73:
                rmd = traditional_balance / rmd_factor(age)
                rmd = min(rmd, traditional_balance)

            # Determine withdrawals by strategy
            withdrawals = withdraw_by_strategy(
                net_need, rmd, strategy, balances)

            # Calculate taxes using PolicyEngine
            taxes = calculate_taxes(
                traditional=withdrawals.traditional + rmd,
                taxable=withdrawals.taxable,
                social_security=ss_income,
                year=calendar_year
            )

            # Total withdrawal including taxes
            gross_withdrawal = withdrawals.total + taxes

            # Apply returns
            returns = sample_returns(year)
            new_balance = (balance - gross_withdrawal) * (1 + returns)

            # Apply mortality
            if random() < mortality_prob(age, gender):
                mark_death(sim, year)
                break

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

At 10,000 simulations:
- Success rate standard error: ~0.5%
- Median final value standard error: ~2%

Results stabilize after approximately 5,000 simulations for most statistics.

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
    social_security_monthly: float = 0
    social_security_start_age: int = 67
    pension_annual: float = 0
    employment_income: float = 0

    # Tax
    state: str = "CA"
    filing_status: str = "single"

    # Strategy
    withdrawal_strategy: str = "taxable_first"
    stock_allocation: float = 0.6

    # Simulation
    n_simulations: int = 10000
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
```

### SimulationResult Model

```python
class SimulationResult(BaseModel):
    success_rate: float
    median_final_value: float
    mean_final_value: float
    total_withdrawn_median: float
    total_taxes_median: float
    median_depletion_age: int | None
    percentile_paths: PercentilePaths
    yearly_breakdown: list[YearBreakdown]
```
