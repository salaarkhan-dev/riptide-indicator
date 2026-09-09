"""Telegram command handling.

Only TELEGRAM_CHAT_ID is obeyed. The getUpdates offset is persisted and
advanced before a command runs, so /restart cannot be redelivered to the
process it just started.
"""

from __future__ import annotations

import asyncio
import time

import aiohttp

from . import journal
from . import telegram as tg
from . import market
from . import tracker
from .config import (BAR_SECONDS, CFG_OVERRIDES, DI_INTERVAL, ENTRY_INTERVAL,
                     INTERVAL, INTERVALS, LOG_MARKET, MIN_GRADE, POI_REQUIRED,
                     POI_SWEEPS, SCAN_INTERVAL, SWEEP_ALERTS, SWEEP_INTERVALS,
                     SWEEP_WATCH_ONLY,
                     TG_CHAT, TG_TOKEN, TRACK, TRACK_FILL_BARS,
                     TRACK_HORIZON_BARS, TRACK_TARGET_R, TREND_FACTOR,
                     TREND_FILTER, TREND_INTERVAL, TREND_LEN, build_id, log)
from .engine import band_stats
from .scanner import cycle, seconds_to_next_close, trend_on
from .scanner import state_gate as _gate


def scanner_gate():
    return _gate

from .storage import meta_get, meta_set

HELP = (
    "<b>Riptide</b>\n\n"
    "/status — build, symbols, last and next scan\n"
    "/stats — how the alerts have actually scored\n"
    "/open — your open positions, with buttons to settle them\n"
    "/today — what you logged today, and the free slots\n"
    "/book — your own record, per grade\n"
    "/oi — export the open-interest table as a file\n"
    "/scan — run a scan now\n"
    "/trend on|off — filter setups by the higher-timeframe trend\n"
    "/pause — record setups but stop sending\n"
    "/resume — start sending again\n"
    "/update — check GitHub for a new build now\n"
    "/restart — restart the service\n"
    "/help — this\n\n"
    "<i>Symbols and settings are edited in riptide.conf on GitHub; the box "
    "picks them up within about five minutes.</i>"
)


def _fmt_ago(seconds: float) -> str:
    seconds = int(max(seconds, 0))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"


async def _run(*argv) -> tuple[int, str]:
    """Run a command, capturing output. Used only for systemctl."""
    p = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await p.communicate()
    return p.returncode, out.decode(errors="replace").strip()


def status_text(db, state) -> str:
    # The loop wakes on SCAN_INTERVAL — the FASTEST timeframe scanned — not on
    # RIPTIDE_INTERVAL. Reading the wrong one here reported "next scan in 28m"
    # while the scanner was correctly running every 15, which looks exactly
    # like a broken scanner and is only a broken status line.
    step = BAR_SECONDS[SCAN_INTERVAL]
    paused = meta_get(db, "alerts_paused", "0") == "1"
    seen_n = db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
    swp_n = db.execute("SELECT COUNT(*) FROM seen_sweeps").fetchone()[0]
    last = state.get("last_cycle", 0)
    if last:
        scan_line = f"{_fmt_ago(time.time() - last)} ago · {state.get('last_sent', 0)} sent"
    else:
        scan_line = "none yet"
    if TRACK:
        live = db.execute("SELECT COUNT(*) FROM outcomes WHERE status IN "
                          "('pending','open')").fetchone()[0]
        done = db.execute("SELECT COUNT(*) FROM outcomes WHERE status NOT IN "
                          "('pending','open','stale')").fetchone()[0]
        track_line = f"{done} settled · {live} live · /stats"
    else:
        track_line = "off"
    if LOG_MARKET:
        rows, msyms, mdays = market.coverage(db)
        oi_line = (f"{rows} rows · {msyms} symbols · {mdays:.1f}d"
                   if rows else "on, nothing yet")
    else:
        oi_line = "off"
    sweeps = "on" if SWEEP_ALERTS else "off"
    live = trend_on(db)
    src = "" if (meta_get(db, "trend_filter", "") not in ("0", "1")) else " (/trend)"
    # The grade now reads the daily POI and the HTF trend (SuperTrend AND
    # DI agreeing), so both intervals are shown next to the filter's.
    trend_line = ((f"ON · {TREND_INTERVAL} ST({TREND_LEN},{TREND_FACTOR:g})"
                   if live else "off") + src
                  + f" · grade POI+trend on {TREND_INTERVAL}/{DI_INTERVAL}")
    # Why the last cycle was quiet, if it was. Costs nothing when everything
    # is flowing and answers the only question that matters when it is not.
    gate_line = ""
    g = scanner_gate()
    if g:
        for kind in ("confirmed", "early", "sweep"):
            d = g.get(kind)
            if not d or not d["seen"]:
                continue
            gate_line += (f"{kind:<11}{d['seen']} seen · {d['dupe']} dup · "
                          f"{d['stale']} stale · {d['poi']} no POI · "
                          f"{d.get('grade', 0)} low grade · "
                          f"{d['sent']} sent\n")
    poi_line = ("POI required" if POI_REQUIRED else "POI not required")
    poi_line += (f" · grade {MIN_GRADE} and better"
                 if MIN_GRADE != "C" else " · all grades")
    if SWEEP_ALERTS:
        poi_line += (f" · sweeps {'+'.join(SWEEP_INTERVALS)}"
                     + (" in POI" if POI_SWEEPS and POI_REQUIRED else "")
                     + (" · WATCH only" if SWEEP_WATCH_ONLY else ""))
    return (
        f"<b>Riptide status</b>\n\n"
        f"build      <code>{build_id()}</code>\n"
        f"symbols    {len(state.get('symbols', []))} · {'+'.join(INTERVALS)}"
        f"{f' → {ENTRY_INTERVAL} entries' if ENTRY_INTERVAL else ''}\n"
        f"alerts     {'PAUSED' if paused else 'on'} · sweeps {sweeps}\n"
        f"filter     {poi_line}\n"
        f"trend      {trend_line}\n"
        f"outcomes   {track_line}\n"
        f"oi log     {oi_line}\n"
        f"uptime     {_fmt_ago(time.time() - state.get('started', time.time()))}\n"
        f"last scan  {scan_line}\n"
        f"next scan  in {int(seconds_to_next_close(step) // 60)}m\n"
        f"recorded   {seen_n} setups · {swp_n} sweeps\n"
        + gate_line +
        f"clock      {tg.local_clock() or 'UTC only'}"
    )


def _bucket_line(name: str, b: dict) -> str:
    if not b["setups"]:
        return f"{name:<12}—"
    # The standard error is the whole point of showing this: a mean without
    # one invites a decision the sample cannot support.
    return (f"{name:<12}{b['r_setup']:+.3f} ± {b['se_setup']:.3f}   "
            f"{b['setups']:>3} setups · {b['win_pct']:.0f}% win")


def stats_text(db) -> str:
    if not TRACK:
        return ("Outcome tracking is off.\n\n"
                "Set <code>RIPTIDE_TRACK=1</code> in riptide.conf to score "
                "alerts forward.")
    s = tracker.summary(db)
    if not s.get("armed"):
        return ("<b>Outcomes</b>\n\nNothing tracked yet. Scoring starts with "
                "the next alert — a setup needs to fill and then run its "
                "course, so the first results are hours away and a sample "
                "worth reading is weeks away.")

    days = max(0.0, (time.time() - s["since"]) / 86400)
    a = s["all"]
    settled = a["setups"]
    fill_pct = 100.0 * a["trades"] / settled if settled else 0.0

    body = (
        f"<b>Outcomes</b>\n"
        f"<i>{TRACK_TARGET_R:g}R target · {TRACK_FILL_BARS} bar fill window · "
        f"{TRACK_HORIZON_BARS} bar horizon · stop taken first</i>\n\n"
        f"tracked    {s['armed']} signals over {days:.1f} days\n"
        f"settled    {settled} · {a['trades']} filled ({fill_pct:.0f}%)\n"
        f"live       {s['pending']} pending · {s['open']} open\n"
        # Unscoreable rows are named rather than quietly dropped: a sample
        # with an invisible hole in it is worse than a smaller honest one.
        + (f"unscored   {s['stale']} · symbol left the scan\n" if s["stale"]
           else "")
        + "\n"
    )

    # The two strategies first, since that is the open question they exist to
    # answer. Each is then split by trend, which is the one thing measured to
    # separate winners from losers.
    body += "<b>R per signal</b>  <i>(unfilled counts as zero)</i>\n"
    for kind, label in ((tracker.CONFIRMED, "confirmed"), (tracker.EARLY, "early")):
        k = tracker.summary(db, kind)
        if not k.get("armed"):
            continue
        ka = k["all"]
        kfill = 100.0 * ka["trades"] / ka["setups"] if ka["setups"] else 0.0
        body += (f"\n<b>{'🅑 confirmed' if kind == tracker.CONFIRMED else '⚡ early'}"
                 f"</b>  <i>{ka['trades']}/{ka['setups']} filled "
                 f"({kfill:.0f}%)</i>\n"
                 f"<code>{_bucket_line('  all', ka)}</code>\n"
                 f"<code>{_bucket_line('  with trend', k['aligned'])}</code>\n"
                 f"<code>{_bucket_line('  against', k['against'])}</code>\n")

    g = s.get("grades") or {}
    if any(b["setups"] for b in g.values()):
        body += ("\n<b>by grade</b>  <i>(daily POI × HTF trend; "
                 "D is the cell that measured negative)</i>\n")
        for k in ("A", "B", "C", "D"):
            b = g.get(k)
            if b and b["setups"]:
                hist = band_stats(k)
                mark = f"   vs {hist[3]:+.3f} back" if hist else ""
                body += f"<code>{_bucket_line('  ' + k, b)}{mark}</code>\n"
        body += ("<i>The backtest column is what these rows exist to "
                 "overturn. A over D measured +0.87 R there, and the POI half "
                 "of it is the only filter that has passed a held-out test. "
                 "The ordering is what replicates, not the level.</i>\n")

    body += (f"\n<b>both together</b>\n"
             f"<code>{_bucket_line('  all', a)}</code>\n"
             f"<code>{_bucket_line('  with trend', s['aligned'])}</code>\n"
             f"<code>{_bucket_line('  against', s['against'])}</code>\n")
    if a["trades"]:
        body += (f"\nper filled trade  {a['r_trade']:+.3f} ± {a['se_trade']:.3f}\n"
                 f"avg excursion     +{s['mfe']:.2f}R best · "
                 f"{s['mae']:.2f}R worst\n")

    # Twenty settled setups cannot separate anything; saying so is the point.
    if settled < 20:
        body += "\n<i>Far too few to read. Let it run.</i>"
    elif settled < 200:
        body += ("\n<i>Still thin — the standard errors above are wide enough "
                 "to contain almost any conclusion. The backtest that produced "
                 "the trend filter used 1188 setups.</i>")
    else:
        body += ("\n<i>This is out-of-sample: live alerts, in whatever regime "
                 "has actually occurred. Where it disagrees with the backtest, "
                 "believe this.</i>")
    return body


async def handle_command(sess, db, state, text: str) -> None:
    cmd = text.strip().split()[0].lower().lstrip("/").split("@")[0]

    if cmd in ("start", "help"):
        await tg.tg_send(sess, HELP)

    elif cmd == "status":
        await tg.tg_send(sess, status_text(db, state))

    elif cmd == "stats":
        await tg.tg_send(sess, stats_text(db))

    elif cmd == "open":
        await send_open(sess, db)

    elif cmd == "today":
        await tg.tg_send(sess, today_text(db))

    elif cmd == "book":
        await tg.tg_send(sess, book_text(db))

    elif cmd == "oi":
        await send_oi(sess, db)

    elif cmd == "scan":
        await tg.tg_send(sess, "Scanning…")
        n = await cycle(sess, db, state.get("symbols", []))
        state["last_cycle"] = time.time()
        state["last_sent"] = n
        await tg.tg_send(sess, f"Scan done · {n} alert(s) sent")

    elif cmd == "trend":
        parts = text.strip().split()
        want = parts[1].lower() if len(parts) > 1 else ""
        if want not in ("on", "off"):
            now = "ON" if trend_on(db) else "off"
            await tg.tg_send(sess,
                             f"Trend filter is <b>{now}</b>"
                             f" · {TREND_INTERVAL} ST({TREND_LEN},{TREND_FACTOR:g})\n\n"
                             "<code>/trend on</code> — only setups facing the HTF trend\n"
                             "<code>/trend off</code> — every setup\n\n"
                             "<i>Measured: with the trend +0.119 R per setup, against "
                             "it -0.016, over 1188 setups. Roughly halves the alerts. "
                             "The gap is what replicates; the level moves with the "
                             "window, so read /stats over this.</i>")
            return
        meta_set(db, "trend_filter", "1" if want == "on" else "0")
        await tg.tg_send(sess,
                         f"Trend filter <b>{want.upper()}</b>. Applies from the next "
                         "scan — no restart.\n\n"
                         "<i>This overrides RIPTIDE_TREND_FILTER in riptide.conf and "
                         "survives updates, so a change on GitHub will not take "
                         "effect until you /trend the other way.</i>")

    elif cmd == "pause":
        meta_set(db, "alerts_paused", "1")
        await tg.tg_send(sess, "Paused. Setups are still recorded, so /resume "
                            "will not replay the backlog.")

    elif cmd == "resume":
        meta_set(db, "alerts_paused", "0")
        await tg.tg_send(sess, "Resumed.")

    elif cmd == "update":
        await tg.tg_send(sess, "Checking GitHub…")
        rc, out = await _run("sudo", "-n", "systemctl", "start",
                             "riptide-update.service")
        if rc != 0:
            await tg.tg_send(sess, f"Could not start the updater:\n<code>"
                                f"{out[:300]}</code>")
        # A real update restarts the service and reports separately. Silence
        # here means the branch had nothing new.

    elif cmd == "restart":
        # Reply first — the restart kills this process.
        await tg.tg_send(sess, "Restarting…")
        rc, out = await _run("sudo", "-n", "systemctl", "restart", "riptide")
        if rc != 0:
            await tg.tg_send(sess, f"Restart failed:\n<code>{out[:300]}</code>")

    else:
        await tg.tg_send(sess, f"Unknown command /{cmd}\n\n{HELP}")


async def command_loop(sess, db, state) -> None:
    """
    Long-poll getUpdates and act on commands from TELEGRAM_CHAT_ID only.

    The offset is persisted and advanced BEFORE the command runs. /restart
    would otherwise be replayed by the process it just started, forever.
    """
    if not (TG_TOKEN and TG_CHAT):
        return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
    offset = int(meta_get(db, "tg_offset", "0") or 0)

    # No stored offset means a fresh database. Skip whatever is already queued
    # rather than acting on commands sent before this process existed.
    if offset == 0:
        try:
            async with sess.get(url, params={"offset": -1, "timeout": 0},
                                timeout=aiohttp.ClientTimeout(total=20)) as r:
                for u in (await r.json()).get("result", []):
                    offset = max(offset, int(u["update_id"]))
        except Exception as e:
            log.warning("telegram command backlog check failed: %s", e)
        meta_set(db, "tg_offset", offset)
        log.info("telegram commands ready (backlog skipped to %d)", offset)

    while True:
        try:
            async with sess.get(url,
                                params={"offset": offset + 1, "timeout": 25},
                                timeout=aiohttp.ClientTimeout(total=45)) as r:
                if r.status != 200:
                    log.warning("getUpdates %s", r.status)
                    await asyncio.sleep(10)
                    continue
                updates = (await r.json()).get("result", [])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("getUpdates failed: %s", e)
            await asyncio.sleep(15)
            continue

        for u in updates:
            offset = max(offset, int(u["update_id"]))
            meta_set(db, "tg_offset", offset)      # commit before acting

            # A tapped inline button arrives as a callback_query rather than
            # a message. Same identity check: the chat it sits in AND the
            # account that pressed it must both be the configured one.
            cb = u.get("callback_query")
            if cb:
                cb_chat = str(((cb.get("message") or {}).get("chat") or {})
                              .get("id", ""))
                cb_who = str((cb.get("from") or {}).get("id", ""))
                if cb_chat != str(TG_CHAT) or cb_who != str(TG_CHAT):
                    log.warning("ignoring button from chat=%s user=%s",
                                cb_chat, cb_who)
                    continue
                log.info("telegram button: %s", cb.get("data"))
                try:
                    await handle_callback(sess, db, cb)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    log.exception("button %s failed: %s", cb.get("data"), e)
                    await tg.answer_callback(sess, cb.get("id", ""),
                                             "That did not work — see the log")
                continue

            msg = u.get("message") or u.get("edited_message") or {}
            text = (msg.get("text") or "").strip()
            chat = str((msg.get("chat") or {}).get("id", ""))
            who = str((msg.get("from") or {}).get("id", ""))

            if not text.startswith("/"):
                continue
            # Both must match: the configured chat, and a sender who is that
            # same account. Anyone else is ignored without a reply, so the bot
            # does not confirm it exists.
            if chat != str(TG_CHAT) or who != str(TG_CHAT):
                log.warning("ignoring command from chat=%s user=%s", chat, who)
                continue

            log.info("telegram command: %s", text.split()[0])
            try:
                await handle_command(sess, db, state, text)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.exception("command failed: %s", e)
                await tg.tg_send(sess, f"Command failed: {e}")


# --------------------------------------------------------------------------
# The journal: your positions, as opposed to tracker.py's record of every
# alert. See riptide/journal.py for why this lives in the bot rather than on
# a web page the box would have to open a port for.
# --------------------------------------------------------------------------

def _pos_line(r: dict) -> str:
    arrow = "🟢" if r["side"] == "long" else "🔴"
    return (f"{arrow} <b>{r['grade']}</b> {r['symbol']} {r['tf']} · "
            f"{tg.fmt(r['entry'])} → {tg.fmt(r['stop'])} · "
            f"{r['risk_pct']:.2f}% · 2R {tg.fmt(r['target'])}")


def slot_line(db) -> str:
    used, free, free_b = journal.slots(db)
    a, b = journal.counts(db)
    bar = "▰" * used + "▱" * free
    return (f"<code>{bar}</code>  {used} of {journal.MAX_OPEN} open "
            f"({a}A {b}B)\n<i>{free} free · {free_b} of them open to an early "
            f"signal · {journal.RESERVE} held for confirmed</i>")


def open_text(db) -> str:
    rows = journal.open_rows(db)
    if not rows:
        return "No open positions.\n\n" + slot_line(db)
    return (f"<b>{len(rows)} open</b>\n\n"
            + "\n\n".join(_pos_line(r) for r in rows)
            + "\n\n" + slot_line(db)
            + "\n\n<i>Settle each one with the buttons below it.</i>")


def today_text(db) -> str:
    midnight = int(time.time()) - (int(time.time()) % 86400)
    rows = journal.since(db, midnight)
    a = sum(1 for r in rows if r["grade"] == "A")
    head = (f"<b>{len(rows)} logged today</b> · {a}A {len(rows) - a}B"
            if rows else "<b>Nothing logged today.</b>")
    body = "\n".join(
        f"{'🟢' if r['side'] == 'long' else '🔴'} {r['grade']} {r['symbol']} "
        f"{r['tf']} · " + ("open" if r["status"] == "open"
                           else f"{r['r']:+.2f}R") for r in rows)
    return "\n\n".join(x for x in (
        head, body or None, slot_line(db),
        "<i>No measurement caps how many you take per day — the slot rule "
        "above is the one that was measured. This is here so you can see "
        "your own pattern.</i>") if x)


MEASURED_R = {"A": 0.271, "B": 0.180}


def book_text(db) -> str:
    rec = journal.record(db)
    if not rec["n"]:
        return ("Nothing settled yet.\n\n<i>Log a trade with the button on an "
                "alert, then settle it from /open.</i>")
    win = f"{100 * rec['wins'] / rec['fills']:.0f}%" if rec["fills"] else "—"
    lines = [f"<b>Your book</b> · {rec['n']} settled",
             f"total <b>{rec['total_r']:+.1f}R</b> · win {win} · "
             f"{rec['total_r'] / rec['n']:+.3f} R per trade", ""]
    for g in ("A", "B"):
        v = rec["by"].get(g)
        if not v:
            continue
        w = f"{100 * v['wins'] / v['fills']:.0f}%" if v["fills"] else "—"
        lines.append(f"<b>{g}</b> {v['n']} · win {w} · "
                     f"{v['r'] / v['n']:+.3f} R  <i>(measured "
                     f"{MEASURED_R[g]:+.3f})</i>")
    lines.append("\n<i>About 30 trades in a grade before yours means anything. "
                 "/stats is the bot's record of every alert; this is only the "
                 "ones you took.</i>")
    return "\n".join(lines)


def _settle_buttons(row_id: int) -> dict:
    return tg.keyboard([("🎯 Target", f"jw:{row_id}"),
                        ("🛑 Stopped", f"jx:{row_id}"),
                        ("⚪ Never filled", f"jz:{row_id}")])


async def send_open(sess, db) -> None:
    """/open — one message, then one small message per position so each can
    carry its own settle buttons. Telegram attaches a keyboard to a message,
    not to a line, so three positions need three messages."""
    rows = journal.open_rows(db)
    await tg.tg_send(sess, open_text(db))
    for r in rows:
        await tg.tg_send(sess, _pos_line(r), _settle_buttons(r["id"]))


async def handle_callback(sess, db, cb: dict) -> None:
    """A tapped inline button.

    Every path answers the callback, including the failures — an unanswered
    one leaves a spinner on the user's screen for several seconds and looks
    like the bot died.
    """
    cb_id = cb.get("id", "")
    data = cb.get("data") or ""
    msg = cb.get("message") or {}
    chat_id = (msg.get("chat") or {}).get("id")
    msg_id = msg.get("message_id")

    kind, _, raw = data.partition(":")
    if not raw.isdigit():
        await tg.answer_callback(sess, cb_id, "Unrecognised button")
        return
    row_id = int(raw)

    if kind == "jl":
        outcome, row = journal.take(db, row_id)
        if outcome == "missing":
            await tg.answer_callback(sess, cb_id, "That alert is no longer on file")
            return
        if outcome == "already":
            await tg.answer_callback(sess, cb_id, "Already logged")
            await tg.edit_markup(sess, chat_id, msg_id, None)
            return
        used, free, _ = journal.slots(db)
        if outcome == "over":
            _, why = journal.may_take(db, row["grade"])
            await tg.answer_callback(
                sess, cb_id,
                f"Logged, but you are over the slot rule — {why}. "
                "Recorded anyway so your book stays true.", alert=True)
        else:
            await tg.answer_callback(
                sess, cb_id, f"Logged · {used} of {journal.MAX_OPEN} open, {free} free")
        await tg.edit_markup(sess, chat_id, msg_id, None)
        await tg.tg_send(sess,
                         ("📓 <b>Logged</b> " if outcome == "taken"
                          else "⚠️ <b>Logged, over the slot rule</b> ")
                         + f"· {row['symbol']} {row['grade']} {row['tf']}\n\n"
                         + slot_line(db),
                         _settle_buttons(row_id))
        return

    if kind in ("jw", "jx", "jz"):
        row = journal.close(db, row_id,
                            {"jw": "win", "jx": "loss", "jz": "zero"}[kind])
        if not row:
            await tg.answer_callback(sess, cb_id, "Already settled")
            await tg.edit_markup(sess, chat_id, msg_id, None)
            return
        await tg.answer_callback(sess, cb_id, f"{row['r']:+.2f}R recorded")
        await tg.edit_markup(sess, chat_id, msg_id, None)
        used, free, _ = journal.slots(db)
        await tg.tg_send(sess,
                         f"{'✅' if row['r'] > 0 else '❌' if row['r'] < 0 else '⚪'} "
                         f"<b>{row['symbol']} {row['grade']}</b> "
                         f"{row['r']:+.2f}R\n\n{slot_line(db)}")
        return

    await tg.answer_callback(sess, cb_id, "Unrecognised button")


async def send_oi(sess, db) -> None:
    """/oi — the open-interest table as a CSV file in the chat.

    Gzipped and sent as a document rather than pasted: 92 symbols at a row per
    30m bar is already thousands of lines and grows forever, and a Telegram
    message caps at 4096 characters.

    This exists so the OI data can be analysed OFF the box without opening a
    port or copying a database by hand. It reads only the market table, which
    holds no keys and nothing about the account.
    """
    import csv
    import gzip
    import io

    cur = db.execute("""SELECT symbol, t, hold_vol, funding, price, amount24
                        FROM market ORDER BY t, symbol""")
    rows = cur.fetchall()
    if not rows:
        await tg.tg_send(sess, "No open-interest rows yet. market.py records "
                            "one per symbol per closed bar.")
        return

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([c[0] for c in cur.description])
    w.writerows(rows)
    blob = gzip.compress(buf.getvalue().encode())

    syms = len({r[0] for r in rows})
    span = (rows[-1][1] - rows[0][1]) / 86400 if len(rows) > 1 else 0.0
    caption = (f"open interest · {len(rows):,} rows · {syms} symbols · "
               f"{span:.1f} days\n\n"
               f"<i>Needs roughly six weeks before a split on it can say "
               f"anything. See MEASUREMENTS.md.</i>")

    form = aiohttp.FormData()
    form.add_field("chat_id", str(TG_CHAT))
    form.add_field("caption", caption)
    form.add_field("parse_mode", "HTML")
    form.add_field("document", blob, filename="riptide-oi.csv.gz",
                   content_type="application/gzip")
    try:
        async with sess.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                data=form,
                timeout=aiohttp.ClientTimeout(total=120)) as r:
            body = await r.json()
        if not body.get("ok"):
            await tg.tg_send(sess, f"Could not send the file: "
                                f"<code>{str(body)[:200]}</code>")
    except Exception as e:
        log.warning("/oi send failed: %s", e)
        await tg.tg_send(sess, f"Could not send the file: {e}")
