import os
import requests
from typing import Dict, Any

class SMSService:
    @classmethod
    def send_sms(cls, phone_number: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS via Africa's Talking API.
        Automatically detects Sandbox vs Production based on environment variables.
        """
        username = os.getenv("AFRICASTALKING_USERNAME", "sandbox")
        api_key = os.getenv("AFRICASTALKING_API_KEY")
        sender_id = os.getenv("SMS_SENDER_ID")
        
        # Determine environment
        is_sandbox = username == "sandbox"
        
        if is_sandbox:
            print(f"SMS SANDBOX MOCK: To {phone_number} | Msg: {message}")
            return {
                "status": "SENT",
                "message": "Simulated in sandbox mode",
                "provider_id": "MOCK-12345",
                "environment": "sandbox"
            }
            
        if not api_key:
            return {
                "status": "FAILED",
                "message": "AFRICASTALKING_API_KEY is not set",
                "environment": "production"
            }

        url = "https://api.africastalking.com/version1/messaging"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": api_key
        }
        data = {
            "username": username,
            "to": phone_number,
            "message": message
        }
        if sender_id:
            data["from"] = sender_id

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            res_json = response.json()
            
            # AT Response structure: {'SMSMessageData': {'Message': 'Sent to X/1 Total Cost: Y', 'Recipients': [{'statusCode': 101, 'number': '...', 'status': 'Success', 'cost': '...', 'messageId': '...'}]}}
            recipients = res_json.get("SMSMessageData", {}).get("Recipients", [])
            if recipients and recipients[0].get("status") == "Success":
                return {
                    "status": "SENT",
                    "provider_id": recipients[0].get("messageId"),
                    "environment": "production"
                }
            else:
                return {
                    "status": "FAILED",
                    "message": res_json.get("SMSMessageData", {}).get("Message", "Unknown provider error"),
                    "environment": "production"
                }
        except Exception as e:
            return {
                "status": "FAILED",
                "message": str(e),
                "environment": "production"
            }
