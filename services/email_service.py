import os
import smtplib
from email.message import EmailMessage
from typing import Dict, Any, Optional


class EmailService:
    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an email via SMTP. Falls back to sandbox mock when SMTP is not configured.
        """
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USER")
        password = os.getenv("SMTP_PASS")
        sender = os.getenv("SMTP_FROM") or username or "no-reply@loanofficer.ai"
        use_tls = os.getenv("SMTP_TLS", "true").lower() == "true"

        if not host:
            print(f"EMAIL SANDBOX MOCK: To {to_email} | Subject: {subject} | Body: {body_text}")
            return {
                "status": "SENT",
                "environment": "sandbox",
                "provider_id": "MOCK-EMAIL"
            }

        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body_text)

        if body_html:
            msg.add_alternative(body_html, subtype="html")

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if use_tls:
                    server.starttls()
                if username and password:
                    server.login(username, password)
                server.send_message(msg)
            return {
                "status": "SENT",
                "environment": "production"
            }
        except Exception as e:
            return {
                "status": "FAILED",
                "environment": "production",
                "message": str(e)
            }
