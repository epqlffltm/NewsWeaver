# NewsWeaver/src/news_weaver/deliver/base.py

"""
다이제스트 발송기가 지켜야 할 인터페이스와 발송 결과 표현.

테스트에서 실제 메일을 보낼 수는 없으므로 가짜 구현으로 대체하기 위해
프로토콜을 둔다. 발송 수단을 SMTP 외의 것으로 바꿀 가능성은 부수적이다.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """한 번의 발송 시도 결과."""

    is_sent: bool
    error: str | None = None


class MailSender(Protocol):
    """다이제스트를 전달하는 구현이 지켜야 할 인터페이스."""

    def send(self, subject: str, html_body: str) -> DeliveryResult:
        """
        메일을 보낸다.

        발송 실패는 배치 전체를 중단시킬 이유가 아니므로 예외 대신
        결과값으로 알린다. 요약은 이미 캐시에 남아 재시도가 저렴하다.
        """
        ...