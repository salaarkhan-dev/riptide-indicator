# Reference card

`alert-card.png` is the one-page cheat sheet for reading a Riptide alert: what
the first line is telling you to do, what the rows are, and what the word next
to the stop means.

White background, phone-first — 1080 CSS pixels wide at 2x, legible at full
width on a handset without zooming.

**It is deliberately short.** A first version carried every measurement behind
every claim and was unreadable at a glance, which is the one thing a reference
card cannot be. The evidence lives where it can be as long as it needs to be:

| Claim on the card | Where the evidence is |
|---|---|
| take only the 🎯 | `research/studies/pick_rule.py` — recovery 0.13 taking everything, 6.66 taking one per window |
| 18 of 85 alerts a day | `research/studies/pick_rule.py` |
| tight / normal / wide | the block above `stop_width` in `riptide/telegram.py` |
| wide loses money | `research/studies/poi_risk.py` — 141.9 of the 1h stream's 150 R drawdown sits in the wide bucket |
| about 5 positions | `research/studies/report.py::compound` — ten open returned −39% over the same year |
| the edge decays fast | `research/studies/pick_hybrid.py` — 0.06 R per trade per 15 minutes of waiting |
| the trendline list is not a trade | `research/studies/trendline_measure.py` |

`/legend` in the bot carries the same claims with their confidence intervals,
and `/stats` carries the live forward score. If the card and `/legend` ever
disagree, `/legend` is the one written next to the measurement.

## Rebuilding

`alert-card.html` is the source. `alert-card.png` is a build product, checked
in because the card exists to be opened on a phone.

```
cd docs && npm i playwright && node render-card.mjs
```
