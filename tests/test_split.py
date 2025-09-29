from partyshare.services.split import ExpenseItemShare, ExpenseShare, calculate_balances, split_amount


def test_split_amount_even():
    shares = split_amount(1000, [1, 2, 3, 4])
    assert shares == {1: 250, 2: 250, 3: 250, 4: 250}


def test_split_amount_remainder():
    shares = split_amount(1001, [1, 2, 3])
    assert sum(shares.values()) == 1001
    assert sorted(shares.values()) == [333, 334, 334]


def test_calculate_balances_mixed():
    expenses = [
        ExpenseShare(
            payer_id=1,
            amount_cents=3000,
            is_shared=True,
            going_participants=[1, 2, 3],
        ),
        ExpenseShare(
            payer_id=2,
            amount_cents=1500,
            is_shared=False,
            going_participants=[1, 2, 3],
            items=[
                ExpenseItemShare(amount_cents=700, consumers=[1, 2]),
                ExpenseItemShare(amount_cents=800, consumers=[2, 3]),
            ],
        ),
    ]

    balances = calculate_balances(expenses)

    assert sum(balances.values()) == 0
    assert balances[1] == 2000
    assert balances[2] == -500

