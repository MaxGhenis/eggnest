"""Holdings-based portfolio management for simulation.

Tracks multiple holdings with different account types and funds,
handles per-fund returns, RMDs, and withdrawal ordering.
"""

from dataclasses import dataclass

import numpy as np

from .models import Holding, SimulationInput
from .returns import generate_correlated_fund_returns
from .rmd import get_rmd_factor
from .withdrawal_policies import (
    ROTH_ACCOUNTS,
    TAXABLE_ACCOUNTS,
    TRADITIONAL_ACCOUNTS,
    WithdrawalPolicy,
    resolve_withdrawal_policy,
)


@dataclass
class HoldingState:
    """State of a single holding during simulation."""

    account_type: str
    fund: str
    balance: np.ndarray  # (n_simulations,) current balance across all sims
    price_growth: np.ndarray  # (n_simulations, n_years) pre-generated returns
    div_yields: np.ndarray  # (n_simulations, n_years) pre-generated dividends
    cost_basis: np.ndarray | None = None  # Tax basis for taxable holdings only


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
        withdrawal_policy: WithdrawalPolicy | None = None,
        return_method: str = "bootstrap",
        fund_returns: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
        sampled_return_years: np.ndarray | None = None,
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
        self.withdrawal_policy = withdrawal_policy or resolve_withdrawal_policy(
            withdrawal_strategy
        )
        self.withdrawal_strategy = self.withdrawal_policy.name
        self._rng = rng or np.random.default_rng()

        unique_funds = list(dict.fromkeys(h.fund for h in holdings))
        if fund_returns is not None:
            self._fund_returns = fund_returns
            self.sampled_return_years = sampled_return_years
        else:
            # Generate fund returns once with shared historical sampling so the
            # selected funds preserve same-year cross-asset relationships.
            generated_returns = generate_correlated_fund_returns(
                funds=unique_funds,
                n_simulations=n_simulations,
                n_years=n_years,
                method=return_method,
                rng=self._rng,
                return_sampled_years=True,
            )
            self._fund_returns, self.sampled_return_years = generated_returns

        # Create holding states
        self.holdings: list[HoldingState] = []
        for h in holdings:
            price_growth, div_yields = self._fund_returns[h.fund]
            self.holdings.append(
                HoldingState(
                    account_type=h.account_type,
                    fund=h.fund,
                    balance=np.full(n_simulations, h.balance, dtype=float),
                    cost_basis=(
                        np.full(
                            n_simulations,
                            h.cost_basis if h.cost_basis is not None else 0.0,
                            dtype=float,
                        )
                        if h.account_type in TAXABLE_ACCOUNTS
                        else None
                    ),
                    price_growth=price_growth,
                    div_yields=div_yields,
                )
            )

        # Excess RMDs and similar cash flows are carried as taxable cash.
        self.cash_balance = np.zeros(n_simulations, dtype=float)

    def _get_or_create_roth_holding(self, source: HoldingState) -> HoldingState:
        """Return the Roth holding paired to a traditional source holding."""
        target_account_type = (
            "roth_401k"
            if source.account_type == "traditional_401k"
            else "roth_ira"
        )
        for holding in self.holdings:
            if (
                holding.account_type == target_account_type
                and holding.fund == source.fund
            ):
                return holding

        created = HoldingState(
            account_type=target_account_type,
            fund=source.fund,
            balance=np.zeros(self.n_simulations, dtype=float),
            price_growth=source.price_growth,
            div_yields=source.div_yields,
            cost_basis=None,
        )
        self.holdings.append(created)
        return created

    @property
    def total_balance(self) -> np.ndarray:
        """Total portfolio balance across all holdings (n_simulations,)."""
        return self.cash_balance + sum(h.balance for h in self.holdings)

    def get_balance_by_account_category(self, category: tuple[str, ...]) -> np.ndarray:
        """Get total balance for an account category (n_simulations,)."""
        balances = [h.balance for h in self.holdings if h.account_type in category]
        if any(account_type in TAXABLE_ACCOUNTS for account_type in category):
            balances.append(self.cash_balance)
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

    def apply_growth(self, year: int, mask: np.ndarray | None = None) -> None:
        """Apply one year of growth to all active holdings."""
        for h in self.holdings:
            growth = h.balance * h.price_growth[:, year]
            if mask is not None:
                growth = np.where(mask, growth, 0)
            h.balance = h.balance + growth

    def get_dividends(
        self, year: int, mask: np.ndarray | None = None
    ) -> dict[str, np.ndarray]:
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
            if mask is not None:
                divs = np.where(mask, divs, 0)
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
        factor = get_rmd_factor(age)
        if factor == 0.0:
            return np.zeros(self.n_simulations)
        trad_balance = self.traditional_balance
        return np.maximum(0.0, trad_balance * factor)

    def withdraw(
        self,
        amount: np.ndarray,
        age: int,
        include_rmd: bool = True,
        mask: np.ndarray | None = None,
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
            - 'taxable': Taxable withdrawal proceeds
            - 'taxable_cash': Tax-free withdrawal from taxable cash reserves
            - 'taxable_capital_gains': Realized capital gains from taxable sales
            - 'total': Total withdrawn
        """
        return self.withdrawal_policy.withdraw(
            self, amount, age, include_rmd=include_rmd, mask=mask
        )

    def withdraw_from_category(
        self,
        category: tuple[str, ...],
        amount: np.ndarray,
        mask: np.ndarray | None = None,
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

        if mask is not None:
            amount = np.where(mask, amount, 0)

        # Calculate total balance in category
        cat_total = sum(h.balance for h in cat_holdings)

        # Withdraw pro-rata from each holding
        for h in cat_holdings:
            # Avoid division by zero - use np.divide with where parameter
            proportion = np.divide(
                h.balance, cat_total, out=np.zeros_like(h.balance), where=cat_total > 0
            )
            withdrawal = amount * proportion
            h.balance = np.maximum(0, h.balance - withdrawal)

    def convert_traditional_to_roth(
        self,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Convert traditional assets to Roth assets while keeping them invested.

        Args:
            amount: Desired conversion amount across simulations.

        Returns:
            Actual amount converted for each simulation path.
        """
        if mask is not None:
            amount = np.where(mask, amount, 0)

        trad_holdings = [
            holding
            for holding in self.holdings
            if holding.account_type in TRADITIONAL_ACCOUNTS
        ]
        if not trad_holdings:
            return np.zeros(self.n_simulations)

        trad_total = sum(holding.balance for holding in trad_holdings)
        actual_amount = np.minimum(amount, trad_total)
        converted = np.zeros(self.n_simulations)

        for holding in trad_holdings:
            proportion = np.divide(
                holding.balance,
                trad_total,
                out=np.zeros_like(holding.balance),
                where=trad_total > 0,
            )
            moved = actual_amount * proportion
            holding.balance = np.maximum(0, holding.balance - moved)
            self._get_or_create_roth_holding(holding).balance += moved
            converted += moved

        return converted

    def withdraw_from_taxable(
        self,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Withdraw from taxable cash first, then from invested taxable holdings.

        Returns:
            Tuple of (cash_withdrawal, invested_taxable_withdrawal, realized_gains)
        """
        if mask is not None:
            amount = np.where(mask, amount, 0)

        cash_withdrawal = np.minimum(amount, self.cash_balance)
        self.cash_balance = np.maximum(0, self.cash_balance - cash_withdrawal)

        invested_withdrawal = np.maximum(0, amount - cash_withdrawal)
        realized_gains = np.zeros(self.n_simulations)
        if np.any(invested_withdrawal > 0):
            realized_gains = self._withdraw_from_taxable_holdings(
                invested_withdrawal, mask=mask
            )

        return cash_withdrawal, invested_withdrawal, realized_gains

    def _withdraw_from_taxable_holdings(
        self,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Withdraw from invested taxable holdings and return realized gains."""
        if mask is not None:
            amount = np.where(mask, amount, 0)

        cat_holdings = [h for h in self.holdings if h.account_type in TAXABLE_ACCOUNTS]
        if not cat_holdings:
            return np.zeros(self.n_simulations)

        cat_total = sum(h.balance for h in cat_holdings)
        realized_gains = np.zeros(self.n_simulations)

        for h in cat_holdings:
            proportion = np.divide(
                h.balance, cat_total, out=np.zeros_like(h.balance), where=cat_total > 0
            )
            withdrawal = amount * proportion
            basis_ratio = np.divide(
                h.cost_basis,
                h.balance,
                out=np.zeros_like(h.balance),
                where=h.balance > 0,
            )
            basis_ratio = np.clip(basis_ratio, 0, 1)
            basis_reduction = withdrawal * basis_ratio
            realized_gains += np.maximum(0, withdrawal - basis_reduction)
            h.balance = np.maximum(0, h.balance - withdrawal)
            h.cost_basis = np.maximum(0, h.cost_basis - basis_reduction)

        return realized_gains

    def deposit_to_taxable(
        self,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> None:
        """Deposit cash into the taxable cash reserve."""
        deposit = np.maximum(0, amount)
        if mask is not None:
            deposit = np.where(mask, deposit, 0)
        self.cash_balance = self.cash_balance + deposit


def create_holdings_tracker(
    params: SimulationInput,
    n_simulations: int,
    n_years: int,
    withdrawal_policy: WithdrawalPolicy | None = None,
    fund_returns: dict[str, tuple[np.ndarray, np.ndarray]] | None = None,
    sampled_return_years: np.ndarray | None = None,
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
        withdrawal_policy=withdrawal_policy,
        return_method=(
            params.return_model
            if params.return_model in ("bootstrap", "block_bootstrap")
            else "bootstrap"
        ),
        fund_returns=fund_returns,
        sampled_return_years=sampled_return_years,
        rng=rng,
    )
