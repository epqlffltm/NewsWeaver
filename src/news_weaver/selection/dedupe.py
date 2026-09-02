# NewsWeaver/src/news_weaver/selection/dedupe.py

"""
같은 사건을 다루는 기사를 묶어 대표 하나만 남긴다.

여러 매체가 같은 사건을 보도하면 URL이 달라 URL 해시로는 걸러지지 않는다.
그대로 두면 다이제스트에 같은 내용이 여러 번 실리고, 소스를 늘릴수록
심해진다.

무엇을 남길지는 선별 점수 순위를 따른다. 점수가 이미 관심도를 나타내므로
별도의 대표 선정 기준이 필요하지 않다.
"""

from dataclasses import dataclass

from news_weaver.selection.keyword import ScoredArticle


@dataclass(frozen=True, slots=True)
class DedupeReport:
    """중복 제거 결과와 무엇이 왜 제외됐는지를 담는다."""

    kept: list[ScoredArticle]

    # 제외된 기사의 제목과 그 원인이 된 대표 기사의 제목.
    # 임계값이 적절한지 사람이 검토하는 근거가 된다
    removed: list[tuple[str, str]]


def _build_similarity_map(
    pairs: list[tuple[str, str, float]],
) -> dict[str, set[str]]:
    """유사 쌍 목록을 url_hash에서 유사한 상대들로 가는 사전으로 만든다."""
    similar_to: dict[str, set[str]] = {}

    for left_hash, right_hash, _ in pairs:
        similar_to.setdefault(left_hash, set()).add(right_hash)
        similar_to.setdefault(right_hash, set()).add(left_hash)

    return similar_to


def remove_near_duplicates(
    scored: list[ScoredArticle],
    similarity_pairs: list[tuple[str, str, float]],
) -> DedupeReport:
    """
    유사한 기사 중 점수가 높은 것만 남긴다.

    점수 높은 순으로 순회하며 이미 선택된 기사와 유사하면 제외한다.
    클러스터링 대신 이 방식을 쓰는 이유는 후보가 수십 건 규모라 결과가
    같으면서 훨씬 단순하기 때문이다.
    """
    similar_to = _build_similarity_map(similarity_pairs)

    kept: list[ScoredArticle] = []
    kept_by_hash: dict[str, str] = {}
    removed: list[tuple[str, str]] = []

    for item in scored:
        current_hash = item.article.url_hash
        neighbors = similar_to.get(current_hash, set())

        representative = next(
            (kept_by_hash[hash_] for hash_ in neighbors if hash_ in kept_by_hash),
            None,
        )

        if representative is None:
            kept.append(item)
            kept_by_hash[current_hash] = item.article.title
        else:
            removed.append((item.article.title, representative))

    return DedupeReport(kept=kept, removed=removed)