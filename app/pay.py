"""Pay math. Plain Python on purpose: no AI is involved in any calculation."""
from dataclasses import dataclass

from .config import Config


@dataclass
class Expected:
    gross: float
    net: float
    mode: str


def gross_pay(regular: float, overtime: float, c: Config) -> float:
    g = regular * c.hourly_rate + overtime * c.hourly_rate * c.ot_multiplier
    return round(g + c.extra_pay_per_period, 2)


def expected_net(gross: float, c: Config) -> float:
    if c.calc_mode == "ratio":
        return round(gross * c.net_ratio, 2)

    health = c.health_pretax
    k401 = gross * c.k401_pct
    # Section 125 health reduces FICA wages and income-taxable wages.
    fica = max(gross - health, 0) * c.fica_rate
    taxable = gross - health - (0 if c.k401_roth else k401)
    tax = max(taxable, 0) * c.effective_tax_rate
    net = gross - health - k401 - fica - tax - c.other_posttax
    return round(net, 2)


def expected_for_period(regular: float, overtime: float, c: Config) -> Expected:
    g = gross_pay(regular, overtime, c)
    return Expected(gross=g, net=expected_net(g, c), mode=c.calc_mode)


def compare(actual: float, expected: float, tolerance: float):
    """Returns (ok, difference) where difference = actual - expected."""
    diff = round(actual - expected, 2)
    return abs(diff) <= tolerance + 1e-9, diff
