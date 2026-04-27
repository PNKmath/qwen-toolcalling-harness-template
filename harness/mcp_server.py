#!/usr/bin/env python3
"""MCP server: local LLM coding agent harness.

Exposes run_coding_agent tool to Claude Code.
When phase/run_id/project_dir are provided, logs file writes to
.claude/phase-run-edits.log so phase-run Scope Audit can track edits.
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from harness.config import HarnessConfig
from harness.runner import run_agent
from harness.tools import exec_tool as _base_exec_tool

_DEFAULT_BASE_URL = os.getenv(
    "QWEN_MCP_BASE_URL",
    os.getenv("LLM_MCP_BASE_URL", "http://127.0.0.1:8022/v1"),
)
_DEFAULT_MODEL = os.getenv(
    "QWEN_MCP_MODEL",
    os.getenv("LLM_MCP_MODEL", "MiniMax-M2.7-JANGTQ-CRACK"),
)

CFG = HarnessConfig(
    base_url=_DEFAULT_BASE_URL,
    model=_DEFAULT_MODEL,
    max_turns=int(os.getenv("QWEN_MCP_MAX_TURNS", os.getenv("LLM_MCP_MAX_TURNS", "20"))),
    request_timeout=int(os.getenv("QWEN_MCP_TIMEOUT", os.getenv("LLM_MCP_TIMEOUT", "600"))),
    max_tokens=int(os.getenv("LLM_MCP_MAX_TOKENS", "65536")),
    enable_thinking=os.getenv("LLM_MCP_ENABLE_THINKING", "true").lower() == "true",
    thinking_budget=int(os.getenv("LLM_MCP_THINKING_BUDGET", "8192")),
    preserve_thinking_turns=int(os.getenv("LLM_MCP_PRESERVE_THINKING", "999")),
)

server = Server("local-coding-agent")


# ── Audit logging ──────────────────────────────────────────────────────────────

def _cleanup_stale(log: Path) -> None:
    if not log.exists():
        return
    lines = log.read_text(encoding="utf-8").splitlines(keepends=True)
    if len(lines) <= 200:
        return
    cutoff = int(time.time()) - 48 * 3600
    kept = [
        l for l in lines
        if (p := l.split("\t")) and p[0].strip().isdigit() and int(p[0]) > cutoff
    ]
    if len(kept) < len(lines):
        log.write_text("".join(kept), encoding="utf-8")


def _log_edit(log_dir: Path, session_id: str, file_path: str) -> None:
    log = log_dir / "phase-run-edits.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{int(time.time())}\t{session_id}\twrite_file\t{file_path}\n")
    _cleanup_stale(log)


def _register_session(log_dir: Path, session_id: str, phase: int, run_id: str) -> None:
    log = log_dir / "phase-run-sessions.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"{int(time.time())}\t{session_id}\t{phase}\t{run_id}\n")
    _cleanup_stale(log)


def _make_exec_tool(log_dir: Path | None, session_id: str):
    """Returns exec_tool variant that logs write_file calls when log_dir is set."""
    if log_dir is None:
        return _base_exec_tool

    def _logged(name: str, raw_arguments: str) -> str:
        result_str = _base_exec_tool(name, raw_arguments)
        if name == "write_file":
            try:
                if json.loads(result_str).get("ok"):
                    path = json.loads(raw_arguments or "{}").get("path", "")
                    if path:
                        _log_edit(log_dir, session_id, str(Path(path).expanduser().resolve()))
            except Exception:
                pass
        return result_str

    return _logged


# ── Prompt builder ─────────────────────────────────────────────────────────────

_WORKER_PROMPT_TEMPLATE = (
    Path(__file__).parent / "qwen_worker_prompt.md"
).read_text(encoding="utf-8")


def _build_prompt(phase_file: str | None, prompt: str) -> str:
    if not phase_file:
        return prompt
    extra = f"\n추가 지시사항:\n{prompt}" if prompt else ""
    return (
        _WORKER_PROMPT_TEMPLATE
        .replace("__PHASE_FILE__", phase_file)
        .replace("__EXTRA_PROMPT__", extra)
    )


# ── MCP tool definition ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="run_coding_agent",
            description=(
                f"Delegate a coding task to the local LLM ({CFG.model}) "
                "running via mlx-openai-server. "
                "The agent autonomously uses read_file, write_file, list_dir, and bash "
                "to implement the task and returns a summary of what was done. "
                "Use phase_file to pass a phase spec (recommended for phase-run); "
                "use prompt alone for free-form tasks."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "Coding task or additional instructions. "
                            "When phase_file is provided, this supplements the spec. "
                            "When used alone, include file paths, what to implement, and constraints."
                        ),
                    },
                    "phase_file": {
                        "type": "string",
                        "description": (
                            "Absolute path to the phase spec MD file (phase-NN-*.md). "
                            "When provided, Qwen reads the spec directly — no context compression. "
                            "Recommended for all phase-run delegations."
                        ),
                    },
                    "phase": {
                        "type": "integer",
                        "description": "phase-run phase number (for Scope Audit). Omit outside phase-run.",
                    },
                    "run_id": {
                        "type": "string",
                        "description": "phase-run RUN_ID (for Scope Audit). Omit outside phase-run.",
                    },
                    "project_dir": {
                        "type": "string",
                        "description": "Absolute project root (for Scope Audit). Omit outside phase-run.",
                    },
                },
                "required": [],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name != "run_coding_agent":
        raise ValueError(f"Unknown tool: {name}")

    prompt = arguments.get("prompt", "")
    phase_file = arguments.get("phase_file")
    phase = arguments.get("phase")
    run_id = arguments.get("run_id")
    project_dir = arguments.get("project_dir")

    if not prompt and not phase_file:
        return [TextContent(type="text", text="ERROR: prompt 또는 phase_file 중 하나는 필요합니다.")]

    final_prompt = _build_prompt(phase_file, prompt)

    log_dir: Path | None = None
    mcp_session_id = f"mcp-llm-{uuid.uuid4().hex[:12]}"

    if phase is not None and run_id and project_dir:
        candidate = Path(project_dir) / ".claude"
        if candidate.exists():
            log_dir = candidate
            _register_session(log_dir, mcp_session_id, phase, run_id)

    exec_fn = _make_exec_tool(log_dir, mcp_session_id)

    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: run_agent(final_prompt, cfg=CFG, exec_tool_fn=exec_fn)
    )

    if not result.get("ok"):
        return [TextContent(type="text", text=f"ERROR: {result.get('error', 'unknown')}")]

    tool_msgs = [m for m in result.get("messages", []) if m.get("role") == "tool"]
    tools_used = [m.get("name") for m in tool_msgs]

    output = f"completed | turns={result.get('turns', '?')} | tools={tools_used}\n\n"
    output += result.get("final") or ""
    return [TextContent(type="text", text=output)]


# ── Entry point ────────────────────────────────────────────────────────────────

_WATCHDOG_URL = os.getenv("QWEN_WATCHDOG_URL", "")


def _ensure_server_running() -> None:
    """Start the LLM inference server if it is not responding.

    Two modes:
    - Local (Mac):  LLM_MCP_AUTOSTART_SCRIPT → bash script runs dflash in background.
    - Remote (WSL): QWEN_WATCHDOG_URL → POST /start to watchdog on Mac via Tailscale.
                    The POST blocks until dflash is up (max ~120 s) or returns 503.
    """
    import subprocess
    import sys
    from urllib import request as urlreq

    url = CFG.base_url.rstrip("/").removesuffix("/v1") + "/health"
    try:
        urlreq.urlopen(url, timeout=2)
        return  # already up
    except Exception:
        pass

    # ── Remote watchdog (WSL → Mac Tailscale) ──────────────────────────────
    if _WATCHDOG_URL:
        print(
            f"[mcp_server] dflash not responding at {url}. "
            f"Triggering watchdog at {_WATCHDOG_URL}/start …",
            file=sys.stderr,
        )
        try:
            resp = urlreq.urlopen(
                urlreq.Request(_WATCHDOG_URL + "/start", data=b"", method="POST"),
                timeout=130,
            )
            body = resp.read().decode()
            print(f"[mcp_server] watchdog responded: {body}", file=sys.stderr)
        except Exception as e:
            print(f"[mcp_server] watchdog call failed: {e}", file=sys.stderr)
        return

    # ── Local auto-start (Mac, via script) ─────────────────────────────────
    script_env = os.getenv("LLM_MCP_AUTOSTART_SCRIPT", "")
    if not script_env:
        print(
            f"[mcp_server] WARNING: {url} not responding. "
            "Set LLM_MCP_AUTOSTART_SCRIPT or QWEN_WATCHDOG_URL to enable auto-start.",
            file=sys.stderr,
        )
        return

    script = Path(script_env)
    if not script.is_absolute():
        script = Path(__file__).parent.parent / script_env
    if not script.exists():
        print(f"[mcp_server] WARNING: autostart script not found: {script}", file=sys.stderr)
        return

    port = CFG.base_url.rstrip("/").rsplit(":", 1)[-1].split("/")[0]
    log_path = f"/tmp/llm-autostart-{port}.log"
    log = open(log_path, "a")
    subprocess.Popen(["bash", str(script)], stdout=log, stderr=log, start_new_session=True)
    print(f"[mcp_server] auto-starting server via {script.name} → {log_path}", file=sys.stderr)


async def _main() -> None:
    await asyncio.get_event_loop().run_in_executor(None, _ensure_server_running)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
