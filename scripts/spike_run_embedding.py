# NewsWeaver/scripts/spike_run_embedding.py

"""
저장된 기사에 임베딩을 생성하고 결과를 확인하는 스파이크 스크립트.

두 번 실행했을 때 두 번째가 0건이어야 재생성 대상 판정이 제대로 동작하는
것이다. 생성 후에는 같은 주제의 기사끼리 실제로 가까운 벡터가 나오는지도
확인해야 검색 단계로 넘어갈 수 있다.
"""

import time

from dotenv import load_dotenv

from news_weaver.config import get_settings
from news_weaver.db.article_repository import ArticleRepository
from news_weaver.db.engine import get_session_factory
from news_weaver.embedding.ollama import OllamaEmbedder
from news_weaver.logging_config import configure_logging

load_dotenv()

# 한 번에 처리할 상한. 수집 규모가 커져도 배치 시간이 예측 가능하게 한다
EMBEDDING_BATCH_LIMIT = 300


def main() -> None:
    configure_logging()

    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        repository = ArticleRepository(session)
        targets = repository.find_articles_without_embedding(
            settings.embedding_model,
            EMBEDDING_BATCH_LIMIT,
        )

        print(f"대상 {len(targets)}건 / 모델 {settings.embedding_model}")

        if not targets:
            print("생성할 임베딩이 없습니다.")
            return

        started_at = time.perf_counter()
        results = OllamaEmbedder().embed(targets)
        elapsed_seconds = time.perf_counter() - started_at

        updated_count = repository.save_embeddings(results)
        session.commit()

    failed = [result for result in results if not result.is_success]

    print(f"소요 {elapsed_seconds:.1f}초 / 건당 {elapsed_seconds / len(targets):.2f}초")
    print(f"저장 {updated_count}건 / 실패 {len(failed)}건")

    for result in failed[:5]:
        print(f"  실패: {result.url_hash[:12]} — {result.error}")


if __name__ == "__main__":
    main()