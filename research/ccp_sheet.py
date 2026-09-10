from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib import colors

GREEN = colors.HexColor("#26a69a")
RED   = colors.HexColor("#ef5350")
INK   = colors.HexColor("#1f2430")
MUTED = colors.HexColor("#6b7280")
FAINT = colors.HexColor("#9aa1ad")
HAIR  = colors.HexColor("#dfe2e8")
W, H  = A4
M     = 16 * mm

# (low, bodyBottom, bodyTop, high, isGreen) in 0..1 of the cell's plot height
def flip(s):
    lo, bb, bt, hi, g = s
    return (1 - hi, 1 - bt, 1 - bb, 1 - lo, g)

def candle(c, cx, y0, ph, cw, s):
    lo, bb, bt, hi, g = s
    col = GREEN if g else RED
    c.setStrokeColor(col); c.setFillColor(col)
    c.setLineWidth(1.4); c.line(cx, y0 + lo * ph, cx, y0 + hi * ph)
    c.setLineWidth(1.0)
    c.rect(cx - cw / 2, y0 + bb * ph, cw, max((bt - bb) * ph, 1.5), stroke=1, fill=1)

def leader(c, x1, x2, y, txt, col):
    c.setStrokeColor(HAIR); c.setLineWidth(0.7); c.setDash(1, 2)
    c.line(x1, y, x2, y); c.setDash()
    c.setFillColor(col); c.setFont("Helvetica-Bold", 7)
    c.drawString(x2 + 4, y - 2.4, txt)

def cell(c, x, y, w, h, title, sub, cands, ann):
    c.setStrokeColor(HAIR); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 5, stroke=1, fill=0)
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 9)
    c.drawString(x + 11, y + h - 16, title)
    c.setFillColor(FAINT); c.setFont("Helvetica", 6.8)
    c.drawString(x + 11, y + h - 26, sub)

    ph = h - 44
    y0 = y + 11
    cw = 17
    gp = 30
    bx = x + 34
    for i, s in enumerate(cands):
        candle(c, bx + i * gp, y0, ph, cw, s)
    right = bx + (len(cands) - 1) * gp + cw / 2 + 3
    for lvl, txt, col in ann:
        leader(c, right, x + w - 44, y0 + lvl * ph, txt, col)

def header(c, page, title, blurb):
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 16)
    c.drawString(M, H - 19 * mm, title)
    c.setFillColor(MUTED); c.setFont("Helvetica", 8.2)
    ty = H - 25 * mm
    for l in blurb:
        c.drawString(M, ty, l); ty -= 11
    c.setStrokeColor(HAIR); c.setLineWidth(0.7); c.line(M, ty - 2, W - M, ty - 2)
    c.setFillColor(FAINT); c.setFont("Helvetica", 6.6)
    c.drawRightString(W - M, 11 * mm, "MMC candle confirmations  ·  %d of 2" % page)
    return ty - 16

def colhead(c, x, w, y, txt, col):
    c.setFillColor(col); c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x, y, txt)
    c.setStrokeColor(col); c.setLineWidth(1.4); c.line(x, y - 6, x + w, y - 6)

def footnote(c, y, head, lines):
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 8.4)
    c.drawString(M, y, head)
    c.setFillColor(MUTED); c.setFont("Helvetica", 7.6)
    for i, t in enumerate(lines):
        c.drawString(M, y - 13 - i * 10.5, t)

# ── the four pin shapes, drawn full-height for the 1CP page ────────────────
HAMMER  = (0.05, 0.63, 0.86, 0.92, True)
HANGING = (0.05, 0.63, 0.86, 0.92, False)
INVHAM  = flip(HAMMER)[:4]  + (True,)
SHOOT   = flip(HANGING)[:4] + (False,)

# ── compressed pins for the 2CP page ───────────────────────────────────────
# SHIFTED, NOT FLIPPED, for the bearish column. Flipping a hammer produces an
# inverted hammer — the flip is exactly the operation that turns one shape into
# the other — so the bearish side was drawing the wrong candle under every name.
# A bearish 2CP uses the SAME four pins as the bullish one, sitting high instead
# of low, which is a translation.
def shift(s, d):
    lo, bb, bt, hi, g = s
    return (lo + d, bb + d, bt + d, hi + d, g)

P_HAMMER  = (0.04, 0.28, 0.44, 0.48, True)
P_HANGING = (0.04, 0.28, 0.44, 0.48, False)
P_INVHAM  = (0.24, 0.26, 0.42, 0.70, True)
P_SHOOT   = (0.24, 0.26, 0.42, 0.70, False)
BIG_GREEN = (0.10, 0.16, 0.90, 0.95, True)
BIG_RED   = (0.06, 0.10, 0.86, 0.90, False)
# Raised so each pin's own high becomes the pair's high, which is where the
# sheet puts the stop.
UP_HAMMER  = shift(P_HAMMER,  0.50)
UP_HANGING = shift(P_HANGING, 0.50)
UP_INVHAM  = shift(P_INVHAM,  0.28)
UP_SHOOT   = shift(P_SHOOT,   0.28)

c = canvas.Canvas("/home/user/riptide-indicator/MMC_CP_Confirmations.pdf", pagesize=A4)
c.setTitle("MMC candle confirmations")
c.setAuthor("Riptide")

# ═══════════════════════ PAGE 1 — 1CP ═══════════════════════════════════════
top = header(c, 1, "1CP  —  one-candle confirmations", [
    "One candle: a long wick doing the rejecting, a small body.",
    "The WICK sets the direction — lower is bullish, upper is bearish. The body colour only sets the name.",
    "Entry sits at the body edge on the trade side. The stop sits beyond the wick."])

CW = (W - 2 * M - 9 * mm) / 2
X2 = M + CW + 9 * mm
CH = 214

colhead(c, M,  CW, top, "BULLISH  ·  long lower wick", GREEN)
colhead(c, X2, CW, top, "BEARISH  ·  long upper wick", RED)
ry = top - 22

L = [("Hammer", "green body", [HAMMER],
      [(0.86, "ENTRY", GREEN), (0.05, "SL", MUTED)]),
     ("Hanging man", "red body", [HANGING],
      [(0.86, "ENTRY", GREEN), (0.05, "SL", MUTED)])]
R = [("Shooting star", "red body", [SHOOT],
      [(0.14, "ENTRY", RED), (0.95, "SL", MUTED)]),
     ("Inverted hammer", "green body", [INVHAM],
      [(0.14, "ENTRY", RED), (0.95, "SL", MUTED)])]

for i in range(2):
    yy = ry - CH - i * (CH + 14)
    cell(c, M,  yy, CW, CH, *L[i])
    cell(c, X2, yy, CW, CH, *R[i])

footnote(c, ry - 2 * (CH + 14) - 16, "Four names, two shapes", [
    "A hammer and a hanging man are the identical candle in two colours, and both are bullish.",
    "So are the inverted hammer and the shooting star, and both are bearish.",
    "Naming by body colour rather than by position is deliberate: colour is in the data,",
    "position is a judgement about where a move 'was', which cannot be made without hindsight."])
c.showPage()

# ═══════════════════════ PAGE 2 — 2CP ═══════════════════════════════════════
top = header(c, 2, "2CP  —  two-candle confirmations", [
    "Any of those four pins, then a decisive candle that engulfs it.",
    "Here the SECOND candle sets the direction: a green engulfing is bullish, a red one bearish.",
    "Entry sits at the body edge of the second candle. The stop sits beyond the furthest wick of the pair."])

CH2 = 118
colhead(c, M,  CW, top, "BULLISH  ·  pin + green engulfing", GREEN)
colhead(c, X2, CW, top, "BEARISH  ·  pin + red engulfing", RED)
ry = top - 22

pins = [(P_HAMMER, UP_HAMMER, "Hammer"), (P_HANGING, UP_HANGING, "Hanging man"),
        (P_INVHAM, UP_INVHAM, "Inverted hammer"), (P_SHOOT, UP_SHOOT, "Shooting star")]

for i, (loPin, hiPin, nm) in enumerate(pins):
    yy = ry - CH2 - i * (CH2 + 10)
    cell(c, M, yy, CW, CH2, nm + "  +  green engulfing", "the green candle decides",
         [loPin, BIG_GREEN], [(0.90, "ENTRY", GREEN), (0.04, "SL", MUTED)])
    cell(c, X2, yy, CW, CH2, nm + "  +  red engulfing", "the red candle decides",
         [hiPin, BIG_RED], [(0.10, "ENTRY", RED), (hiPin[3], "SL", MUTED)])

footnote(c, ry - 4 * (CH2 + 10) - 16, "Why a shooting star can open a long", [
    "In a 2CP the pin's job is to mark that price was rejected AT ALL, not which way.",
    "The engulfing candle settles the direction, so any of the four pins can open either side.",
    "Four pins x two directions is eight, and with the four 1CPs that is the twelve."])
c.save()
print("written")
