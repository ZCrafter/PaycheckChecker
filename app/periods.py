"""Pay period / week arithmetic, all derived from one known payday."""
from datetime import date, timedelta

from .config import Config


def week_end_weekday(c: Config) -> int:
    """Weekday (Mon=0) that your work weeks end on."""
    return (c.pay_anchor_date - timedelta(days=c.pay_lag_days)).weekday()


def next_week_ending(d: date, c: Config) -> date:
    """Week-ending date on or after d."""
    return d + timedelta(days=(week_end_weekday(c) - d.weekday()) % 7)


def prev_week_ending(d: date, c: Config) -> date:
    """Week-ending date on or before d."""
    return d - timedelta(days=(d.weekday() - week_end_weekday(c)) % 7)


def default_week_ending(today: date, c: Config) -> date:
    if c.default_week == "previous":
        return prev_week_ending(today, c)
    return next_week_ending(today, c)


def last_payday_on_or_before(d: date, c: Config) -> date:
    n = (d - c.pay_anchor_date).days // 14  # floor division works for negatives
    return c.pay_anchor_date + timedelta(days=14 * n)


def next_payday_after(d: date, c: Config) -> date:
    return last_payday_on_or_before(d, c) + timedelta(days=14)


def weeks_for_payday(payday: date, c: Config) -> list[date]:
    """The two week-ending dates that make up the paycheck paid on `payday`."""
    end = payday - timedelta(days=c.pay_lag_days)
    return [end - timedelta(days=7), end]


def is_payday(d: date, c: Config) -> bool:
    return (d - c.pay_anchor_date).days % 14 == 0
