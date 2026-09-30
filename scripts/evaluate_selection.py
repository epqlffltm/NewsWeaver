# NewsWeaver/scripts/evaluate_selection.py

"""
선별 결과를 사람이 매긴 라벨과 대조해 품질을 수치로 낸다.

키워드 조정이나 임계값 변경이 실제로 개선인지 판단하려면 비교 가능한
숫자가 필요하다. 눈으로 목록을 훑는 방식은 변경 전후를 나란히 놓을 수 없다.

DB 대신 커밋된 고정 평가셋(evaluation/selection_eval.jsonl)만 읽으므로,
저장소를 받은 누구나 같은 숫자를 얻는다. 규칙 조정은 --split dev로 보고,
test는 조정을 마친 뒤 최종 확인에만 쓴다. test를 보며 고치면 test도
조정용 데이터가 되어 성능을 부풀린다.
"""

import argparse
from pathlib import Path

from news_weaver.selection.evaluation import (
    EvalRecord,
    compute_metrics,
    filter_split,
    read_eval_set,
)
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import score_article, select_articles

EVAL_SET_FILE = Path("evaluation/selection_eval.jsonl")


def parse_args() -> argparse.Namespace:
    """명령줄 인자를 해석한다."""
    parser = argparse.ArgumentParser(description="선별 품질을 평가한다.")
    parser.add_argument(
        "--split",
        choices=("dev", "test", "all"),
        default="test",
        help="평가할 분할. 규칙 조정 중에는 dev만 본다 (기본값: test)",
    )
    return parser.parse_args()


def print_details(records: list[EvalRecord], precision_k: int, recall_k: int) -> None:
    """뽑힌 기사와 놓친 관련 기사를 보여준다."""
    labels = {r.article.url_hash: r.is_relevant for r in records}
    articles = [r.article for r in records]

    print(f"{'=' * 70}")
    print(f"상위 {precision_k}건")
    for item in select_articles(articles, INTEREST_TOPICS, precision_k):
        marker = "O" if labels[item.article.url_hash] else "X"
        print(f"  [{marker}] {item.score}점 {item.article.title[:45]}")

    wide = {
        item.article.url_hash
        for item in select_articles(articles, INTEREST_TOPICS, recall_k)
    }
    missed = [r.article for r in records if r.is_relevant and r.article.url_hash not in wide]
    if missed:
        print(f"\n{'=' * 70}")
        print(f"상위 {recall_k}건에도 못 든 관련 기사")
        for article in missed:
            score = score_article(article, INTEREST_TOPICS).score
            print(f"  {score}점 {article.title[:45]}")


def main() -> None:
    args = parse_args()

    if not EVAL_SET_FILE.exists():
        print(
            f"{EVAL_SET_FILE}이 없습니다. "
            "먼저 export_eval_set.py 실행: uv run python scripts/export_eval_set.py"
        )
        return

    records = filter_split(read_eval_set(EVAL_SET_FILE), args.split)
    if not records:
        print(f"'{args.split}' 분할에 기사가 없습니다.")
        return

    metrics = compute_metrics(records)

    print(f"분할 {args.split}: {metrics.total}건 (관련 {metrics.relevant}건)")
    print(f"주제: {', '.join(t.name for t in INTEREST_TOPICS)}")
    print(
        "k는 라벨 60건 기준(P@10, R@30)을 평가 건수에 비례해 줄인 값이다\n"
    )
    print(f"Precision@{metrics.precision_k}: {metrics.precision:.2f}")
    print(f"Recall@{metrics.recall_k}: {metrics.recall:.2f}\n")

    print_details(records, metrics.precision_k, metrics.recall_k)


if __name__ == "__main__":
    main()
