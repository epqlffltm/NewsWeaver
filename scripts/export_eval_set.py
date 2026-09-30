# NewsWeaver/scripts/export_eval_set.py

"""
라벨 붙은 기사를 DB에서 꺼내 고정 평가셋(JSONL)으로 얼린다.

평가가 로컬 DB에 묶이면 저장소를 새로 받은 사람은 숫자를 재현할 수 없다.
기사 본문 정보와 정답, dev/test 분할을 파일에 함께 담아 커밋하면, 평가
스크립트는 DB 없이 이 파일만으로 같은 숫자를 낸다.

분할 규칙은 news_weaver.selection.evaluation.assign_splits를 따른다.
라벨을 추가했다면 이 스크립트를 다시 실행해 파일을 갱신한다.
"""

import json
from pathlib import Path

from dotenv import load_dotenv

from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.selection.evaluation import (
    SPLIT_TEST,
    EvalRecord,
    assign_splits,
    write_eval_set,
)

load_dotenv()

LABEL_FILE = Path("evaluation/selection_labels.json")
EVAL_SET_FILE = Path("evaluation/selection_eval.jsonl")


def main() -> None:
    if not LABEL_FILE.exists():
        print("라벨이 없습니다. scripts/label_articles.py를 먼저 실행하세요.")
        return

    labels: dict[str, bool] = json.loads(LABEL_FILE.read_text(encoding="utf-8"))

    session_factory = get_session_factory()
    with session_factory() as session:
        articles = ArticleRepository(session).find_articles_by_hashes(list(labels))

    # DB에 없는 라벨로 분할을 정하면, 나중에 기사가 채워질 때 분할이 흔들린다.
    # 실제로 내보내는 기사만으로 정한다
    found = {article.url_hash: labels[article.url_hash] for article in articles}
    missing_count = len(labels) - len(found)
    if missing_count:
        print(f"경고: 라벨 {missing_count}건의 기사가 DB에 없어 제외합니다.")

    if not found:
        print("내보낼 기사가 없습니다.")
        return

    splits = assign_splits(found)
    records = [
        EvalRecord(
            article=article,
            is_relevant=found[article.url_hash],
            split=splits[article.url_hash],
        )
        for article in articles
    ]
    write_eval_set(EVAL_SET_FILE, records)

    test_records = [r for r in records if r.split == SPLIT_TEST]
    print(
        f"{EVAL_SET_FILE}에 {len(records)}건 저장 "
        f"(test {len(test_records)}건, 관련 "
        f"{sum(r.is_relevant for r in test_records)}건 / "
        f"dev {len(records) - len(test_records)}건)"
    )


if __name__ == "__main__":
    main()
