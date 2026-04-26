# Tool Call Normalizer — 운영 가이드

하네스가 `<tool_call>` 태그 방식과 표준 OpenAI `tool_calls` 방식을 모두 처리하는 방법과, 각 서버 설정에서 어떻게 동작하는지 설명합니다.

---

## 왜 필요한가

Qwen3-Coder 계열 모델은 서버 설정에 따라 tool call을 두 가지 형태로 반환합니다.

| 서버 설정 | 응답 형태 | 하네스 처리 |
|----------|-----------|------------|
| `--tool-call-parser qwen3_coder` 있음 | 표준 `tool_calls` 객체 | `source=standard` |
| parser 없음 또는 파싱 실패 | content 안에 `<tool_call>` 태그 | `source=fallback` |
| 도구 미사용 응답 | 일반 텍스트 | `source=none` |

`harness/runner.py`는 `normalize_tool_calls_from_message()`를 경유하여 두 경로를 동일하게 처리합니다. 서버를 바꿔도 하네스 코드를 수정할 필요가 없습니다.

---

## 서버 설정

### 권장 설정 (parser 활성화)

```bash
mlx-openai-server launch \
  --reasoning-parser qwen3 \
  --tool-call-parser qwen3_coder \
  --enable-auto-tool-choice \
  ...
```

이 경우 서버가 `<tool_call>` 태그를 파싱해 표준 `tool_calls` 객체로 변환합니다. 하네스는 `source=standard` 경로를 탑니다.

### parser 없는 설정

```bash
mlx-openai-server launch ...  # --tool-call-parser 없음
```

서버가 raw content를 그대로 반환합니다. 하네스의 fallback 파서가 `<tool_call>` 태그를 직접 파싱합니다. `source=fallback` 경로를 탑니다.

---

## 실행 방법

### 단일 프롬프트 테스트

```bash
python scripts/chat_once.py "12.5와 7.5를 더해줘. 도구를 사용해."
```

### 회귀 스위트 실행 (live 서버 필요)

```bash
python scripts/regression.py
```

출력 예시:
```json
{
  "total": 5,
  "passed": 5,
  "pass_rate": 1.0,
  "cases": [
    {"name": "add_numbers tool", "passed": true, "used_tool": true},
    {"name": "fallback-normalizer (inline, no server)", "passed": true, "used_tool": true, "norm_source": "fallback"}
  ]
}
```

`fallback-normalizer (inline, no server)` 케이스는 live 서버 없이도 항상 실행되어 fallback 파서가 올바르게 연결됐는지 확인합니다.

### 단위 테스트 (서버 불필요)

```bash
uv run --python 3.11 --with pytest python -m pytest -q
# 또는 normalizer만:
uv run --python 3.11 --with pytest python -m pytest -q tests/test_toolcall_normalizer.py
```

35개 테스트 (normalizer 32 + tool_exec 3). 서버 없이 두 경로를 모두 검증합니다.

### HTTP 벤치마크 (서버 수준 파싱 테스트)

```bash
python scripts/tool_harness_qwen36.py \
  --base-url http://127.0.0.1:8006/v1 \
  --model Qwen3.6-27B-UD-MLX-4bit \
  --out reports/tool_harness_qwen36.json
```

이 스크립트는 SDK를 우회해 raw HTTP로 서버를 직접 호출합니다. 결과에 `tool_call_source` 필드가 포함됩니다.

---

## 출력 결과 읽기

### `source` 필드 의미

`normalize_tool_calls_from_message()`의 반환값 `source` 필드로 어느 경로를 사용했는지 확인합니다.

- `"standard"` — 서버가 tool_calls를 파싱했음. parser가 활성화된 정상 환경.
- `"fallback"` — 서버가 content에 `<tool_call>` 태그를 그대로 반환했고 하네스가 파싱했음.
- `"none"` — 도구 호출 없음.

### `tool_harness_qwen36.py` 결과의 `tool_call_source`

```json
{
  "tool_call_source": "standard (server-parsed)"
}
```

parser가 활성화된 서버라면 항상 `"standard (server-parsed)"`. parser 없는 서버에서는 `"none"` (서버가 tool_calls 객체 없이 content만 반환하기 때문).

---

## 트러블슈팅

### 도구가 실행되지 않음 (used_tool=false)

1. 서버가 `tool_calls`를 반환하는지 확인:
   ```bash
   curl -s http://127.0.0.1:8006/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model":"...","messages":[{"role":"user","content":"1+1은?"}],"tools":[...]}' \
     | python3 -m json.tool | grep -A5 tool_calls
   ```

2. parser 없는 서버라면 content에 `<tool_call>` 태그가 있는지 확인. 있으면 하네스가 fallback으로 처리해야 합니다.

3. fallback 파서가 동작하는지 확인:
   ```python
   from harness.toolcall_normalizer import extract_fallback_tool_calls
   content = "<tool_call><function=add_numbers><parameter=a>1</parameter><parameter=b>2</parameter></function></tool_call>"
   print(extract_fallback_tool_calls(content))
   ```

### fallback 파싱은 됐지만 인자가 비어있음

`<parameter=key>value</parameter>` 형식인지 확인하세요. 다음은 파싱에 실패합니다:
- JSON 인라인 형식: `<tool_call>{"function":"...","arguments":{...}}</tool_call>` — 지원 안 함
- `</parameter>` 닫힘 태그가 완전히 없는 경우 (다음 `<parameter=` 또는 `</function>`으로 경계를 감지하므로 보통 동작함)

### Python 3.9 venv에서 import 오류

`harness/runner.py`는 `X | Y` 유니온 구문(Python 3.10+)을 사용합니다. Python 3.11 이상에서 실행하거나 uv를 사용하세요:
```bash
uv run --python 3.11 --with pytest python -m pytest -q
```
