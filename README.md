# qwen-toolcalling-harness-template

Qwen3.6 (OpenAI-compatible endpoint)용 최소 툴콜링 하네스 템플릿입니다.

목표:
- 다른 환경에서도 바로 재사용 가능한 호출기
- tool_calls 처리 루프 표준화
- 회귀 테스트(툴 사용/미사용) 자동 점검

## 포함 내용

- `harness/runner.py`: 에이전트 실행 루프 (tool_calls -> tool 실행 -> 재호출)
- `harness/tools.py`: 샘플 도구 3개 + 스키마
- `scripts/chat_once.py`: 단일 프롬프트 실행
- `scripts/regression.py`: 4개 회귀 케이스 실행
- `tests/test_tool_exec.py`: 로컬 유닛 테스트

## 빠른 시작

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cp .env.harness.example .env.harness
```

`.env` 수정:
- `OPENAI_BASE_URL` (예: `http://YOUR_SERVER:8008/v1`)
- `OPENAI_API_KEY`
- `MODEL`

## 사용

단일 실행:
```bash
python scripts/chat_once.py "서울 날씨를 도구로 조회해줘"
```

회귀 실행:
```bash
python scripts/regression.py
```

유닛 테스트 (서버 불필요 — tool exec + normalizer 32케이스 포함):
```bash
pytest -q
# normalizer만 선택 실행:
pytest -q tests/test_toolcall_normalizer.py
```

Qwen3.6 전용 툴콜링 벤치(직접 HTTP 호출):
```bash
python scripts/tool_harness_qwen36.py \
  --base-url http://127.0.0.1:8008/v1 \
  --model Qwen3.6-27B-UD-MLX-4bit \
  --out reports/tool_harness_qwen36.json
```

## 하네스 설계 핵심

1. 모델 서버와 하네스 책임 분리
- 서버: 추론/파서/샘플링
- 하네스: 툴 라우팅, 인자 검증, 재시도, 실패 처리

2. no-tool 케이스를 반드시 유지
- 툴 과호출(over-calling) 감지에 필요

3. max_turns/timeout 강제
- 무한 루프 방지

## Tool Call 정규화 정책 (`harness/toolcall_normalizer.py`)

하네스는 서버 설정에 관계없이 tool call을 안정적으로 처리하기 위해 `normalize_tool_calls_from_message()` 함수를 사용합니다.

**"표준 tool_calls 우선, content fallback" 정책**:
1. **standard** — 응답 메시지에 `tool_calls` 필드가 있으면 그것을 우선 사용합니다. `--tool-call-parser qwen3_coder`가 활성화된 서버(포트 8006/8008/8016/8018/8020)에서 항상 이 경로를 사용합니다.
2. **fallback** — `tool_calls`가 없고 content에 `<tool_call><function=...>` 태그가 포함된 경우 XML 파싱으로 추출합니다. parser 플래그 없이 실행된 서버나 직접 텍스트 생성 모드에서 발생합니다.
3. **none** — tool call이 없는 일반 텍스트 응답입니다.

반환 값의 `source` 필드(`"standard"` | `"fallback"` | `"none"`)로 어느 경로를 거쳤는지 확인할 수 있습니다.

**단위 테스트**: `tests/test_toolcall_normalizer.py` (32개 케이스) — 라이브 서버 없이 두 경로를 모두 검증합니다. `pytest -q`로 실행하세요.

## 지난 Qwen27 테스트 자산(추가 포함)

- 실행 스크립트
  - `scripts/context_probe_qwen27.py`
  - `scripts/start_qwen27_4bit_harness.sh`
  - `scripts/start_qwen27_6bit_harness.sh`
  - `scripts/start_qwen27_8bit_harness.sh`
- 사용 가이드
  - `docs/hermes_qwen27_harness_usage.txt`
- 샘플 리포트
  - `reports/samples/qwen27-harness-compare.json`
  - `reports/samples/qwen27-4_6_8bit-coding-context-summary.json`
  - `reports/samples/qwen27-4_6_8bit-interim-summary-2026-04-25.json`

환경 설정:
- `start_qwen27_*_harness.sh`는 `../.env.harness`를 자동 로드합니다.
- 다른 환경에서는 `.env.harness.example`를 복사한 뒤 모델 경로/포트/로그 경로만 바꾸면 됩니다.

## 배포 팁

- 사내 공유용이면 Dockerfile/CI를 추가하세요.
- 운영에서는 툴 실행 whitelist + 감사 로그를 추가하세요.
- 실제 외부 API 도구는 `harness/tools.py`에서 mock을 교체하면 됩니다.
