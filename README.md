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

유닛 테스트:
```bash
pytest -q
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
