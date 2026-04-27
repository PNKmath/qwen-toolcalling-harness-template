#!/usr/bin/env python3
"""
Watchdog server — dflash on-demand starter.

Runs on Mac, always-on via launchd (port 8017, 0.0.0.0).
WSL mcp_server.py calls POST /start via Tailscale when dflash is down.
The call blocks until dflash is up or timeout.
"""
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib import request as urlreq

DFLASH_HEALTH = os.getenv("DFLASH_HEALTH_URL", "http://127.0.0.1:8016/health")
START_SCRIPT   = Path(__file__).parent / "start_dflash_server.sh"
HOST           = os.getenv("WATCHDOG_HOST", "0.0.0.0")
PORT           = int(os.getenv("WATCHDOG_PORT", "8017"))
START_TIMEOUT  = int(os.getenv("WATCHDOG_START_TIMEOUT", "120"))

_lock    = threading.Lock()
_running = False  # True while we're in the middle of starting dflash


def _is_alive(timeout: int = 3) -> bool:
    try:
        urlreq.urlopen(DFLASH_HEALTH, timeout=timeout)
        return True
    except Exception:
        return False


def _trigger_start_bg() -> None:
    """Fire-and-forget: launch dflash in a background thread if not already starting."""
    global _running
    with _lock:
        if _running or _is_alive():
            return
        _running = True

    def _worker():
        global _running
        try:
            env = os.environ.copy()
            env["QWEN_HOST"] = "0.0.0.0"
            log = open("/tmp/dflash-watchdog.log", "a")
            subprocess.Popen(
                ["bash", str(START_SCRIPT)],
                env=env,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            print("[watchdog] dflash start triggered (bg)", file=sys.stderr)
            for _ in range(START_TIMEOUT):
                time.sleep(1)
                if _is_alive():
                    print("[watchdog] dflash is up", file=sys.stderr)
                    return
            print("[watchdog] dflash start timed out", file=sys.stderr)
        finally:
            global _running
            with _lock:
                _running = False

    threading.Thread(target=_worker, daemon=True).start()


def _start_and_wait() -> str:
    """Start dflash (0.0.0.0), block until healthy. Returns 'started'|'already_running'|'timeout'."""
    if _is_alive():
        return "already_running"
    _trigger_start_bg()  # kicks off if not already running
    for _ in range(START_TIMEOUT):
        time.sleep(1)
        if _is_alive():
            return "started"
    return "timeout"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress access logs
        pass

    def _send_json(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            alive = _is_alive()
            if not alive and START_SCRIPT.exists():
                # 꺼져 있으면 백그라운드 시작 트리거 (응답은 즉시)
                _trigger_start_bg()
            self._send_json(200, {"watchdog": "ok", "dflash": alive, "starting": _running})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/start":
            if not START_SCRIPT.exists():
                self._send_json(500, {"error": f"start script not found: {START_SCRIPT}"})
                return
            status = _start_and_wait()
            code = 200 if status != "timeout" else 503
            self._send_json(code, {"status": status})
        else:
            self._send_json(404, {"error": "not found"})


if __name__ == "__main__":
    if not START_SCRIPT.exists():
        print(f"[watchdog] ERROR: start script not found: {START_SCRIPT}", file=sys.stderr)
        sys.exit(1)
    print(f"[watchdog] listening on {HOST}:{PORT}  dflash={DFLASH_HEALTH}", file=sys.stderr)
    server = HTTPServer((HOST, PORT), Handler)
    server.serve_forever()
