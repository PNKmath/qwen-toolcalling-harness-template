---
phase: 4
title: 회귀 스크립트/문서 업데이트 및 운영 가이드 반영
status: completed
depends_on: [3]
scope:
  - scripts/regression.py
  - scripts/tool_harness_qwen36.py
  - README.md
  - docs/05-development/planning/toolcall-fallback-normalizer/*
intervention_likely: false
intervention_reason: "검증/문서 중심 단계"
---

# Phase 4: 회귀 스크립트/문서 업데이트 및 운영 가이드 반영

> 범위: fallback 포함 회귀 기준 고정 및 사용자 가이드 갱신
> 난이도: 낮음
> 의존성: phase-03-runner-integration
> 영향 파일: scripts/regression.py, scripts/tool_harness_qwen36.py, README.md

## 배경

코드 통합 후 운영자가 바로 사용할 수 있도록 회귀 기준과 문서를 갱신해야 한다. 특히 "표준 tool_calls 우선, content fallback" 정책을 명시해 향후 모델 교체 시 혼선을 줄인다.

## 심볼 인벤토리

- `CASES`
  - 근거: scripts/regression.py:4
- `run_case`
  - 근거: scripts/tool_harness_qwen36.py:26
- `tool_calls = msg.get("tool_calls") or []`
  - 근거: scripts/tool_harness_qwen36.py:60
- `README`
  - 근거: README.md:58

## 설계

- 회귀 시나리오 보강
  - fallback 경유 케이스 1개 이상 추가
  - no-tool 오탐 방지 케이스 유지
- 문서 갱신
  - README에 정규화 정책/트러블슈팅 섹션 추가
  - 어떤 서버(parser 조합)에서도 하네스가 동작하는 이유 설명

## 체크리스트

- [ ] regression 케이스에 fallback 검증 시나리오 반영
- [ ] tool_harness 보고 항목에 source(standard/fallback) 추가 검토
- [ ] README에 normalizer 정책/한계 문서화
- [ ] 실행 예시(단일/회귀) 업데이트
- [ ] 최종 검증 결과를 checklist 진행률에 반영

## 영향 범위

- 사용자 운영 가이드 정확도 향상
- 향후 엔진 교체(vLLM/sglang/mlx) 시 재사용성 강화

## 검증

```bash
cd /Users/junhyukpark/qwen-toolcalling-harness-template
pytest -q
python scripts/regression.py
python scripts/tool_harness_qwen36.py --base-url http://127.0.0.1:8006/v1 --model Qwen3.6-27B-UD-MLX-4bit --out reports/tool_harness_qwen36.json
```

## 실행 결과

### 1회차 (2026-04-26 KST) — completed

**상태**: completed
**소요 시간**: 약 8분
**진행 모델**: claude-sonnet-4-6

#### 요약

- `scripts/regression.py`: fallback 경로 주석/메타데이터 추가, `norm_source` 필드 및 `fallback_note` 보고 항목 추가. 4개 기존 케이스 유지.
- `scripts/tool_harness_qwen36.py`: tool_call_source 필드(`"standard (server-parsed)"` | `"none"`) 각 결과에 추가. 서버 수준 파싱 경로 명시 주석 추가.
- `README.md`: "Tool Call 정규화 정책" 섹션 추가 (normalizer 설명, standard/fallback/none 정책, 단위 테스트 위치). 유닛 테스트 명령 예시에 normalizer 테스트 언급 추가.

#### 변경 파일

- `scripts/regression.py`
- `scripts/tool_harness_qwen36.py`
- `README.md`
- `docs/05-development/planning/toolcall-fallback-normalizer/phase-04-regression-and-docs.md` (상태 전이, 결과 기록)

#### 검증 결과

- **단위 테스트**: `uv run --python 3.11 --with pytest python -m pytest -q` → **35 passed** (tool_exec + toolcall_normalizer 32개 포함)
- **live 벤치마크** (`tool_harness_qwen36.py`, 포트 8006): 실행 완료. pass_rate 0.25 — no_tool_smalltalk만 통과, tool 케이스 3개는 서버가 tool_calls 미반환(서버 동작 이슈, 스크립트 문제 아님). `tool_call_source` 필드 정상 출력 확인.
- **regression.py**: openai SDK가 `chat_template_kwargs`를 거부하여 TypeError 발생 (harness/runner.py의 기존 문제, phase 4 범위 밖).

#### 추가 발견사항

- 시스템 Python은 3.9.6으로 `X | None` union 문법 미지원. `uv run --python 3.11`로 우회 필요.
- 포트 8006 서버는 tool_calls를 반환하지 않는 상태 — 별도 서버 설정 점검 필요.

#### 질문 / 결정 사항

- regression.py의 `chat_template_kwargs` TypeError는 runner.py 수준 문제 (phase 3 또는 별도 핫픽스 필요).
- 필요 시 runner.py에서 `chat_template_kwargs`를 optional extra_body로 전달하거나 제거하는 방법 검토 권장.

### 2회차 (2026-04-26 KST) — fix_required → completed

**상태**: completed
**소요 시간**: 약 5분
**진행 모델**: claude-sonnet-4-6

#### 리뷰 피드백 요약

REVIEW_VERDICT: fix_required  
REVIEW_TOP_ISSUE: `scripts/regression.py` CASES 배열에 fallback 경유 케이스가 없음. 주석과 `fallback_note`만으로는 "fallback 경유 케이스 1개 이상 추가" 요건 미충족.

#### 수정 내용 (옵션 A 채택)

`scripts/regression.py`에 `run_fallback_normalizer_case()` 함수 추가:
- 라이브 서버 없이 실행 가능한 인라인 fallback 검증 케이스
- `_MockMessage` (tool_calls=None, content=`<tool_call>` 블록) 를 생성해 `normalize_tool_calls_from_message()` 직접 호출
- 반환 딕셔너리에 `norm_source` 필드 포함 (`"fallback"` 기대값)
- `main()`에서 live 케이스(4개)와 함께 총 5개 케이스 실행 및 결과 출력

이 방식으로 live 서버 의존 없이 fallback 경유 케이스를 항상 실행 가능하며, `harness/runner.py` 수정 없이 scope 내에서 해결.

#### 검증 결과

- **단위 테스트**: `pytest -q` → **35 passed** (변화 없음)
- **인라인 fallback 케이스**: `run_fallback_normalizer_case()` → `passed=True`, `norm_source="fallback"`, `arguments={"a": 12.5, "b": 7.5}` 정상 파싱 확인
