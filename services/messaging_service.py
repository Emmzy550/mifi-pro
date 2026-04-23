import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from services.sms_service import SMSService


class MessagingService:
    @classmethod
    def _mode(cls) -> str:
        return str(os.getenv("MESSAGING_PROVIDER_MODE", "mock")).strip().lower() or "mock"

    @classmethod
    def _provider_name(cls, channel: str) -> str:
        if channel == "WHATSAPP":
            return os.getenv("WHATSAPP_PROVIDER", "MOCK_WHATSAPP").upper()
        return os.getenv("SMS_PROVIDER", "TWILIO").upper()

    @classmethod
    def _mock_result(cls, channel: str, message: str) -> Dict[str, Any]:
        provider = cls._provider_name(channel)
        return {
            "status": "MOCKED",
            "provider": provider,
            "provider_id": f"{channel[:2]}-MOCK-{int(datetime.now(timezone.utc).timestamp())}",
            "environment": cls._mode(),
            "message": message,
        }

    @classmethod
    def _send_twilio_whatsapp(cls, phone_number: str, message: str) -> Dict[str, Any]:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_WHATSAPP_FROM_NUMBER")

        if not account_sid or not auth_token or not from_number:
            return cls._mock_result("WHATSAPP", "WhatsApp provider not configured; message logged in mock mode.")

        try:
            from twilio.rest import Client
        except Exception as exc:
            return {
                "status": "FAILED",
                "provider": "TWILIO",
                "environment": "production",
                "message": f"Twilio SDK not available: {exc}",
            }

        try:
            client = Client(account_sid, auth_token)
            msg = client.messages.create(
                body=message,
                from_=from_number if str(from_number).startswith("whatsapp:") else f"whatsapp:{from_number}",
                to=phone_number if str(phone_number).startswith("whatsapp:") else f"whatsapp:{phone_number}",
            )
            return {
                "status": "SENT",
                "provider": "TWILIO",
                "provider_id": msg.sid,
                "environment": "production",
            }
        except Exception as exc:
            return {
                "status": "FAILED",
                "provider": "TWILIO",
                "environment": "production",
                "message": str(exc),
            }

    @classmethod
    def send(
        cls,
        channel: str,
        phone_number: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        del metadata
        normalized_channel = str(channel or "SMS").strip().upper()
        if cls._mode() == "mock":
            return cls._mock_result(normalized_channel, "Messaging provider is in mock mode.")

        if normalized_channel == "WHATSAPP":
            return cls._send_twilio_whatsapp(phone_number, message)

        sms_result = SMSService.send_sms(phone_number, message)
        sms_result["provider"] = cls._provider_name("SMS")
        return sms_result
