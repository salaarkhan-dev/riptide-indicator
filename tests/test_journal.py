"""The journal, its slot rule, and the button callbacks.

Telegram is stubbed; SQLite is real. Covers the cases that would be expensive
to discover live: a double tap, the reservation for confirmed setups, an
over-cap position still being recorded, realised R with fees, settling twice,
and malformed callback data.

    PYTHONPATH=. python3 tests/test_journal.py     # exit 1 on any failure
"""
import os, sys, tempfile, asyncio, types
os.environ["RIPTIDE_DB"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("TELEGRAM_TOKEN","x"); os.environ.setdefault("TELEGRAM_CHAT_ID","1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from riptide.config import DB_PATH
from riptide import storage, journal, commands
from riptide import telegram as tg

# stub every outbound Telegram call
sent, answers, edits = [], [], []
async def fake_send(sess, text, buttons=None): sent.append((text, buttons)); return True
async def fake_answer(sess, cb_id, text="", alert=False): answers.append((text, alert))
async def fake_edit(sess, c, m, markup): edits.append(markup)
tg.tg_send, tg.answer_callback, tg.edit_markup = fake_send, fake_answer, fake_edit

db = storage.db_init()
class Sig:
    def __init__(s, sym, long=True, e=100.0, st=98.0):
        s.symbol, s.is_long, s.entry, s.stop = sym, long, e, st

def offer(sym, grade):
    return journal.offer(db, f"sig-{sym}-{grade}", Sig(sym), grade, "30m")

async def tap(data):
    await commands.handle_callback(db=db, sess=None, cb={
        "id":"c1","data":data,"message":{"message_id":9,"chat":{"id":1}}})

async def main():
    ok = lambda c,m: print(("  PASS  " if c else "  FAIL  ")+m) or c
    good = []

    # 1. offer + take
    i = offer("AAA","A"); await tap(f"jl:{i}")
    good.append(ok(journal.slots(db)==(1,7,5), f"one A open -> slots {journal.slots(db)}"))
    good.append(ok("Logged ·" in answers[-1][0], f"answer: {answers[-1][0]!r}"))

    # 2. double tap cannot duplicate
    await tap(f"jl:{i}")
    good.append(ok(journal.slots(db)[0]==1 and answers[-1][0]=="Already logged",
                   "second tap on the same button is refused"))

    # 3. the reservation: 5 B's max
    for k in range(5):
        j = offer(f"B{k}","B"); await tap(f"jl:{j}")
    good.append(ok(journal.may_take(db,"B")[0] is False, "6th B blocked: "+journal.may_take(db,"B")[1]))
    good.append(ok(journal.may_take(db,"A")[0] is True, "A still allowed: "+journal.may_take(db,"A")[1]))

    # 4. over-cap still LOGS (journal must stay true)
    j = offer("BX","B"); await tap(f"jl:{j}")
    good.append(ok(journal.get(db,j)["status"]=="open" and answers[-1][1] is True,
                   "over-cap B is logged with an alert-style warning"))

    # 5. total cap
    for k in range(2):
        a = offer(f"A{k}","A"); await tap(f"jl:{a}")
    good.append(ok(journal.slots(db)[0]==9 and journal.may_take(db,"A")[0] is False,
                   f"past the cap both grades block: {journal.may_take(db,'A')[1]}"))

    # 5b. the clamp: 7 A's leave 1 slot, so "open to an early" cannot say 5
    db.execute("DELETE FROM journal"); db.commit()
    for k in range(7):
        a = offer(f"Z{k}","A"); await tap(f"jl:{a}")
    u,f,fb = journal.slots(db)
    good.append(ok(f==1 and fb==1, f"7 A's open -> free {f}, open to an early {fb}"))
    db.execute("DELETE FROM journal"); db.commit()
    i = offer("AAA2","A"); await tap(f"jl:{i}")

    # 6. settle: fees in R, 2% stop -> win +1.98, loss -1.04
    await tap(f"jw:{i}")
    r = journal.get(db,i)
    good.append(ok(abs(r["r"]-(2-0.04/2))<1e-9, f"win on a 2% stop = {r['r']:+.3f}R"))
    k = offer("CCC","B"); await tap(f"jl:{k}"); await tap(f"jx:{k}")
    good.append(ok(abs(journal.get(db,k)["r"]-(-1-0.08/2))<1e-9,
                   f"loss on a 2% stop = {journal.get(db,k)['r']:+.3f}R"))
    z = offer("DDD","B"); await tap(f"jl:{z}"); await tap(f"jz:{z}")
    good.append(ok(journal.get(db,z)["r"]==0.0, "never filled = 0R, no fee"))

    # 7. settling twice
    await tap(f"jw:{i}")
    good.append(ok(answers[-1][0]=="Already settled", "re-settling is refused"))

    # 8. garbage / unknown ids
    await tap("jl:999999"); good.append(ok("no longer on file" in answers[-1][0], "unknown row id handled"))
    await tap("nonsense");  good.append(ok(answers[-1][0]=="Unrecognised button", "malformed data handled"))

    # 9. the text renderers must not throw
    for f in (commands.open_text, commands.today_text, commands.book_text, commands.slot_line):
        f(db)
    good.append(ok(True, "/open /today /book render"))
    print("\n" + commands.book_text(db).replace("<b>","").replace("</b>","")
          .replace("<i>","").replace("</i>",""))
    print("\n" + ("ALL PASS" if all(good) else "SOME FAILED"))
    return 0 if all(good) else 1

sys.exit(asyncio.run(main()))
