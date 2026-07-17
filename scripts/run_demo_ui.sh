#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend/app"
API_HOST="${DI_API_HOST:-127.0.0.1}"
API_PORT="${DI_API_PORT:-8000}"
UI_HOST="${DI_UI_HOST:-127.0.0.1}"
UI_PORT="${DI_UI_PORT:-5173}"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
UVICORN_BIN="$ROOT_DIR/.venv/bin/uvicorn"

API_PID=""
UI_PID=""

cleanup() {
  if [[ -n "$UI_PID" ]] && kill -0 "$UI_PID" 2>/dev/null; then
    kill "$UI_PID" 2>/dev/null || true
  fi
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing project virtual environment: $ROOT_DIR/.venv"
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [[ ! -x "$UVICORN_BIN" ]]; then
  echo "Missing uvicorn in .venv. Install project requirements first:"
  echo "source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to run the browser UI."
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  npm --prefix "$FRONTEND_DIR" install
fi

echo "Starting Decision Intelligence demo"
echo "API: http://$API_HOST:$API_PORT"
echo "UI:  http://$UI_HOST:$UI_PORT"
echo
echo "Press Ctrl+C to stop both servers."
echo

cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/src" "$UVICORN_BIN" \
  decision_intelligence.api.app:app \
  --host "$API_HOST" \
  --port "$API_PORT" &
API_PID="$!"

(
  cd "$FRONTEND_DIR"
  npm exec vite -- \
    --host "$UI_HOST" \
    --port "$UI_PORT"
) &
UI_PID="$!"

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$UI_PID" 2>/dev/null; do
  sleep 1
done

status=0
if ! kill -0 "$API_PID" 2>/dev/null; then
  wait "$API_PID" 2>/dev/null || status=$?
fi
if ! kill -0 "$UI_PID" 2>/dev/null; then
  wait "$UI_PID" 2>/dev/null || status=$?
fi

cleanup
exit "$status"
