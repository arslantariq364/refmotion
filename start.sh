#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

HOST="${UNICO_HOST:-0.0.0.0}"
PORT="${UNICO_PORT:-8000}"
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1')"

if [ ! -d "frontend/dist" ]; then
  echo "[RefMotion] Building frontend bundle..."
  (cd frontend && npm run build)
fi

echo "======================================================================"
echo "  REFMOTION — Open-Source AI Reference Video & Motion Studio"
echo "  Local URL : http://127.0.0.1:${PORT}"
echo "  LAN URL   : http://${LAN_IP}:${PORT}"
echo "  API Docs  : http://${LAN_IP}:${PORT}/docs"
echo "======================================================================"

exec "$SCRIPT_DIR/.venv/bin/uvicorn" backend.main:app --host "$HOST" --port "$PORT"
