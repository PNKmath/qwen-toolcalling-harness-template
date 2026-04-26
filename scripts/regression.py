#!/usr/bin/env python3
from harness.runner import pretty_json, run_case

CASES = [
    {
        "name": "add_numbers tool",
        "type": "tool_expected",
        "prompt": "12.5와 7.5를 더해줘. 계산은 반드시 도구를 사용해.",
    },
    {
        "name": "weather tool",
        "type": "tool_expected",
        "prompt": "서울 날씨를 조회해줘. 도구를 사용해.",
    },
    {
        "name": "search_docs tool",
        "type": "tool_expected",
        "prompt": "tool calling 핵심 포인트를 문서에서 찾아줘. 도구 사용.",
    },
    {
        "name": "no-tool simple text",
        "type": "no_tool_expected",
        "prompt": "안녕이라고 한 문장으로만 답해. 도구는 사용하지 마.",
    },
]


def main() -> None:
    rows = [run_case(c) for c in CASES]
    passed = sum(1 for r in rows if r["passed"])
    summary = {
        "total": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3),
        "cases": [
            {"name": r["name"], "passed": r["passed"], "used_tool": r["used_tool"]}
            for r in rows
        ],
    }
    print(pretty_json(summary))


if __name__ == "__main__":
    main()
