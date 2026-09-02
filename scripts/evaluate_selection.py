# NewsWeaver/scripts/evaluate_selection.py

"""
선별 결과를 사람이 매긴 라벨과 대조해 품질을 수치로 낸다.

키워드 조정이나 임계값 변경이 실제로 개선인지 판단하려면 비교 가능한
숫자가 필요하다. 눈으로 목록을 훑는 방식은 변경 전후를 나란히 놓을 수 없다.

라벨이 없는 기사는 평가에서 제외한다. 전체를 라벨링하지 않은 상태에서
미라벨을 오답으로 세면 지표가 실제보다 낮게 나온다.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import score_article, select_articles

load_dotenv()

LABEL_FILE = Path("evaluation/selection_labels.json")

CANDIDATE_WINDOW_DAYS = 2

# 실제 배치가 메일에 담는 건수와 맞춘다
EVALUATION_TOP_K = 10


def load_labels() -> dict[str, bool]:
    """사람이 매긴 정답 라벨을 읽어온다."""
    if not LABEL_FILE.exists():
        return {}

    with LABEL_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def load_candidates() -> list[Article]:
    """평가 대상 기사를 읽어온다."""
    since = datetime.now(UTC) - timedelta(days=CANDIDATE_WINDOW_DAYS)
    session_factory = get_session_factory()

    with session_factory() as session:
        return ArticleRepository(session).find_recent_articles(since)


def measure_precision(
    labeled_articles: list[Article],
    labels: dict[str, bool],
    top_k: int,
) -> tuple[float, list[tuple[Article, bool]]]:
    """
    상위 K건 중 실제로 관련 있는 비율을 계산한다.

    메일에 담기는 건수만 평가하므로, 하위권의 오차는 반영되지 않는다.
    사용자가 실제로 보는 것이 상위 K건이기 때문이다.
    """
    selected = select_articles(labeled_articles, INTEREST_TOPICS, top_k)

    judged = [(item.article, labels[item.article.url_hash]) for item in selected]
    hit_count = sum(1 for _, is_relevant in judged if is_relevant)

    precision = hit_count / len(judged) if judged else 0.0

    return precision, judged


def measure_recall(
    labeled_articles: list[Article],
    labels: dict[str, bool],
    top_k: int,
) -> tuple[float, list[Article]]:
    """
    관련 있다고 표시된 기사 중 상위 K건이 잡아낸 비율을 계산한다.

    상한이 K건이므로 관련 기사가 K건보다 많으면 재현율은 구조적으로
    1에 도달할 수 없다. 절대값보다 변경 전후의 차이를 본다.
    """
    relevant = [a for a in labeled_articles if labels[a.url_hash]]

    if not relevant:
        return 0.0, []

    selected = select_articles(labeled_articles, INTEREST_TOPICS, top_k)
    selected_hashes = {item.article.url_hash for item in selected}

    found = [a for a in relevant if a.url_hash in selected_hashes]
    missed = [a for a in relevant if a.url_hash not in selected_hashes]

    return len(found) / len(relevant), missed


def main() -> None:
    labels = load_labels()

    if not labels:
        print("라벨이 없습니다. scripts/label_articles.py를 먼저 실행하세요.")
        return

    candidates = load_candidates()
    labeled = [a for a in candidates if a.url_hash in labels]

    relevant_count = sum(1 for a in labeled if labels[a.url_hash])

    print(f"평가 대상 {len(labeled)}건 (관련 {relevant_count}건)")
    print(f"주제: {', '.join(t.name for t in INTEREST_TOPICS)}\n")

    precision, judged = measure_precision(labeled, labels, EVALUATION_TOP_K)
    recall, missed = measure_recall(labeled, labels, EVALUATION_TOP_K)

    print(f"Precision@{EVALUATION_TOP_K}: {precision:.2f}")
    print(f"Recall: {recall:.2f}\n")

    print(f"{'=' * 70}")
    print("선별된 기사")
    for article, is_relevant in judged:
        marker = "O" if is_relevant else "X"
        score = score_article(article, INTEREST_TOPICS).score
        print(f"  [{marker}] {score}점 {article.title[:45]}")

    if missed:
        print(f"\n{'=' * 70}")
        print("놓친 관련 기사")
        for article in missed:
            score = score_article(article, INTEREST_TOPICS).score
            print(f"  {score}점 {article.title[:45]}")


if __name__ == "__main__":
    main()