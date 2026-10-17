"""Turns a chat message into hours. Plain regex first; optional local LLM (Ollama)."""
import json
import logging
import re
from datetime import date

import requests

from .config import Config

log = logging.getLogger(__name__)

NUM = r"(\d+(?:\.\d+)?)"
HRS = r"(?:h|hr|hrs|hour|hours)?"
OT_AFTER = re.compile(NUM + r"\s*" + HRS + r"\s*(?:of\s+)?(?:ot|overtime)\b")
OT_BEFORE = re.compile(r"\b(?:ot|overtime)\s*[:=]?\s*" + NUM)
REG_AFTER = re.compile(NUM + r"\s*" + HRS + r"\s*(?:of\s+)?(?:reg|regular)\b")
REG_BEFORE = re.compile(r"\b(?:reg|regular)\s*[:=]?\s*" + NUM)
ISO_DATE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
US_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")

MAX_WEEKLY_HOURS = 120


def _extract_date(text: str, today: date):
    """Finds an explicit week-ending date. Returns (date|None, text_without_date)."""
    m = ISO_DATE.search(text)
    if m:
        try:
            d = date(int(m[1]), int(m[2]), int(m[3]))
            return d, text.replace(m[0], " ", 1)
        except ValueError:
            return None, text
    m = US_DATE.search(text)
    if m:
        month, day = int(m[1]), int(m[2])
        year = today.year
        if m[3]:
            year = int(m[3])
            year += 2000 if year < 100 else 0
        try:
            d = date(year, month, day)
            return d, text.replace(m[0], " ", 1)
        except ValueError:
            return None, text
    return None, text


def _take(patterns, text):
    for p in patterns:
        m = p.search(text)
        if m:
            return float(m[1]), text.replace(m[0], " ", 1)
    return None, text


def parse_regex(text: str, c: Config, today: date):
    """Returns dict(regular, overtime, week_ending|None) or None."""
    t = text.lower().replace(",", " ")
    week_ending, t = _extract_date(t, today)
    ot, t = _take([OT_AFTER, OT_BEFORE], t)
    reg, t = _take([REG_AFTER, REG_BEFORE], t)
    rest = [float(x) for x in re.findall(NUM, t)]

    if reg is None and ot is None:
        if not rest:
            return None
        if len(rest) == 1:
            total = rest[0]
            thr = c.weekly_ot_threshold
            if thr > 0 and total > thr:
                reg, ot = thr, round(total - thr, 2)
            else:
                reg, ot = total, 0.0
        else:
            reg, ot = rest[0], rest[1]
    elif reg is None:
        reg = rest[0] if rest else 0.0
    elif ot is None:
        ot = rest[0] if rest else 0.0

    if reg < 0 or ot < 0 or reg + ot > MAX_WEEKLY_HOURS:
        return None
    return {"regular": reg, "overtime": ot, "week_ending": week_ending}


LLM_PROMPT = (
    "Extract work hours from the user's message. Reply with JSON only, exactly this shape: "
    '{"regular": number, "overtime": number, "week_ending": "YYYY-MM-DD" or null}. '
    "regular = non-overtime hours worked. overtime = overtime hours (0 if none mentioned). "
    "week_ending only if the user states a date. Today is %s. Do not do any other math. "
    'Message: "%s"'
)


def parse_llm(text: str, c: Config, today: date):
    """Ask Ollama to structure the message. Returns same shape as parse_regex, or None."""
    try:
        r = requests.post(
            f"{c.ollama_url}/api/chat",
            json={
                "model": c.ollama_model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
                "messages": [{"role": "user", "content": LLM_PROMPT % (today.isoformat(), text)}],
            },
            timeout=c.ollama_timeout,
        )
        r.raise_for_status()
        data = json.loads(r.json()["message"]["content"])
        reg, ot = float(data.get("regular") or 0), float(data.get("overtime") or 0)
        we = data.get("week_ending")
        week_ending = date.fromisoformat(we) if we else None
    except Exception as e:  # unreachable, bad JSON, bad date, ...
        log.warning("LLM parse failed (%s); falling back to regex", e)
        return None
    if reg < 0 or ot < 0 or reg + ot > MAX_WEEKLY_HOURS or (reg == 0 and ot == 0):
        return None
    return {"regular": reg, "overtime": ot, "week_ending": week_ending}


def parse_hours(text: str, c: Config, today: date):
    if c.use_llm:
        result = parse_llm(text, c, today)
        if result:
            return result
    return parse_regex(text, c, today)
