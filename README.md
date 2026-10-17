# paycheck-bot

A self-hosted Discord bot that checks your bi-weekly paycheck against your **Actual Budget** server.

You message it your hours each week. After payday it works out what you *should* have been paid, finds the deposit in Actual, and tells you if something is off. Optionally, drop in your paystub PDF (ADP works) for an exact check.

- 100% self-hosted and free. Only the chat itself goes through Discord.
- **No AI is needed.** All math is plain Python. A local LLM (Ollama) is an optional extra for parsing casual messages.
- Every setting and secret is in one `.env` file.

```
You (Discord)  ──"40 5"──▶  bot ──▶ SQLite (hours)
                                │
payday + 1 day ─────────────────┤
                                ├─▶ hours × rate → expected gross → expected net   (ratio OR deduction model)
                                ├─▶ Actual Budget → deposit found near payday
                                └─▶ (optional) paystub PDF → real gross & net
                                │
                    ✅ matches  /  ⚠️ off by $X   ──▶ Discord
```

## What it checks

| Check | Needs | Catches |
|---|---|---|
| Hours → expected net vs. deposit in Actual | just your hours | wrong hours/rate, missing OT, wrong deposit |
| Paystub gross vs. hours × rate | paystub PDF | employer pay errors |
| Paystub net vs. deposit in Actual | paystub PDF | bank/deposit problems (should match to the cent) |

With a stub, the exact stub numbers are used and the estimate is skipped, so the paystub route is the most accurate.

---

## 1. Try it on your PC first

Debug here first, then move it to TrueNAS. You need Python 3.11+.

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/paycheck-bot.git
cd paycheck-bot
python -m venv venv
# Windows: venv\Scripts\activate      Mac/Linux: source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Open `.env` in a text editor and fill it in (sections below explain each part). For local runs set `DATA_DIR=./data` and `STUB_DIR=./data/paystubs`.

Run the tests (no network needed):

```bash
python -m pytest -q
```

## 2. Create the Discord bot

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. **Bot** tab → **Reset Token** → copy it into `DISCORD_TOKEN`. On the same page enable **Message Content Intent**.
3. **OAuth2 → URL Generator**: tick `bot`; permissions: *View Channels, Send Messages, Read Message History, Attach Files*. Open the generated URL to invite the bot.
4. Create a **private server** (just you and the bot) with a channel like `#paycheck`.
5. In Discord: *Settings → Advanced → Developer Mode* on. Right-click yourself → **Copy User ID** → `ALLOWED_USER_ID`. Right-click the channel → **Copy Channel ID** → `ALERT_CHANNEL_ID`.

The bot ignores everyone except `ALLOWED_USER_ID`, and refuses to start without it.

## 3. Connect Actual Budget

Fill in `ACTUAL_URL`, `ACTUAL_PASSWORD`, `ACTUAL_FILE` (budget name or Sync ID from *Settings → Advanced*), and `PAYEE_MATCH`, which is text found in your paycheck payee name (e.g. `ACME`).

Test the connection:

```bash
python -m app.actual_client
```

It prints your 10 newest transactions and any deposits matching `PAYEE_MATCH`. If that works, the hardest part is done.

- If you use a **split direct deposit**, `DEPOSIT_MODE=sum` adds the matching deposits together. Make sure your expected net is the *total* across them.
- `ACTUAL_ACCOUNT` limits the search to one account.
- Using `actualpy`: its version needs to be compatible with your Actual server version. If you get sync/format errors after an Actual update, run `pip install -U actualpy`.

## 4. Describe your pay schedule

- `PAY_ANCHOR_DATE`: any one real payday (`YYYY-MM-DD`). All other paydays are every 14 days from it.
- `PAY_LAG_DAYS`: days from the **end of your pay period** to payday. Look at a paystub: "Period ending 10/17, pay date 10/23" → `6`.
- Your work week ends on the weekday of `payday − PAY_LAG_DAYS` (Saturday in that example).

Which week does a plain message like `40 5` apply to? That's `DEFAULT_WEEK`:
- `current`: the week ending on or after today. Use this if you send hours at the end of the week.
- `previous`: the last completed week. Use this if you send hours after the week ended (and set `REMINDER_OFFSET_DAYS=1`).

The bot always tells you which week it used. Send `undo`, or resend with `ending MM/DD`.

## 5. Pay model: ratio or deduction

Set `HOURLY_RATE`, `OT_MULTIPLIER`, then choose `CALC_MODE`:

**`ratio`** (simplest): `net = gross × NET_RATIO`. Take `NET_RATIO` from a past stub (net ÷ gross). Good to roughly 2–3%.

**`deduction`** (more accurate): subtracts your known per-paycheck deductions, applies FICA, and an effective income tax rate: `HEALTH_PRETAX`, `K401_PCT`, `K401_ROTH`, `OTHER_POSTTAX`, `FICA_RATE`, `EFFECTIVE_TAX_RATE`.

Rather than working these out by hand, enter numbers from **one stub** into the helper:

```bash
python -m app.calibrate --gross 2400 --net 1830.55 --taxes 310.20 --health 85 --k401 120
```

- `--taxes` = federal + state + local income tax withheld (not Social Security/Medicare)
- `--health` = pre-tax health/dental/vision deduction
- `--k401` = traditional 401k dollars (use 0 if Roth or none)

It prints lines to paste into `.env` and shows how far your current settings are from that stub. Repeat with 2–3 older stubs. If the results are consistent, you're calibrated.

Honest limits: federal withholding is bracket-based, so an *effective rate* only approximates it. It is typically within a few dollars for normal hours, but weeks with big overtime or bonuses will drift. That's what the paystub route (below) fixes. Recalibrate when you change your W-4, get a raise, or change benefits. `TOLERANCE_DOLLARS` controls how much difference is accepted.

## 6. Run it

```bash
python -m app.bot
```

Message it in your channel:

| You send | Result |
|---|---|
| `38 3` | 38 regular + 3 overtime |
| `43` | total hours; above `WEEKLY_OT_THRESHOLD` (40) counts as overtime |
| `38 reg 3 ot ending 10/03` | explicit week |
| `check` / `check 10/09` | check the latest (or a specific) paycheck |
| `status` | next payday + recent hours |
| `undo` | remove the last entry |
| *(attach a paystub PDF)* | saves it, reads it, and runs the exact check |
| `help` | command list |

**Automatic mode**: the bot (a) reminds you on the day your week ends if you haven't sent hours, and (b) the day after payday checks automatically and posts the result. If the deposit hasn't appeared (bank sync delay) it retries daily and alerts you after `DEPOSIT_GIVE_UP_DAYS`. Times are `AUTO_CHECK_TIME` / `REMINDER_TIME` in your `TZ`.

## 7. Paystubs and ADP

ADP's API is only for employers and software partners, and scraping the login (MFA, bot detection, terms of service) is fragile, so this project doesn't do it. Instead:

1. Download the stub PDF from ADP each payday.
2. Drag it into the Discord channel (or copy it into the `data/paystubs` folder).

The bot extracts **pay date, gross, and net** with the regexes `STUB_*_REGEX`. Stub layouts vary by employer, so test yours:

```bash
python -m app.paystub path/to/stub.pdf
```

It prints the raw text it can see and the parsed values. If something shows `None`, tweak the matching regex in `.env` to fit the text (each needs exactly one capture group). The defaults suit stubs with lines like `Pay Date: 10/23/2026`, `Gross Pay $2,625.00`, and `Net Pay $2,012.34`. Scanned/image-only PDFs have no text to read.

## 8. Optional: local LLM (Ollama)

Not needed. Messages like `38 3` already work. If you want to type naturally ("worked 41 this week, 3 of it overtime"):

```bash
ollama pull qwen2.5:7b
```

Then set `USE_LLM=true`, `OLLAMA_URL`, and `OLLAMA_MODEL` in `.env`. The model **only extracts numbers** from your text; all calculation stays in Python. If Ollama is unreachable (for instance your gaming PC is off), the bot silently falls back to the plain parser. The bot always echoes what it understood so a misread is obvious.

If Ollama runs on your gaming PC, it must listen on the network (set `OLLAMA_HOST=0.0.0.0`) and your firewall must allow port 11434 from the NAS.

## 9. Deploy on TrueNAS SCALE (Docker-based Apps)

TrueNAS's Apps UI can't build images from source, so the image is built for you by GitHub.

**One-time:**
1. Create a GitHub repo and push this project (`.env` is git-ignored, so your secrets stay local).
2. The included workflow (`.github/workflows/docker.yml`) runs the tests and publishes `ghcr.io/<you>/paycheck-bot:latest` on every push to `main`.
3. On GitHub: your profile → *Packages* → `paycheck-bot` → *Package settings* → set visibility to **Public** (the image contains no secrets because `.env` is excluded). Otherwise TrueNAS needs registry credentials.

**On the NAS:**
1. Create a dataset, e.g. `tank/apps/paycheck-bot`, with a `data` folder inside.
2. Put your finished `.env` at `/mnt/tank/apps/paycheck-bot/.env`.
3. In the `.env` set `ACTUAL_URL=http://<NAS-IP>:<Actual-port>`. Don't use `localhost`; inside a container that means the bot itself.
4. *Apps → Discover Apps → Custom App → Install via YAML*, and paste `docker-compose.yml`, edited to:

```yaml
services:
  paycheck-bot:
    image: ghcr.io/YOUR_GITHUB_USERNAME/paycheck-bot:latest
    container_name: paycheck-bot
    restart: unless-stopped
    env_file: /mnt/tank/apps/paycheck-bot/.env
    volumes:
      - /mnt/tank/apps/paycheck-bot/data:/data
```

5. Check the app's logs. You should see `Logged in as ...`. Message the bot `help`.

If the YAML editor rejects `env_file`, paste the contents of your `.env` under an `environment:` block instead (`KEY: value` lines).

**Updating:** push changes to GitHub, wait for the workflow, then redeploy the app (pull the latest image).

**Alternative without GitHub:** SSH into the NAS, clone the repo, and run `docker build -t paycheck-bot .`. Then use `image: paycheck-bot` in the YAML. Its permissions on the `data` folder must let the container write (it runs as root by default, so this normally just works).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Config problems: ...` at startup | a required `.env` value is empty. The message names which |
| Bot online but silent | **Message Content Intent** not enabled, or wrong `ALLOWED_USER_ID` |
| `Couldn't read Actual Budget` | wrong `ACTUAL_URL`/password/`ACTUAL_FILE`, `localhost` used inside Docker, or an `actualpy` ↔ Actual version mismatch. Run `python -m app.actual_client` to see the real error |
| "No matching deposit" | bank hasn't synced yet, `PAYEE_MATCH` doesn't appear in the payee name, or the deposit is more than `DEPOSIT_WINDOW_DAYS` from payday |
| Stub fields show ❌ | tune `STUB_*_REGEX` using `python -m app.paystub file.pdf` |
| Alerts don't arrive by DM | you must share a server with the bot and allow DMs. Easier: set `ALERT_CHANNEL_ID` |
| Log says PyNaCl/davey not installed | harmless. Those are for Discord voice, which this bot doesn't use |

## Security notes

- `.env` holds your Discord token and Actual password. It is git-ignored and excluded from the Docker image. Never commit or share it. If it leaks, reset the Discord token and change your Actual password.
- The bot only answers `ALLOWED_USER_ID`.
- Paystubs are stored only in your `data/paystubs` folder. Your hours, pay rate, and deposits are never sent anywhere except in the Discord messages you see (Discord can read those).

## Project layout

```
app/
  bot.py           Discord bot, commands, scheduled jobs
  checker.py       the comparison logic and messages
  pay.py           gross/net math (ratio + deduction models)
  periods.py       biweekly pay-period and week arithmetic
  parser.py        message → hours (regex, optional Ollama)
  actual_client.py reads deposits from Actual (python -m app.actual_client to test)
  paystub.py       reads paystub PDFs (python -m app.paystub file.pdf to test)
  calibrate.py     turns one stub into .env values
  db.py            SQLite storage
  config.py        loads all settings from .env
tests/             pytest unit tests
```

## Status

The pay math, schedule logic, message parser, paystub reader, and checker are unit-tested. The live Discord connection and the Actual Budget connection use well-known libraries (`discord.py`, `actualpy`) but need a real-world test with your accounts. Use steps 2 and 3 above to confirm each piece before relying on it, and calibrate against a few past paychecks first.
