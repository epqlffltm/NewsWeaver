# NewsWeaver/src/news_weaver/selection/dedupe.py

"""
같은 사건을 다루는 기사를 하나의 그룹으로 묶는다.

여러 매체가 같은 사건을 보도하면 URL이 달라 URL 해시로는 걸러지지 않는다.
그대로 두면 다이제스트에 같은 내용이 여러 번 실리고, 소스를 늘릴수록
심해진다.

묶인 기사를 버리지 않고 그룹으로 남기는 이유는, 매체마다 강조하는 부분이
달라 함께 요약하면 단일 기사보다 정보가 풍부해지기 때문이다. 대표 하나만
필요한 경우를 위해 그룹에서 대표를 뽑는 함수를 따로 둔다.

무엇을 대표로 삼을지는 선별 점수 순위를 따른다. 점수가 이미 관심도를
나타내므로 별도의 기준이 필요하지 않다.
"""

import hashlib
from dataclasses import dataclass

from news_weaver.selection.keyword import ScoredArticle


@dataclass(frozen=True, slots=True)
class ArticleGroup:
    """같은 사건을 다룬 것으로 판정된 기사들."""

    # 선별 점수가 가장 높은 기사. 그룹을 대표한다
    representative: ScoredArticle

    # 대표를 제외한 나머지. 단일 기사 그룹이면 비어 있다
    others: tuple[ScoredArticle, ...] = ()

    @property
    def members(self) -> tuple[ScoredArticle, ...]:
        """대표를 포함한 모든 구성원."""
        return (self.representative, *self.others)

    @property
    def size(self) -> int:
        """그룹에 속한 기사 수."""
        return 1 + len(self.others)

    @property
    def group_key(self) -> str:
        """
        그룹 구성을 식별하는 키.

        브리핑 캐시의 키로 쓴다. 구성원이 하나라도 바뀌면 종합 결과가
        달라지므로, 구성 자체가 키에 반영되어야 한다.
        """
        joined = "|".join(sorted(item.article.url_hash for item in self.members))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _build_similarity_map(
    pairs: list[tuple[str, str, float]],
) -> dict[str, set[str]]:
    """유사 쌍 목록을 url_hash에서 유사한 상대들로 가는 사전으로 만든다."""
    similar_to: dict[str, set[str]] = {}

    for left_hash, right_hash, _ in pairs:
        similar_to.setdefault(left_hash, set()).add(right_hash)
        similar_to.setdefault(right_hash, set()).add(left_hash)

    return similar_to


def group_similar_articles(
    scored: list[ScoredArticle],
    similarity_pairs: list[tuple[str, str, float]],
) -> list[ArticleGroup]:
    """
    유사한 기사를 하나의 그룹으로 묶는다.

    점수 높은 순으로 순회하며, 이미 만들어진 그룹의 구성원과 유사하면
    그 그룹에 합류시킨다. 클러스터링 대신 이 방식을 쓰는 이유는 후보가
    수십 건 규모라 결과가 같으면서 훨씬 단순하기 때문이다.

    짝이 없는 기사도 구성원이 하나인 그룹이 된다. 호출자가 단일 기사와
    묶인 기사를 나눠 처리하지 않아도 되게 하기 위함이다.
    """
    similar_to = _build_similarity_map(similarity_pairs)

    groups: list[list[ScoredArticle]] = []
    group_index_by_hash: dict[str, int] = {}

    for item in scored:
        current_hash = item.article.url_hash
        neighbors = similar_to.get(current_hash, set())

        existing_index = next(
            (
                group_index_by_hash[neighbor]
                for neighbor in neighbors
                if neighbor in group_index_by_hash
            ),
            None,
        )

        if existing_index is None:
            groups.append([item])
            group_index_by_hash[current_hash] = len(groups) - 1
        else:
            groups[existing_index].append(item)
            group_index_by_hash[current_hash] = existing_index

    return [
        ArticleGroup(representative=members[0], others=tuple(members[1:]))
        for members in groups
    ]


def take_representatives(groups: list[ArticleGroup]) -> list[ScoredArticle]:
    """각 그룹의 대표만 뽑는다. 브리핑 없이 기사 단위로 다룰 때 쓴다."""
    return [group.representative for group in groups]