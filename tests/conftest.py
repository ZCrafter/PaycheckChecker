import pytest

from app import config

ENV = {
    "HOURLY_RATE": "30", "OT_MULTIPLIER": "1.5", "WEEKLY_OT_THRESHOLD": "40",
    "PAY_ANCHOR_DATE": "2026-10-09",  # a Friday
    "PAY_LAG_DAYS": "6",              # period ends the Saturday before => weeks end Saturday
    "CALC_MODE": "deduction", "HEALTH_PRETAX": "85", "K401_PCT": "0.05",
    "FICA_RATE": "0.0765", "EFFECTIVE_TAX_RATE": "0.16", "NET_RATIO": "0.78",
    "DEFAULT_WEEK": "current",
}


@pytest.fixture
def cfg(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    return config.load()
