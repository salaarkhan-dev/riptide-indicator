"""Build docs/alert-card.html from the scorecard study's output.

WHY THIS IS A SCRIPT AND NOT A COPY-PASTE. The card's whole job is to make a
reader confident, so a number on it that does not match the study is worse than
no card at all — and a hand-transcribed table is exactly where that happens.
This reads the study's own stdout and writes the rows, so the card can only
ever say what was measured.

    PYTHONPATH=. python3 research/studies/scorecard.py > /tmp/sc.out
    python3 docs/build-card.py /tmp/sc.out
    cd docs && node render-card.mjs

The table shown is the PICKED population — only the alerts carrying a 🎯 —
because that is the stream a reader following the card actually experiences.
The SENT population is measured and lives in the study; putting both on one
card was the mess the first version was.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

ROWS = [("confirmed", "Min15", "15m"), ("confirmed", "Min30", "30m"),
        ("confirmed", "Min60", "1h"), ("early", "Min15", "15m"),
        ("early", "Min30", "30m"), ("early", "Min60", "1h")]
LABEL = {"Min15": "15m", "Min30": "30m", "Min60": "1h"}


def parse(text: str) -> dict:
    """{(kind, tf_label): {...}} from the PICKED block of the study output.

    Anchored on the PICKED banner so a layout change upstream fails loudly
    here rather than silently reading the SENT numbers onto the card.
    """
    marker = text.find("ONLY THE")
    if marker < 0:
        sys.exit("scorecard output has no PICKED block — did the study finish?")
    block = text[marker:]
    end = block.find("WHICH DIFFERENCES ARE REAL")
    block = block[:end] if end > 0 else block

    out = {}
    # e.g. "  confirmed 30m          412    43%     1.84      1.06   1.74
    #          +0.187   0.064   +77.1    24.6   3.13"
    pat = re.compile(
        r"^\s{2}(confirmed|early)\s+(15m|30m|1h)\s+"
        r"(\d+)\s+(\d+)%\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+"
        r"([+-][\d.]+)\s+([\d.]+)\s+([+-][\d.]+)\s+([\d.]+)\s+([\d.-]+)\s*$")
    for line in block.split("\n"):
        m = pat.match(line)
        if not m:
            continue
        out[(m.group(1), m.group(2))] = dict(
            n=int(m.group(3)), win=int(m.group(4)), avg_win=float(m.group(5)),
            avg_loss=float(m.group(6)), rr=float(m.group(7)),
            r=float(m.group(8)), se=float(m.group(9)),
            total=float(m.group(10)), dd=float(m.group(11)),
            recov=float(m.group(12)))
    thin = [f"{k} {t}" for k, _, t in ROWS if (k, t) not in out]
    if thin:
        print(f"  note: no row for {', '.join(thin)} — too thin to report, "
              f"the card will say so")
    return out


def verdicts(text: str) -> list:
    """The separability lines for the picked population, as (label, real?)."""
    out = []
    for line in text.split("\n"):
        m = re.match(r"^\s{2}picked · (.+?)\s{2,}([+-][\d.]+)\s+([\d.]+)\s+"
                     r"([\d.]+)\s+(SEPARABLE|not separable)\s*$", line)
        if m:
            out.append((m.group(1).strip(), m.group(5) == "SEPARABLE"))
    return out


def table_html(data: dict) -> str:
    rows = []
    for kind, tf, label in ROWS:
        d = data.get((kind, label))
        if not d:
            rows.append(
                f'      <tr><td class="k">{kind}</td><td class="t">{label}</td>'
                f'<td colspan="4" class="thin">too few to report</td></tr>')
            continue
        rows.append(
            f'      <tr><td class="k">{kind}</td><td class="t">{label}</td>'
            f'<td>{d["win"]}%</td><td>{d["rr"]:.2f}</td>'
            f'<td>{d["r"]:+.2f} <span class="se">± {d["se"]:.2f}</span></td>'
            f'<td>{d["dd"]:.0f} R</td></tr>')
    return "\n".join(rows)


def build(sc_path: str) -> None:
    text = Path(sc_path).read_text()
    data = parse(text)
    vs = verdicts(text)
    real = [label for label, ok in vs if ok]
    # THE SENTENCE UNDER THE TABLE IS THE POINT OF THE TABLE. A per-timeframe
    # grid with no statement about which gaps are real pushes a reader off 15m,
    # which is 64% of all picks, on noise. So it is generated from the study's
    # own verdicts rather than written by hand.
    if not real:
        note = ("No row here is separable from another — the gaps are smaller "
                "than their error bars. <b>Take the 🎯 whatever it says.</b>")
    else:
        note = ("Only " + ", ".join(f"<b>{r}</b>" for r in real) +
                " separates from the rest. Every other gap is inside its "
                "error bar — <b>take the 🎯 whatever it says.</b>")

    tpl = (HERE / "card-template.html").read_text()
    out = tpl.replace("<!--TABLE-->", table_html(data)).replace(
        "<!--NOTE-->", note)
    (HERE / "alert-card.html").write_text(out)
    print(f"  wrote {HERE / 'alert-card.html'} — {len(data)} of {len(ROWS)} "
          f"rows, {len(real)} separable")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/sc.out")
