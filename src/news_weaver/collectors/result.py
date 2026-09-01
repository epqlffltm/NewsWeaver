# NewsWeaver/src/news_weaver/collectors/result.py

"""
소스 하나를 수집한 결과와 그 건강 상태를 표현한다.

피드는 예외 없이 조용히 실패하는 경우가 있어(0건 반환, 파싱 오류 무시),
기사 목록만으로는 정상 수집인지 장애인지 구분할 수 없다. 따라서 수집 결과에
상태를 함께 담아 호출자가 판단할 수 있게 한다.
"""

from dataclasses import dataclass, field

from news_weaver.domain.article import Article


@dataclass(frozen=True, slots=True)
class CollectionResult:
    """소스 하나에 대한 수집 결과."""

    source_name: str

    # 정상적으로 변환된 기사들
    articles: list[Article] = field(default_factory=list)

    # 피드 자체를 읽는 데 성공했는지. 0건과 장애를 구분하는 기준이 된다
    is_healthy: bool = True

    # 실패했다면 그 이유. 로그와 알림에 쓴다
    error: str | None = None

    # 제목이나 링크가 없어 버려진 항목 수. 급증하면 파서 점검이 필요하다
    skipped_count: int = 0

    @property
    def article_count(self) -> int:
        """
        수집에 성공한 기사 수.
        """
        return len(self.articles)