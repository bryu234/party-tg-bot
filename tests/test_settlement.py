from partyshare.services.settlement import Transfer, settle


def test_settle_balances():
    balances = {
        1: 500,
        2: -300,
        3: -200,
    }

    transfers = settle(balances)

    assert transfers == [
        Transfer(from_user=2, to_user=1, amount_cents=300),
        Transfer(from_user=3, to_user=1, amount_cents=200),
    ]

    total = sum(t.amount_cents for t in transfers)
    assert total == 500

    after = balances.copy()
    for t in transfers:
        after[t.to_user] -= t.amount_cents
        after[t.from_user] += t.amount_cents

    assert all(value == 0 for value in after.values())

