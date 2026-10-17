"""All configuration comes from environment variables (the .env file)."""
import os
from dataclasses import dataclass
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _s(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _f(name: str, default: float) -> float:
    raw = _s(name)
    return float(raw) if raw else default


def _i(name: str, default: int) -> int:
    raw = _s(name)
    return int(raw) if raw else default


def _b(name: str, default: bool) -> bool:
    raw = _s(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _t(name: str, default: str) -> time:
    raw = _s(name, default)
    h, m = raw.split(":")
    return time(int(h), int(m))


@dataclass(frozen=True)
class Config:
    # discord
    discord_token: str
    allowed_user_id: int
    alert_channel_id: int
    # actual
    actual_url: str
    actual_password: str
    actual_file: str
    actual_encryption_password: str
    payee_match: str
    actual_account: str
    deposit_window_days: int
    deposit_mode: str
    # schedule
    pay_anchor_date: date
    pay_lag_days: int
    tz: str
    # pay rules
    hourly_rate: float
    ot_multiplier: float
    weekly_ot_threshold: float
    extra_pay_per_period: float
    # net prediction
    calc_mode: str
    net_ratio: float
    health_pretax: float
    k401_pct: float
    k401_roth: bool
    other_posttax: float
    fica_rate: float
    effective_tax_rate: float
    # tolerances
    tolerance_dollars: float
    stub_gross_tolerance: float
    stub_net_tolerance: float
    # automation
    auto_check_enabled: bool
    auto_check_time: time
    deposit_delay_days: int
    deposit_give_up_days: int
    reminder_enabled: bool
    reminder_time: time
    reminder_offset_days: int
    default_week: str
    # stubs
    stub_dir: Path
    stub_gross_regex: str
    stub_net_regex: str
    stub_date_regex: str
    stub_date_format: str
    # llm
    use_llm: bool
    ollama_url: str
    ollama_model: str
    ollama_timeout: int
    # storage
    data_dir: Path

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


def load() -> Config:
    anchor = _s("PAY_ANCHOR_DATE")
    return Config(
        discord_token=_s("DISCORD_TOKEN"),
        allowed_user_id=_i("ALLOWED_USER_ID", 0),
        alert_channel_id=_i("ALERT_CHANNEL_ID", 0),
        actual_url=_s("ACTUAL_URL", "http://localhost:5006"),
        actual_password=_s("ACTUAL_PASSWORD"),
        actual_file=_s("ACTUAL_FILE"),
        actual_encryption_password=_s("ACTUAL_ENCRYPTION_PASSWORD"),
        payee_match=_s("PAYEE_MATCH"),
        actual_account=_s("ACTUAL_ACCOUNT"),
        deposit_window_days=_i("DEPOSIT_WINDOW_DAYS", 3),
        deposit_mode=_s("DEPOSIT_MODE", "sum").lower(),
        pay_anchor_date=date.fromisoformat(anchor) if anchor else date(2026, 1, 2),
        pay_lag_days=_i("PAY_LAG_DAYS", 6),
        tz=_s("TZ", "America/New_York"),
        hourly_rate=_f("HOURLY_RATE", 0.0),
        ot_multiplier=_f("OT_MULTIPLIER", 1.5),
        weekly_ot_threshold=_f("WEEKLY_OT_THRESHOLD", 40),
        extra_pay_per_period=_f("EXTRA_PAY_PER_PERIOD", 0),
        calc_mode=_s("CALC_MODE", "deduction").lower(),
        net_ratio=_f("NET_RATIO", 0.78),
        health_pretax=_f("HEALTH_PRETAX", 0),
        k401_pct=_f("K401_PCT", 0),
        k401_roth=_b("K401_ROTH", False),
        other_posttax=_f("OTHER_POSTTAX", 0),
        fica_rate=_f("FICA_RATE", 0.0765),
        effective_tax_rate=_f("EFFECTIVE_TAX_RATE", 0.16),
        tolerance_dollars=_f("TOLERANCE_DOLLARS", 5.0),
        stub_gross_tolerance=_f("STUB_GROSS_TOLERANCE", 1.0),
        stub_net_tolerance=_f("STUB_NET_TOLERANCE", 0.02),
        auto_check_enabled=_b("AUTO_CHECK_ENABLED", True),
        auto_check_time=_t("AUTO_CHECK_TIME", "09:00"),
        deposit_delay_days=_i("DEPOSIT_DELAY_DAYS", 1),
        deposit_give_up_days=_i("DEPOSIT_GIVE_UP_DAYS", 5),
        reminder_enabled=_b("REMINDER_ENABLED", True),
        reminder_time=_t("REMINDER_TIME", "18:00"),
        reminder_offset_days=_i("REMINDER_OFFSET_DAYS", 0),
        default_week=_s("DEFAULT_WEEK", "current").lower(),
        stub_dir=Path(_s("STUB_DIR", "/data/paystubs")),
        stub_gross_regex=_s("STUB_GROSS_REGEX", r"Gross Pay[^\d\-]*\$?\s*([\d,]+\.\d{2})"),
        stub_net_regex=_s("STUB_NET_REGEX", r"Net Pay[^\d\-]*\$?\s*([\d,]+\.\d{2})"),
        stub_date_regex=_s("STUB_DATE_REGEX", r"Pay Date:?\s*(\d{1,2}/\d{1,2}/\d{4})"),
        stub_date_format=_s("STUB_DATE_FORMAT", "%m/%d/%Y"),
        use_llm=_b("USE_LLM", False),
        ollama_url=_s("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=_s("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout=_i("OLLAMA_TIMEOUT", 60),
        data_dir=Path(_s("DATA_DIR", "/data")),
    )
