---
phase: 2
title: `<tool_call>` fallback 파서 모듈 구현
status: completed
depends_on: [1]
scope:
  - harness/toolcall_normalizer.py
  - tests/test_toolcall_normalizer.py
intervention_likely: false
intervention_reason: "qwen3_coder_parser.py 소스 분석으로 포맷 및 엣지 케이스 정책 확정"
---

# Phase 2: `<tool_call>` fallback 파서 모듈 구현

> 범위: 표준/비표준 tool call을 단일 내부 포맷으로 정규화
> 난이도: 중간
> 의존성: phase-01-contract-and-baseline
> 영향 파일: harness/toolcall_normalizer.py, tests/test_toolcall_normalizer.py

## 배경

Qwen 계열에서 `<tool_call><function=...><parameter=...>` 형태가 content에 나타나도, 하네스가 이를 파싱하지 못하면 도구 실행 없이 종료한다. parser를 runner에 직접 박아넣지 말고 재사용 가능한 모듈로 분리해 회귀를 안정화한다.

## 심볼 인벤토리

- `run_agent`
  - 근거: harness/runner.py:14
- `assistant_message`
  - 근거: harness/runner.py:31
- `exec_tool`
  - 근거: harness/tools.py:78
- `ToolCallNormalized`
  - [NEW]
- `extract_fallback_tool_calls`
  - [NEW]
- `normalize_tool_calls_from_message`
  - [NEW]

## 설계

포맷 출처: `~/.hermes/hermes-agent/environments/tool_call_parsers/qwen3_coder_parser.py` 소스 분석

- 신규 모듈 `harness/toolcall_normalizer.py`
  - 입력: OpenAI message 객체(또는 동등 dict), raw content
  - 출력: `tool_calls(list[dict])`, `clean_content(str|None)`, `source(standard|fallback|none)`
- 파싱 대상
  - 1) OpenAI 표준 `message.tool_calls` — 우선
  - 2) content 내 qwen3_coder 태그 포맷 (fallback):
    ```
    <tool_call>
    <function=function_name>
    <parameter=param_name>value</parameter>
    </function>
    </tool_call>
    ```
- 엣지 케이스 정책 (파서 소스 기반 확정):
  - `</tool_call>` / `</function>` 미닫힘 → EOF까지 파싱 (정규식 fallback)
  - `</parameter>` 미닫힘 → 다음 `<parameter=` 또는 `</function>` 위치까지를 값으로 사용
  - 복수 `<tool_call>` 블록 → 순서대로 모두 추출
  - 함수명에 `>` 없거나 함수 블록 파싱 실패 → skip (None 반환, 에러 전파 없음)
  - 파라미터 값 타입 변환: JSON parse → ast.literal_eval → string 순
  - clean_content: 첫 `<tool_call>` 이전 텍스트 (없으면 None)
- 안전장치
  - 표준 경로(`message.tool_calls`)가 있으면 fallback 파싱 건너뜀
  - 전체 파싱 예외 → (original_content, None) 반환

## 체크리스트

- [x] `toolcall_normalizer.py` 파일 생성
- [x] 표준 `tool_calls` 우선 반환 구현
- [x] content 태그형 파싱 구현(복수 블록 지원)
- [x] cleaned content 생성 규칙 구현
- [x] 단위 테스트 6개 이상 작성(표준/태그/혼합/깨짐/no-tool)
- [x] 타입/문자열 직렬화 정책 고정

## 영향 범위

- 신규 유틸 모듈/테스트 추가
- 기존 runner 로직 변경 전, parser 단위 품질 보장

## 검증

```bash
cd /Users/junhyukpark/qwen-toolcalling-harness-template
pytest -q tests/test_toolcall_normalizer.py
```

## 실행 결과

### 1회차 (2026-04-26 KST) — 완료

**상태**: completed
**소요 시간**: 약 5분
**진행 모델**: claude-sonnet-4-6

#### 요약
`harness/toolcall_normalizer.py` 신규 모듈을 생성하여 OpenAI 표준 `tool_calls`와 qwen3_coder 태그 포맷(`<tool_call><function=…><parameter=…>`) 양쪽을 단일 내부 포맷으로 정규화하는 `normalize_tool_calls_from_message()` 함수를 구현했다. qwen3_coder_parser.py 소스를 기반으로 동일 정규식 전략을 채용하여 미닫힘 태그, 복수 블록, 타입 변환 등 엣지 케이스를 모두 처리한다. 32개의 단위 테스트를 작성했으며 기존 3개 포함 전체 35개 테스트가 통과한다.

#### 변경 파일
- `harness/toolcall_normalizer.py` (신규, +185줄)
- `tests/test_toolcall_normalizer.py` (신규, +250줄)

#### 검증 결과
- [x] `pytest -q tests/test_toolcall_normalizer.py`: `32 passed in 0.02s` → pass
- [x] `pytest -q tests/`: `35 passed in 0.01s` → pass (기존 회귀 없음)

#### 추가 발견사항
- harness 전체가 `X | Y` 유니온 구문(Python 3.10+)을 사용 중이라 venv 3.9와 불일치. 신규 모듈은 `Optional[X]`, `Union[X, Y]` + TypedDict로 3.9 호환성 확보. 테스트 실행은 `uv run --python 3.11` 사용.
- 표준 경로에서 content에 `<tool_call>` 태그가 있을 때에도 clean_content가 정상 추출된다.

#### 질문 / 결정 사항
없음
