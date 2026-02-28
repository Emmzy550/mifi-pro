import os
from typing import Dict, Any


class SMSService:
    @classmethod
    def send_sms(cls, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS via Twilio.
        Provider: TWILIO only.
        """
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_FROM_NUMBER")
        messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

        if not account_sid or not auth_token:
            return {
                "status": "FAILED",
                "message": "TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN is not set",
                "environment": "production"
            }

        if not from_number and not messaging_service_sid:
            return {
                "status": "FAILED",
                "message": "Set TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID",
                "environment": "production"
            }

        try:
            from twilio.rest import Client
        except Exception as e:
            return {
                "status": "FAILED",
                "message": f"Twilio SDK not available: {e}",
                "environment": "production"
            }

        try:
            client = Client(account_sid, auth_token)
            create_args: Dict[str, Any] = {
                "body": message,
                "to": phone_number
            }
            if messaging_service_sid:
                create_args["messaging_service_sid"] = messaging_service_sid
            else:
                create_args["from_"] = from_number

            msg = client.messages.create(**create_args)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"TWILIO SMS SENT: To={phone_number}, SID={msg.sid}, Status={msg.status}")
            return {
                "status": "SENT",
                "provider_id": msg.sid,
                "environment": "production"
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"TWILIO SMS FAILED: {str(e)}")
            return {
                "status": "FAILED",
                "message": str(e),
                "environment": "production"
            }
