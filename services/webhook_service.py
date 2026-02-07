import json
import time
import uuid
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional
from urllib import request
from urllib.parse import urlparse

from models.organization import Organization

logger = logging.getLogger(__name__)


class WebhookService:
    """
    Lightweight webhook sender with HMAC signing and retries.
    Uses only stdlib to avoid extra dependencies.
    """

    @staticmethod
    def _sign_payload(secret: str, payload: str) -> str:
        signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"sha256={signature}"

    @staticmethod
    def send_event(
        org: Organization,
        event_type: str,
        payload: Dict[str, Any],
        max_attempts: int = 3,
        timeout_seconds: int = 8
    ) -> Optional[str]:
        """
        Send a signed webhook event. Returns webhook_id on best-effort send, None if no webhook configured.
        """
        if not org or not org.webhook_url:
            return None

        parsed = urlparse(org.webhook_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            logger.warning(
                "Skipping webhook send: invalid webhook_url for org %s: %r",
                getattr(org, "id", "unknown"),
                org.webhook_url,
            )
            return None

        webhook_id = f"wh_{uuid.uuid4().hex}"
        body = json.dumps({
            "id": webhook_id,
            "event": event_type,
            "organization_id": org.id,
            "timestamp": int(time.time()),
            "data": payload
        }, default=str)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Id": webhook_id,
            "X-Webhook-Event": event_type,
        }

        if org.webhook_secret:
            headers["X-Webhook-Signature"] = WebhookService._sign_payload(org.webhook_secret, body)

        try:
            req = request.Request(org.webhook_url, data=body.encode("utf-8"), headers=headers, method="POST")
        except ValueError:
            logger.warning(
                "Skipping webhook send: malformed webhook_url for org %s: %r",
                getattr(org, "id", "unknown"),
                org.webhook_url,
            )
            return None

        for attempt in range(1, max_attempts + 1):
            try:
                with request.urlopen(req, timeout=timeout_seconds) as resp:
                    _ = resp.read()
                    return webhook_id
            except Exception:
                if attempt >= max_attempts:
                    return webhook_id
                time.sleep(2 ** (attempt - 1))

        return webhook_id
