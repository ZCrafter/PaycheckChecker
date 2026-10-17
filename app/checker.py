"""Ties it together: hours -> expected pay -> compare with Actual (and the stub, if present)."""
from dataclasses import dataclass, field
from datetime import date

from . import actual_client, pay, paystub
from .config import Config
from .db import DB
from .periods import weeks_for_payday


def money(x: float) -> str:
    return f"${x:,.2f}"


@dataclass
class Result:
    status: str  # ok | mismatch | no_deposit | missing_hours | error
    message: str
    payday: date
    details: dict = field(default_factory=dict)


def run_check(c: Config, db: DB, payday: date) -> Result:
    weeks = weeks_for_payday(payday, c)
    entries = [db.get_week(w) for w in weeks]
    header = f"**Paycheck for {payday:%a %b %d}** (weeks ending {weeks[0]:%m/%d} and {weeks[1]:%m/%d})"

    missing = [w for w, e in zip(weeks, entries) if e is None]
    if missing:
        names = ", ".join(f"{w:%m/%d}" for w in missing)
        return Result("missing_hours", f"{header}\n⚠️ No hours logged for week ending {names}. "
                      f"Send them (e.g. `40 0 ending {missing[0]:%m/%d}`) and run `check` again.", payday)

    reg = sum(e["regular"] for e in entries)
    ot = sum(e["overtime"] for e in entries)
    exp = pay.expected_for_period(reg, ot, c)
    lines = [header, f"Hours: {reg:g} regular + {ot:g} OT",
             f"Expected gross {money(exp.gross)} → expected net {money(exp.net)} ({exp.mode} model)"]

    try:
        deposits = actual_client.find_deposits(c, payday)
    except Exception as e:
        return Result("error", f"{header}\n❌ Couldn't read Actual Budget: `{e}`", payday)
    total = actual_client.deposit_total(c, deposits)

    stub = paystub.find_stub_for_payday(c, payday)
    problems = []

    if stub and stub["gross"] is not None:
        ok, diff = pay.compare(stub["gross"], exp.gross, c.stub_gross_tolerance)
        lines.append(f"Stub gross {money(stub['gross'])} → " + ("✅ matches your hours" if ok else
                     f"⚠️ {'over' if diff > 0 else 'under'} by {money(abs(diff))} vs hours × rate"))
        if not ok:
            problems.append("stub gross")

    if total is None:
        lines.append("No matching deposit found in Actual yet (bank sync lag, or check PAYEE_MATCH).")
        return Result("no_deposit", "\n".join(lines), payday,
                      {"expected_net": exp.net, "expected_gross": exp.gross})

    where = ", ".join(sorted({d["account"] for d in deposits if d["account"]}))
    lines.append(f"Deposit in Actual: {money(total)}" + (f" ({where})" if where else ""))

    if stub and stub["net"] is not None:
        # Ground truth: the stub's net should equal the bank deposit almost exactly.
        ok, diff = pay.compare(total, stub["net"], c.stub_net_tolerance)
        lines.append("Stub net vs deposit: " + ("✅ exact match" if ok else
                     f"⚠️ deposit is {'over' if diff > 0 else 'under'} the stub by {money(abs(diff))}"))
        if not ok:
            problems.append("deposit vs stub")
    else:
        ok, diff = pay.compare(total, exp.net, c.tolerance_dollars)
        lines.append(f"Deposit vs expected net: " + (f"✅ within {money(c.tolerance_dollars)} (off by {money(abs(diff))})" if ok else
                     f"⚠️ {'over' if diff > 0 else 'under'} by {money(abs(diff))} (tolerance {money(c.tolerance_dollars)})"))
        if not ok:
            problems.append("net estimate")
        if not stub:
            lines.append("_Tip: drop this period's paystub PDF into the chat for an exact check._")

    status = "mismatch" if problems else "ok"
    return Result(status, "\n".join(lines), payday, {"expected_net": exp.net, "deposit": total})
