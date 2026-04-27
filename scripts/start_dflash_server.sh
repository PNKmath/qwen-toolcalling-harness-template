#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/../.env.harness" ]; then
  source "${SCRIPT_DIR}/../.env.harness"
fi

PYTHON="${DFLASH_PYTHON:-$HOME/.mlx-env/bin/python}"
PORT="${DFLASH_PORT:-8016}"
# DFLASH_OVERRIDE_HOST takes priority over .env.harness QWEN_HOST
HOST="${DFLASH_OVERRIDE_HOST:-${QWEN_HOST:-127.0.0.1}}"

# 로컬 draft 모델 경로 — snapshot_download 패치에서 사용
export DFLASH_DRAFT_LOCAL="${DFLASH_DRAFT_LOCAL:-$HOME/MLX_Models/Qwen3.6-27B-DFlash}"
export DFLASH_DRAFT_ID="${DFLASH_DRAFT_ID:-z-lab/Qwen3.6-27B-DFlash}"
export DFLASH_PORT="$PORT"

echo "Starting DFlash server on ${HOST}:${PORT} ..."
echo "  main:  ${QWEN27_4BIT_MODEL_PATH:-$HOME/MLX_Models/Qwen3.6-27B-UD-MLX-4bit}"
echo "  draft: ${DFLASH_DRAFT_LOCAL}"

exec "$PYTHON" "${SCRIPT_DIR}/dflash_server.py" \
  --host "$HOST" \
  --port "$PORT"
