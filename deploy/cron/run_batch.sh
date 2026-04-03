#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"
BASE_URL="http://127.0.0.1:${NGINX_PORT:-8080}"

cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
  echo ".env not found. Copy .env.example to .env before running this script." >&2
  exit 1
fi

docker compose up -d postgres app nginx >/dev/null

until curl -fsS "${BASE_URL}/healthz" >/dev/null; do
  sleep 2
done

MODE="batch"
SYMBOL=""
SYMBOLS=""
ALL_VARIETIES="false"
TARGET_DATE=""
CONCURRENCY="2"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --symbol)
      MODE="single"
      SYMBOL="${2:-}"
      shift 2
      ;;
    --symbols)
      MODE="batch"
      SYMBOLS="${2:-}"
      shift 2
      ;;
    --all-varieties)
      MODE="batch"
      ALL_VARIETIES="true"
      shift 1
      ;;
    --target-date)
      TARGET_DATE="${2:-}"
      shift 2
      ;;
    --concurrency)
      CONCURRENCY="${2:-2}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [ -z "$SYMBOL" ] && [ -z "$SYMBOLS" ] && [ "$ALL_VARIETIES" != "true" ]; then
  ALL_VARIETIES="true"
fi

if [ "$MODE" = "single" ]; then
  PAYLOAD="$(SYMBOL="$SYMBOL" TARGET_DATE="$TARGET_DATE" python3 - <<'PY'
import json
import os

payload = {"symbol": os.environ["SYMBOL"]}
if os.environ.get("TARGET_DATE"):
    payload["target_date"] = os.environ["TARGET_DATE"]
print(json.dumps(payload, ensure_ascii=False))
PY
)"
  curl -fsS \
    -X POST "${BASE_URL}/runs" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD"
  printf '\n'
  exit 0
fi

PAYLOAD="$(SYMBOLS="$SYMBOLS" ALL_VARIETIES="$ALL_VARIETIES" TARGET_DATE="$TARGET_DATE" CONCURRENCY="$CONCURRENCY" python3 - <<'PY'
import json
import os

symbols = [item.strip().upper() for item in os.environ.get("SYMBOLS", "").split(",") if item.strip()]
payload = {
    "symbols": symbols,
    "all_varieties": os.environ.get("ALL_VARIETIES", "false").lower() == "true",
    "concurrency": int(os.environ.get("CONCURRENCY", "2")),
}
if os.environ.get("TARGET_DATE"):
    payload["target_date"] = os.environ["TARGET_DATE"]
print(json.dumps(payload, ensure_ascii=False))
PY
)"

curl -fsS \
  -X POST "${BASE_URL}/batches" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
printf '\n'
