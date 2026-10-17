from dataclasses import replace
from datetime import date

import pytest
from reportlab.pdfgen import canvas

from app import actual_client, checker, paystub
from app.db import DB

PAYDAY = date(2026, 10, 23)


@pytest.fixture
def db(tmp_path):
    d = DB(tmp_path)
    d.save_week(date(2026, 10, 10), 40, 0)
    d.save_week(date(2026, 10, 17), 40, 5)
    return d


def deposit(amount):
    return [{"date": PAYDAY, "amount": amount, "payee": "ACME CORP", "account": "Checking"}]


def test_missing_hours(cfg, tmp_path):
    r = checker.run_check(cfg, DB(tmp_path), PAYDAY)
    assert r.status == "missing_hours"


def test_ok_and_mismatch(cfg, db, monkeypatch):
    from app import pay
    exp = pay.expected_for_period(80, 5, cfg).net
    monkeypatch.setattr(actual_client, "find_deposits", lambda c, p: deposit(exp + 1))
    assert checker.run_check(cfg, db, PAYDAY).status == "ok"
    monkeypatch.setattr(actual_client, "find_deposits", lambda c, p: deposit(exp - 150))
    r = checker.run_check(cfg, db, PAYDAY)
    assert r.status == "mismatch" and "under by $150.00" in r.message


def test_no_deposit(cfg, db, monkeypatch):
    monkeypatch.setattr(actual_client, "find_deposits", lambda c, p: [])
    assert checker.run_check(cfg, db, PAYDAY).status == "no_deposit"


def make_stub(path, gross, net, pay_date="10/23/2026"):
    c = canvas.Canvas(str(path))
    y = 800
    for line in [f"Pay Date: {pay_date}", f"Gross Pay ${gross:,.2f} $50,000.00", f"Net Pay ${net:,.2f} $38,000.00"]:
        c.drawString(50, y, line)
        y -= 20
    c.save()


def test_stub_reading_and_exact_check(cfg, db, tmp_path, monkeypatch):
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    make_stub(stubs / "stub.pdf", 2625.00, 2012.34)
    cfg = replace(cfg, stub_dir=stubs)
    info = paystub.parse_stub(stubs / "stub.pdf", cfg)
    assert info["gross"] == 2625.00 and info["net"] == 2012.34 and info["pay_date"] == PAYDAY

    monkeypatch.setattr(actual_client, "find_deposits", lambda c, p: deposit(2012.34))
    r = checker.run_check(cfg, db, PAYDAY)
    assert r.status == "ok" and "exact match" in r.message and "matches your hours" in r.message

    monkeypatch.setattr(actual_client, "find_deposits", lambda c, p: deposit(1900.00))
    assert checker.run_check(cfg, db, PAYDAY).status == "mismatch"


def test_split_deposits_sum(cfg):
    deps = [{"amount": 1500.0}, {"amount": 500.5}]
    assert actual_client.deposit_total(cfg, deps) == 2000.5
    assert actual_client.deposit_total(replace(cfg, deposit_mode="largest"), deps) == 1500.0
