# NewsWeaver/scripts/spike_bench_ollama.py

"""
요약 모델 후보들의 속도와 출력 품질을 실제 수집 기사로 비교하기 위한 스파이크 스크립트.

모델 선택은 배치 소요 시간과 요약 품질을 동시에 좌우하므로 추측이 아니라 실측으로
정한다. 한 건만으로는 판단할 수 없어 DB에 저장된 실제 기사 여러 건을 사용하며,
첫 호출에 포함되는 모델 로딩 시간은 측정에서 제외한다.
"""

import time

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from news_weaver.db.engine import get_session_factory
from news_weaver.db.tables import ArticleRow

load_dotenv()

OLLAMA_URL = "http://localhost:11434/api/generate"

SAMPLE_SIZE = 3

# think 옵션은 지원하지 않는 모델에서는 무시되므로 None으로 두어 전달하지 않는다.
MODEL_CANDIDATES = (
    {"name": "qwen3:8b", "think": False},
    {"name": "gemma4:e4b", "think": None},
    {"name": "gemma4:26b", "think": None},
)


def fetch_sample_articles(limit: int) -> list[tuple[str, str]]:
    """DB에서 요약 대상 기사를 뽑는다. 요약 원문이 있는 것만 고른다."""
    session_factory = get_session_factory()

    with session_factory() as session:
        rows = session.execute(
            select(ArticleRow.title, ArticleRow.summary)
            .where(ArticleRow.summary.is_not(None))
            .limit(limit)
        ).all()

    return [(row.title, row.summary) for row in rows]


def build_prompt(title: str, summary: str) -> str:
    """요약 요청 프롬프트를 만든다."""
    return (
        "다음 뉴스를 3문장 이내로 요약해줘. "
        "원문에 없는 내용은 추가하지 말고, 핵심 사실은 빠뜨리지 마.\n\n"
        f"제목: {title}\n본문: {summary}"
    )


def request_summary(model_name: str, think: bool | None, prompt: str) -> str:
    """Ollama에 요약을 요청하고 응답 텍스트를 반환한다."""
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
    }
    if think is not None:
        payload["think"] = think

    response = requests.post(OLLAMA_URL, json=payload, timeout=600)
    response.raise_for_status()

    return response.json()["response"]


def measure_model(
    model_name: str,
    think: bool | None,
    articles: list[tuple[str, str]],
) -> None:
    """모델을 워밍업한 뒤 기사별 소요 시간과 출력을 보고한다."""
    print(f"\n{'=' * 70}")
    print(f"[{model_name}]")

    # 모델 로딩은 배치 전체에서 한 번만 발생하므로 측정에서 제외한다
    request_summary(model_name, think, build_prompt(*articles[0]))

    total_seconds = 0.0

    for index, (title, summary) in enumerate(articles, start=1):
        started_at = time.perf_counter()
        result = request_summary(model_name, think, build_prompt(title, summary))
        elapsed_seconds = time.perf_counter() - started_at
        total_seconds += elapsed_seconds

        print(f"\n  ({index}) {title[:40]}")
        print(f"  소요: {elapsed_seconds:.1f}초")
        print(f"  요약: {result.strip()}")

    average_seconds = total_seconds / len(articles)
    print(f"\n  평균 {average_seconds:.1f}초 / 20건 환산 {average_seconds * 20 / 60:.1f}분")


def main() -> None:
    articles = fetch_sample_articles(SAMPLE_SIZE)

    if not articles:
        print("요약 가능한 기사가 없습니다. 먼저 수집을 실행하세요.")
        return

    print(f"샘플 {len(articles)}건으로 비교합니다.")

    for candidate in MODEL_CANDIDATES:
        measure_model(candidate["name"], candidate["think"], articles)


if __name__ == "__main__":
    main()