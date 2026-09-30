# NewsWeaver/src/news_weaver/selection/evaluation.py

"""
선별 품질 평가에 쓰는 고정 평가셋과 지표 계산.

평가가 DB에 묶이면 저장소를 새로 받은 사람은 숫자를 재현할 수 없다. 그래서
라벨 붙은 기사를 JSONL로 얼려 커밋하고, 평가는 그 파일만 읽는다.

규칙을 조정할 때 본 데이터로 성능을 재면 실제보다 좋게 나오므로, 기사마다
dev/test를 고정 배정한다. 조정은 dev만 보고, test는 최종 확인에만 쓴다.
스크립트와 테스트가 같은 로직을 쓰도록 순수 함수로 이 모듈에 둔다.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS, Topic
from news_weaver.selection.keyword import select_articles

SPLIT_DEV = "dev"
SPLIT_TEST = "test"

# 해시 버킷 3개 중 1개를 test로 둔다(약 1/3)
SPLIT_BUCKETS = 3

# 평가 K는 라벨 60건일 때 정했다. 분할마다 건수가 달라 K를 고정하면 비교가
# 안 되므로, 이 건수 대비 비율로 줄여 쓴다
REFERENCE_SET_SIZE = 60
REFERENCE_PRECISION_K = 10
REFERENCE_RECALL_K = 30


@dataclass(frozen=True, slots=True)
class EvalRecord:
    """평가셋의 기사 한 건과 그 정답."""

    article: Article
    is_relevant: bool
    split: str


@dataclass(frozen=True, slots=True)
class EvalMetrics:
    """한 분할에 대한 평가 결과."""

    total: int
    relevant: int
    precision_k: int
    precision: float
    recall_k: int
    recall: float


def hash_bucket_split(url_hash: str) -> str:
    """
    url_hash만으로 분할을 정한다.

    다른 기사에 의존하지 않으므로, 라벨이 늘어도 기존 기사의 분할이 바뀌지 않는다.
    """
    digest = hashlib.sha256(url_hash.encode("utf-8")).digest()
    return SPLIT_TEST if digest[0] % SPLIT_BUCKETS == 0 else SPLIT_DEV


def _sort_key(url_hash: str) -> str:
    """보정 대상을 고르는 결정적 순서."""
    return hashlib.sha256(url_hash.encode("utf-8")).hexdigest()


def assign_splits(labels: dict[str, bool]) -> dict[str, str]:
    """
    기사마다 dev/test를 배정한다.

    기본은 hash_bucket_split이다. 다만 관련 기사가 적으면 한쪽 분할에 관련
    기사가 하나도 없을 수 있고, 그러면 재현율을 잴 수 없다. 관련 기사가 2건
    이상인데 한쪽이 비면, 다른 쪽에서 해시 순서가 가장 앞선 관련 기사 하나를
    옮긴다. 옮기는 기사도 해시로 정해지므로 결과는 항상 같다.
    """
    splits = {url_hash: hash_bucket_split(url_hash) for url_hash in labels}

    positives = sorted((h for h, rel in labels.items() if rel), key=_sort_key)
    if len(positives) < 2:
        return splits

    for empty, donor in ((SPLIT_TEST, SPLIT_DEV), (SPLIT_DEV, SPLIT_TEST)):
        if not any(splits[h] == empty for h in positives):
            moved = next(h for h in positives if splits[h] == donor)
            splits[moved] = empty

    return splits


def record_to_json(record: EvalRecord) -> dict:
    """평가셋 한 줄로 바꾼다."""
    article = record.article
    return {
        "url_hash": article.url_hash,
        "source_name": article.source_name,
        "title": article.title,
        "summary": article.summary,
        "url": article.url,
        "collected_at": article.collected_at.isoformat(),
        "published_at": (
            article.published_at.isoformat() if article.published_at else None
        ),
        "label": record.is_relevant,
        "split": record.split,
    }


def record_from_json(data: dict) -> EvalRecord:
    """평가셋 한 줄을 읽는다."""
    published_raw = data.get("published_at")
    article = Article(
        source_name=data["source_name"],
        title=data["title"],
        url=data["url"],
        url_hash=data["url_hash"],
        collected_at=datetime.fromisoformat(data["collected_at"]),
        published_at=datetime.fromisoformat(published_raw) if published_raw else None,
        summary=data.get("summary"),
    )
    return EvalRecord(article=article, is_relevant=data["label"], split=data["split"])


def write_eval_set(path: Path, records: list[EvalRecord]) -> None:
    """
    평가셋을 JSONL로 쓴다.

    url_hash 순으로 정렬해, 같은 입력이면 파일 내용이 같아 diff가 깔끔하다.
    """
    lines = [
        json.dumps(record_to_json(r), ensure_ascii=False, sort_keys=True)
        for r in sorted(records, key=lambda r: r.article.url_hash)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def read_eval_set(path: Path) -> list[EvalRecord]:
    """평가셋 JSONL을 읽는다."""
    with path.open(encoding="utf-8") as file:
        return [record_from_json(json.loads(line)) for line in file if line.strip()]


def filter_split(records: list[EvalRecord], split: str) -> list[EvalRecord]:
    """지정한 분할만 남긴다. "all"이면 전부 돌려준다."""
    if split == "all":
        return records
    return [r for r in records if r.split == split]


def scale_k(reference_k: int, set_size: int) -> int:
    """
    기준 K를 평가 대상 건수에 비례해 줄인다.

    60건에서 정한 K=10을 20건짜리 test에 그대로 쓰면 절반을 뽑는 셈이라
    정밀도의 의미가 달라진다. 같은 비율을 유지해 분할끼리 비교할 수 있게 한다.
    """
    return max(1, round(reference_k * set_size / REFERENCE_SET_SIZE))


def compute_metrics(
    records: list[EvalRecord],
    topics: tuple[Topic, ...] = INTEREST_TOPICS,
) -> EvalMetrics:
    """
    Precision@k와 Recall@k를 계산한다.

    정밀도는 상위 k건 중 관련 비율(메일에 실리는 부분의 품질), 재현율은
    관련 기사 중 더 넓은 상위 k건에 든 비율(놓치는 기사가 있는지)이다.
    주제에 하나도 걸리지 않은 기사는 선별되지 않으므로 뽑힌 건수가 k보다
    적을 수 있고, 정밀도의 분모는 실제로 뽑힌 건수다.
    """
    labels = {r.article.url_hash: r.is_relevant for r in records}
    articles = [r.article for r in records]
    relevant_count = sum(labels.values())

    precision_k = scale_k(REFERENCE_PRECISION_K, len(records))
    recall_k = scale_k(REFERENCE_RECALL_K, len(records))

    top = select_articles(articles, topics, precision_k)
    hits = sum(1 for item in top if labels[item.article.url_hash])
    precision = hits / len(top) if top else 0.0

    wide = {item.article.url_hash for item in select_articles(articles, topics, recall_k)}
    found = sum(1 for h, rel in labels.items() if rel and h in wide)
    recall = found / relevant_count if relevant_count else 0.0

    return EvalMetrics(
        total=len(records),
        relevant=relevant_count,
        precision_k=precision_k,
        precision=precision,
        recall_k=recall_k,
        recall=recall,
    )
