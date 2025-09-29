from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Iterable, Mapping, Sequence


@dataclass(slots=True)
class ExpenseItemShare:
    amount_cents: int
    consumers: Sequence[int]


@dataclass(slots=True)
class ExpenseShare:
    payer_id: int
    amount_cents: int
    is_shared: bool
    going_participants: Sequence[int]
    items: Sequence[ExpenseItemShare] | None = None


def split_amount(amount_cents: int, consumers: Sequence[int]) -> dict[int, int]:
    if amount_cents < 0:
        raise ValueError("amount_cents must be non-negative")
    if not consumers:
        raise ValueError("consumers must not be empty")

    n = len(consumers)
    decimal_amount = Decimal(amount_cents)
    base_share = (decimal_amount / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)

    shares = [int(base_share) for _ in consumers]
    total = sum(shares)
    remainder = amount_cents - total

    idx = 0
    step = 1 if remainder > 0 else -1
    while remainder != 0:
        shares[idx] += step
        remainder -= step
        idx = (idx + 1) % n

    return {consumer: share for consumer, share in zip(consumers, shares)}


def merge_shares(shares: Iterable[Mapping[int, int]]) -> dict[int, int]:
    result: dict[int, int] = {}
    for share in shares:
        for user_id, amount in share.items():
            result[user_id] = result.get(user_id, 0) + amount
    return result


def calculate_expense_split(expense: ExpenseShare) -> dict[int, int]:
    if expense.is_shared:
        return split_amount(expense.amount_cents, expense.going_participants)

    if not expense.items:
        raise ValueError("itemized expense must have items")

    per_item = []
    for item in expense.items:
        per_item.append(split_amount(item.amount_cents, item.consumers))

    return merge_shares(per_item)


def calculate_balances(expenses: Sequence[ExpenseShare]) -> dict[int, int]:
    balances: dict[int, int] = {}
    for expense in expenses:
        shares = calculate_expense_split(expense)
        for user_id, share in shares.items():
            balances[user_id] = balances.get(user_id, 0) - share
        balances[expense.payer_id] = balances.get(expense.payer_id, 0) + expense.amount_cents
    return balances

