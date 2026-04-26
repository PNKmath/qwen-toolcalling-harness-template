# Tool Call Normalizer — API 레퍼런스

`harness/toolcall_normalizer.py` 모듈의 타입과 함수를 정리합니다.

---

## 모듈 위치

```
harness/
  toolcall_normalizer.py   # 이 모듈
tests/
  test_toolcall_normalizer.py  # 단위 테스트 32개
```

---

## 타입

### `ToolCallNormalized`

```python
class ToolCallNormalized(TypedDict):
    id: str          # "call_xxx" (standard) 또는 "fallback-{uuid hex}" (fallback)
    name: str        # 함수명 (예: "add_numbers")
    arguments: str   # JSON 문자열 — exec_tool()에 그대로 전달
```

### `NormalizeResult`

```python
class NormalizeResult(TypedDict):
    tool_calls: List[ToolCallNormalized]  # 빈 리스트 = 도구 호출 없음
    clean_content: Optional[str]          # 첫 <tool_call> 이전 텍스트, 없으면 None
    source: str                           # "standard" | "fallback" | "none"
```

---

## 공개 함수

### `normalize_tool_calls_from_message(msg)`

메시지 객체 또는 dict를 받아 통일된 `NormalizeResult`를 반환합니다.

```python
def normalize_tool_calls_from_message(msg: Any) -> NormalizeResult
```

**우선순위**:
1. `msg.tool_calls` (또는 `msg["tool_calls"]`)가 있으면 → `source="standard"`
2. `msg.content`에 `<tool_call>` 태그가 있으면 → `source="fallback"`
3. 둘 다 없으면 → `source="none"`, `tool_calls=[]`

**에러 처리**: 모든 예외를 catch해 `source="none"` 결과를 반환합니다. 예외를 전파하지 않습니다.

**dict와 객체 모두 지원**:
```python
# OpenAI SDK 객체
norm = normalize_tool_calls_from_message(resp.choices[0].message)

# raw dict (tool_harness_qwen36.py 스타일)
norm = normalize_tool_calls_from_message({"tool_calls": [...], "content": "..."})
```

---

### `extract_fallback_tool_calls(content)`

content 문자열에서 `<tool_call>` 태그를 파싱해 `ToolCallNormalized` 리스트를 반환합니다.

```python
def extract_fallback_tool_calls(content: str) -> List[ToolCallNormalized]
```

파싱에 실패하거나 태그가 없으면 빈 리스트를 반환합니다.

**지원하는 태그 형식 (qwen3_coder)**:

```
<tool_call>
<function=function_name>
<parameter=param_name>value</parameter>
<parameter=param_name2>value2</parameter>
</function>
</tool_call>
```

**엣지 케이스 처리**:

| 상황 | 동작 |
|------|------|
| `</tool_call>` 없음 (스트리밍 중단) | EOF까지 파싱 |
| `</function>` 없음 | EOF까지 파싱 |
| `</parameter>` 없음 | 다음 `<parameter=` 또는 `</function>` 위치까지를 값으로 사용 |
| 복수 `<tool_call>` 블록 | 순서대로 모두 추출 |
| 함수명에 `>` 없음 | 해당 블록 skip, 에러 전파 없음 |

**파라미터 값 타입 변환**:

`null` → `None`, 그 외 JSON parse → `ast.literal_eval` → string 순서로 시도합니다.

```python
# 예: <parameter=count>3</parameter>  →  3 (int)
# 예: <parameter=flag>true</parameter>  →  True (bool via JSON)
# 예: <parameter=name>hello</parameter>  →  "hello" (str)
```

---

## 내부 함수

### `_try_convert_value(value: str) -> Any`

파라미터 값 문자열을 Python 네이티브 타입으로 변환합니다. `null` → `None`, JSON parse → `ast.literal_eval` → string 순서.

### `_parse_function_block(function_str: str) -> Optional[ToolCallNormalized]`

단일 `<function=name>...</function>` 블록을 파싱합니다. 실패 시 `None` 반환.

---

## runner.py 통합 방식

```python
# harness/runner.py 내부 (단순화)
from .toolcall_normalizer import normalize_tool_calls_from_message

norm = normalize_tool_calls_from_message(msg)

if norm["tool_calls"]:
    assistant_message["tool_calls"] = [
        {"id": tc["id"], "type": "function",
         "function": {"name": tc["name"], "arguments": tc["arguments"]}}
        for tc in norm["tool_calls"]
    ]
    for tc in norm["tool_calls"]:
        result = exec_tool(tc["name"], tc["arguments"])
        messages.append({"role": "tool", "tool_call_id": tc["id"], ...})
```

`source`에 관계없이 동일한 코드 경로를 탑니다. `tc["id"]`가 assistant_message의 `tool_calls[].id`와 role:tool의 `tool_call_id`를 연결합니다.

---

## 테스트 작성

```python
from harness.toolcall_normalizer import normalize_tool_calls_from_message

# 표준 경로 테스트 (dict 스타일)
def test_standard():
    msg = {
        "tool_calls": [
            {"id": "call_abc", "function": {"name": "add_numbers", "arguments": '{"a": 1, "b": 2}'}}
        ],
        "content": None,
    }
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "standard"
    assert result["tool_calls"][0]["name"] == "add_numbers"

# fallback 경로 테스트
def test_fallback():
    class MockMsg:
        tool_calls = None
        content = "<tool_call><function=add_numbers><parameter=a>1</parameter><parameter=b>2</parameter></function></tool_call>"

    result = normalize_tool_calls_from_message(MockMsg())
    assert result["source"] == "fallback"
    assert result["tool_calls"][0]["name"] == "add_numbers"

# no-tool 테스트
def test_no_tool():
    msg = {"tool_calls": None, "content": "안녕하세요."}
    result = normalize_tool_calls_from_message(msg)
    assert result["source"] == "none"
    assert result["tool_calls"] == []
```

더 많은 예시는 `tests/test_toolcall_normalizer.py` 참고 (32개 케이스).

---

## 새 포맷 추가

다른 모델의 포맷을 지원해야 한다면 `extract_fallback_tool_calls()`를 수정하거나, 새 파서 함수를 추가한 뒤 `normalize_tool_calls_from_message()` 내부의 fallback 분기에서 호출하세요.

현재 지원: **qwen3_coder** 포맷만. 다른 포맷(Hermes JSON 인라인, Functionary 등)은 실제 모델을 연결하고 raw 출력을 확인한 뒤 추가하는 것을 권장합니다 — 검증 없는 파서는 dead code가 됩니다.
