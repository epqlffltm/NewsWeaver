# NewsWeaver/src/news_weaver/deliver/fake.py

"""
테스트용 가짜 발송기.

테스트가 실제 메일을 보내면 안 되므로 전송 대신 내용을 보관한다.
발송 실패 상황도 재현할 수 있어야 실패 처리 로직을 검증할 수 있다.
"""

from news_weaver.deliver.base import DeliveryResult


class FakeMailSender:
    """보내는 대신 마지막 메일을 기억한다."""

    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail

        # 검증을 위해 보관한다. 실제 발송기에는 없는 속성이다
        self.sent_subject: str | None = None
        self.sent_body: str | None = None
        self.send_count = 0

    def send(self, subject: str, html_body: str) -> DeliveryResult:
        """발송을 흉내 내고 내용을 보관한다."""
        self.send_count += 1

        if self._should_fail:
            return DeliveryResult(is_sent=False, error="의도적으로 실패시킨 발송")

        self.sent_subject = subject
        self.sent_body = html_body

        return DeliveryResult(is_sent=True)