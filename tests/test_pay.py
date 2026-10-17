from dataclasses import replace

from app import pay


def test_gross_with_overtime(cfg):
    # 80 reg * 30 = 2400; 5 OT * 45 = 225
    assert pay.gross_pay(80, 5, cfg) == 2625.00


def test_deduction_model_matches_hand_calc(cfg):
    gross = 2400.0
    health, k401 = 85.0, 120.0
    fica = (gross - health) * 0.0765
    tax = (gross - health - k401) * 0.16
    expected = round(gross - health - k401 - fica - tax, 2)
    assert pay.expected_net(gross, cfg) == expected


def test_roth_401k_does_not_reduce_taxable(cfg):
    roth = replace(cfg, k401_roth=True)
    assert pay.expected_net(2400, roth) < pay.expected_net(2400, cfg)


def test_ratio_mode(cfg):
    assert pay.expected_net(1000, replace(cfg, calc_mode="ratio")) == 780.0


def test_compare_tolerance():
    assert pay.compare(100.0, 104.99, 5)[0] is True
    ok, diff = pay.compare(100.0, 110.0, 5)
    assert ok is False and diff == -10.0
