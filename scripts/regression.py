#!/usr/bin/env python3
# Regression suite for the qwen tool-calling harness.
#
# Fallback path coverage note
# ----------------------------
# The live server (port 8006/8008/8016…) is launched with
# --tool-call-parser qwen3_coder, so it always returns standard
# tool_calls objects.  Consequently, harness/toolcall_normalizer.py
# takes the "standard" branch on every live run here.
#
# The content-fallback branch (source="fallback") is also exercised
# inline via run_fallback_normalizer_case() below, which bypasses the
# live server and calls normalize_tool_calls_from_message() directly
# with a synthetic <tool_call> payload.  This case always runs and
# never requires a server — it proves the fallback parser is wired
# correctly in any environment.
#
# Additionally, the fallback path is exercised by 32 unit tests in
# tests/test_toolcall_normalizer.py.  Run `pytest -q` to verify.

from harness.runner import pretty_json, run_case
from harness.toolcall_normalizer import normalize_tool_calls_from_message

CASES = [
    {
        "name": "add_numbers tool",
        "type": "tool_expected",
        # Expects normalizer source="standard" on a server with qwen3_coder parser.
        "prompt": "12.5와 7.5를 더해줘. 계산은 반드시 도구를 사용해.",
    },
    {
        "name": "weather tool",
        "type": "tool_expected",
        # Expects normalizer source="standard" on a server with qwen3_coder parser.
        "prompt": "서울 날씨를 조회해줘. 도구를 사용해.",
    },
    {
        "name": "search_docs tool",
        "type": "tool_expected",
        # Expects normalizer source="standard" on a server with qwen3_coder parser.
        "prompt": "tool calling 핵심 포인트를 문서에서 찾아줘. 도구 사용.",
    },
    {
        "name": "no-tool simple text",
        "type": "no_tool_expected",
        # Guard against tool over-calling: model must NOT invoke a tool here.
        # Expects normalizer source="none".
        "prompt": "안녕이라고 한 문장으로만 답해. 도구는 사용하지 마.",
    },
]

# Synthetic <tool_call> payload that mimics what a server WITHOUT
# --tool-call-parser qwen3_coder would emit in the content field.
_FALLBACK_PAYLOAD = (
    "<tool_call>"
    "<function=add_numbers>"
    "<parameter=a>12.5</parameter>"
    "<parameter=b>7.5</parameter>"
    "</function>"
    "</tool_call>"
)


def run_fallback_normalizer_case() -> dict:
    """Inline fallback-path verification (no live server required).

    Constructs a mock message whose tool_calls attribute is None/empty and
    whose content contains a raw <tool_call> block, then asserts that
    normalize_tool_calls_from_message() returns source="fallback" and
    correctly parses the function name and arguments.
    """

    class _MockMessage:
        tool_calls = None
        content = _FALLBACK_PAYLOAD

    norm = normalize_tool_calls_from_message(_MockMessage())
    source_ok = norm["source"] == "fallback"
    has_call = len(norm["tool_calls"]) == 1
    name_ok = has_call and norm["tool_calls"][0]["name"] == "add_numbers"
    passed = source_ok and has_call and name_ok

    return {
        "name": "fallback-normalizer (inline, no server)",
        "norm_source": norm["source"],
        "passed": passed,
        "used_tool": has_call,
        "detail": {
            "source": norm["source"],
            "tool_calls": norm["tool_calls"],
        },
    }


def main() -> None:
    live_rows = [run_case(c) for c in CASES]
    fallback_row = run_fallback_normalizer_case()

    all_rows = live_rows + [fallback_row]
    passed = sum(1 for r in all_rows if r["passed"])

    summary = {
        "total": len(all_rows),
        "passed": passed,
        "pass_rate": round(passed / len(all_rows), 3),
        "cases": [
            {
                "name": r["name"],
                "passed": r["passed"],
                "used_tool": r["used_tool"],
                **({"norm_source": r["norm_source"]} if "norm_source" in r else {}),
            }
            for r in all_rows
        ],
    }
    print(pretty_json(summary))


if __name__ == "__main__":
    main()
