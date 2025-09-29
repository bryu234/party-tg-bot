from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(slots=True)
class Transfer:
    from_user: int
    to_user: int
    amount_cents: int


def settle(balances: dict[int, int]) -> List[Transfer]:
    creditors: list[tuple[int, int]] = []
    debtors: list[tuple[int, int]] = []

    for user_id, balance in balances.items():
        if balance > 0:
            creditors.append((user_id, balance))
        elif balance < 0:
            debtors.append((user_id, -balance))

    creditors.sort(key=lambda x: x[1], reverse=True)
    debtors.sort(key=lambda x: x[1], reverse=True)

    transfers: list[Transfer] = []
    i, j = 0, 0

    while i < len(creditors) and j < len(debtors):
        cred_id, cred_amount = creditors[i]
        debt_id, debt_amount = debtors[j]

        transfer_amount = min(cred_amount, debt_amount)
        transfers.append(Transfer(from_user=debt_id, to_user=cred_id, amount_cents=transfer_amount))

        cred_amount -= transfer_amount
        debt_amount -= transfer_amount

        if cred_amount == 0:
            i += 1
        else:
            creditors[i] = (cred_id, cred_amount)

        if debt_amount == 0:
            j += 1
        else:
            debtors[j] = (debt_id, debt_amount)

    return transfers

