#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/../.env.harness" ]; then
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/../.env.harness"
fi

MLX_OPENAI_SERVER_BIN="${MLX_OPENAI_SERVER_BIN:-$HOME/.mlx-env/bin/mlx-openai-server}"
MODEL_PATH="${QWEN27_6BIT_MODEL_PATH:-$HOME/MLX_Models/Qwen3.6-27B-UD-MLX-6bit}"
SERVED_MODEL_NAME="${QWEN27_6BIT_SERVED_MODEL_NAME:-Qwen3.6-27B-UD-MLX-6bit}"
HOST="${QWEN_HOST:-127.0.0.1}"
PORT="${QWEN27_6BIT_PORT:-8018}"
LOG_DIR="${QWEN_LOG_DIR:-$HOME/.mlx-model-control/logs}"
LOG_FILE="${QWEN27_6BIT_LOG_FILE:-$LOG_DIR/qwen36-27b-6bit-parser${PORT}.log}"

mkdir -p "$LOG_DIR"

"$MLX_OPENAI_SERVER_BIN" launch \
  --model-path "$MODEL_PATH" \
  --model-type lm \
  --served-model-name "$SERVED_MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  --temperature 0.6 \
  --presence-penalty 0.0 \
  --log-file "$LOG_FILE"
