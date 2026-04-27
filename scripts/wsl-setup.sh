#!/usr/bin/env bash
# WSL bootstrap — qwen harness + Claude Code skills/hooks 설정
# 실행: bash wsl-setup.sh <mac-tailscale-ip>
# 예시: bash wsl-setup.sh 100.64.0.1
set -euo pipefail

MAC_IP="${1:-}"
if [ -z "$MAC_IP" ]; then
  echo "Usage: $0 <mac-tailscale-ip>"
  echo "  Mac Tailscale IP 확인: tailscale ip -4 (Mac에서)"
  exit 1
fi

HARNESS_REPO="https://github.com/PNKmath/qwen-toolcalling-harness-template.git"
HARNESS_DIR="$HOME/qwen-toolcalling-harness-template"
VENV_DIR="$HOME/.qwen-harness-env"
CLAUDE_DIR="$HOME/.claude"
MAC_USER="junhyukpark"

echo "=== [1/6] harness repo 클론/업데이트 ==="
if [ -d "$HARNESS_DIR/.git" ]; then
  git -C "$HARNESS_DIR" pull --ff-only
else
  git clone "$HARNESS_REPO" "$HARNESS_DIR"
fi

echo "=== [2/6] Python venv 생성 및 의존성 설치 ==="
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$HARNESS_DIR/requirements.txt"

echo "=== [3/6] skills 동기화 (Mac → WSL via Tailscale SSH) ==="
mkdir -p "$CLAUDE_DIR/skills"
rsync -az --delete \
  "${MAC_USER}@${MAC_IP}:.claude/skills/" \
  "$CLAUDE_DIR/skills/"

echo "=== [4/6] phase-run-hook.sh 복사 ==="
rsync -az \
  "${MAC_USER}@${MAC_IP}:.claude/phase-run-hook.sh" \
  "$CLAUDE_DIR/phase-run-hook.sh"
chmod +x "$CLAUDE_DIR/phase-run-hook.sh"

echo "=== [5/6] ~/.claude/.mcp.json 생성 ==="
cat > "$CLAUDE_DIR/.mcp.json" <<MCPEOF
{
  "mcpServers": {
    "qwen-coding-agent": {
      "command": "${VENV_DIR}/bin/python",
      "args": ["${HARNESS_DIR}/harness/mcp_server.py"],
      "env": {
        "LLM_MCP_BASE_URL":         "http://${MAC_IP}:8016/v1",
        "LLM_MCP_MODEL":            "Qwen3.6-27B-UD-MLX-4bit",
        "LLM_MCP_MAX_TURNS":        "20",
        "LLM_MCP_TIMEOUT":          "1200",
        "LLM_MCP_MAX_TOKENS":       "65536",
        "LLM_MCP_ENABLE_THINKING":  "true",
        "LLM_MCP_THINKING_BUDGET":  "8192",
        "LLM_MCP_PRESERVE_THINKING":"999",
        "QWEN_WATCHDOG_URL":        "http://${MAC_IP}:8017"
      }
    },
    "qwen-coding-agent-fast": {
      "command": "${VENV_DIR}/bin/python",
      "args": ["${HARNESS_DIR}/harness/mcp_server.py"],
      "env": {
        "LLM_MCP_BASE_URL":         "http://${MAC_IP}:8016/v1",
        "LLM_MCP_MODEL":            "Qwen3.6-27B-UD-MLX-4bit",
        "LLM_MCP_MAX_TURNS":        "12",
        "LLM_MCP_TIMEOUT":          "600",
        "LLM_MCP_MAX_TOKENS":       "16384",
        "LLM_MCP_ENABLE_THINKING":  "false",
        "LLM_MCP_THINKING_BUDGET":  "0",
        "LLM_MCP_PRESERVE_THINKING":"0",
        "QWEN_WATCHDOG_URL":        "http://${MAC_IP}:8017"
      }
    }
  }
}
MCPEOF

echo "=== [6/6] ~/.claude/settings.json (hooks) 생성 ==="
# 이미 존재하면 mcpServers 이외 섹션 보존 — 없으면 새로 생성
if [ -f "$CLAUDE_DIR/settings.json" ]; then
  echo "  settings.json 이미 존재 — hooks만 병합"
  python3 - <<PYEOF
import json, pathlib
p = pathlib.Path("$CLAUDE_DIR/settings.json")
d = json.loads(p.read_text())
d.setdefault("hooks", {})
d["hooks"]["PostToolUse"] = [
  {
    "matcher": "Edit|Write|Bash",
    "hooks": [{"type": "command", "command": "bash $CLAUDE_DIR/phase-run-hook.sh"}]
  }
]
p.write_text(json.dumps(d, indent=2, ensure_ascii=False))
print("  hooks 병합 완료")
PYEOF
else
  cat > "$CLAUDE_DIR/settings.json" <<SETEOF
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_DIR}/phase-run-hook.sh"
          }
        ]
      }
    ]
  }
}
SETEOF
fi

echo ""
echo "✓ WSL 설정 완료"
echo ""
echo "검증:"
echo "  claude mcp list          # qwen-coding-agent 두 항목 확인"
echo "  curl http://${MAC_IP}:8017/health  # watchdog 상태 확인"
echo ""
echo "재동기화 (skills/hook 업데이트 시):"
echo "  bash $HARNESS_DIR/scripts/wsl-setup.sh $MAC_IP"
