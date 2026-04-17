"""Withdrawal policy abstractions for portfolio drawdown."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .models import WithdrawalStrategy

AccountCategory = tuple[str, ...]
WithdrawalResult = dict[str, np.ndarray]

TRADITIONAL_ACCOUNTS: AccountCategory = ("traditional_401k", "traditional_ira")
ROTH_ACCOUNTS: AccountCategory = ("roth_401k", "roth_ira")
TAXABLE_ACCOUNTS: AccountCategory = ("taxable",)

WITHDRAWAL_RESULT_KEYS = (
    "traditional_rmd",
    "traditional",
    "roth",
    "taxable",
    "taxable_cash",
    "taxable_capital_gains",
    "total",
)


class WithdrawalExecutionContext(Protocol):
    """Operations a withdrawal policy needs from the portfolio tracker."""

    n_simulations: int

    @property
    def total_balance(self) -> np.ndarray: ...

    def calculate_rmd(self, age: int) -> np.ndarray: ...

    def get_balance_by_account_category(
        self, category: AccountCategory
    ) -> np.ndarray: ...

    def withdraw_from_category(
        self,
        category: AccountCategory,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> None: ...

    def withdraw_from_taxable(
        self,
        amount: np.ndarray,
        mask: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...


class WithdrawalPolicy(Protocol):
    """Interface for account drawdown policies."""

    name: WithdrawalStrategy

    def withdraw(
        self,
        context: WithdrawalExecutionContext,
        amount: np.ndarray,
        age: int,
        include_rmd: bool = True,
        mask: np.ndarray | None = None,
    ) -> WithdrawalResult: ...


def empty_withdrawal_result(n_sims: int) -> WithdrawalResult:
    """Create a zeroed withdrawal result."""
    return {key: np.zeros(n_sims) for key in WITHDRAWAL_RESULT_KEYS}


def _result_key_for_category(category: AccountCategory) -> str:
    if category == TAXABLE_ACCOUNTS:
        return "taxable"
    if category == TRADITIONAL_ACCOUNTS:
        return "traditional"
    return "roth"


def _finalize_withdrawal_result(result: WithdrawalResult) -> WithdrawalResult:
    result["total"] = (
        result["traditional_rmd"]
        + result["traditional"]
        + result["roth"]
        + result["taxable"]
        + result["taxable_cash"]
    )
    return result


def _initialize_withdrawal(
    context: WithdrawalExecutionContext,
    amount: np.ndarray,
    age: int,
    include_rmd: bool,
    mask: np.ndarray | None,
) -> tuple[WithdrawalResult, np.ndarray]:
    result = empty_withdrawal_result(context.n_simulations)
    remaining = amount.copy()
    if mask is not None:
        remaining = np.where(mask, remaining, 0)

    if not include_rmd:
        return result, remaining

    rmd = context.calculate_rmd(age)
    if mask is not None:
        rmd = np.where(mask, rmd, 0)
    rmd_withdrawal = np.minimum(
        rmd, context.get_balance_by_account_category(TRADITIONAL_ACCOUNTS)
    )
    context.withdraw_from_category(TRADITIONAL_ACCOUNTS, rmd_withdrawal, mask=mask)
    result["traditional_rmd"] = rmd_withdrawal
    remaining = np.maximum(0, remaining - rmd_withdrawal)
    return result, remaining


@dataclass(frozen=True)
class SequentialWithdrawalPolicy:
    """Withdraw from account categories in a fixed order."""

    name: WithdrawalStrategy
    order: tuple[AccountCategory, ...]

    def withdraw(
        self,
        context: WithdrawalExecutionContext,
        amount: np.ndarray,
        age: int,
        include_rmd: bool = True,
        mask: np.ndarray | None = None,
    ) -> WithdrawalResult:
        result, remaining = _initialize_withdrawal(
            context, amount, age, include_rmd, mask
        )

        for category in self.order:
            key = _result_key_for_category(category)
            cat_balance = context.get_balance_by_account_category(category)
            withdrawal = np.minimum(remaining, cat_balance)
            if category == TAXABLE_ACCOUNTS:
                cash_withdrawal, invested_withdrawal, realized_gains = (
                    context.withdraw_from_taxable(withdrawal, mask=mask)
                )
                result["taxable_cash"] += cash_withdrawal
                result[key] += invested_withdrawal
                result["taxable_capital_gains"] += realized_gains
                actual_withdrawal = cash_withdrawal + invested_withdrawal
            else:
                context.withdraw_from_category(category, withdrawal, mask=mask)
                result[key] += withdrawal
                actual_withdrawal = withdrawal
            remaining = np.maximum(0, remaining - actual_withdrawal)

        return _finalize_withdrawal_result(result)


@dataclass(frozen=True)
class ProRataWithdrawalPolicy:
    """Withdraw proportionally from each account category."""

    name: WithdrawalStrategy = "pro_rata"
    categories: tuple[AccountCategory, ...] = (
        TAXABLE_ACCOUNTS,
        TRADITIONAL_ACCOUNTS,
        ROTH_ACCOUNTS,
    )

    def withdraw(
        self,
        context: WithdrawalExecutionContext,
        amount: np.ndarray,
        age: int,
        include_rmd: bool = True,
        mask: np.ndarray | None = None,
    ) -> WithdrawalResult:
        result, remaining = _initialize_withdrawal(
            context, amount, age, include_rmd, mask
        )

        total_balance = context.total_balance
        amount_to_distribute = remaining.copy()

        for category in self.categories:
            key = _result_key_for_category(category)
            cat_balance = context.get_balance_by_account_category(category)
            proportion = np.where(total_balance > 0, cat_balance / total_balance, 0)
            withdrawal = np.minimum(amount_to_distribute * proportion, cat_balance)
            if category == TAXABLE_ACCOUNTS:
                cash_withdrawal, invested_withdrawal, realized_gains = (
                    context.withdraw_from_taxable(withdrawal, mask=mask)
                )
                result["taxable_cash"] += cash_withdrawal
                result[key] += invested_withdrawal
                result["taxable_capital_gains"] += realized_gains
            else:
                context.withdraw_from_category(category, withdrawal, mask=mask)
                result[key] += withdrawal

        return _finalize_withdrawal_result(result)


WITHDRAWAL_POLICIES: dict[WithdrawalStrategy, WithdrawalPolicy] = {
    "taxable_first": SequentialWithdrawalPolicy(
        name="taxable_first",
        order=(TAXABLE_ACCOUNTS, TRADITIONAL_ACCOUNTS, ROTH_ACCOUNTS),
    ),
    "traditional_first": SequentialWithdrawalPolicy(
        name="traditional_first",
        order=(TRADITIONAL_ACCOUNTS, TAXABLE_ACCOUNTS, ROTH_ACCOUNTS),
    ),
    "roth_first": SequentialWithdrawalPolicy(
        name="roth_first",
        order=(ROTH_ACCOUNTS, TAXABLE_ACCOUNTS, TRADITIONAL_ACCOUNTS),
    ),
    "pro_rata": ProRataWithdrawalPolicy(),
}


def resolve_withdrawal_policy(
    strategy: WithdrawalStrategy | str,
) -> WithdrawalPolicy:
    """Resolve a strategy name to a concrete withdrawal policy."""
    return WITHDRAWAL_POLICIES.get(strategy, WITHDRAWAL_POLICIES["taxable_first"])
