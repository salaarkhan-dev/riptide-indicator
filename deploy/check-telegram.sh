#!/usr/bin/env bash
#
# Diagnose Telegram delivery. Never prints the token — every line of output is
# scrubbed, so the result is safe to paste into a chat or an issue.
#
#     bash deploy/check-telegram.sh

set -uo pipefail

APP_DIR=/home/ubuntu/riptide
cd "$APP_DIR" 2>/dev/null || { echo "FAIL: $APP_DIR not found"; exit 1; }

[[ -f .env ]] || { echo "FAIL: .env missing — run install.sh"; exit 1; }
echo "  .env: mode $(stat -c '%a %U:%G' .env)"

set -a; . ./.env; set +a

tok="${TELEGRAM_TOKEN:-}"
chat="${TELEGRAM_CHAT_ID:-}"

# scrub() removes the token from anything we print, belt and braces
scrub() { if [[ -n $tok ]]; then sed "s/${tok//\//\\/}/<TOKEN>/g"; else cat; fi; }

[[ -n $tok  ]] || { echo "FAIL: TELEGRAM_TOKEN empty after sourcing .env"; exit 1; }
[[ -n $chat ]] || { echo "FAIL: TELEGRAM_CHAT_ID empty after sourcing .env"; exit 1; }

echo "== shape =="
if [[ $tok =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]]; then
  echo "  token:   ${#tok} chars, format OK (digits:letters)"
else
  echo "  token:   ${#tok} chars, format BAD — expected 123456789:AAH..."
  echo "           a token with quotes, spaces or a stray newline lands here"
fi
if [[ $chat =~ ^-?[0-9]+$ ]]; then
  echo "  chat id: ${#chat} chars, format OK (digits)"
else
  echo "  chat id: ${#chat} chars, format BAD — expected digits only"
fi
[[ $tok  == *$'\r'* ]] && echo "  WARN: token contains a carriage return"
[[ $tok  == *' '*   ]] && echo "  WARN: token contains a space"
[[ $chat == *$'\r'* ]] && echo "  WARN: chat id contains a carriage return"
[[ $chat == *' '*   ]] && echo "  WARN: chat id contains a space"

echo
echo "== getMe (is the token valid?) =="
curl -sS -m 15 "https://api.telegram.org/bot${tok}/getMe" 2>&1 | scrub | head -c 400
echo

echo
echo "== sendMessage (does delivery work?) =="
curl -sS -m 15 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
  -d "chat_id=${chat}" \
  --data-urlencode "text=Riptide connectivity test — if you can read this, delivery works." \
  2>&1 | scrub | head -c 600
echo

echo
echo "How to read the result:"
echo '  {"ok":true,...}                         delivery works'
echo '  401 Unauthorized                        token is wrong'
echo '  400 "chat not found"                    chat id is wrong'
echo '  403 "bot was blocked by the user"       unblock the bot in Telegram'
echo '  400 "chat_id is empty"                  .env did not load'
