"""Every message the bot sends must survive Telegram's HTML parser.

WHY THIS FILE EXISTS. On 12 Sep /status returned this, on every single call:

    Bad Request: can't parse entities: Unsupported start tag "1.55"
    at byte offset 208

The cause was one character. The sweep line built "rvol<1.55", Telegram parses
messages as HTML, "<1.55" looks like a start tag, and the parser rejects THE
WHOLE MESSAGE with a 400. /status had been dead for as long as
RIPTIDE_SWEEP_WATCH_ONLY had been on, and nothing said so: the bot logged a
400 and carried on scanning perfectly.

THAT IS THE FAILURE MODE WORTH TESTING. It is not that a message looks wrong —
it is that a message does not arrive at all, from a process that is otherwise
completely healthy, because of a "<" someone typed next to a number. It cannot
be caught by reading the code, because the offending line looks exactly like
the twenty correct lines around it.

So this renders the real command output under the settings that trigger it and
runs a parser over the result. It does not check wording or layout — only that
Telegram will accept it.

    PYTHONPATH=. python3 tests/test_tg_html.py      # exit 1 on any failure
"""
import os
import sys
from html.parser import HTMLParser

sys.path.insert(0, ".")

# The settings that produced the live 400. Set BEFORE riptide.config is
# imported, because it reads the environment once at import time.
os.environ.setdefault("RIPTIDE_DB", ":memory:")
os.environ["RIPTIDE_SWEEP_WATCH_ONLY"] = "1"
os.environ["RIPTIDE_MAX_SWEEP_RVOL"] = "1.55"

from riptide import commands as cm            # noqa: E402
from riptide import storage as st             # noqa: E402

fails = []


def check(ok, what):
    print(f"  {'PASS' if ok else 'FAIL'}  {what}")
    if not ok:
        fails.append(what)


# The tags Telegram's HTML mode actually accepts. Anything else is a 400, so
# the list is deliberately closed rather than permissive: a <div> someone adds
# for structure would be just as fatal as a stray "<".
# https://core.telegram.org/bots/api#html-style
OK_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
           "span", "tg-spoiler", "a", "code", "pre", "blockquote",
           "tg-emoji"}


class TgParser(HTMLParser):
    """Rejects what Telegram rejects: unknown tags and unclosed ones."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.bad = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in OK_TAGS:
            self.bad.append(f"unsupported start tag <{tag}>")
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag not in OK_TAGS:
            self.bad.append(f"unsupported end tag </{tag}>")
        if not self.stack:
            self.bad.append(f"</{tag}> with nothing open")
        elif self.stack[-1] != tag:
            self.bad.append(f"</{tag}> closes <{self.stack[-1]}>")
            self.stack.pop()
        else:
            self.stack.pop()


def tg_ok(text: str) -> list:
    """Every reason Telegram would refuse this message. Empty means it sends."""
    bad = []
    # PYTHON'S PARSER IS MORE FORGIVING THAN TELEGRAM'S, AND THAT GAP IS THE
    # WHOLE BUG. HTML5 says a "<" not followed by a letter is ordinary text, so
    # html.parser reads "rvol<1.55" as a string and reports nothing — which is
    # exactly the message Telegram answered with a 400. So the bare "<" is
    # checked directly rather than left to the parser.
    for i, ch in enumerate(text):
        if ch != "<":
            continue
        nxt = text[i + 1:i + 2]
        if not (nxt.isalpha() or nxt == "/"):
            bad.append(f"bare '<' at {i}: {text[i:i + 12]!r} — escape it "
                       f"as &lt;")
    p = TgParser()
    try:
        p.feed(text)
        p.close()
    except Exception as e:                       # a malformed tag can raise
        p.bad.append(f"parser error: {e}")
    if p.stack:
        p.bad.append(f"never closed: {'<' + '>, <'.join(p.stack)}>")
    return bad + p.bad


print("THE PARSER CATCHES THE BUG IT WAS WRITTEN FOR")
# If this passes, the test below proves nothing — so the detector is tested
# before the thing it detects.
check(tg_ok("sweeps · rvol<1.55") != [],
      "a bare '<' before a number is rejected, as Telegram rejects it")
check(tg_ok("sweeps · rvol&lt;1.55") == [],
      "and the escaped form is accepted")
check(tg_ok("<b>bold</b> and <code>x</code>") == [],
      "ordinary markup still passes")
check(tg_ok("<div>structure</div>") != [],
      "a tag Telegram does not support is rejected")
check(tg_ok("<b>never closed") != [], "an unclosed tag is rejected")

print("\nEVERY COMMAND RENDERS INTO SOMETHING TELEGRAM ACCEPTS")
db = st.db_init()
state = {"symbols": ["BTC_USDT", "ETH_USDT"], "started": 0}

messages = {
    "/status": lambda: cm.status_text(db, state),
    "/help": lambda: cm.HELP,
    "/legend": lambda: cm.LEGEND,
    "/trendline": lambda: cm.trendline_cmd(db, "/trendline"),
    "/trendline slope": lambda: cm.trendline_cmd(db, "/trendline slope"),
    "/trendline on": lambda: cm.trendline_cmd(db, "/trendline on"),
    "/trendline 15m,30m": lambda: cm.trendline_cmd(db, "/trendline 15m,30m"),
    "/trendline 5m (rejected)": lambda: cm.trendline_cmd(db, "/trendline 5m"),
    "/exhaust": lambda: cm.exhaust_cmd(db, "/exhaust"),
    "/exhaust on": lambda: cm.exhaust_cmd(db, "/exhaust on"),
    "/exhaust 15m,30m,1h": lambda: cm.exhaust_cmd(db, "/exhaust 15m,30m,1h"),
    "/exhaust terminal": lambda: cm.exhaust_cmd(db, "/exhaust terminal"),
    "/exhaust perfect off": lambda: cm.exhaust_cmd(db, "/exhaust perfect off"),
    "/exhaust 5m (rejected)": lambda: cm.exhaust_cmd(db, "/exhaust 5m"),
    "/exhaust off": lambda: cm.exhaust_cmd(db, "/exhaust off"),
}
for name, build in messages.items():
    try:
        text = build()
    except Exception as e:
        check(False, f"{name} raised {type(e).__name__}: {e}")
        continue
    bad = tg_ok(text)
    check(not bad, f"{name} ({len(text)} chars)"
                   + ("" if not bad else "  → " + "; ".join(bad)))

print("\nTHE SETTING THAT BROKE IT LIVE IS THE ONE RENDERED HERE")
status = cm.status_text(db, state)
check("rvol" in status,
      "the sweep line is actually present in this render, so the case is "
      "covered rather than skipped")
check("rvol<" not in status,
      "and it no longer contains the bare '<' that returned 400 on every call")

print("\nNOTHING EXCEEDS TELEGRAM'S 4096-CHARACTER CAP UNSPLIT")
# /legend is over the cap by design and is split by legend_parts; everything
# else has to fit whole, because nothing else splits.
for name, build in messages.items():
    if name == "/legend":
        continue
    check(len(build()) <= 4096, f"{name} fits in one message")
parts = cm.legend_parts(cm.LEGEND)
check(parts and all(len(p) <= 4096 for p in parts),
      f"/legend splits into {len(parts)} sendable parts "
      f"(longest {max(len(p) for p in parts)})")
for i, p in enumerate(parts):
    bad = tg_ok(p)
    check(not bad, f"/legend part {i + 1} parses"
                   + ("" if not bad else "  → " + "; ".join(bad)))

print("\n" + ("ALL PASS" if not fails
               else f"{len(fails)} FAILED:\n  " + "\n  ".join(fails)))
sys.exit(1 if fails else 0)
