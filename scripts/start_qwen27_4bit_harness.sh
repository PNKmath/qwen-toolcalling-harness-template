#!/usr/bin/env bash
set -euo pipefail
LOG="/Users/junhyukpark/.mlx-model-control/logs/qwen36-27b-4bit-parser8016.log"
/Users/junhyukpark/.mlx-env/bin/mlx-openai-server launch \
  --model-path /Users/junhyukpark/MLX_Models/Qwen3.6-27B-UD-MLX-4bit \
  --model-type lm \
  --served-model-name Qwen3.6-27B-UD-MLX-4bit \
  --host 127.0.0.1 \
  --port 8016 \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  --temperature 0.6 \
  --presence-penalty 0.0 \
  --log-file "$LOG"
