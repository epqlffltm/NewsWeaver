# NewsWeaver/src/news_weaver/deliver/smtp.py

"""
SMTP로 다이제스트 메일을 발송한다.

발송 실패는 네트워크나 인증 문제로 흔히 발생하지만 배치를 중단시킬 이유는
아니다. 요약이 이미 캐시에 남아 있어 재실행 비용이 낮으므로, 실패를 예외가
아닌 결과값으로 돌려 호출자가 판단하게 한다.
"""

import smtplib
from email.message import EmailMessage

from news_weaver.config import get_settings
from news_weaver.deliver.base import DeliveryResult

# 응답이 없을 때 배치가 멈추지 않도록 상한을 둔다
SMTP_TIMEOUT_SECONDS = 30


class SmtpMailSender:
    """SMTP 서버를 통해 메일을 보낸다."""

    def __init__(self) -> None:
        settings = get_settings()
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = settings.smtp_password
        self._recipient = settings.mail_recipient

    def send(self, subject: str, html_body: str) -> DeliveryResult:
        """메일을 보내고 성공 여부를 반환한다."""
        message = self._build_message(subject, html_body)

        try:
            self._transmit(message)
        except (smtplib.SMTPException, OSError) as error:
            return DeliveryResult(is_sent=False, error=f"발송 실패: {error}")

        return DeliveryResult(is_sent=True)

    def _build_message(self, subject: str, html_body: str) -> EmailMessage:
        """발송할 메시지를 조립한다."""
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self._username
        message["To"] = self._recipient

        # HTML을 읽지 못하는 환경을 위해 대체 본문을 함께 넣는다
        message.set_content("이 메일은 HTML 형식입니다.")
        message.add_alternative(html_body, subtype="html")

        return message

    def _transmit(self, message: EmailMessage) -> None:
        """SMTP 서버에 접속해 메시지를 전송한다."""
        with smtplib.SMTP(self._host, self._port, timeout=SMTP_TIMEOUT_SECONDS) as server:
            # 587 포트는 평문으로 연결한 뒤 TLS로 승격하는 방식이다
            server.starttls()
            server.login(self._username, self._password)
            server.send_message(message)