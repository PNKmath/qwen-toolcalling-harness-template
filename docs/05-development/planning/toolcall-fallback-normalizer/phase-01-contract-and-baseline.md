---
phase: 1
title: 현재 tool_call 계약 정리 및 baseline 고정
status: completed
depends_on: []
scope:
  - harness/runner.py
  - scripts/tool_harness_qwen36.py
  - scripts/regression.py
  - tests/test_tool_exec.py
intervention_likely: false
intervention_reason: "읽기/계약 정리 중심으로 코드 변경 없음"
---

# Phase 1: 현재 tool_call 계약 정리 및 baseline 고정

> 범위: 기존 호출/검증 경로를 명시화해 fallback 도입 기준선 확보
> 난이도: 낮음
> 의존성: 없음
> 영향 파일: harness/runner.py, scripts/tool_harness_qwen36.py, scripts/regression.py

## 배경

현재 하네스는 `msg.tool_calls`가 채워진 경우만 도구 실행 루프를 돈다. 로컬 Qwen 계열에서 `<tool_call>`이 content로 내려오는 변형이 있으므로, 기존 계약(입력/출력/검증)을 먼저 문서화해야 이후 phase에서 회귀를 안전하게 관리할 수 있다.

## 심볼 인벤토리

- `run_agent`
  - 근거: harness/runner.py:14
- `msg.tool_calls`
  - 근거: harness/runner.py:36
- `run_case`
  - 근거: scripts/tool_harness_qwen36.py:26
- `tool_calls = msg.get("tool_calls") or []`
  - 근거: scripts/tool_harness_qwen36.py:60
- `CASES`
  - 근거: scripts/regression.py:4
- `exec_tool`
  - 근거: harness/tools.py:78

## 설계

- baseline 계약 문서화
  - 표준 경로: OpenAI `tool_calls`
  - 비표준 경로: content 태그형 `<tool_call>` (아직 미지원)
- acceptance criteria
  - 기존 4개 회귀 케이스 결과 보존
  - fallback 도입 후에도 no-tool 케이스 오탐 금지

## 체크리스트

- [x] runner/tool_harness/regression의 현재 분기 조건 기록
- [x] `tool_calls`가 없는 경우 현재 종료 동작 명시
- [x] no-tool 케이스 판단식(`used_tool`) 현 상태 확인
- [x] phase-02 입력 계약(정규화 함수 I/O) 초안 작성
- [x] baseline 검증 명령/기대 결과 문서화

## 현재 분기 조건 기록 (체크리스트 항목 1–3 근거)

### harness/runner.py — `run_agent()`

```
판단식 (runner.py:36): if msg.tool_calls:
  - True  → exec_tool 루프 진입, role:tool 메시지 append, continue
  - False → assistant 메시지 append 후 ok:True 반환
  최대 반복: cfg.max_turns (기본 6), 초과 시 ok:False + error:"max_turns_exceeded(N)"
```

**tool_calls 부재 시 종료 동작**:
- `msg.tool_calls`가 None/빈 리스트인 경우 즉시 반환
  ```python
  return {"ok": True, "turns": turn, "final": msg.content, "messages": messages, "usage": ...}
  ```
- content 태그형 `<tool_call>` 이 msg.content 에 있어도 **무시됨** — 이것이 fallback이 필요한 근거

### scripts/tool_harness_qwen36.py — `run_case()`

```
판단식 (tool_harness_qwen36.py:60): tool_calls = msg.get("tool_calls") or []
  - 비어 있으면(또는 None) → expect_tool=None 이면 pass, 아니면 fail
  - 채워져 있으면 → expect_tool 일치 + arguments JSON 파싱 성공 시 pass
```

이 스크립트는 SDK를 거치지 않고 raw HTTP dict를 파싱하므로, 서버 수준의 `tool_call_parser` 출력을 직접 검사한다.

### scripts/regression.py — `run_case()` (harness.runner 위임)

```
판단식 (runner.py:73–77):
  tool_expected    → used_tool = any(m["role"]=="tool" ...)  +  ok → passed
  no_tool_expected → not used_tool  +  ok → passed
```

**`used_tool` 현 상태**: `role=="tool"` 메시지 존재 여부로만 판정.
- content에 `<tool_call>` 태그가 오더라도 exec_tool이 호출되지 않으므로 `used_tool=False` → no_tool 케이스는 오탐 없음.
- 반면 tool_expected 케이스는 실제 tool_calls 없으면 `used_tool=False` → 미탐.

### 4개 회귀 케이스 (scripts/regression.py:4–25)

| 이름 | 타입 | 기대 |
|------|------|------|
| add_numbers tool | tool_expected | exec_tool("add_numbers", ...) 호출됨 |
| weather tool | tool_expected | exec_tool("get_weather", ...) 호출됨 |
| search_docs tool | tool_expected | exec_tool("search_docs", ...) 호출됨 |
| no-tool simple text | no_tool_expected | role:tool 메시지 없음 |

## Phase-02 입력 계약 — 정규화 함수 I/O 초안

```
함수명:  extract_tool_calls(msg) -> list[ToolCallLike]

입력:
  msg: OpenAI ChatCompletionMessage 또는 raw dict
    - msg.tool_calls (OpenAI SDK path): list[ChatCompletionMessageToolCall] | None
    - msg.content (fallback path): str | None  — "<tool_call>...</tool_call>" 태그 포함 가능

출력:
  list of dict, 각 항목:
    {
      "id": str,           # tool_calls[i].id 또는 "fallback-{uuid4}" 생성
      "name": str,         # function.name
      "arguments": str,    # JSON 문자열 (그대로 exec_tool에 넘길 것)
    }
  빈 리스트([])는 "도구 없음" 신호 → run_agent가 최종 응답으로 반환

불변식:
  - no_tool 케이스(tool_calls=None, content에 태그 없음) → 반환값 len == 0
  - 표준 경로와 fallback 경로 모두 동일한 dict 구조 반환
  - arguments 파싱 실패 시 함수 내에서 에러를 던지지 않고 빈 리스트 반환 또는 에러 dict 포함
```

## 영향 범위

- 코드 변경 없음 (문서/계약만 정리)
- 이후 phase에서 변경될 함수와 회귀 포인트를 고정

## 검증

```bash
# pytest (PYTHONPATH 또는 uv run으로 실행)
PYTHONPATH=. pytest -q
# 또는: uv run --python 3.11 --with pytest python -m pytest -q tests/

# regression.py — 라이브 서버 필요. smoke test 대안:
# uv run --python 3.11 --with openai --with python-dotenv python -c \
#   "import sys; sys.path.insert(0,''); from scripts.regression import CASES; print(len(CASES))"
```

**기대 결과**:
- `pytest -q`: `3 passed` (test_add_numbers, test_unknown_tool, test_invalid_json)
- regression smoke: `4` (CASES 길이)
- regression live: 4/4 passed (라이브 서버 있을 때)

## 실행 결과

### 1회차 (2026-04-26 18:35 KST) — completed

**상태**: completed
**소요 시간**: 약 10분
**진행 모델**: claude-sonnet-4-6

#### 요약
scope 내 4개 파일(runner.py, tool_harness_qwen36.py, regression.py, test_tool_exec.py)을 전량 분석하여 현재 tool_call 분기 조건·종료 동작·no_tool 판단식을 명시화했다. Phase-02를 위한 정규화 함수 I/O 초안도 함께 작성. 코드 변경은 없고 계약 문서화만 수행.

비고: venv가 Python 3.9 기반이어서 `HarnessConfig | None` 유니온 구문이 import 시 TypeError 발생. `uv run --python 3.11` 우회로 pytest 3 passed 확인. `PYTHONPATH=. pytest -q`도 동일 결과.

#### 변경 파일
- `docs/05-development/planning/toolcall-fallback-normalizer/phase-01-contract-and-baseline.md` (수정, +75줄 — 계약/체크리스트/결과 기록)

#### 검증 결과
- [x] pytest: `uv run --python 3.11 --with pytest python -m pytest -q tests/` → `3 passed`
- [x] regression smoke: `uv run --python 3.11 --with openai --with python-dotenv python -c "...from scripts.regression import CASES; print(len(CASES))"` → `4`
- [ ] regression live: skip — 라이브 모델 서버 없음 (환경 제약)

#### 추가 발견사항
- venv가 Python 3.9 기반이나 harness/runner.py는 `X | Y` 유니온 구문(Python 3.10+) 사용 → `PYTHONPATH=. pytest -q` 실행 시 venv 활성화 상태에서만 실패하고, `uv run --python 3.11`로 우회 필요. Phase-02 구현 시 Python 버전 주석 또는 `Optional[X]` 사용 권고.
- `tool_harness_qwen36.py`는 SDK를 우회하는 standalone이라 `<tool_call>` 태그 fallback 구현 대상이 아님 — runner.py + harness/tools.py만 Phase-03 수정 대상.

#### 질문 / 결정 사항
없음
