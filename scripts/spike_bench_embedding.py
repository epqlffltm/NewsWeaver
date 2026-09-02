# NewsWeaver/scripts/spike_bench_embedding.py

"""
임베딩 모델 후보의 차원과 속도, 유사도 분별력을 실측하는 스파이크 스크립트.

임베딩은 수집한 기사 전부에 적용되므로 요약보다 건수가 10배 이상 많고,
차원은 벡터 컬럼 타입으로 스키마에 고정된다. 따라서 추측이 아니라 실측으로
정해야 하며, 나중에 바꾸려면 전체 재임베딩이 필요하다.

속도만으로는 판단할 수 없어, 같은 주제의 기사끼리 실제로 가까운 벡터가
나오는지도 함께 확인한다.
"""

import time

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.config import get_settings
from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow

load_dotenv()

SAMPLE_SIZE = 10

MODEL_CANDIDATES = ("embeddinggemma", "bge-m3")


def fetch_sample_texts(limit: int) -> list[tuple[str, str]]:
    """제목과 요약이 모두 있는 기사를 뽑는다."""
    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            select(ArticleRow.title, ArticleRow.summary)
            .where(ArticleRow.summary.is_not(None))
            .limit(limit)
        ).all()

    return [(row.title, row.summary) for row in rows]


def request_embedding(base_url: str, model_name: str, text: str) -> list[float]:
    """Ollama에 임베딩을 요청하고 벡터를 반환한다."""
    response = requests.post(
        f"{base_url}/api/embed",
        json={"model": model_name, "input": text},
        timeout=120,
    )
    response.raise_for_status()

    return response.json()["embeddings"][0]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """두 벡터의 코사인 유사도를 계산한다."""
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5

    return dot / (left_norm * right_norm)


def measure_model(base_url: str, model_name: str, texts: list[str]) -> None:
    """모델을 워밍업한 뒤 차원, 속도, 유사도 분포를 보고한다."""
    print(f"\n{'=' * 70}")
    print(f"[{model_name}]")

    # 모델 로딩은 배치 전체에서 한 번만 발생하므로 측정에서 제외한다
    request_embedding(base_url, model_name, texts[0])

    started_at = time.perf_counter()
    vectors = [request_embedding(base_url, model_name, text) for text in texts]
    elapsed_seconds = time.perf_counter() - started_at

    dimension = len(vectors[0])
    per_item = elapsed_seconds / len(texts)

    print(f"차원: {dimension}")
    print(f"소요: {elapsed_seconds:.1f}초 / 건당 {per_item:.2f}초")
    print(f"140건 환산: {per_item * 140 / 60:.1f}분")

    # 유사도가 전부 비슷하면 분별력이 없다는 뜻이므로 분포를 함께 본다
    similarities = [
        cosine_similarity(vectors[0], vectors[index])
        for index in range(1, len(vectors))
    ]
    print(f"첫 기사와의 유사도: 최고 {max(similarities):.3f} / ")
    print(f"최저 {min(similarities):.3f} / 폭 {max(similarities) - min(similarities):.3f}")


def main() -> None:
    settings = get_settings()
    samples = fetch_sample_texts(SAMPLE_SIZE)

    if not samples:
        print("기사가 없습니다. 먼저 수집을 실행하세요.")
        return

    texts = [f"{title}\n{summary}" for title, summary in samples]

    print(f"샘플 {len(texts)}건")
    print(f"기준 기사: {samples[0][0][:50]}")

    for model_name in MODEL_CANDIDATES:
        measure_model(settings.ollama_base_url, model_name, texts)


if __name__ == "__main__":
    main()