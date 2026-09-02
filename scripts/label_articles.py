# NewsWeaver/scripts/label_articles.py

"""
선별 품질을 측정하기 위한 정답 라벨을 수집한다.

키워드 조정이나 임계값 변경이 실제로 나아진 것인지 판단하려면 기준이 되는
정답이 필요하다. 라벨은 코드와 함께 버전 관리해야 "어떤 기준에서 이 점수가
나왔는지" 추적할 수 있으므로 DB가 아니라 파일에 남긴다.

이미 라벨이 있는 기사는 건너뛰므로, 여러 번 나눠서 작업할 수 있다.
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.domain.article import Article

load_dotenv()

LABEL_FILE = Path("evaluation/selection_labels.json")

# 한 번에 라벨링할 건수. 집중력이 떨어지면 라벨 품질도 떨어진다
BATCH_SIZE = 30

# 후보 조회 범위. 평가 대상은 최근 기사로 한정한다
CANDIDATE_WINDOW_DAYS = 2


def load_labels() -> dict[str, bool]:
    """기존 라벨을 읽어온다. url_hash에서 관련 여부로 가는 사전이다."""
    if not LABEL_FILE.exists():
        return {}

    with LABEL_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def save_labels(labels: dict[str, bool]) -> None:
    """라벨을 파일에 저장한다."""
    LABEL_FILE.parent.mkdir(exist_ok=True)

    with LABEL_FILE.open("w", encoding="utf-8") as file:
        json.dump(labels, file, ensure_ascii=False, indent=2, sort_keys=True)


def load_candidates() -> list[Article]:
    """평가 대상 기사를 읽어온다."""
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=CANDIDATE_WINDOW_DAYS)
    session_factory = get_session_factory()

    with session_factory() as session:
        return ArticleRepository(session).find_recent_articles(since)


def ask_relevance(article: Article, index: int, total: int) -> bool | None:
    """
    기사 하나에 대한 관련 여부를 묻는다.

    중단하면 None을 반환해, 지금까지의 라벨만 저장하고 종료할 수 있게 한다.
    """
    print(f"\n{'=' * 70}")
    print(f"[{index}/{total}] {article.source_name}")
    print(f"제목: {article.title}")

    if article.summary:
        print(f"요약: {article.summary[:150]}")

    while True:
        answer = input("관련 있음? (y/n/q=중단): ").strip().lower()

        if answer == "y":
            return True
        if answer == "n":
            return False
        if answer == "q":
            return None

        print("y, n, q 중 하나를 입력하세요.")


def main() -> None:
    labels = load_labels()
    candidates = load_candidates()

    unlabeled = [a for a in candidates if a.url_hash not in labels]

    print(f"전체 {len(candidates)}건 / 라벨 완료 {len(labels)}건 ")
    print(f"/ 남음 {len(unlabeled)}건")

    if not unlabeled:
        print("모든 기사에 라벨이 있습니다.")
        return

    targets = unlabeled[:BATCH_SIZE]

    for index, article in enumerate(targets, start=1):
        answer = ask_relevance(article, index, len(targets))

        if answer is None:
            break

        labels[article.url_hash] = answer

    save_labels(labels)
    relevant_count = sum(1 for value in labels.values() if value)

    print(f"\n저장 완료: 총 {len(labels)}건 (관련 {relevant_count}건)")


if __name__ == "__main__":
    main()