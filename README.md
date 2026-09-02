# NewsWeaver
다중 소스 뉴스 수집부터 정제·임베딩·벡터 검색·RAG·LLM 요약까지 구현하는 개인화 AI 뉴스 인텔리전스 플랫폼

# NewsWeaver

여러 소스에서 뉴스를 수집하고, 관심 주제와 관련된 기사를 선별해
요약본을 이메일로 전달하는 개인용 뉴스 다이제스트 파이프라인.

## 현재 상태

Phase 2 진행 중 — 임베딩과 벡터 검색 도입

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | RSS 수집 → PostgreSQL 저장 | 완료 |
| 1 | 키워드 선별 → 요약 → 메일 발송 | 완료 |
| 2 | 임베딩 + 벡터 검색 | 진행 중 |
| 3 | 공공/오픈 API 소스 확장 | |
| 4 | 검색·요약 품질 측정 | |

## 요구 사항

- Python 3.13 이상
- Docker (PostgreSQL + pgvector)
- Ollama (로컬 LLM)
- uv (패키지 관리)

## 새 환경에서 시작하기

### 1. 저장소와 의존성

```bash
git clone https://github.com/epqlffltm/NewsWeaver.git
cd NewsWeaver
uv sync
```

### 2. 환경 변수

`.env.example`을 복사해 `.env`를 만들고 값을 채운다.
이 파일은 커밋하지 않는다.

```bash
cp .env.example .env
```

포트가 이미 사용 중이면 `POSTGRES_PORT`를 바꾸고
`DATABASE_URL`의 포트도 함께 맞춘다.

Windows에서 `localhost`가 IPv6로 해석되어 접속이 멈추는 경우가 있다.
그때는 `DATABASE_URL`의 호스트를 `127.0.0.1`로 바꾼다.

### 3. 데이터베이스

```bash
docker compose up -d
uv run alembic upgrade head
```

### 4. Ollama 모델

Ollama 모델은 파이썬 패키지가 아니므로 `uv sync`로 설치되지 않는다.
`.env`의 `OLLAMA_MODEL`, `EMBEDDING_MODEL`과 이름이 일치해야 한다.

```bash
ollama pull gemma4:e4b        # 요약용
ollama pull embeddinggemma    # 임베딩용
```

실행 환경의 성능에 따라 모델을 바꿀 수 있다.
바꿀 때는 `.env`만 수정하며, 코드는 건드리지 않는다.

### 5. 확인

```bash
uv run pytest
uv run python -m news_weaver.cli
```

## 실행

```bash
uv run python -m news_weaver.cli
```

수집 → 저장 → 선별 → 요약 → 발송이 한 번에 실행된다.
요약은 캐시되므로 재실행 시 이미 요약된 기사는 건너뛴다.

## 매일 자동 실행

Windows 작업 스케줄러에 등록한다. 관리자 권한 PowerShell에서:

```powershell
$action = New-ScheduledTaskAction -Execute "<프로젝트경로>\scripts\run_daily.bat"
$trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName "NewsWeaver" -Action $action `
  -Trigger $trigger -Settings $settings
```

실행 결과 확인:

```powershell
Get-ScheduledTaskInfo -TaskName "NewsWeaver"
```

`LastTaskResult`가 0이면 정상 종료다.

## 로그

`logs/newsweaver.log`에 기록된다. 5MB 단위로 순환하며 5개까지 보관한다.
배치는 사람이 보지 않는 시각에 실행되므로, 실패 원인은 이 파일로 추적한다.

## 개발

```bash
uv run ruff check --fix .    # 린트
uv run pytest -v             # 테스트
```

`scripts/`의 `spike_*.py`는 설계 판단을 위한 실측 스크립트다.
프로덕션 코드가 아니며 임포트하지 않는다.

## 설계 메모

- 시각은 DB에 UTC로 저장하고 표시할 때만 변환한다.
  소스마다 타임존 표기 유무가 달라 수집기에서 흡수한다.
- `url_hash`는 정규화된 URL의 해시이며 중복 판정에만 쓴다.
  실제 접속과 메일 링크에는 원본 `url`을 쓴다.
- 요약 캐시 키는 `(url_hash, model_name, prompt_version)`이다.
  프롬프트나 모델을 바꾸면 자동으로 다시 생성된다.
- 실패는 예외가 아니라 결과값으로 다룬다.
  한 건의 실패가 배치 전체를 중단시키면 안 된다.