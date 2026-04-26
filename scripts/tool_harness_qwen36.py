#!/usr/bin/env python3
import argparse
import json
import os
import time
from urllib import request, error


def post_json(url: str, payload: dict, timeout: int = 120):
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace"), time.time() - t0
    except error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), time.time() - t0
    except Exception as e:
        return -1, str(e), time.time() - t0


def run_case(base_url: str, model: str, case: dict, preserve_thinking: bool = False):
    chat_template_kwargs = {"enable_thinking": True}
    # NOTE: current local mlx-openai-server (v1.7.1 observed) logs preserve_thinking as ignored.
    # Keep it opt-in for future compatibility checks.
    if preserve_thinking:
        chat_template_kwargs["preserve_thinking"] = True

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": case["prompt"]}],
        "tools": case["tools"],
        "tool_choice": case.get("tool_choice", "auto"),
        "temperature": 0.6,
        "presence_penalty": 0.0,
        "max_tokens": 256,
        "chat_template_kwargs": chat_template_kwargs,
    }

    status, body, elapsed = post_json(base_url.rstrip("/") + "/chat/completions", payload, timeout=120)
    rec = {"case": case["name"], "status": status, "elapsed_sec": round(elapsed, 3)}
    if status != 200:
        rec["pass"] = False
        rec["error"] = body[:400]
        return rec

    try:
        parsed = json.loads(body)
    except Exception:
        rec["pass"] = False
        rec["error"] = "invalid_json_response"
        rec["raw"] = body[:400]
        return rec

    msg = parsed.get("choices", [{}])[0].get("message", {})
    tool_calls = msg.get("tool_calls") or []
    names = [tc.get("function", {}).get("name") for tc in tool_calls]
    rec["tool_calls"] = names

    expected = case.get("expect_tool")
    if expected is None:
        ok = len(tool_calls) == 0
    else:
        ok = expected in names
        if ok:
            # validate argument JSON
            try:
                for tc in tool_calls:
                    if tc.get("function", {}).get("name") == expected:
                        json.loads(tc.get("function", {}).get("arguments", "{}"))
            except Exception:
                ok = False

    rec["pass"] = ok
    rec["usage"] = parsed.get("usage", {})
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preserve-thinking", action="store_true", help="Send chat_template_kwargs.preserve_thinking=true")
    args = ap.parse_args()

    shared_tools = [
        {
            "type": "function",
            "function": {
                "name": "add_numbers",
                "description": "Add two integers",
                "parameters": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                    "required": ["a", "b"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather by city",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_docs",
                "description": "Search docs for keyword",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
    ]

    cases = [
        {"name": "math_add", "prompt": "Use tool add_numbers with a=12, b=30. Do not compute directly.", "tools": shared_tools, "expect_tool": "add_numbers"},
        {"name": "weather_seoul", "prompt": "Use get_weather for Seoul first.", "tools": shared_tools, "expect_tool": "get_weather"},
        {"name": "docs_query", "prompt": "Find docs about 'parser flags'. Use search_docs tool.", "tools": shared_tools, "expect_tool": "search_docs"},
        {"name": "no_tool_smalltalk", "prompt": "Say hello in one short sentence.", "tools": shared_tools, "expect_tool": None},
    ]

    results = [run_case(args.base_url, args.model, c, preserve_thinking=args.preserve_thinking) for c in cases]
    passed = sum(1 for r in results if r.get("pass"))

    report = {
        "endpoint": args.base_url,
        "model": args.model,
        "settings": {
            "reasoning_parser": "qwen3 (server launch)",
            "tool_call_parser": "qwen3_coder (server launch)",
            "temperature": 0.6,
            "presence_penalty": 0.0,
            "chat_template_kwargs": {"enable_thinking": True, "preserve_thinking": bool(args.preserve_thinking)},
        },
        "summary": {
            "total": len(results),
            "passed": passed,
            "pass_rate": round(passed / len(results), 3),
        },
        "results": results,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
