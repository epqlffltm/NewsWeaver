# NewsWeaver/src/news_weaver/db/summary_repository.py

"""
요약 캐시의 조회와 저장을 담당한다.

요약은 건당 수십 초에서 수 분이 걸리므로 재실행 때마다 다시 만들면 안 된다.
다만 모델이나 프롬프트가 바뀌면 결과가 달라지므로, 그 조건을 조회 키에 포함해
조건이 바뀐 요약은 캐시에 없는 것으로 취급한다.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from news_weaver.db.tables import SummaryRow
from news_weaver.summarize.base import SummaryResult


class SummaryRepository:
    """summaries 테이블에 대한 읽기와 쓰기를 담당한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_cached(
        self,
        url_hashes: list[str],
        model_name: str,
        prompt_version: str,
    ) -> dict[str, str]:
        """
        이미 요약된 기사들을 url_hash에서 요약문으로 가는 사전으로 반환한다.

        기사마다 조회하면 왕복이 건수만큼 늘어나므로 한 번에 가져온다.
        모델과 프롬프트가 다른 요약은 재사용할 수 없으므로 조회 조건에 포함한다.
        """
        if not url_hashes:
            return {}

        statement = select(SummaryRow.url_hash, SummaryRow.summary_text).where(
            SummaryRow.url_hash.in_(url_hashes),
            SummaryRow.model_name == model_name,
            SummaryRow.prompt_version == prompt_version,
        )

        rows = self._session.execute(statement).all()

        return {row.url_hash: row.summary_text for row in rows}

    def save_summaries(self, results: list[SummaryResult]) -> int:
        """
        성공한 요약만 저장하고 새로 저장된 건수를 반환한다.

        실패한 결과를 저장하면 다음 실행에서 재시도할 수 없게 되므로 제외한다.
        중복 저장 시도는 재실행 시 정상적인 상황이므로 DB 제약에 맡겨 건너뛴다.
        """
        rows = [_to_row_values(result) for result in results if result.is_success]

        if not rows:
            return 0

        statement = (
            insert(SummaryRow)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["url_hash", "model_name", "prompt_version"]
            )
            .returning(SummaryRow.id)
        )

        inserted_ids = self._session.execute(statement).scalars().all()

        return len(inserted_ids)


def _to_row_values(result: SummaryResult) -> dict:
    """요약 결과를 테이블 컬럼 값으로 변환한다."""
    return {
        "url_hash": result.url_hash,
        "summary_text": result.summary_text,
        "model_name": result.model_name,
        "prompt_version": result.prompt_version,
    }