# NewsWeaver/src/news_weaver/summarize/fake.py

"""
테스트용 가짜 요약기.

실제 모델 호출은 건당 1~2분이 걸려 테스트에서 쓸 수 없다. 요약 자체가 아니라
그 결과를 다루는 파이프라인 로직을 검증하기 위해 즉시 응답하는 구현을 둔다.
"""

from news_weaver.selection.dedupe import ArticleGroup
from news_weaver.summarize.base import SummaryResult

FAKE_MODEL_NAME = "fake"
FAKE_PROMPT_VERSION = "fake-v1"


class FakeSummarizer:
    """대표 기사의 제목을 돌려주는 요약기. 실패를 재현할 수도 있다."""

    def __init__(self, failing_content_keys: frozenset[str] = frozenset()) -> None:
        # 부분 실패 처리를 검증하려면 일부러 실패시킬 수단이 필요하다
        self._failing_content_keys = failing_content_keys

    def summarize(self, groups: list[ArticleGroup]) -> list[SummaryResult]:
        """각 그룹에 대해 즉시 결과를 만들어 반환한다."""
        return [self._summarize_one(group) for group in groups]

    def _summarize_one(self, group: ArticleGroup) -> SummaryResult:
        """그룹 하나에 대한 결과를 만든다."""
        if group.group_key in self._failing_content_keys:
            return SummaryResult(
                content_key=group.group_key,
                error="의도적으로 실패시킨 항목",
                model_name=FAKE_MODEL_NAME,
                prompt_version=FAKE_PROMPT_VERSION,
            )

        titles = " + ".join(item.article.title for item in group.members)

        return SummaryResult(
            content_key=group.group_key,
            summary_text=f"[요약] {titles}",
            model_name=FAKE_MODEL_NAME,
            prompt_version=FAKE_PROMPT_VERSION,
        )