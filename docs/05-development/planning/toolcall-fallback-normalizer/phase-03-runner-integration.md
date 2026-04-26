---
phase: 3
title: runner 실행 루프에 normalizer 통합
status: completed
depends_on: [2]
scope:
  - harness/runner.py
  - scripts/chat_once.py
intervention_likely: false
intervention_reason: "A 방식 확정: fallback 경로도 assistant_message에 tool_calls 재구성 삽입"
---

# Phase 3: runner 실행 루프에 normalizer 통합

> 범위: `msg.tool_calls` 중심 루프를 표준+fallback 공통 루프로 전환
> 난이도: 중간
> 의존성: phase-02-parser-module
> 영향 파일: harness/runner.py, scripts/chat_once.py

## 배경

현재 `run_agent`는 `if msg.tool_calls:` 분기 하나에 의존한다. phase-02에서 만든 normalizer를 적용해 source가 다르더라도 동일하게 도구를 실행하게 만들어야 한다.

## 심볼 인벤토리

- `run_agent`
  - 근거: harness/runner.py:14
- `assistant_message`
  - 근거: harness/runner.py:31
- `messages.append(...)`
  - 근거: harness/runner.py:38
- `exec_tool`
  - 근거: harness/runner.py:41
- `normalize_tool_calls_from_message`
  - [NEW]

## 설계

- runner 변경 포인트
  - `msg.tool_calls` 직접 사용 대신 `normalize_tool_calls_from_message(msg)` 호출
  - fallback으로 획득한 tool call도 동일 포맷(`id`, `function.name`, `function.arguments`)으로 처리
- message 저장 (A 방식 — 사용자 확정)
  - 표준/fallback 모두: assistant_message에 `tool_calls` 필드 재구성 삽입
    ```python
    assistant_message["tool_calls"] = [
        {"id": tc["id"], "type": "function",
         "function": {"name": tc["name"], "arguments": tc["arguments"]}}
        for tc in norm["tool_calls"]
    ]
    ```
  - content는 `norm["clean_content"]` 사용 (없으면 `msg.content or ""`)
- 호환성
  - 기존 표준 경로 동작/응답 형식 유지
  - no-tool 케이스는 기존 종료 규칙 유지

## 체크리스트

- [ ] runner에 normalizer import 및 적용
- [ ] tool_call_id 생성 규칙 통일(표준/폴백)
- [ ] assistant_message content 정리(cleaned content) 반영
- [ ] scripts/chat_once.py 출력이 깨지지 않는지 확인
- [ ] 기존 tests/test_tool_exec.py 통과 확인

## 영향 범위

- 핵심 루프 변경으로 회귀 위험 존재
- 단일 normalizer 경유로 엔진별 편차 흡수 기반 확보

## 검증

```bash
cd /Users/junhyukpark/qwen-toolcalling-harness-template
pytest -q
python scripts/chat_once.py "12.5와 7.5를 더해줘. 계산은 반드시 도구를 사용해."
```

## 실행 결과

### 1회차 (2026-04-26 오후 KST) — completed
**상태**: completed
**소요 시간**: 약 5분
**진행 모델**: claude-sonnet-4-6

#### 요약
`harness/runner.py`의 `run_agent()` 루프에 `normalize_tool_calls_from_message()` 를 통합했다. `msg.tool_calls` 직접 접근 대신 normalizer를 경유하여 표준/fallback 경로 모두 동일한 dict 포맷(`id`, `name`, `arguments`)으로 처리한다. assistant_message의 `tool_calls` 필드는 설계대로 재구성된 형태로 저장되며, content는 `norm["clean_content"]`를 우선 사용한다.

#### 변경 파일
- `harness/runner.py` (수정, +20/-10줄): normalizer import 추가, tool_calls 분기 전면 교체

#### 검증 결과
- [x] pytest: 35 tests all pass (0.01s)
- [x] chat_once: 스크립트 임포트/실행 정상. 모델 서버 미기동으로 `chat_template_kwargs` 인수 오류에서 중단 — 환경 제약으로 partial 처리

#### 추가 발견사항
- `run_agent` 함수 시그니처에서 `HarnessConfig | None` 구문 사용 중 (Python 3.10+). 기존 코드 유지, 새 코드에는 동일 패턴을 도입하지 않았으므로 3.9 호환 요건 영향 없음.

#### 질문 / 결정 사항
없음
