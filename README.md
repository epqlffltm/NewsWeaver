# NewsWeaver

여러 소스에서 뉴스를 수집하고, 같은 사건을 다룬 기사를 묶어 종합 브리핑을
만들어 이메일로 전달하는 개인용 뉴스 다이제스트 파이프라인.

## 동작 방식

````
수집 → 저장 → 임베딩 → 선별 → 사건 묶기 → 종합 요약 → 발송
````

- **수집** — RSS 6개 소스에서 하루 약 240건
````
````

한 줄짜리 흐름도인데, 아래 목록보다 먼저 전체 그림을 보여주는 역할입니다. 없으면 목록만 나열돼서 순서 관계가 안 보이죠.

나머지는 그대로입니다.

````powershell
git add -A
git commit -m "docs: 사건 브리핑 도입과 환경 설정을 반영해 README 갱신"
git push
````

---


## 현재 상태

| Phase | 내용 | 상태 |
|---|---|---|
| 0 | RSS 수집 → PostgreSQL 저장 | 완료 |
| 1 | 키워드 선별 → 요약 → 메일 발송 | 완료 |
| 2 | 임베딩 + 벡터 검색 + 준중복 처리 | 완료 |
| 3 | 소스 확장 (RSS 6개) | 완료 |
| 4 | 선별 품질 측정 | 완료 |

### 측정된 품질

라벨 60건 기준.

- **Precision@10** 0.90 — 상위 10건 중 9건이 관심 기사
- **Recall@30** 1.00 — 관련 기사를 놓치지 않음

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

필요한 항목은 다음과 같다.

| 키 | 설명 |
|---|---|
| `POSTGRES_USER` / `PASSWORD` / `DB` | 컨테이너 초기화에 쓰인다 |
| `POSTGRES_PORT` | 호스트 쪽 포트. 기본 5432 |
| `DATABASE_URL` | 위 값들과 일치해야 한다 |
| `OLLAMA_BASE_URL` | 보통 `http://localhost:11434` |
| `OLLAMA_MODEL` | 요약 모델 |
| `EMBEDDING_MODEL` | 임베딩 모델 |
| `EMBEDDING_DIMENSION` | 벡터 차원. 스키마와 일치해야 한다 |
| `DUPLICATE_SIMILARITY_THRESHOLD` | 이 값 이상이면 같은 사건으로 본다 |
| `SMTP_*` / `MAIL_RECIPIENT` | 발송 계정. Gmail은 앱 비밀번호가 필요하다 |

### 3. 데이터베이스

컨테이너를 먼저 띄우고, `healthy` 상태가 된 뒤에 마이그레이션을 적용한다.
초기화 중에 접속하면 응답을 기다리다 멈춘다.

```bash
docker compose up -d
docker compose ps
uv run alembic upgrade head
```

### 4. Ollama 모델

Ollama 모델은 파이썬 패키지가 아니므로 `uv sync`로 설치되지 않는다.
`.env`의 모델명과 이름이 일치해야 한다.

```bash
ollama pull gemma4:e4b        # 요약용
ollama pull embeddinggemma    # 임베딩용
```

실행 환경의 성능에 따라 모델을 바꿀 수 있다. 바꿀 때는 `.env`만
수정하며, 코드는 건드리지 않는다. 임베딩 모델을 바꾸면 기존 벡터는
자동으로 재생성 대상이 된다.

### 5. 확인

```bash
uv run pytest
uv run python -m news_weaver.cli
```

첫 실행은 캐시가 비어 있어 요약에 20~30분이 걸린다.

## 자주 겪는 문제

**접속이 멈추고 타임아웃이 난다**

컨테이너가 떠 있는지 먼저 확인한다.

```bash
docker compose ps
docker port newsweaver-postgres
```

`docker port`가 비어 있으면 포트 바인딩에 실패한 것이다. Windows에서
Hyper-V가 특정 대역을 예약하는 경우가 있으므로 `.env`의 `POSTGRES_PORT`를
다른 값으로 바꾸고 `DATABASE_URL`의 포트도 함께 맞춘다.

```bash
netsh interface ipv4 show excludedportrange protocol=tcp
```

**포트는 열렸는데 접속이 걸린다**

`localhost`가 IPv6로 해석되면서 응답을 못 받는 경우가 있다.
`DATABASE_URL`의 호스트를 `127.0.0.1`로 바꾼다.

**마이그레이션이 NotNullViolation으로 실패한다**

기존 행이 있는 테이블에 NOT NULL 컬럼을 추가하려는 경우다. 데이터를
보존해야 하면 nullable로 추가 → UPDATE로 채우기 → NOT NULL 적용의
세 단계로 나눈다.

## 실행

```bash
uv run python -m news_weaver.cli
```

수집부터 발송까지 한 번에 실행된다. 요약은 캐시되므로 재실행 시 이미
만든 브리핑은 건너뛴다. 모델이나 프롬프트를 바꾸거나 사건 그룹의 구성이
달라지면 자동으로 다시 생성된다.

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

### 스크립트

`scripts/`의 파일들은 용도가 둘로 나뉜다.

**`spike_*.py`** — 설계 판단을 위한 일회성 실측 스크립트. 프로덕션 코드가
아니며 임포트하지 않는다. 모델 선택이나 임계값처럼 추측으로 정할 수 없는
값을 실제 데이터로 확인하는 데 쓴다.

**평가 도구** — 선별 품질을 수치로 재는 데 쓴다.

```bash
uv run python scripts/label_articles.py      # 정답 라벨 수집
uv run python scripts/evaluate_selection.py  # 지표 측정
```

라벨은 `evaluation/selection_labels.json`에 누적되며 커밋한다. 코드와 함께
버전 관리해야 "어떤 기준에서 이 점수가 나왔는지" 추적할 수 있다.

## 설계 메모

**시각은 UTC로 저장한다.** 소스마다 타임존 표기 유무가 달라 수집기에서
흡수한다. 표기가 없으면 한국 언론사 기준으로 KST로 간주한다.

**`url_hash`는 중복 판정에만 쓴다.** 정규화된 URL의 해시이며, 실제 접속과
메일 링크에는 원본 `url`을 쓴다.

**요약 캐시 키는 `(content_key, model_name, prompt_version)`이다.**
`content_key`는 사건 그룹의 구성원을 정렬해 해시한 값이라, 구성원이
하나라도 바뀌면 다시 생성된다. 프롬프트나 모델을 바꿔도 마찬가지다.

**실패는 예외가 아니라 결과값으로 다룬다.** 한 소스의 장애나 한 건의 요약
실패가 배치 전체를 중단시키면 안 된다. 실패한 항목은 캐시에 남기지 않아
다음 실행에서 재시도된다.

**선별 후보는 건수가 아니라 시간으로 자른다.** 건수로 제한하면 수집량이
늘 때마다 범위가 좁아져 같은 날 기사가 밀려나고 사건 묶기가 성립하지 않는다.

**보도량을 순위에 반영한다.** 여러 매체가 같은 사건을 다뤘다는 것은 관심
주제 일치와는 다른 종류의 신호이므로, 기사 점수가 아니라 그룹 점수에 더한다.

**벡터는 재현율 확대가 아니라 사건 묶기에 쓴다.** 관심 프로필 임베딩과
유사 기사 확장을 두 차례 실측했으나, 관심사와 소스가 정렬된 현재 구성에서는
키워드가 놓치는 기사가 없어 추가 가치가 없었다. 표현을 직접 등록하는 편이
확실하며, 벡터의 실질적 쓸모는 같은 사건을 묶는 데 있다.

## 소스 추가

`src/news_weaver/collectors/sources.py`만 수정한다. 추가 전에는 실제 응답을
확인한다.

```bash
uv run python scripts/spike_inspect_rss.py
```

피드는 예고 없이 죽거나 형식이 바뀐다. 종합지는 관심 밖 기사만 대량으로
늘려 임베딩 비용을 낭비하므로, 관심 영역과 정렬된 매체만 등록한다.