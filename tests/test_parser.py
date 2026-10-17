from datetime import date

from app.parser import parse_regex

T = date(2026, 10, 14)


def p(cfg, s):
    return parse_regex(s, cfg, T)


def test_two_numbers(cfg):
    r = p(cfg, "38 3")
    assert (r["regular"], r["overtime"]) == (38, 3)


def test_single_total_splits_at_threshold(cfg):
    r = p(cfg, "43")
    assert (r["regular"], r["overtime"]) == (40, 3)
    r = p(cfg, "36.5")
    assert (r["regular"], r["overtime"]) == (36.5, 0)


def test_labels(cfg):
    r = p(cfg, "worked 40 regular and 5 ot")
    assert (r["regular"], r["overtime"]) == (40, 5)
    r = p(cfg, "ot: 4 reg: 38")
    assert (r["regular"], r["overtime"]) == (38, 4)
    r = p(cfg, "3 hours overtime")
    assert (r["regular"], r["overtime"]) == (0, 3)


def test_dates(cfg):
    r = p(cfg, "40 2 ending 10/03")
    assert r["week_ending"] == date(2026, 10, 3) and (r["regular"], r["overtime"]) == (40, 2)
    r = p(cfg, "40 0 for 2026-10-10")
    assert r["week_ending"] == date(2026, 10, 10) and r["regular"] == 40


def test_rejects_nonsense(cfg):
    assert p(cfg, "hello there") is None
    assert p(cfg, "500 20") is None
