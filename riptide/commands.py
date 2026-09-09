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
from . import watch
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
    "/trendline on|off|4h — trendline-break heads-ups (not trades)\n"
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
    # The watch is a separate product on a separate timer, so it gets its own
    # line rather than being folded into the alert line — "alerts on" saying
    # nothing about whether the heads-ups are running would be the same kind of
    # silence the gate counters exist to remove.
    if watch.enabled(db):
        tl_n = db.execute("SELECT COUNT(*) FROM seen_trendline").fetchone()[0]
        tl_line = (f"{'+'.join(tg.tf_label(t) for t in watch.intervals(db))}"
                   f" · slope ≥ {watch.min_slope(db):.2f} · ~{_tl_rate(db)}"
                   f"/day · {tl_n} recorded · not in /stats")
        # WHY THE LAST CLOSE WAS QUIET, if it was. A lifetime row count cannot
        # tell "18 breaks, all too flat" from "the loop never woke", and those
        # are the two things worth telling apart when nothing has arrived.
        c = watch.last_cycle
        if c:
            tl_line += (f"\n           last close {_fmt_ago(time.time() - c['at'])}"
                        f" ago · {c['seen'] + c['flat']} break(s) · "
                        f"{c['flat']} too flat · {c['dupe']} already sent · "
                        f"{c['stale']} not fresh · {c['sent']} SENT")
            if c["failed"]:
                tl_line += f" · {c['failed']} FETCH FAILED"
        else:
            tl_line += "\n           no close scanned yet since restart"
    else:
        tl_line = "off · /trendline on"
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
        f"trendline  {tl_line}\n"
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


# The measured alert rate per timeframe, across 60 symbols, at slope >= 0
# (research/studies/trendline_rate.py). Printed by /trendline because the
# timeframe IS the product decision here: a heads-up fails by arriving too
# often to read, and this is the only number that says whether it will.
TRENDLINE_RATE = {"Min15": 109, "Min30": 52, "Min60": 25, "Hour4": 7}
# What fraction of breaks each steepness gate keeps, measured over 9082 breaks
# at Min15 and 4327 at Min30 — the two curves agreed to within a point, so one
# table covers both. See research/studies/trendline_slope.py.
TRENDLINE_KEEP = ((0.0, 1.00), (0.05, 0.68), (0.10, 0.39), (0.15, 0.20),
                  (0.20, 0.10), (0.30, 0.02))
# What a human types, and what the exchange calls it.
_TF_WORD = {v: k for k, v in tg.TF_LABEL.items()}


def _tl_rate(db) -> int:
    """Alerts a day at the current timeframes and steepness gate."""
    floor = watch.min_slope(db)
    keep = 1.0
    for cut, frac in TRENDLINE_KEEP:
        if floor >= cut:
            keep = frac
    return round(sum(TRENDLINE_RATE.get(t, 0) for t in watch.intervals(db))
                 * keep)


def trendline_cmd(db, text: str) -> str:
    """/trendline — read the state, or set the switch, timeframes or slope."""
    parts = text.strip().split()
    arg = parts[1].lower() if len(parts) > 1 else ""

    if arg in ("on", "off"):
        watch.set_enabled(db, arg == "on")
        return (f"Trendline heads-ups <b>{arg.upper()}</b> · "
                f"{'+'.join(tg.tf_label(t) for t in watch.intervals(db))}"
                + (f"\n<i>about {_tl_rate(db)} a day across the universe, in "
                   f"one digest per bar close.</i>" if arg == "on" else "")
                + "\n\n<i>This overrides RIPTIDE_TRENDLINE_ALERTS in "
                  "riptide.conf and survives updates, so a change on GitHub "
                  "will not take effect until you set it back the other "
                  "way.</i>")

    if arg == "slope":
        try:
            v = float(parts[2])
        except (IndexError, ValueError):
            return ("<code>/trendline slope 0.15</code> — the minimum "
                    "steepness of the broken line, in ATR per bar.\n\n"
                    + "\n".join(f"  <code>{c:.2f}</code>  keeps {f:.0%} of "
                                f"breaks" for c, f in TRENDLINE_KEEP)
                    + "\n\n<i>0 sends every break, including flat lines.</i>")
        watch.set_min_slope(db, v)
        return (f"Steepness gate <b>{max(0.0, v):.2f}</b> ATR per bar · about "
                f"<b>{_tl_rate(db)} a day</b> now.\n"
                f"Takes effect at the next close — no restart.\n\n"
                f"<i>This is a VOLUME dial, not a quality one, and that was "
                f"measured rather than assumed: steep breaks looked 9 points "
                f"better on the discovery half at 4.4 SE and the held-out half "
                f"reversed it. Steeper means fewer and better-looking, not "
                f"more likely to work.</i>")

    if arg:
        want = []
        for w in arg.replace("+", ",").split(","):
            w = w.strip()
            tf = _TF_WORD.get(w, w if w in BAR_SECONDS else "")
            if tf not in TRENDLINE_RATE:
                return ("Timeframes must come from "
                        + ", ".join(f"<code>{tg.tf_label(t)}</code>"
                                    for t in TRENDLINE_RATE)
                        + " — e.g. <code>/trendline 15m,30m</code>.\n\n"
                          "<i>Not because the others would break anything — "
                          "because those are the four whose alert rate has "
                          "been counted, and the rate is the only thing that "
                          "decides whether this stays readable.</i>")
            want.append(tf)
        watch.set_intervals(db, want)
        rate = _tl_rate(db)
        warn = ("\n\n⚠️ <i>That is a feed, not an alert. Anything you scroll "
                "past also buries the ones you would have opened. "
                "<code>/trendline slope 0.2</code> thins it.</i>"
                if rate > 40 else "")
        return (f"Trendline heads-ups now on <b>"
                f"{'+'.join(tg.tf_label(t) for t in want)}</b> · about "
                f"<b>{rate} a day</b> at slope "
                f"{watch.min_slope(db):.2f}.\nTakes effect at the next close "
                f"— no restart." + warn)

    on = watch.enabled(db)
    tfs = watch.intervals(db)
    floor = watch.min_slope(db)
    rows = "\n".join(
        f"  <code>/trendline {tg.tf_label(t):<4}</code> ~{n:>3} a day on its "
        f"own" + ("   <b>← watched</b>" if t in tfs else "")
        for t, n in TRENDLINE_RATE.items())
    return (f"<b>Trendline breakout heads-ups</b> — "
            f"{'ON' if on else 'off'} · "
            f"{'+'.join(tg.tf_label(t) for t in tfs)} · slope ≥ {floor:.2f} · "
            f"<b>~{_tl_rate(db)} a day</b>\n\n"
            f"<i>A break of a trendline drawn from confirmed pivots, on every "
            f"symbol at once, in one digest per bar close. The whole candle "
            f"has to clear the line — wick included — which is stricter than "
            f"closing beyond it, and it is exactly the blue and red arrows on "
            f"the chart.</i>\n\n"
            f"<b>It is not a trade.</b> <i>The same break was scored through "
            f"the same harness as everything else here and came out NEGATIVE "
            f"per signal and indistinguishable from a random entry. Over the "
            f"next 8 bars it continues 44-48% of the time against a 50% coin "
            f"flip. There is no entry, no stop and no grade on it, and it is "
            f"not in /stats — there is no outcome to score.</i>\n\n"
            f"<b>Rate per timeframe</b>, 60 symbols, before the slope "
            f"gate:\n{rows}\n\n"
            f"<code>/trendline 15m,30m</code> — watch both\n"
            f"<code>/trendline slope 0.2</code> — steeper lines only, fewer\n"
            f"<code>/trendline off</code> — stop them")


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

    elif cmd == "trendline":
        await tg.tg_send(sess, trendline_cmd(db, text))

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
