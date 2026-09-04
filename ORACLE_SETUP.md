# Oracle Cloud + Riptide, from zero

Complete walkthrough: create the Always Free account, get an ARM instance,
deploy the bot. Companion to `DEPLOY.md`, which covers the bot half in more
detail.

Budget roughly 45 minutes, plus however long Oracle makes you fight for ARM
capacity (see the troubleshooting section — this is the one step that
genuinely blocks people).

---

## Part 0 — Telegram first

Do this before touching Oracle; `install.sh` will ask for both values.

1. Open Telegram, message **@BotFather**, send `/newbot`.
2. Give it a name and a username ending in `bot`. Copy the **token** —
   looks like `7123456789:AAH...`.
3. **Send any message to your new bot** (click the `t.me/...` link BotFather
   gives you, then Start). This step is mandatory — a bot cannot message you
   until you have messaged it first.
4. Open this in a browser, with your token pasted in:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Find `"chat":{"id":123456789` — that number is your **chat id**.

If `getUpdates` returns `{"ok":true,"result":[]}`, step 3 did not happen.

Keep both values somewhere safe. You will type them once, on the server.

---

## Part 1 — Oracle account

1. Go to <https://cloud.oracle.com> → **Start for free**.
2. Country + email → verify the email.
3. Set a password and a company name (anything).
4. **Home region — choose carefully. It cannot be changed, ever.** All your
   Always Free resources must live in it. **Do not pick for proximity** — see
   the section below. Latency is irrelevant to a bot that polls every 30
   minutes, and the wrong jurisdiction breaks it outright.
5. Add a credit or debit card. Oracle places a small temporary authorisation
   (~$1, reversed) to verify identity. **You are not charged** and the account
   cannot exceed free limits unless you explicitly upgrade.
6. Wait for provisioning — a few minutes, sometimes ~15.

You land on a 30-day Free Trial with $300 of credits. When that expires the
account drops to Always Free only, and anything beyond the free limits is
reclaimed. The bot fits inside Always Free permanently, so this is fine.

---

## Choosing a home region

Two independent constraints, and the second one eliminates most of the
regions the internet will tell you to use.

### 1. MEXC must not geo-block the jurisdiction

MEXC blocks by **IP address**, so an instance in a blocked country cannot
reach the API at all. The bot will not work, and the home region is
permanent. Blocked as of 2026:

| Blocked | Oracle regions this rules out |
|---|---|
| United States | Ashburn, Phoenix, Chicago, San Jose, Salt Lake City |
| Canada | Toronto, Montreal |
| United Kingdom | London, Newport — upgraded to a **full** ban in 2026 |
| EU / EEA | Frankfurt, Amsterdam, Paris, Marseille, Madrid, Milan, Stockholm |
| Singapore | Singapore |
| Hong Kong, mainland China | Hong Kong |
| North Korea, Iran, Cuba, Sudan, occupied Ukrainian oblasts | — |

The EU exclusion is recent and catches people out: MEXC holds **no MiCA
licence**, and the transitional period ended **1 July 2026**, so it cannot
legally serve EEA residents. Frankfurt and Amsterdam are the two regions most
commonly recommended for A1 capacity, and both are now dead ends for this bot.

Do not route around any of this with a VPN. It breaches MEXC's terms and the
documented outcome is a frozen account.

### 2. Ampere A1 capacity must actually exist

Capacity is not published, varies by the hour, and no list stays accurate.
The structural rules that do hold:

- Ask for **less**. 1 OCPU / 6 GB provisions far more often than the maximum.
- Multi-AD regions give you three chances instead of one.
- Newer, less fashionable regions are less contended than the famous ones.

### The intersection

Ranked, best first:

| Region | Why |
|---|---|
| **ap-tokyo-1** (Japan) | Permitted; large; widely reported as one of the fastest to provision |
| **ap-osaka-1** (Japan) | Same jurisdiction, less contended than Tokyo |
| **ap-seoul-1** / **ap-chuncheon-1** (South Korea) | Permitted; Chuncheon is the quieter of the two |
| **eu-zurich-1** (Switzerland) | **Not EU or EEA**, so MiCA does not apply — the `eu-` prefix is only Oracle's naming. Crypto-friendly jurisdiction |
| **me-dubai-1** / **me-abudhabi-1** (UAE) | Permitted, crypto-friendly, newer regions tend to have headroom |
| **ap-mumbai-1** / **ap-hyderabad-1** (India) | Permitted — only the mobile apps are restricted there, the API is not |
| **sa-saopaulo-1** / **sa-vinhedo-1** (Brazil), **mx-queretaro-1** (Mexico) | Permitted, newer, good capacity odds |
| **ap-sydney-1** / **ap-melbourne-1** (Australia) | Permitted |

**Tokyo or Osaka is the pick** unless you have a reason to prefer another —
permitted jurisdiction, and the capacity reputation is the best of the
permitted set. Japan restricts MEXC's *mobile apps* only; the website and API
are unaffected, which is all this bot uses.

Capacity claims are community anecdote and shift constantly — treat the
ranking as a starting order, not a guarantee. Jurisdiction is the hard
constraint; capacity is just a queue.

`deploy/install.sh` checks MEXC reachability as its very first action and
stops with an explanation if the region is blocked, so you will find out in
seconds rather than after a full install.

---

## Part 2 — SSH key

On your own machine, not in the browser.

**macOS / Linux:**

```bash
ssh-keygen -t ed25519 -f ~/.ssh/oracle_riptide -C "riptide"
chmod 600 ~/.ssh/oracle_riptide
cat ~/.ssh/oracle_riptide.pub
```

**Windows (PowerShell):**

```powershell
ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\oracle_riptide -C "riptide"
type $env:USERPROFILE\.ssh\oracle_riptide.pub
```

Press Enter at the passphrase prompt for no passphrase, or set one — with a
passphrase you will type it on every SSH connection, which is fine here since
the bot runs unattended under systemd.

Copy the `.pub` output. That is the **public** key and the only one that
leaves your machine. The file without `.pub` is private — never upload,
paste, or share it.

---

## Part 3 — Create the instance

1. Console → hamburger menu (top left) → **Compute** → **Instances**.
2. Check the **compartment** selector on the left is your root compartment
   (usually named after your tenancy).
3. **Create instance**.
4. **Name:** `riptide`
5. **Placement:** leave the default availability domain for now. If you hit a
   capacity error later, this is the first thing you change.
6. **Image and shape** → **Edit**:
   - **Change shape** → **Ampere** → `VM.Standard.A1.Flex`
   - **OCPUs: 1**, **Memory: 6 GB**
     Always Free gives you **2 OCPUs / 12 GB** total across all A1 instances.
     Oracle halved this from 4 / 24 on **15 June 2026** with no announcement,
     so most guides you will find still quote the old figure. The bot needs a
     tiny fraction either way, and **smaller shapes are noticeably easier to
     get when capacity is tight.** Take 1/6.
   - **Change image** → **Canonical Ubuntu** → **24.04**
     Once the Ampere shape is selected the list filters to `aarch64` builds
     automatically. Confirm the image says aarch64 — `install.sh` hard-fails
     on anything else.
7. **Networking:** accept the defaults — it creates a VCN with a public
   subnet. Ensure **Assign a public IPv4 address = Yes**. Without it you
   cannot SSH in.
8. **Add SSH keys** → **Paste public keys** → paste the `.pub` contents.
   (If you instead choose "Generate a key pair for me", download **both**
   files immediately — Oracle will not show them again.)
9. **Boot volume:** leave the default (~47 GB). Always Free allows 200 GB
   total.
10. **Create.** Provisioning takes 1–3 minutes.

When it goes green, copy the **Public IP address** from the instance page.

### Do not touch the security list

The default rules already allow inbound SSH on 22, which is all you need. The
bot makes **outbound** connections only — to MEXC and Telegram — and outbound
is unrestricted by default. Do not add ingress rules. Oracle's Ubuntu images
also ship local iptables rules permitting only 22 inbound; leave those alone
too.

---

## Part 4 — Connect

```bash
ssh -i ~/.ssh/oracle_riptide ubuntu@<PUBLIC_IP>
```

Accept the host fingerprint on first connection.

If it hangs, the instance is still booting — wait a minute and retry. If you
get `Permission denied (publickey)`, you either pasted the wrong key or used
the wrong username: on Ubuntu images it is `ubuntu`, not `root` or `opc`.

---

## Part 5 — Deploy the bot

Now follow `DEPLOY.md`. Short version, run from your own machine:

```bash
git clone https://github.com/salaarkhan-dev/riptide-indicator.git
cd riptide-indicator
git checkout claude/oracle-free-tier-alerts-3vzflp
scp -i ~/.ssh/oracle_riptide -r riptide_bot.py deploy ubuntu@<PUBLIC_IP>:~/
ssh -i ~/.ssh/oracle_riptide ubuntu@<PUBLIC_IP>
```

Then on the server:

```bash
bash deploy/install.sh          # steps 1-2: apt, checks, venv, .env prompt
```

It asks for the Telegram token and chat id from Part 0. Input is hidden.

```bash
# step 3 — foreground test
cd ~/riptide && set -a && . ./.env && set +a && .venv/bin/python riptide_bot.py
```

Expect `riptide up: 6 symbols, Min30 bars` and a "Riptide scanner started"
message on your phone. Confirm it arrived. Leave it running until the next
half-hour boundary for `scanned 6 symbols, sent 0 alerts` and `first run:
history recorded, nothing sent` — zero alerts on the first cycle is correct.

```bash
# step 4 — prove alerts deliver (Ctrl-C the above first)
bash deploy/flood-test.sh

# step 5 — install the service
bash deploy/install-service.sh
sudo reboot
```

Reconnect after the reboot and confirm:

```bash
systemctl is-enabled riptide && systemctl is-active riptide
journalctl -u riptide -f
```

---

## Troubleshooting

### "Out of host capacity" / "Out of capacity for shape VM.Standard.A1.Flex"

By far the most common blocker. Ampere A1 is heavily oversubscribed in most
regions. In rough order of effectiveness:

1. **Ask for less.** 1 OCPU / 6 GB succeeds far more often than the 2 / 12
   maximum.
2. **Try each availability domain.** In multi-AD regions, AD-2 and AD-3 are
   often less contended than AD-1. Just re-run Create instance with a
   different one.
3. **Retry at off-peak hours** for the region — early morning local time
   tends to be best. Capacity is released continuously as others tear down.
4. **Upgrade to Pay As You Go.** PAYG accounts get priority for A1 capacity,
   and this is the reliable fix when the above fail. Your Always Free
   allowances stay free after upgrading — you are only billed for usage
   beyond them, and 1 OCPU / 6 GB of A1 stays inside the free tier. It does
   mean a real card on file with real spend possible if you later provision
   something outside the limits, so it is a genuine decision, not a
   formality.
5. If you want to automate retries, people script the OCI CLI to loop on
   `oci compute instance launch` until it succeeds. Not required, and not
   something to leave running unattended for days.

An x86 `VM.Standard.E2.1.Micro` Always Free instance is almost always
available as a fallback. It would run this bot fine — but `install.sh`
asserts `aarch64`, so tell me if you go that route and I will adjust the
check.

### Idle instance reclamation — relevant to this bot

Oracle may reclaim **Always Free** compute instances judged idle over a
7-day window, based on low CPU, network and memory utilisation. A polling
bot that wakes up once every 30 minutes is close to the definition of idle,
so this is a real risk for exactly this workload, not a theoretical one.

Two things to know:

- Reclamation applies to Always Free instances on accounts that have **not**
  upgraded to Pay As You Go. Upgrading removes the risk entirely, which is a
  second argument for the PAYG route above.
- Check Oracle's current documentation for the exact thresholds before
  relying on any specific number — the policy has been revised since it was
  introduced and the details vary by shape.

If your instance disappears, this is usually why. You get email warning
first, and the boot volume is preserved.

### Account stuck provisioning, or card declined

Virtual cards and some prepaid cards are rejected. A few regions require the
billing address to match the account country. Oracle support handles this,
but response times on free accounts are slow — using a normal credit card
from the start avoids it.

---

## What this costs

Nothing, if you stay inside Always Free: **2 OCPUs / 12 GB** of Ampere A1
(halved from 4 / 24 on 15 June 2026), 200 GB block storage, 10 TB/month
outbound transfer. At 1 OCPU / 6 GB the bot sits at half the compute
allowance, uses a few hundred MB of RAM, and moves negligible traffic — six
symbols polled every 30 minutes is a rounding error against 10 TB.

One trap from that June change: a free-tier instance **above** the new limits
gets shut down until resized, and Oracle support has indicated a resource
terminated above the new cap may not be recreatable. Provisioning at 1 / 6
keeps you clear of all of it.
