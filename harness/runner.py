import json
from typing import Any

from openai import OpenAI

from .config import HarnessConfig
from .toolcall_normalizer import normalize_tool_calls_from_message
from .tools import TOOLS_SPEC, exec_tool


def _client(cfg: HarnessConfig) -> OpenAI:
    return OpenAI(base_url=cfg.base_url, api_key=cfg.api_key, timeout=cfg.request_timeout)


def run_agent(user_prompt: str, cfg: HarnessConfig | None = None) -> dict[str, Any]:
    cfg = cfg or HarnessConfig()
    client = _client(cfg)

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

    for turn in range(1, cfg.max_turns + 1):
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            tools=TOOLS_SPEC,
            tool_choice="auto",
            temperature=0.2,
            chat_template_kwargs={"enable_thinking": False, "reasoning_effort": "low"},
        )
        msg = resp.choices[0].message
        norm = normalize_tool_calls_from_message(msg)

        content = norm["clean_content"] or msg.content or ""
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": content,
        }

        if norm["tool_calls"]:
            assistant_message["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["arguments"]},
                }
                for tc in norm["tool_calls"]
            ]
            messages.append(assistant_message)

            for tc in norm["tool_calls"]:
                result = exec_tool(tc["name"], tc["arguments"])
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": tc["name"],
                        "content": result,
                    }
                )
            continue

        messages.append(assistant_message)
        return {
            "ok": True,
            "turns": turn,
            "final": norm["clean_content"] or msg.content,
            "messages": messages,
            "usage": resp.usage.model_dump() if resp.usage else None,
        }

    return {
        "ok": False,
        "error": f"max_turns_exceeded({cfg.max_turns})",
        "messages": messages,
    }


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    result = run_agent(case["prompt"])
    text = (result.get("final") or "").lower() if result.get("ok") else ""

    if case["type"] == "tool_expected":
        used_tool = any(m.get("role") == "tool" for m in result.get("messages", []))
        passed = bool(result.get("ok")) and used_tool
    else:  # no_tool_expected
        used_tool = any(m.get("role") == "tool" for m in result.get("messages", []))
        passed = bool(result.get("ok")) and (not used_tool)

    return {
        "name": case["name"],
        "passed": passed,
        "used_tool": used_tool,
        "result": result,
    }


def pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
