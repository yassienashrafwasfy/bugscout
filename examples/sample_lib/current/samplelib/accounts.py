def withdraw(balance: float, amount: float) -> dict:
    """Withdraw `amount` from `balance`. Invariant: the resulting balance is never negative."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    new_balance = balance - amount  # PLANTED BUG: no overdraft check -> balance can go negative
    return {"balance": new_balance, "withdrawn": amount}


def deposit(balance: float, amount: float) -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")
    return {"balance": balance + amount, "deposited": amount}
