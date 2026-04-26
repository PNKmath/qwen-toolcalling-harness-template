import json
from typing import Any, Callable


def add_numbers(a: float, b: float) -> dict[str, float]:
    return {"result": a + b}


def get_weather(city: str) -> dict[str, str]:
    # 실제 외부 API 대신 데모용 mock
    return {"city": city, "weather": "sunny", "temp_c": "23"}


def search_docs(query: str) -> dict[str, list[str]]:
    docs = [
        "Tool calling은 함수 이름/인자 JSON 스키마 일치가 핵심",
        "No-tool 케이스를 반드시 회귀 테스트에 포함",
        "max_turns와 timeout을 명시적으로 제한",
    ]
    hits = [d for d in docs if query.lower() in d.lower()]
    return {"hits": hits or docs[:1]}


TOOL_IMPLS: dict[str, Callable[..., dict[str, Any]]] = {
    "add_numbers": add_numbers,
    "get_weather": get_weather,
    "search_docs": search_docs,
}


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "두 숫자를 더한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "도시의 날씨를 조회한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "내부 문서를 검색한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
        },
    },
]


def exec_tool(name: str, raw_arguments: str) -> str:
    if name not in TOOL_IMPLS:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"invalid tool args json: {str(e)}"}, ensure_ascii=False)

    try:
        result = TOOL_IMPLS[name](**args)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:  # noqa
        return json.dumps({"error": str(e)}, ensure_ascii=False)
