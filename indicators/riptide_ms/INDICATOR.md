# Riptide MS — the market-structure engine (v2)

**Status: research.** The version usually charted. Not what the bot runs.

```
pine/riptide-indicator-v2.pine    the chart source
port/ms_struct.py                 section 12 transcribed into Python
studies/                          the entry models, the BOS gate, cycle position
measurements/                     what each of them concluded
prereg/                           what was promised before each ran
tools/                            the inducement-engine trace
```

## What was measured

| question | answer | where |
|---|---|---|
| do MS entry models pay? | see the table | `measurements/MS_ENTRY_MODELS.md` |
| does a BOS gate help? | `measurements/MS_BOS_GATE.md` | |
| does cycle position sort entries? | `measurements/CYCLE_POSITION.md` | |
| does inducement transfer to Riptide? | `measurements/INDUCEMENT_ON_RIPTIDE.md` | |
| are the borrowed liquidity ideas sound? | `measurements/LIQUIDITY_BORROW_ASSESSMENT.md` | |

`measurements/INDUCEMENT_ENGINE_AUDIT.md` and
`measurements/LIQUIDITY_INDUCEMENTS_AUDIT.md` are code audits rather than
measurements, and say so.

## The port is checked, not trusted

`port/ms_struct.py` is a transcription, so it can drift from the Pine
silently. `deploy/ms-py-parity.py` pairs every logic statement in both and
fails when one has no partner:

```
python3 deploy/ms-py-parity.py \
    indicators/riptide_ms/pine/riptide-indicator-v2.pine \
    indicators/riptide_ms/port/ms_struct.py
```

It runs under `python3 deploy/preflight.py riptide_ms`, along with
`deploy/pine-input-active.py`, which finds inputs the Pine declares and never
reads.
