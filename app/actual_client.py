"""Reads paycheck deposits from your Actual Budget server (via the actualpy library)."""
import logging
from datetime import date, timedelta

from actual import Actual
from actual.queries import get_transactions

from .config import Config, load

log = logging.getLogger(__name__)


def _open(c: Config):
    kwargs = dict(base_url=c.actual_url, password=c.actual_password, file=c.actual_file)
    if c.actual_encryption_password:
        kwargs["encryption_password"] = c.actual_encryption_password
    return Actual(**kwargs)


def find_deposits(c: Config, payday: date):
    """All deposits matching PAYEE_MATCH within DEPOSIT_WINDOW_DAYS of payday.
    Returns a list of dicts: date, amount, payee, account."""
    start = payday - timedelta(days=c.deposit_window_days)
    end = payday + timedelta(days=c.deposit_window_days)
    needle = c.payee_match.lower()
    found = []
    with _open(c) as actual:
        # end_date is exclusive in actualpy, so pad it and filter ourselves
        txns = get_transactions(actual.session, start_date=start, end_date=end + timedelta(days=1))
        for t in txns:
            amount = t.get_amount()
            if amount <= 0:
                continue
            d = t.get_date()
            if not (start <= d <= end):
                continue
            payee = t.payee.name if t.payee else ""
            if needle not in payee.lower():
                continue
            account = t.account.name if t.account else ""
            if c.actual_account and c.actual_account.lower() != account.lower():
                continue
            found.append({"date": d, "amount": float(amount), "payee": payee, "account": account})
    return found


def deposit_total(c: Config, deposits):
    if not deposits:
        return None
    if c.deposit_mode == "largest":
        return max(d["amount"] for d in deposits)
    return round(sum(d["amount"] for d in deposits), 2)


if __name__ == "__main__":
    # Connection test:  python -m app.actual_client
    cfg = load()
    with _open(cfg) as actual:
        print("Connected. Most recent transactions:")
        for t in get_transactions(actual.session)[:10]:
            print(t.get_date(), t.payee.name if t.payee else None, t.get_amount())
    today = date.today()
    print(f"\nDeposits matching '{cfg.payee_match}' within {cfg.deposit_window_days} days of today:")
    for d in find_deposits(cfg, today):
        print(d)
