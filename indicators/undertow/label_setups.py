"""Turn "I can't explain what my eye is doing" into data.

    PYTHONPATH=. python3 indicators/undertow/label_setups.py sheet BTC_USDT Min30
    PYTHONPATH=. python3 indicators/undertow/label_setups.py report labels.json

WHY THIS EXISTS. Twenty measurement pages score the strategy TAKING EVERY
SETUP. Nobody trades that way: the chart finds 150 and a person takes one or
two. So the one thing every page has in common -- a null -- may be a fact about
indiscriminate execution rather than about the setups, and
../measurements/UNDERTOW_DEFAULT.md says as much in its closing section.

The obstacle is that visual pattern recognition does not decompose into words
on demand. Asking "what do you look for?" gets an answer that is sincere and
incomplete, which is how the coded rule came to be an approximation nobody
noticed was an approximation.

So: don't ask. Show the setups the strategy actually armed, one panel each, and
record take or skip. Then work backwards and find what separates them.

THE LABELLING IS BLIND AND THAT IS THE WHOLE DESIGN. Each panel draws bars up
to the ARMING BAR AND NOT ONE BAR FURTHER. The outcome is in the file, never on
the screen. A sheet that showed what happened next would record hindsight and
read exactly like skill.

NO NEW DEPENDENCIES. The chart is inline SVG built with the standard library,
for the reason indicators/README.md gives about the research tree.
"""
from __future__ import annotations

import html
import json
import pathlib
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from indicators.undertow.port import undertow as U               # noqa: E402
from indicators.undertow.studies.undertow_sweep import load      # noqa: E402

LOOKBACK = 70          # bars of context per panel
W, H = 460, 200        # panel size


def _retrace(st, cs, i):
    mx, mn = st["msMax"][i], st["msMin"][i]
    if mx is None or mn is None or mx <= mn:
        return None
    up = st["os"][i] == 1
    v = (mx - cs[i].c) / (mx - mn) if up else (cs[i].c - mn) / (mx - mn)
    return round(100 * v, 1)


def _since(flags, i):
    for k in range(i, -1, -1):
        if flags[k]:
            return i - k
    return None


def features(cs, st, a, i):
    """Everything about a setup that a rule could plausibly key on.

    Deliberately WIDER than anything the strategy reads, because the point is
    to find what the eye uses that the code does not. A feature that turns out
    to separate take from skip is a candidate rule; one that does not is one
    fewer thing to wonder about.
    """
    c = cs[i]
    rng = c.h - c.l
    body = abs(c.c - c.o)
    up = c.h - max(c.o, c.c)
    dn = min(c.o, c.c) - c.l
    atr = st["atr"][i] if "atr" in st else None
    risk = abs(a["stop"] - a["entry"])
    past = cs[max(0, i - 20):i + 1]
    hi = max(x.h for x in past)
    lo = min(x.l for x in past)
    return {
        "code": a["code"],
        "short": bool(a["short"]),
        "state": a.get("state"),
        # BOTH WICKS, because guessing which one matters got it backwards.
        # With the priority gate on, a SHORT is a HAMMER -- its defining wick
        # is the LOWER one -- and keying "the short's wick" to the upper wick
        # measured the wrong end of every setup in the sheet.
        "upper_wick": round(up / rng, 3) if rng else 0,
        "lower_wick": round(dn / rng, 3) if rng else 0,
        "body_frac": round(body / rng, 3) if rng else 0,
        "range_vs_atr": round(rng / atr, 2) if atr else None,
        "risk_vs_atr": round(risk / atr, 2) if atr else None,
        "risk_pct": round(100 * risk / a["entry"], 3) if a["entry"] else None,
        # Where in the last 20 bars' range does the pin sit? 1.0 = at the high.
        "pos_in_range": round((c.c - lo) / (hi - lo), 3) if hi > lo else 0.5,
        "bars_since_pin": i - a["pin"],
        "hour_utc": (c.t // 3600) % 24 if getattr(c, "t", None) else None,
        # HOW MUCH OF THE IMPULSE HAS BEEN GIVEN BACK at the moment of the
        # signal. Recomputed here rather than read from `st` because bias()
        # keeps it as a local -- and it is the single most likely thing an eye
        # is using without being able to name it: "this pullback has gone too
        # far to still be a pullback".
        "retrace": _retrace(st, cs, i),
        "bias_state": st["biasState"][i],
        "bars_since_choch": _since(st["choch"], i),
    }


def collect(sym, tf, p=None, limit=200):
    p = p or U.P()
    cs = load(tf, [sym]).get(sym)
    if not cs:
        raise SystemExit(f"no cached candles for {sym} {tf}")
    st, atr = U.structure(cs, p)
    st["atr"] = atr
    U.bias(cs, st, p)
    r = U.run(cs, p, sym)
    by_arm = {(t.symbol, t.armBar): t for t in r.real}
    out = []
    for a in r.armed[-limit:]:
        i = a["bar"]
        t = by_arm.get((sym, i))
        out.append({
            "id": f"{sym}|{tf}|{i}",
            "symbol": sym, "tf": tf, "bar": i,
            "entry": a["entry"], "stop": a["stop"], "target": a["target"],
            "short": bool(a["short"]), "code": a["code"],
            "feat": features(cs, st, a, i),
            # OUTCOME IS CARRIED, NEVER RENDERED. See the module docstring.
            "r": None if t is None else round(t.r, 4),
            "bars": [(c.o, c.h, c.l, c.c) for c in cs[max(0, i - LOOKBACK):i + 1]],
        })
    return out


def svg(s):
    bars = s["bars"]
    lo = min(b[2] for b in bars)
    hi = max(b[1] for b in bars)
    for lvl in (s["entry"], s["stop"], s["target"]):
        lo, hi = min(lo, lvl), max(hi, lvl)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad

    def y(v):
        return round(H - (v - lo) / (hi - lo) * H, 1)
    n = len(bars)
    bw = W / n
    parts = []
    for k, (o, h, l, c) in enumerate(bars):
        x = round(k * bw + bw / 2, 1)
        last = k == n - 1
        col = "var(--pin)" if last else ("var(--up)" if c >= o else "var(--dn)")
        parts.append(f'<line x1="{x}" x2="{x}" y1="{y(h)}" y2="{y(l)}" '
                     f'stroke="{col}" stroke-width="1"/>')
        top, bot = y(max(o, c)), y(min(o, c))
        parts.append(f'<rect x="{round(x - bw * 0.3, 1)}" y="{top}" '
                     f'width="{round(bw * 0.6, 1)}" height="{max(1, bot - top)}" '
                     f'fill="{col}"/>')
    for lvl, col, lbl in ((s["entry"], "var(--entry)", "entry"),
                          (s["stop"], "var(--stopc)", "stop"),
                          (s["target"], "var(--tgt)", "target")):
        parts.append(f'<line x1="0" x2="{W}" y1="{y(lvl)}" y2="{y(lvl)}" '
                     f'stroke="{col}" stroke-width="1" stroke-dasharray="4 3"/>')
        parts.append(f'<text x="4" y="{y(lvl) - 3}" font-size="9" '
                     f'fill="{col}">{lbl}</text>')
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" '
            f'preserveAspectRatio="none">{"".join(parts)}</svg>')


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Which ones would you take?</title><style>
:root{--bg:#fbfbfa;--fg:#1a1a18;--mut:#6b6b66;--line:#e4e4e0;--card:#fff;
--up:#12a37a;--dn:#d1495b;--pin:#1a1a18;--entry:#3b6ea5;--stopc:#d1495b;
--tgt:#12a37a;--take:#12a37a;--skip:#9a9a94}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){
--bg:#16161a;--fg:#e9e9e4;--mut:#9a9a93;--line:#2c2c32;--card:#1e1e23;
--pin:#e9e9e4;--entry:#7aa5d2}}
:root[data-theme=dark]{--bg:#16161a;--fg:#e9e9e4;--mut:#9a9a93;--line:#2c2c32;
--card:#1e1e23;--pin:#e9e9e4;--entry:#7aa5d2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 ui-sans-serif,
system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{position:sticky;top:0;background:var(--bg);border-bottom:1px solid
var(--line);padding:14px 16px;z-index:5}
h1{margin:0 0 2px;font-size:17px;font-weight:600}
.sub{color:var(--mut);font-size:13px}
.wrap{max-width:980px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px;margin-bottom:14px}
.card.done{opacity:.4}
.meta{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;color:var(--mut);
margin-bottom:8px}
.meta b{color:var(--fg);font-weight:600}
.btns{display:flex;gap:8px;margin-top:10px}
button{flex:1;padding:9px;border:1px solid var(--line);border-radius:7px;
background:transparent;color:var(--fg);font:inherit;font-size:14px;cursor:pointer}
button.t{border-color:var(--take);color:var(--take)}
button.s{border-color:var(--skip);color:var(--skip)}
button[aria-pressed=true].t{background:var(--take);color:#fff}
button[aria-pressed=true].s{background:var(--skip);color:#fff}
#bar{position:sticky;bottom:0;background:var(--card);border-top:1px solid
var(--line);padding:12px 16px;display:flex;gap:12px;align-items:center}
#out{flex:1;color:var(--mut);font-size:13px}
#dl{flex:0 0 auto;padding:9px 16px;border-color:var(--entry);color:var(--entry)}
</style></head><body>
<header><div class="wrap" style="padding:0">
<h1>Which ones would you take?</h1>
<div class="sub">__N__ setups the strategy armed. Bars stop at the signal —
nothing after it is shown, and the outcome is not on this page.
Answer on instinct; <b>T</b> = take, <b>S</b> = skip.</div>
</div></header>
<div class="wrap" id="list"></div>
<div id="bar"><span id="out">0 labelled</span>
<button id="dl">Download labels</button></div>
<script>
const D = __DATA__;
const L = {};
const list = document.getElementById('list');
D.forEach((s, k) => {
  const f = s.feat, d = document.createElement('div');
  d.className = 'card'; d.id = 'c' + k;
  d.innerHTML = '<div class="meta"><span><b>' + s.symbol + '</b> ' + s.tf +
    '</span><span>' + (s.short ? 'SHORT' : 'LONG') + ' <b>' + s.code +
    '</b></span><span>bias <b>' + f.bias_state + '</b></span><span>risk <b>' +
    (f.risk_pct ?? '?') + '%</b></span><span>#' + (k + 1) + ' of ' + D.length +
    '</span></div>' + s.svg +
    '<div class="btns"><button class="t" data-v="take">Take</button>' +
    '<button class="s" data-v="skip">Skip</button></div>';
  list.appendChild(d);
});
function mark(k, v) {
  L[D[k].id] = v;
  const c = document.getElementById('c' + k);
  c.querySelectorAll('button').forEach(b =>
    b.setAttribute('aria-pressed', b.dataset.v === v));
  c.classList.add('done');
  document.getElementById('out').textContent =
    Object.keys(L).length + ' of ' + D.length + ' labelled';
  const nx = document.getElementById('c' + (k + 1));
  if (nx) nx.scrollIntoView({behavior: 'smooth', block: 'center'});
}
list.addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  mark(+b.closest('.card').id.slice(1), b.dataset.v);
});
let cur = 0;
addEventListener('keydown', e => {
  const k = e.key.toLowerCase();
  if (k !== 't' && k !== 's') return;
  while (cur < D.length && L[D[cur].id]) cur++;
  if (cur < D.length) mark(cur, k === 't' ? 'take' : 'skip');
});
document.getElementById('dl').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob(
    [JSON.stringify({labels: L}, null, 1)], {type: 'application/json'}));
  a.download = 'labels.json'; a.click();
};
</script></body></html>"""


def build(syms, tf, out):
    data = []
    for s in syms:
        data += collect(s, tf)
    for s in data:
        s["svg"] = svg(s)
        s.pop("bars")
    key = {s["id"]: {"r": s.pop("r"), "feat": s["feat"]} for s in data}
    pathlib.Path(out).write_text(
        PAGE.replace("__N__", str(len(data)))
            .replace("__DATA__", json.dumps(data)))
    pathlib.Path(out + ".key.json").write_text(json.dumps(key, indent=1))
    print(f"  {len(data)} setups -> {out}")
    print(f"  outcomes held back in {out}.key.json — the sheet cannot see them")


def report(labels_path, key_path):
    lab = json.loads(pathlib.Path(labels_path).read_text())["labels"]
    key = json.loads(pathlib.Path(key_path).read_text())
    take = [k for k, v in lab.items() if v == "take" and k in key]
    skip = [k for k, v in lab.items() if v == "skip" and k in key]
    print(f"\n  {len(take)} taken, {len(skip)} skipped, "
          f"{len(key) - len(lab)} unlabelled")
    if len(take) < 10 or len(skip) < 10:
        print("  NOT ENOUGH YET. Ten of each is the floor for any of this to "
              "mean anything, and thirty is where it starts to.")
        return

    def rs(ks):
        return [key[k]["r"] for k in ks if key[k]["r"] is not None]
    rt, rk = rs(take), rs(skip)
    print("\n  THE QUESTION THIS SHEET EXISTS TO ANSWER")
    for tag, v in (("you took", rt), ("you skipped", rk), ("all of them", rt + rk)):
        if v:
            se = statistics.stdev(v) / len(v) ** 0.5 if len(v) > 1 else 0
            print(f"    {tag:14} {statistics.mean(v):+.3f} +/- {se:.3f} R   n {len(v)}")
    if rt and rk:
        d = statistics.mean(rt) - statistics.mean(rk)
        se = (statistics.pstdev(rt) ** 2 / len(rt)
              + statistics.pstdev(rk) ** 2 / len(rk)) ** 0.5
        print(f"    {'DIFFERENCE':14} {d:+.3f} +/- {se:.3f}  "
              f"z {d / se if se else 0:+.2f}")

    print("\n  WHAT SEPARATES THEM — every feature, taken minus skipped")
    rows = []
    for f in sorted(key[take[0]]["feat"]):
        a = [key[k]["feat"].get(f) for k in take]
        b = [key[k]["feat"].get(f) for k in skip]
        a = [x for x in a if isinstance(x, (int, float)) and not isinstance(x, bool)]
        b = [x for x in b if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if len(a) < 5 or len(b) < 5:
            continue
        d = statistics.mean(a) - statistics.mean(b)
        se = (statistics.pstdev(a) ** 2 / len(a)
              + statistics.pstdev(b) ** 2 / len(b)) ** 0.5
        rows.append((abs(d / se) if se else 0, f, statistics.mean(a),
                     statistics.mean(b), d, se))
    for z, f, ma, mb, d, se in sorted(rows, reverse=True):
        flag = "  <- candidate" if z >= 2 else ""
        print(f"    {f:16} take {ma:8.3f}   skip {mb:8.3f}   "
              f"diff {d:+7.3f} z {z:+.2f}{flag}")
    print("\n  A z of 2 on ONE of a dozen features is what noise looks like.")
    print("  What earns a rule is a feature that separates AND whose R gap")
    print("  survives -- and then it gets a prereg like everything else here.")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "report":
        report(sys.argv[2], sys.argv[3] if len(sys.argv) > 3
               else "setups.html.key.json")
    else:
        args = sys.argv[2:] if sys.argv[1:2] == ["sheet"] else sys.argv[1:]
        tf = next((a for a in args if a.startswith("Min")), "Min30")
        syms = [a for a in args if not a.startswith("Min")] or ["BTC_USDT"]
        build(syms, tf, "setups.html")
