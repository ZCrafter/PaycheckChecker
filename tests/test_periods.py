from datetime import date

from app import periods


def test_weeks_end_saturday(cfg):
    assert periods.week_end_weekday(cfg) == 5  # Saturday


def test_weeks_for_payday(cfg):
    # payday Fri 10/23 -> period ended Sat 10/17 -> weeks ending 10/10 and 10/17
    assert periods.weeks_for_payday(date(2026, 10, 23), cfg) == [date(2026, 10, 10), date(2026, 10, 17)]


def test_last_payday(cfg):
    assert periods.last_payday_on_or_before(date(2026, 10, 17), cfg) == date(2026, 10, 9)
    assert periods.last_payday_on_or_before(date(2026, 10, 23), cfg) == date(2026, 10, 23)
    assert periods.last_payday_on_or_before(date(2026, 9, 1), cfg) == date(2026, 8, 28)  # before anchor


def test_default_week_modes(cfg):
    from dataclasses import replace
    wed = date(2026, 10, 14)
    assert periods.default_week_ending(wed, cfg) == date(2026, 10, 17)
    assert periods.default_week_ending(wed, replace(cfg, default_week="previous")) == date(2026, 10, 10)
    sat = date(2026, 10, 17)
    assert periods.default_week_ending(sat, cfg) == sat
