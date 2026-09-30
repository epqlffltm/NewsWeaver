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

# 출처가 하나 늘 때마다 더할 점수. 여러 매체가 다룬 사건은 그 자체로
# 뉴스 가치가 있다는 신호이므로 순위에 반영한다.
# 값이 크면 관심 밖 사건이 보도량만으로 상위에 오르므로 실측으로 조정한다
EXTRA_SOURCE_SCORE = 2


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
    def score(self) -> int:
        """
        그룹의 순위 점수.

        대표 기사의 관심도에 보도량을 더한다. 같은 사건을 여러 매체가
        다뤘다는 사실은 관심 주제 일치와는 다른 종류의 신호이므로,
        기사 단위 점수에 섞지 않고 그룹 단계에서 더한다.
        """
        return self.representative.score + len(self.others) * EXTRA_SOURCE_SCORE

    @property
    def group_key(self) -> str:
        """
        그룹 구성을 식별하는 키.

        브리핑 캐시의 키로 쓴다. 구성원이 하나라도 바뀌면 종합 결과가
        달라지므로, 구성 자체가 키에 반영되어야 한다.
        """
        joined = "|".join(sorted(item.article.url_hash for item in self.members))
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _find_root(parent: dict[str, str], url_hash: str) -> str:
    """Union-Find의 대표 원소를 찾는다. 경로를 압축해 다음 조회를 줄인다."""
    root = url_hash
    while parent[root] != root:
        root = parent[root]

    while parent[url_hash] != root:
        parent[url_hash], url_hash = root, parent[url_hash]

    return root


def group_similar_articles(
    scored: list[ScoredArticle],
    similarity_pairs: list[tuple[str, str, float]],
) -> list[ArticleGroup]:
    """
    유사한 기사를 하나의 그룹으로 묶는다.

    유사 쌍을 간선으로 보고 연결 요소(connected component)를 구한다.
    기사를 하나씩 기존 그룹에 붙이는 방식은 입력이 C, A, B 순이고
    A-B, B-C만 유사할 때, C와 A가 먼저 따로 그룹을 만든 뒤 B가 둘을
    잇더라도 두 그룹이 합쳐지지 않는다. Union-Find는 간선을 모두 반영한
    뒤 그룹을 정하므로 입력 순서와 무관하게 같은 결과가 나온다.

    짝이 없는 기사도 구성원이 하나인 그룹이 된다. 호출자가 단일 기사와
    묶인 기사를 나눠 처리하지 않아도 되게 하기 위함이다.

    그룹 순서와 그룹 내 구성원 순서는 입력 순서를 따른다. 입력이 점수
    순이면 각 그룹의 첫 기사가 점수 최고 기사, 즉 대표가 된다. 보도량을
    반영한 재정렬은 호출자의 몫이다.
    """
    parent = {item.article.url_hash: item.article.url_hash for item in scored}

    for left_hash, right_hash, _ in similarity_pairs:
        # 후보 밖의 기사가 섞인 쌍은 무시한다. 없는 원소를 만들면
        # 후보에 없던 기사를 통해 무관한 그룹이 이어질 수 있다
        if left_hash not in parent or right_hash not in parent:
            continue

        left_root = _find_root(parent, left_hash)
        right_root = _find_root(parent, right_hash)
        if left_root != right_root:
            parent[right_root] = left_root

    # dict는 삽입 순서를 유지하므로, 대표 원소를 처음 만난 순서가 곧
    # 그룹의 입력 순서가 된다
    members_by_root: dict[str, list[ScoredArticle]] = {}
    for item in scored:
        root = _find_root(parent, item.article.url_hash)
        members_by_root.setdefault(root, []).append(item)

    return [
        ArticleGroup(representative=members[0], others=tuple(members[1:]))
        for members in members_by_root.values()
    ]


def take_representatives(groups: list[ArticleGroup]) -> list[ScoredArticle]:
    """각 그룹의 대표만 뽑는다. 브리핑 없이 기사 단위로 다룰 때 쓴다."""
    return [group.representative for group in groups]