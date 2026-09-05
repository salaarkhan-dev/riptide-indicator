"""Telegram command handling.

Only TELEGRAM_CHAT_ID is obeyed. The getUpdates offset is persisted and
advanced before a command runs, so /restart cannot be redelivered to the
process it just started.
"""

from __future__ import annotations

import asyncio
import time

import aiohttp

from . import telegram as tg
from .config import (BAR_SECONDS, ENTRY_INTERVAL, INTERVAL, SWEEP_ALERTS,
                     TG_CHAT, TG_TOKEN, build_id, log)
from .scanner import cycle, seconds_to_next_close
from .storage import meta_get, meta_set

HELP = (
    "<b>Riptide</b>\n\n"
    "/status — build, symbols, last and next scan\n"
    "/scan — run a scan now\n"
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
    step = BAR_SECONDS[INTERVAL]
    paused = meta_get(db, "alerts_paused", "0") == "1"
    seen_n = db.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
    swp_n = db.execute("SELECT COUNT(*) FROM seen_sweeps").fetchone()[0]
    last = state.get("last_cycle", 0)
    if last:
        scan_line = f"{_fmt_ago(time.time() - last)} ago · {state.get('last_sent', 0)} sent"
    else:
        scan_line = "none yet"
    sweeps = "on" if SWEEP_ALERTS else "off"
    return (
        f"<b>Riptide status</b>\n\n"
        f"build      <code>{build_id()}</code>\n"
        f"symbols    {len(state.get('symbols', []))} · {INTERVAL}"
        f"{f' → {ENTRY_INTERVAL} entries' if ENTRY_INTERVAL else ''}\n"
        f"alerts     {'PAUSED' if paused else 'on'} · sweeps {sweeps}\n"
        f"uptime     {_fmt_ago(time.time() - state.get('started', time.time()))}\n"
        f"last scan  {scan_line}\n"
        f"next scan  in {int(seconds_to_next_close(step) // 60)}m\n"
        f"recorded   {seen_n} setups · {swp_n} sweeps\n"
        f"clock      {tg.local_clock() or 'UTC only'}"
    )


async def handle_command(sess, db, state, text: str) -> None:
    cmd = text.strip().split()[0].lower().lstrip("/").split("@")[0]

    if cmd in ("start", "help"):
        await tg.tg_send(sess, HELP)

    elif cmd == "status":
        await tg.tg_send(sess, status_text(db, state))

    elif cmd == "scan":
        await tg.tg_send(sess, "Scanning…")
        n = await cycle(sess, db, state.get("symbols", []))
        state["last_cycle"] = time.time()
        state["last_sent"] = n
        await tg.tg_send(sess, f"Scan done · {n} alert(s) sent")

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
