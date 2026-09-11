# Reference card

`alert-card.png` is the one-page cheat sheet for reading a Riptide alert:
what the first line is telling you, what the six rows are, what
`tight / normal / wide` means and how the 🎯 is chosen when several signals
fire at once.

It is a phone-first image — 1080 CSS pixels wide at 2x, so it is legible at
full width on a handset without zooming.

**Every number on it is measured**, and each one has a longer form with its
confidence interval somewhere it can be checked:

| On the card | Where it comes from |
|---|---|
| recovery 0.13 vs 6.66, and the 120-minute window | `research/studies/pick_rule.py` |
| 86% of picks are early, 39/47/13 band split | `research/studies/pick_rule.py` |
| tight / normal / wide, the R and the win rates | the block above `stop_width` in `riptide/telegram.py` |
| 141.9 of the 150 R 1h drawdown in the wide bucket | `research/studies/poi_risk.py` |
| ten open returned −39% | `research/studies/report.py::compound` |
| 0.06 R lost per 15 minutes of waiting | `research/studies/pick_hybrid.py` |
| no timeframe measurably better than another | `research/studies/timeframes.py` |
| the trendline break is worth nothing | `research/studies/trendline_measure.py` |

`/legend` in the bot carries the same claims with the intervals attached, and
`/stats` carries the forward score. If a number here ever disagrees with
`/legend`, `/legend` is the one that was written next to the measurement.

## Rebuilding

`alert-card.html` is the source. `alert-card.png` is a build product, checked
in because the card exists to be opened on a phone.

```
cd docs && npm i playwright && node render-card.mjs
```
