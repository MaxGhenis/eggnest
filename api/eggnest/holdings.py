"""Holdings-based portfolio management for simulation.

Tracks multiple holdings with different account types and funds,
handles per-fund returns, RMDs, and withdrawal ordering.
"""

import numpy as np
from typing import Literal
from dataclasses import dataclass

from .models import Holding, SimulationInput
from .rmd import calculate_rmd
from .returns import generate_fund_returns


# Account type categories
TRADITIONAL_ACCOUNTS = ("traditional_401k", "traditional_ira")
ROTH_ACCOUNTS = ("roth_401k", "roth_ira")
TAXABLE_ACCOUNTS = ("taxable",)

# Withdrawal order for each strategy
WITHDRAWAL_ORDER = {
    "taxable_first": [TAXABLE_ACCOUNTS, TRADITIONAL_ACCOUNTS, ROTH_ACCOUNTS],
    "traditional_first": [TRADITIONAL_ACCOUNTS, TAXABLE_ACCOUNTS, ROTH_ACCOUNTS],
    "roth_first": [ROTH_ACCOUNTS, TAXABLE_ACCOUNTS, TRADITIONAL_ACCOUNTS],
}


@dataclass
class HoldingState:
    """State of a single holding during simulation."""
    account_type: str
    fund: str
    balance: np.ndarray  # (n_simulations,) current balance across all sims
    price_growth: np.ndarray  # (n_simulations, n_years) pre-generated returns
    div_yields: np.ndarray  # (n_simulations, n_years) pre-generated dividends


class HoldingsTracker:
    """
    Tracks portfolio holdings through a Monte Carlo simulation.

    Each holding has its own balance array and fund-specific returns.
    Handles RMDs for traditional accounts and withdrawal ordering.
    """

    def __init__(
        self,
        holdings: list[Holding],
        n_simulations: int,
        n_years: int,
        withdrawal_strategy: str = "taxable_first",
        return_method: str = "bootstrap",
        rng: np.random.Generator | None = None,
    ):
        """
        Initialize holdings tracker.

        Args:
            holdings: List of Holding objects from user input
            n_simulations: Number of Monte Carlo simulations
            n_years: Number of years to simulate
            withdrawal_strategy: Order to withdraw from accounts
            return_method: Bootstrap method for returns
            rng: Random number generator
        """
        self.n_simulations = n_simulations
        self.n_years = n_years
        self.withdrawal_strategy = withdrawal_strategy
        self._rng = rng or np.random.default_rng()

        # Generate returns for each unique fund (shared across holdings with same fund)
        self._fund_returns: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        unique_funds = set(h.fund for h in holdings)
        for fund in unique_funds:
            price_growth, div_yields = generate_fund_returns(
                fund=fund,
                n_simulations=n_simulations,
                n_years=n_years,
                method=return_method,
                rng=self._rng,
            )
            self._fund_returns[fund] = (price_growth, div_yields)

        # Create holding states
        self.holdings: list[HoldingState] = []
        for h in holdings:
            price_growth, div_yields = self._fund_returns[h.fund]
            self.holdings.append(HoldingState(
                account_type=h.account_type,
                fund=h.fund,
                balance=np.full(n_simulations, h.balance, dtype=float),
                price_growth=price_growth,
                div_yields=div_yields,
            ))

    @property
    def total_balance(self) -> np.ndarray:
        """Total portfolio balance across all holdings (n_simulations,)."""
        return sum(h.balance for h in self.holdings)

    def get_balance_by_account_category(self, category: tuple[str, ...]) -> np.ndarray:
        """Get total balance for an account category (n_simulations,)."""
        balances = [h.balance for h in self.holdings if h.account_type in category]
        if balances:
            return sum(balances)
        return np.zeros(self.n_simulations)

    @property
    def traditional_balance(self) -> np.ndarray:
        """Total traditional (tax-deferred) balance."""
        return self.get_balance_by_account_category(TRADITIONAL_ACCOUNTS)

    @property
    def roth_balance(self) -> np.ndarray:
        """Total Roth (tax-free) balance."""
        return self.get_balance_by_account_category(ROTH_ACCOUNTS)

    @property
    def taxable_balance(self) -> np.ndarray:
        """Total taxable balance."""
        return self.get_balance_by_account_category(TAXABLE_ACCOUNTS)

    def apply_growth(self, year: int) -> None:
        """Apply one year of growth to all holdings."""
        for h in self.holdings:
            growth = h.balance * h.price_growth[:, year]
            h.balance = h.balance + growth

    def get_dividends(self, year: int) -> dict[str, np.ndarray]:
        """
        Get dividend income by account category for a year.

        Returns:
            Dict with keys 'traditional', 'roth', 'taxable' containing
            dividend amounts (n_simulations,) for each category.
        """
        result = {
            "traditional": np.zeros(self.n_simulations),
            "roth": np.zeros(self.n_simulations),
            "taxable": np.zeros(self.n_simulations),
        }

        for h in self.holdings:
            divs = h.balance * h.div_yields[:, year]
            if h.account_type in TRADITIONAL_ACCOUNTS:
                result["traditional"] += divs
            elif h.account_type in ROTH_ACCOUNTS:
                result["roth"] += divs
            else:
                result["taxable"] += divs

        return result

    def calculate_rmd(self, age: int) -> np.ndarray:
        """
        Calculate Required Minimum Distribution for traditional accounts.

        Args:
            age: Current age of account holder

        Returns:
            RMD amount (n_simulations,)
        """
        trad_balance = self.traditional_balance
        # Vectorized RMD calculation
        rmd = np.zeros(self.n_simulations)
        if age >= 73:  # RMD_START_AGE
            for i in range(self.n_simulations):
                rmd[i] = calculate_rmd(trad_balance[i], age)
        return rmd

    def withdraw(
        self,
        amount: np.ndarray,
        age: int,
    ) -> dict[str, np.ndarray]:
        """
        Withdraw from portfolio following withdrawal strategy.

        Handles RMDs first, then additional withdrawals as needed.

        Args:
            amount: Total amount needed (n_simulations,)
            age: Current age (for RMD calculation)

        Returns:
            Dict with withdrawal amounts by tax category:
            - 'traditional_rmd': RMD amount (taxed as ordinary income)
            - 'traditional': Additional traditional withdrawal (ordinary income)
            - 'roth': Roth withdrawal (tax-free)
            - 'taxable': Taxable withdrawal (capital gains)
            - 'total': Total withdrawn
        """
        result = {
            "traditional_rmd": np.zeros(self.n_simulations),
            "traditional": np.zeros(self.n_simulations),
            "roth": np.zeros(self.n_simulations),
            "taxable": np.zeros(self.n_simulations),
            "total": np.zeros(self.n_simulations),
        }

        remaining = amount.copy()

        # Step 1: Handle RMDs first (must be taken from traditional)
        rmd = self.calculate_rmd(age)
        rmd_withdrawal = np.minimum(rmd, self.traditional_balance)
        self._withdraw_from_category(TRADITIONAL_ACCOUNTS, rmd_withdrawal)
        result["traditional_rmd"] = rmd_withdrawal
        remaining = np.maximum(0, remaining - rmd_withdrawal)

        # Step 2: If RMD exceeds spending need, we're done (excess stays in taxable)
        # Otherwise, continue with withdrawal strategy

        if self.withdrawal_strategy == "pro_rata":
            # Withdraw proportionally from all account types
            total_bal = self.total_balance
            for category, key in [
                (TAXABLE_ACCOUNTS, "taxable"),
                (TRADITIONAL_ACCOUNTS, "traditional"),
                (ROTH_ACCOUNTS, "roth"),
            ]:
                cat_balance = self.get_balance_by_account_category(category)
                # Proportion of remaining portfolio in this category
                proportion = np.where(total_bal > 0, cat_balance / total_bal, 0)
                withdrawal = np.minimum(remaining * proportion, cat_balance)
                self._withdraw_from_category(category, withdrawal)
                result[key] += withdrawal
                remaining = np.maximum(0, remaining - withdrawal)
        else:
            # Sequential withdrawal based on strategy
            order = WITHDRAWAL_ORDER.get(self.withdrawal_strategy, WITHDRAWAL_ORDER["taxable_first"])
            for category in order:
                if category == TAXABLE_ACCOUNTS:
                    key = "taxable"
                elif category == TRADITIONAL_ACCOUNTS:
                    key = "traditional"
                else:
                    key = "roth"

                cat_balance = self.get_balance_by_account_category(category)
                withdrawal = np.minimum(remaining, cat_balance)
                self._withdraw_from_category(category, withdrawal)
                result[key] += withdrawal
                remaining = np.maximum(0, remaining - withdrawal)

        result["total"] = amount - remaining  # What we actually withdrew
        return result

    def _withdraw_from_category(
        self,
        category: tuple[str, ...],
        amount: np.ndarray,
    ) -> None:
        """
        Withdraw amount from holdings in a category (pro-rata within category).

        Args:
            category: Account types to withdraw from
            amount: Amount to withdraw (n_simulations,)
        """
        # Get holdings in this category
        cat_holdings = [h for h in self.holdings if h.account_type in category]
        if not cat_holdings:
            return

        # Calculate total balance in category
        cat_total = sum(h.balance for h in cat_holdings)

        # Withdraw pro-rata from each holding
        for h in cat_holdings:
            # Avoid division by zero - use np.divide with where parameter
            proportion = np.divide(
                h.balance,
                cat_total,
                out=np.zeros_like(h.balance),
                where=cat_total > 0
            )
            withdrawal = amount * proportion
            h.balance = np.maximum(0, h.balance - withdrawal)


def create_holdings_tracker(
    params: SimulationInput,
    n_simulations: int,
    n_years: int,
    rng: np.random.Generator | None = None,
) -> HoldingsTracker | None:
    """
    Create a HoldingsTracker from SimulationInput if holdings are provided.

    Args:
        params: Simulation input parameters
        n_simulations: Number of simulations
        n_years: Number of years
        rng: Random number generator

    Returns:
        HoldingsTracker if holdings provided, None otherwise (use legacy mode)
    """
    if not params.holdings:
        return None

    return HoldingsTracker(
        holdings=params.holdings,
        n_simulations=n_simulations,
        n_years=n_years,
        withdrawal_strategy=params.withdrawal_strategy,
        return_method=params.return_model if params.return_model in ("bootstrap", "block_bootstrap") else "bootstrap",
        rng=rng,
    )
