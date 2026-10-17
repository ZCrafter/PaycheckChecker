"""Discord front-end. Run with:  python -m app.bot"""
import asyncio
import logging
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import discord
from discord.ext import tasks

from . import paystub
from .checker import money, run_check
from .config import load
from .db import DB
from .parser import _extract_date, parse_hours
from .periods import (
    default_week_ending,
    is_payday,
    last_payday_on_or_before,
    next_payday_after,
    next_week_ending,
    week_end_weekday,
    weeks_for_payday,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("paycheck-bot")

cfg = load()
db = DB(cfg.data_dir)

HELP = """**Paycheck checker**
Send your weekly hours:
• `38 3` → 38 regular + 3 overtime
• `43` → total hours; anything over {thr:g} is counted as overtime
• `38 reg 3 ot ending 10/03` → for a specific week
Other commands:
• `check` → check the latest paycheck (`check 10/09` for a specific payday)
• `status` → upcoming payday and recent hours
• `undo` → delete the last entry you logged
• Attach a paystub **PDF** to cross-check it exactly
Your weeks end on **{wd}**.""".format(
    thr=cfg.weekly_ot_threshold,
    wd=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][week_end_weekday(cfg)],
)


def validate_config():
    errors = []
    if not cfg.discord_token:
        errors.append("DISCORD_TOKEN is empty")
    if not cfg.allowed_user_id:
        errors.append("ALLOWED_USER_ID is empty (the bot refuses to run open to everyone)")
    if cfg.hourly_rate <= 0:
        errors.append("HOURLY_RATE must be > 0")
    if not cfg.payee_match:
        errors.append("PAYEE_MATCH is empty")
    if not cfg.actual_file:
        errors.append("ACTUAL_FILE is empty")
    if cfg.calc_mode not in ("ratio", "deduction"):
        errors.append("CALC_MODE must be 'ratio' or 'deduction'")
    if cfg.default_week not in ("current", "previous"):
        errors.append("DEFAULT_WEEK must be 'current' or 'previous'")
    if errors:
        sys.exit("Config problems:\n - " + "\n - ".join(errors))


intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


def today() -> date:
    return datetime.now(cfg.zone).date()


async def notify(text: str):
    """Send an alert to ALERT_CHANNEL_ID, or DM the allowed user."""
    try:
        if cfg.alert_channel_id:
            ch = client.get_channel(cfg.alert_channel_id) or await client.fetch_channel(cfg.alert_channel_id)
            await ch.send(text)
        else:
            user = await client.fetch_user(cfg.allowed_user_id)
            await user.send(text)
    except Exception:
        log.exception("Could not send notification")


# ---------------------------------------------------------------- scheduled jobs
@tasks.loop(time=cfg.auto_check_time.replace(tzinfo=cfg.zone))
async def auto_check():
    t = today()
    payday = last_payday_on_or_before(t, cfg)
    age = (t - payday).days
    if age < cfg.deposit_delay_days or db.seen(f"done:{payday}"):
        return
    res = await asyncio.to_thread(run_check, cfg, db, payday)
    if res.status in ("ok", "mismatch", "missing_hours"):
        await notify(res.message)
        db.mark(f"done:{payday}")
    elif res.status == "no_deposit" and age >= cfg.deposit_give_up_days:
        await notify(res.message + f"\n⚠️ Still no deposit {age} days after payday. Check your bank!")
        db.mark(f"done:{payday}")
    elif res.status == "error" and not db.seen(f"err:{t}"):
        await notify(res.message)
        db.mark(f"err:{t}")


@tasks.loop(time=cfg.reminder_time.replace(tzinfo=cfg.zone))
async def reminder():
    week_end = today() - timedelta(days=cfg.reminder_offset_days)
    if week_end.weekday() != week_end_weekday(cfg) or db.get_week(week_end):
        return
    await notify(f"⏰ Send your hours for the week ending {week_end:%a %m/%d} (e.g. `40 0`).")


# ---------------------------------------------------------------- events
@client.event
async def setup_hook():
    if cfg.auto_check_enabled:
        auto_check.start()
    if cfg.reminder_enabled:
        reminder.start()


@client.event
async def on_ready():
    log.info("Logged in as %s | mode=%s | llm=%s", client.user, cfg.calc_mode, cfg.use_llm)


async def handle_pdf(msg: discord.Message, att: discord.Attachment):
    cfg.stub_dir.mkdir(parents=True, exist_ok=True)
    dest = cfg.stub_dir / Path(att.filename).name
    await att.save(dest)
    try:
        info = await asyncio.to_thread(paystub.parse_stub, dest, cfg)
    except Exception as e:
        await msg.channel.send(f"Saved `{dest.name}` but couldn't read it: `{e}`")
        return
    got = [f"pay date {info['pay_date']:%m/%d/%Y}" if info["pay_date"] else "pay date ❌",
           f"gross {money(info['gross'])}" if info["gross"] is not None else "gross ❌",
           f"net {money(info['net'])}" if info["net"] is not None else "net ❌"]
    await msg.channel.send(f"Saved `{dest.name}`. Read: " + ", ".join(got))
    if not all([info["pay_date"], info["gross"] is not None, info["net"] is not None]):
        await msg.channel.send("Some fields weren't found. Run `python -m app.paystub` on the file and "
                               "tune the `STUB_*_REGEX` settings in .env (see README).")
        return
    if is_payday(info["pay_date"], cfg):
        res = await asyncio.to_thread(run_check, cfg, db, info["pay_date"])
        await msg.channel.send(res.message)
    else:
        await msg.channel.send(f"Heads up: {info['pay_date']:%m/%d} isn't on your biweekly schedule. "
                               "Check PAY_ANCHOR_DATE.")


@client.event
async def on_message(msg: discord.Message):
    if msg.author.bot or msg.author.id != cfg.allowed_user_id:
        return

    for att in msg.attachments:
        if att.filename.lower().endswith(".pdf"):
            await handle_pdf(msg, att)
            return

    text = msg.content.strip()
    low = text.lower()
    t = today()

    if low in ("help", "?", "commands"):
        await msg.channel.send(HELP)
        return

    if low == "undo":
        row = db.delete_last()
        await msg.channel.send(
            f"Removed week ending {row['week_ending']:%m/%d}: {row['regular']:g} reg + {row['overtime']:g} OT."
            if row else "Nothing to undo."
        )
        return

    if low == "status":
        last = last_payday_on_or_before(t, cfg)
        nxt = next_payday_after(t, cfg)
        lines = [f"Last payday: {last:%a %b %d} | Next payday: {nxt:%a %b %d}",
                 f"Next paycheck covers weeks ending " + " and ".join(f"{w:%m/%d}" for w in weeks_for_payday(nxt, cfg)),
                 "**Recent hours:**"]
        rows = db.recent_weeks(6)
        lines += [f"• {r['week_ending']:%a %m/%d}: {r['regular']:g} reg + {r['overtime']:g} OT" for r in rows] or ["(none yet)"]
        await msg.channel.send("\n".join(lines))
        return

    if low.startswith("check"):
        d, _ = _extract_date(low[5:], t)
        payday = last_payday_on_or_before(d or t, cfg)
        async with msg.channel.typing():
            res = await asyncio.to_thread(run_check, cfg, db, payday)
        await msg.channel.send(res.message)
        return

    # otherwise: treat as hours
    async with msg.channel.typing():
        parsed = await asyncio.to_thread(parse_hours, text, cfg, t)
    if not parsed:
        await msg.channel.send("I couldn't find hours in that. Try `38 3` (regular, overtime) or `help`.")
        return

    week_end = parsed["week_ending"]
    note = ""
    if week_end is None:
        week_end = default_week_ending(t, cfg)
    elif week_end.weekday() != week_end_weekday(cfg):
        snapped = next_week_ending(week_end, cfg)
        note = f" (your weeks end on a different day, so I used {snapped:%a %m/%d})"
        week_end = snapped

    previous = db.get_week(week_end)
    db.save_week(week_end, parsed["regular"], parsed["overtime"])
    reply = f"✅ Logged week ending {week_end:%a %m/%d}: {parsed['regular']:g} reg + {parsed['overtime']:g} OT{note}."
    if previous:
        reply += f"\nReplaced earlier entry ({previous['regular']:g} + {previous['overtime']:g})."
    reply += "\nWrong week? Send `undo`, or resend with `ending MM/DD`."
    await msg.channel.send(reply)


if __name__ == "__main__":
    validate_config()
    client.run(cfg.discord_token, log_handler=None)
