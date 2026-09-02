# NewsWeaver/scripts/spike_check_profile.py

"""
관심사를 문장으로 임베딩해 기사를 찾는 방식이 실제로 통하는지 확인한다.

임베딩 모델은 비슷한 성격과 길이의 텍스트끼리 잘 맞는 경향이 있어,
짧은 관심사 문장과 긴 기사 본문이 같은 공간에서 의미 있게 비교될지는
실측해야 안다.

키워드로 이미 잡히는 기사만 나온다면 이 방식은 추가 가치가 없으므로,
결과마다 키워드 매칭 여부를 함께 표시한다.
"""

import requests
from dotenv import load_dotenv
from sqlalchemy import text

from news_weaver.config import get_settings
from news_weaver.db.engine import get_session_factory
from news_weaver.domain.article import Article
from news_weaver.selection.interests import INTEREST_TOPICS
from news_weaver.selection.keyword import score_article

load_dotenv()

TOP_K = 15

# 표현 방식에 따라 결과가 달라지는지 보기 위해 여러 형태를 시험한다
PROFILE_CANDIDATES = {
    "키워드 나열": "AI, 인공지능, 반도체, 클라우드, 정보보안",
    "명사구": "AI 반도체와 클라우드 인프라, 기업 정보보안 기술 동향",
    "기사체 문장": (
        "인공지능과 반도체 산업의 기술 개발 동향, 클라우드 인프라 도입과 "
        "정부 정책, 기업의 정보보안 대응에 관한 소식이다."
    ),
}


def request_embedding(base_url: str, model_name: str, content: str) -> list[float]:
    """Ollama에 임베딩을 요청하고 벡터를 반환한다."""
    response = requests.post(
        f"{base_url}/api/embed",
        json={"model": model_name, "input": content},
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["embeddings"][0]


def find_nearest(session, model_name: str, vector: list[float], limit: int):
    """주어진 벡터와 가까운 기사를 찾는다."""
    statement = text("""
        SELECT
            source_name, title, url, url_hash,
            collected_at, published_at, author, summary,
            1 - (embedding <=> CAST(:query_vector AS vector)) AS similarity
        FROM articles
        WHERE embedding IS NOT NULL
          AND embedding_model = :model_name
        ORDER BY embedding <=> CAST(:query_vector AS vector)
        LIMIT :limit
    """)

    return session.execute(
        statement,
        {
            "query_vector": str(vector),
            "model_name": model_name,
            "limit": limit,
        },
    ).all()


def to_article(row) -> Article:
    """조회 결과를 도메인 모델로 변환한다."""
    return Article(
        source_name=row.source_name,
        title=row.title,
        url=row.url,
        url_hash=row.url_hash,
        collected_at=row.collected_at,
        published_at=row.published_at,
        author=row.author,
        summary=row.summary,
    )


def main() -> None:
    settings = get_settings()
    session_factory = get_session_factory()

    with session_factory() as session:
        for label, profile_text in PROFILE_CANDIDATES.items():
            vector = request_embedding(
                settings.ollama_base_url,
                settings.embedding_model,
                profile_text,
            )
            rows = find_nearest(session, settings.embedding_model, vector, TOP_K)

            print(f"\n{'=' * 70}")
            print(f"[{label}] {profile_text[:50]}")

            new_count = 0
            for row in rows:
                article = to_article(row)
                keyword_score = score_article(article, INTEREST_TOPICS).score
                marker = "키워드O" if keyword_score > 0 else "키워드X"

                if keyword_score == 0:
                    new_count += 1

                print(f"  {row.similarity:.3f} [{marker}] {article.title[:45]}")

            print(f"  → 키워드로 못 잡는 기사 {new_count}/{len(rows)}건")


if __name__ == "__main__":
    main()