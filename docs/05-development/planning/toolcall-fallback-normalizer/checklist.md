---
task: toolcall-fallback-normalizer
phase_count: 4
created: 2026-04-26
---

# Tool-call fallback normalizer — 진행 체크리스트

## 진행 상태 요약

| Phase | 파일 | 항목 | 완료 | 진행률 | 상태 | 커밋 |
|-------|------|------|------|--------|------|------|
| 1 | phase-01-contract-and-baseline.md | 5 | 5 | 100% | completed | edbc776 |
| 2 | phase-02-parser-module.md | 6 | 6 | 100% | completed | 17f5135 |
| 3 | phase-03-runner-integration.md | 5 | 5 | 100% | completed | dfd4de7 |
| 4 | phase-04-regression-and-docs.md | 5 | 5 | 100% | completed | |
| **Total** | | **21** | **21** | **100%** | | |

## Phase 의존성

```text
phase-01 -> phase-02 -> phase-03 -> phase-04
```

## 우선순위

| 등급 | Phase | 설명 | 예상 시간 |
|------|-------|------|-----------|
| P0 | phase-01 | 현재 동작/실패 형태를 계약으로 고정 | 20m |
| P0 | phase-02 | `<tool_call>` fallback 파서 모듈 구현 | 30m |
| P0 | phase-03 | runner 루프에 표준+fallback 병합 | 25m |
| P1 | phase-04 | 회귀/문서 업데이트 및 사용 예시 정리 | 20m |

## 권장 실행 순서

1. Phase 01 완료 후 baseline fixture/기대동작 확정
2. Phase 02에서 parser 단위 테스트까지 통과
3. Phase 03에서 runner 통합 + 기존 tool path 회귀 확인
4. Phase 04에서 regression 문서와 운영 가이드 반영

## 검증 체크리스트

### 공통 검증
- `pytest -q`
- `python scripts/regression.py`
- (선택) `python scripts/chat_once.py "서울 날씨를 도구로 조회해줘"`

## 관련 문서

- [README](./README.md)
- [phase-01-contract-and-baseline.md](./phase-01-contract-and-baseline.md)
- [phase-02-parser-module.md](./phase-02-parser-module.md)
- [phase-03-runner-integration.md](./phase-03-runner-integration.md)
- [phase-04-regression-and-docs.md](./phase-04-regression-and-docs.md)
