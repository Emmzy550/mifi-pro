import logging
logger = logging.getLogger(__name__)

import uuid
import secrets
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
import requests
from models.organization import Organization, BillingPlan, PaymentStatus
from models.payment import (
    ACTIVE_PAYMENT_STATUSES,
    CANCELLABLE_PAYMENT_STATUSES,
    RESUMABLE_PAYMENT_STATUSES,
    TERMINAL_PAYMENT_STATUSES,
    Payment,
    PaymentGateway,
    PaymentStatus as AppPaymentStatus,
)
from utils.db import Database
from pricing_config import PLAN_CONFIG
from agents.audit_agent import AuditAgent
from agents.invoice_agent import InvoiceAgent

class GatewayError(Exception):
    """Custom exception for external payment gateway failures."""
    pass


class DuplicateActivePaymentError(ValueError):
    def __init__(self, payment: Payment):
        self.payment = payment
        super().__init__("A payment request is already active. Resume, cancel, or replace it before starting another.")

class PaymentAgent:
    """
    Handles production payment integrations: Lipila (MoMo), Bank Transfer, and Stripe.
    Enforces Zambia-first localization and webhook-ready workflows.
    """
    GatewayError = GatewayError
    DuplicateActivePaymentError = DuplicateActivePaymentError

    @staticmethod
    def _resolve_lipila_base_url(base_url: str) -> str:
        normalized = (base_url or "").strip().rstrip("/")
        return normalized or "https://api.lipila.dev/api/v1"

    @staticmethod
    def _resolve_callback_url() -> Optional[str]:
        public_url = (os.getenv("SERVER_PUBLIC_URL") or "").strip().rstrip("/")
        if not public_url:
            return None
        lowered = public_url.lower()
        if "your-server-public-url.com" in lowered:
            return None
        if "localhost" in lowered or "127.0.0.1" in lowered:
            return None
        if not lowered.startswith("http://") and not lowered.startswith("https://"):
            return None
        return f"{public_url}/billing/webhook/lipila"

    @staticmethod
    def _build_lipila_headers(secret_key: str, callback_url: Optional[str] = None) -> Dict[str, str]:
        normalized_key = (secret_key or "").strip()
        headers = {
            "x-api-key": normalized_key,
            "Authorization": f"Bearer {normalized_key}",
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        if callback_url:
            headers["callbackUrl"] = callback_url
        return headers

    @staticmethod
    def _normalize_zambian_phone_number(phone: str) -> str:
        digits_only = re.sub(r"\D", "", str(phone or ""))
        if not digits_only:
            raise ValueError("Phone number is required.")

        if digits_only.startswith("00260"):
            digits_only = digits_only[2:]

        local_digits = digits_only
        if local_digits.startswith("260"):
            local_digits = local_digits[3:]
        if local_digits.startswith("0"):
            local_digits = local_digits[1:]

        if len(local_digits) > 9:
            raise ValueError("Phone number has too many digits. Use 0971234567 or 260971234567.")

        if len(local_digits) == 9:
            return f"260{local_digits}"

        raise ValueError("Phone number must be in Zambia format: 0971234567 or 260971234567.")

    @staticmethod
    def _is_active_status(status: AppPaymentStatus) -> bool:
        return status in ACTIVE_PAYMENT_STATUSES

    @staticmethod
    def _is_terminal_status(status: AppPaymentStatus) -> bool:
        return status in TERMINAL_PAYMENT_STATUSES

    @staticmethod
    def _is_resumable_status(status: AppPaymentStatus) -> bool:
        return status in RESUMABLE_PAYMENT_STATUSES

    @staticmethod
    def _is_cancellable_status(status: AppPaymentStatus) -> bool:
        return status in CANCELLABLE_PAYMENT_STATUSES

    @staticmethod
    def _parse_metadata_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _cancellation_grace_period() -> timedelta:
        raw_seconds = os.getenv("PAYMENT_CANCEL_GRACE_SECONDS", "20").strip()
        try:
            seconds = max(10, int(raw_seconds))
        except ValueError:
            seconds = 20
        return timedelta(seconds=seconds)

    @staticmethod
    def _cancellation_deadline(payment: Payment) -> Optional[datetime]:
        metadata = payment.metadata or {}
        explicit_deadline = PaymentAgent._parse_metadata_datetime(metadata.get("cancel_deadline_at"))
        if explicit_deadline:
            return explicit_deadline

        requested_at = PaymentAgent._parse_metadata_datetime(metadata.get("cancel_requested_at"))
        if requested_at:
            return requested_at + PaymentAgent._cancellation_grace_period()
        return None

    @staticmethod
    def _client_flow_state(payment: Payment) -> str:
        if payment.status == AppPaymentStatus.SUCCESS:
            return "approved"
        if payment.status == AppPaymentStatus.CANCELLED:
            return "cancelled"
        if payment.status == AppPaymentStatus.CANCELLING:
            return "cancelling"
        if payment.status == AppPaymentStatus.FAILED:
            return "failed"
        if payment.status == AppPaymentStatus.EXPIRED:
            return "expired"
        if payment.gateway == PaymentGateway.BANK_TRANSFER:
            return "invoice_ready"
        return "awaiting_approval" if payment.status == AppPaymentStatus.PROMPT_SENT else "prompt_sent"

    @staticmethod
    def _recommended_poll_interval_ms(payment: Payment) -> Optional[int]:
        if payment.status == AppPaymentStatus.CANCELLING:
            return 2500
        if payment.status in ACTIVE_PAYMENT_STATUSES:
            return 4000
        return None

    @staticmethod
    def _append_lifecycle_event(payment: Payment, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        metadata = dict(payment.metadata or {})
        events = list(metadata.get("lifecycle_events") or [])
        events.append(
            {
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": details or {},
            }
        )
        metadata["lifecycle_events"] = events[-40:]
        payment.metadata = metadata

    @staticmethod
    def _active_payment_message(payment: Payment) -> str:
        if payment.gateway == PaymentGateway.LIPILA:
            return "A mobile-money request is already active for this organization."
        if payment.gateway == PaymentGateway.BANK_TRANSFER:
            return "An unpaid invoice is already open for this organization."
        return "A payment request is already active for this organization."

    @staticmethod
    def _bank_details() -> str:
        return "Standard Chartered Bank (Zambia) - 01234567890"

    @staticmethod
    def _invoice_payload(payment: Payment) -> Optional[Dict[str, Any]]:
        if not payment.invoice_id and not payment.reference_code:
            return None
        return {
            "id": payment.invoice_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "reference": payment.reference_code,
            "bank_details": PaymentAgent._bank_details(),
        }

    @staticmethod
    def _client_message_for_payment(payment: Payment) -> Dict[str, Optional[str]]:
        if payment.gateway == PaymentGateway.LIPILA:
            return PaymentAgent._build_lipila_client_feedback(
                payment.status,
                payment.metadata or {},
                payment.phone_number,
            )

        status = payment.status
        if status == AppPaymentStatus.SUCCESS:
            return {
                "message": "Payment confirmed successfully.",
                "instructions": "Your organization's plan is now active.",
                "phone_number": payment.phone_number,
            }
        if status == AppPaymentStatus.CANCELLED:
            return {
                "message": "Payment request cancelled.",
                "instructions": "MiFi Pro will not create any additional prompts for this request.",
                "phone_number": payment.phone_number,
            }
        if status == AppPaymentStatus.CANCELLING:
            return {
                "message": "Cancelling payment request...",
                "instructions": "MiFi Pro is stopping this request and waiting for final confirmation before allowing a new one.",
                "phone_number": payment.phone_number,
            }
        if status == AppPaymentStatus.EXPIRED:
            return {
                "message": "Payment request expired.",
                "instructions": "Create a fresh payment request if you still want to continue.",
                "phone_number": payment.phone_number,
            }
        if status == AppPaymentStatus.FAILED:
            return {
                "message": payment.metadata.get("gateway_message") or "Payment failed.",
                "instructions": "Review the payment details and try again when ready.",
                "phone_number": payment.phone_number,
            }
        if payment.gateway == PaymentGateway.BANK_TRANSFER:
            return {
                "message": "Invoice generated successfully.",
                "instructions": "Use the invoice and reference code below to complete the transfer.",
                "phone_number": payment.phone_number,
            }
        return {
            "message": "Payment request created.",
            "instructions": "Complete the payment to activate the selected plan.",
            "phone_number": payment.phone_number,
        }

    @staticmethod
    def _serialize_payment(payment: Payment, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        feedback = PaymentAgent._client_message_for_payment(payment)
        payload = {
            "payment_id": payment.payment_id,
            "plan": payment.plan,
            "status": payment.status.value,
            "amount": payment.amount,
            "currency": payment.currency,
            "gateway": payment.gateway.value if hasattr(payment.gateway, "value") else payment.gateway,
            "phone_number": feedback.get("phone_number") or payment.phone_number,
            "message": feedback.get("message"),
            "instructions": feedback.get("instructions"),
            "gateway_status": payment.metadata.get("gateway_status"),
            "gateway_message": payment.metadata.get("gateway_message"),
            "payment_type": payment.metadata.get("payment_type"),
            "provider_reference": payment.transaction_id,
            "identifier": payment.metadata.get("identifier"),
            "invoice": PaymentAgent._invoice_payload(payment),
            "can_cancel": payment.status in CANCELLABLE_PAYMENT_STATUSES,
            "can_resume": payment.status in RESUMABLE_PAYMENT_STATUSES,
            "is_active": payment.status in ACTIVE_PAYMENT_STATUSES,
            "is_terminal": payment.status in TERMINAL_PAYMENT_STATUSES,
            "flow_state": PaymentAgent._client_flow_state(payment),
            "recommended_poll_interval_ms": PaymentAgent._recommended_poll_interval_ms(payment),
            "cancel_requested_at": payment.metadata.get("cancel_requested_at"),
            "cancel_deadline_at": payment.metadata.get("cancel_deadline_at"),
            "cancelled_at": payment.metadata.get("cancelled_at"),
            "provider_cancel_supported": payment.metadata.get("provider_cancel_supported"),
            "timestamp": payment.timestamp.isoformat(),
        }
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    def _mark_org_payment_pending(org: Organization, payment: Payment) -> None:
        org.payment_status = PaymentStatus.PENDING
        org.last_payment_id = payment.payment_id
        Database.save_organization(org)

    @staticmethod
    def _set_org_after_unsuccessful_resolution(payment: Payment, next_payment_status: PaymentStatus) -> None:
        org = Database.get_organization(payment.org_id)
        if not org:
            return
        if org.last_payment_id == payment.payment_id:
            org.last_payment_id = None
        org.payment_status = next_payment_status
        billing_status = getattr(org.billing_status, "value", org.billing_status)
        if next_payment_status == PaymentStatus.UNPAID and str(billing_status).upper() != "ACTIVE":
            org.environment = "SANDBOX"
        Database.save_organization(org)

    @staticmethod
    def _invalidate_retry_state(payment: Payment, reason: str) -> None:
        metadata = dict(payment.metadata or {})
        metadata["retry_state"] = "invalidated"
        metadata["retry_invalidated_at"] = datetime.now(timezone.utc).isoformat()
        metadata["retry_invalidated_reason"] = reason
        metadata["retry_job_active"] = False
        payment.metadata = metadata

    @staticmethod
    def _is_stale(payment: Payment) -> bool:
        now = datetime.now(timezone.utc)
        if payment.status == AppPaymentStatus.CANCELLING:
            return False
        if payment.gateway == PaymentGateway.BANK_TRANSFER:
            return payment.status == AppPaymentStatus.PENDING and payment.timestamp <= now - timedelta(days=7)
        if payment.gateway == PaymentGateway.LIPILA:
            return payment.status in {AppPaymentStatus.PENDING, AppPaymentStatus.PROMPT_SENT} and payment.timestamp <= now - timedelta(minutes=15)
        return payment.status == AppPaymentStatus.PENDING and payment.timestamp <= now - timedelta(hours=1)

    @staticmethod
    def _expire_payment(payment: Payment, reason: str) -> Payment:
        payment.status = AppPaymentStatus.EXPIRED
        metadata = dict(payment.metadata or {})
        metadata["expired_at"] = datetime.now(timezone.utc).isoformat()
        metadata["expiration_reason"] = reason
        payment.metadata = metadata
        PaymentAgent._invalidate_retry_state(payment, reason)
        PaymentAgent._append_lifecycle_event(payment, "EXPIRED", {"reason": reason})
        Database.save_payment(payment)
        PaymentAgent._set_org_after_unsuccessful_resolution(payment, PaymentStatus.UNPAID)
        AuditAgent.log_event("PAYMENT_EXPIRED", payment.org_id, {"payment_id": payment.payment_id, "reason": reason})
        return payment

    @staticmethod
    def _find_existing_active_payment(org_id: str) -> Optional[Payment]:
        payments = PaymentAgent.list_payments_for_org(org_id)
        for payment in payments:
            if payment.status in ACTIVE_PAYMENT_STATUSES:
                return payment
        return None

    @staticmethod
    def list_payments_for_org(org_id: str) -> List[Payment]:
        payments = sorted(Database.list_payments(org_id), key=lambda item: item.timestamp, reverse=True)
        reconciled_payments: List[Payment] = []
        refreshed_active = False

        for payment in payments:
            payment = PaymentAgent._reconcile_local_payment_state(payment, "list_payments")

            if not refreshed_active and payment.gateway == PaymentGateway.LIPILA and payment.status in ACTIVE_PAYMENT_STATUSES:
                try:
                    PaymentAgent.refresh_payment_status(payment)
                    payment = PaymentAgent._reload_payment(payment.payment_id, payment)
                except GatewayError as exc:
                    logger.warning(
                        "PAYMENT_LIST_REFRESH_FAILED payment_id=%s error=%s",
                        payment.payment_id,
                        str(exc),
                    )
                    payment = PaymentAgent._reconcile_local_payment_state(payment, "list_payments_refresh_failed")
                refreshed_active = True

            reconciled_payments.append(payment)

        reconciled_payments = PaymentAgent._expire_superseded_active_payments(reconciled_payments, "list_payments")
        return reconciled_payments

    @staticmethod
    def _expire_superseded_active_payments(payments: List[Payment], source: str) -> List[Payment]:
        active_payments = [payment for payment in payments if payment.status in ACTIVE_PAYMENT_STATUSES]
        if len(active_payments) <= 1:
            return payments

        winner = sorted(active_payments, key=lambda item: item.timestamp, reverse=True)[0]
        for payment in active_payments:
            if payment.payment_id == winner.payment_id:
                continue
            PaymentAgent._expire_payment(
                payment,
                f"{source}_superseded_by_{winner.payment_id}",
            )

        return [PaymentAgent._reload_payment(payment.payment_id, payment) for payment in payments]

    @staticmethod
    def _finalize_cancelled_payment(payment: Payment, reason: str, source: str) -> Payment:
        metadata = dict(payment.metadata or {})
        metadata["cancelled_at"] = datetime.now(timezone.utc).isoformat()
        metadata["cancel_resolution_reason"] = reason
        metadata["cancel_resolution_source"] = source
        payment.metadata = metadata
        payment.status = AppPaymentStatus.CANCELLED
        PaymentAgent._invalidate_retry_state(payment, reason)
        PaymentAgent._append_lifecycle_event(payment, "CANCELLED", {"reason": reason, "source": source})
        Database.save_payment(payment)
        PaymentAgent._set_org_after_unsuccessful_resolution(payment, PaymentStatus.UNPAID)
        AuditAgent.log_event(
            "PAYMENT_CANCELLED",
            payment.org_id,
            {"payment_id": payment.payment_id, "reason": reason, "source": source},
        )
        return payment

    @staticmethod
    def _reconcile_local_payment_state(payment: Payment, source: str) -> Payment:
        if PaymentAgent._is_terminal_status(payment.status):
            return payment

        if payment.status == AppPaymentStatus.CANCELLING:
            deadline = PaymentAgent._cancellation_deadline(payment)
            if deadline and datetime.now(timezone.utc) >= deadline:
                return PaymentAgent._finalize_cancelled_payment(
                    payment,
                    "cancel_grace_window_elapsed",
                    source,
                )
            return payment

        if PaymentAgent._is_stale(payment):
            return PaymentAgent._expire_payment(payment, f"{source}_stale_request")

        return payment

    @staticmethod
    def _reload_payment(payment_id: str, fallback: Payment) -> Payment:
        latest = Database.get_payment(payment_id)
        return latest or fallback

    @staticmethod
    def _build_lipila_client_feedback(
        payment_status: AppPaymentStatus,
        gateway_summary: Dict,
        phone_number: Optional[str],
    ) -> Dict[str, Optional[str]]:
        normalized_phone = (phone_number or "").strip() or gateway_summary.get("raw", {}).get("accountNumber")
        gateway_message = gateway_summary.get("gateway_message")

        if payment_status == AppPaymentStatus.SUCCESS:
            return {
                "message": gateway_message or "Payment confirmed successfully.",
                "instructions": f"Payment confirmed for {normalized_phone}." if normalized_phone else "Payment confirmed successfully.",
                "phone_number": normalized_phone or None,
            }

        if payment_status == AppPaymentStatus.CANCELLED:
            return {
                "message": gateway_message or "Payment request cancelled.",
                "instructions": "MiFi Pro will not create any additional prompts for this request.",
                "phone_number": normalized_phone or None,
            }

        if payment_status == AppPaymentStatus.CANCELLING:
            return {
                "message": gateway_message or "Cancelling payment request...",
                "instructions": "MiFi Pro is stopping this request and waiting for final confirmation before allowing a new one.",
                "phone_number": normalized_phone or None,
            }

        if payment_status == AppPaymentStatus.EXPIRED:
            return {
                "message": gateway_message or "The mobile-money request expired before confirmation.",
                "instructions": (
                    f"The payment request to {normalized_phone} expired. Create a fresh request if you still want to continue."
                    if normalized_phone
                    else "The payment request expired. Create a fresh request if you still want to continue."
                ),
                "phone_number": normalized_phone or None,
            }

        if payment_status == AppPaymentStatus.FAILED:
            return {
                "message": gateway_message or "The mobile-money provider marked this payment request as failed.",
                "instructions": (
                    f"The payment request to {normalized_phone} failed or expired. Check the number and try again."
                    if normalized_phone
                    else "The payment request failed or expired. Check the number and try again."
                ),
                "phone_number": normalized_phone or None,
            }

        return {
            "message": gateway_message or "Payment prompt sent. Waiting for mobile-money confirmation.",
            "instructions": (
                f"Payment prompt sent to {normalized_phone}. Confirm on your phone once your mobile-money provider shows the approval prompt."
                if normalized_phone
                else "Payment prompt sent. Confirm on your phone once your mobile-money provider shows the approval prompt."
            ),
            "phone_number": normalized_phone or None,
        }

    @staticmethod
    def _parse_lipila_gateway_payload(payload: Dict) -> Dict:
        if not isinstance(payload, dict):
            return {}
        return {
            "reference_id": payload.get("referenceId"),
            "external_id": payload.get("externalId"),
            "identifier": payload.get("identifier"),
            "gateway_status": payload.get("status"),
            "gateway_message": payload.get("message"),
            "payment_type": payload.get("paymentType"),
            "gateway_type": payload.get("type"),
            "account_number": payload.get("accountNumber"),
            "created_at": payload.get("createdAt"),
            "raw": payload,
        }

    @staticmethod
    def _status_from_gateway_summary(gateway_status: Optional[str], gateway_message: Optional[str] = None) -> AppPaymentStatus:
        combined = " ".join(
            [
                str(gateway_status or "").strip().lower(),
                str(gateway_message or "").strip().lower(),
            ]
        ).strip()
        if any(token in combined for token in {"successful", "success", "paid", "completed", "approved"}):
            return AppPaymentStatus.SUCCESS
        if any(token in combined for token in {"expired", "timeout", "timed_out", "timed out"}):
            return AppPaymentStatus.EXPIRED
        if any(
            token in combined
            for token in {
                "cancelled",
                "canceled",
                "cancelled by user",
                "canceled by user",
                "user cancelled",
                "user canceled",
                "customer cancelled",
                "customer canceled",
                "abandoned",
            }
        ):
            return AppPaymentStatus.CANCELLED
        if any(token in combined for token in {"failed", "declined", "rejected", "insufficient"}):
            return AppPaymentStatus.FAILED
        if any(token in combined for token in {"pending", "processing", "queued", "created", "initiated", "sent", "prompt"}):
            return AppPaymentStatus.PROMPT_SENT
        return AppPaymentStatus.PENDING

    @staticmethod
    def _summarize_lipila_status(gateway_payload: Dict) -> Dict:
        parsed = PaymentAgent._parse_lipila_gateway_payload(gateway_payload)
        gateway_status = parsed.get("gateway_status") or "Pending"
        gateway_message = parsed.get("gateway_message") or "Request accepted by Lipila. Waiting for mobile-money network confirmation."
        if str(gateway_status).strip().lower() == "pending":
            gateway_message = "Payment request accepted by Lipila and is still pending mobile-money confirmation."
        return {
            "gateway_status": gateway_status,
            "gateway_message": gateway_message,
            "payment_type": parsed.get("payment_type"),
            "reference_id": parsed.get("reference_id"),
            "external_id": parsed.get("external_id"),
            "identifier": parsed.get("identifier"),
            "raw": parsed.get("raw") or gateway_payload,
        }

    @staticmethod
    def _check_lipila_collection_status(reference_id: str) -> Dict:
        from config import LIPILA_SECRET_KEY, LIPILA_BASE_URL

        if not LIPILA_SECRET_KEY:
            raise ValueError("Lipila API key not configured in the backend environment.")

        lipila_base_url = PaymentAgent._resolve_lipila_base_url(LIPILA_BASE_URL)
        headers = {
            "x-api-key": (LIPILA_SECRET_KEY or "").strip(),
            "accept": "application/json",
        }

        response = requests.get(
            f"{lipila_base_url}/collections/check-status",
            params={"referenceId": reference_id},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def refresh_payment_status(payment: Payment) -> Dict:
        logger.info("PAYMENT_STATUS_REFRESH_STARTED payment_id=%s status=%s", payment.payment_id, payment.status.value)
        if PaymentAgent._is_terminal_status(payment.status):
            return PaymentAgent._serialize_payment(payment)

        payment = PaymentAgent._reconcile_local_payment_state(payment, "status_refresh")
        if PaymentAgent._is_terminal_status(payment.status):
            return PaymentAgent._serialize_payment(payment)

        if payment.gateway != PaymentGateway.LIPILA:
            if payment.status == AppPaymentStatus.CANCELLING:
                payment = PaymentAgent._finalize_cancelled_payment(
                    payment,
                    "cancelled_without_remote_provider",
                    "status_refresh",
                )
            return PaymentAgent._serialize_payment(payment)

        try:
            gateway_payload = PaymentAgent._check_lipila_collection_status(payment.payment_id)
        except requests.exceptions.HTTPError as exc:
            error_body = exc.response.text if exc.response is not None else str(exc)
            if payment.status == AppPaymentStatus.CANCELLING:
                payment = PaymentAgent._reconcile_local_payment_state(payment, "status_refresh_http_error")
                if PaymentAgent._is_terminal_status(payment.status):
                    return PaymentAgent._serialize_payment(payment)
                logger.warning("Failed to refresh cancelling Lipila payment %s: %s", payment.payment_id, error_body)
                return PaymentAgent._serialize_payment(payment)
            raise GatewayError(f"Failed to refresh Lipila status: {error_body}")
        except requests.exceptions.RequestException as exc:
            if payment.status == AppPaymentStatus.CANCELLING:
                payment = PaymentAgent._reconcile_local_payment_state(payment, "status_refresh_request_error")
                if PaymentAgent._is_terminal_status(payment.status):
                    return PaymentAgent._serialize_payment(payment)
                logger.warning("Failed to refresh cancelling Lipila payment %s: %s", payment.payment_id, str(exc))
                return PaymentAgent._serialize_payment(payment)
            raise GatewayError(f"Failed to refresh Lipila status: {str(exc)}")
        gateway_summary = PaymentAgent._summarize_lipila_status(gateway_payload)

        payment.metadata = {
            **(payment.metadata or {}),
            **gateway_summary,
        }

        gateway_account_number = gateway_summary.get("raw", {}).get("accountNumber")
        if gateway_account_number:
            payment.phone_number = gateway_account_number

        external_id = gateway_summary.get("external_id")
        if external_id:
            payment.transaction_id = external_id

        next_status = PaymentAgent._status_from_gateway_summary(
            gateway_summary.get("gateway_status"),
            gateway_summary.get("gateway_message"),
        )
        if next_status == AppPaymentStatus.SUCCESS and payment.status != AppPaymentStatus.SUCCESS:
            payment.status = AppPaymentStatus.SUCCESS
            PaymentAgent._activate_org_plan(payment)
        elif next_status == AppPaymentStatus.FAILED and payment.status != AppPaymentStatus.FAILED:
            payment.status = AppPaymentStatus.FAILED
            PaymentAgent._handle_failure(payment)
        elif next_status == AppPaymentStatus.EXPIRED and payment.status != AppPaymentStatus.EXPIRED:
            payment.status = AppPaymentStatus.EXPIRED
            PaymentAgent._invalidate_retry_state(payment, "gateway_expired")
            PaymentAgent._set_org_after_unsuccessful_resolution(payment, PaymentStatus.UNPAID)
        elif next_status == AppPaymentStatus.CANCELLED and payment.status != AppPaymentStatus.CANCELLED:
            payment = PaymentAgent._finalize_cancelled_payment(payment, "gateway_cancelled", "status_refresh")
            return PaymentAgent._serialize_payment(payment)
        else:
            if payment.status == AppPaymentStatus.CANCELLING:
                deadline = PaymentAgent._cancellation_deadline(payment)
                if deadline and datetime.now(timezone.utc) >= deadline:
                    payment = PaymentAgent._finalize_cancelled_payment(
                        payment,
                        "cancel_grace_window_elapsed",
                        "status_refresh",
                    )
                    return PaymentAgent._serialize_payment(payment)
                payment.status = AppPaymentStatus.CANCELLING
            else:
                payment.status = next_status

        PaymentAgent._append_lifecycle_event(
            payment,
            "STATUS_REFRESHED",
            {"status": payment.status.value, "gateway_status": gateway_summary.get("gateway_status")},
        )
        Database.save_payment(payment)
        logger.info("PAYMENT_STATUS_REFRESH_COMPLETED payment_id=%s status=%s", payment.payment_id, payment.status.value)
        return PaymentAgent._serialize_payment(payment)

    @staticmethod
    def _resolve_plan_charge(plan_name: str) -> tuple[float, str]:
        plan_config = PLAN_CONFIG.get(plan_name.upper())
        if not plan_config:
            raise ValueError(f"Invalid plan: {plan_name}")

        amount = plan_config.get("price")
        currency = str(plan_config.get("currency") or "USD").upper()
        if amount is None:
            raise ValueError(f"{plan_config.get('name', plan_name)} requires custom pricing. Please contact sales.")

        return float(amount), currency

    @staticmethod
    def _amount_in_zmw(amount: float, currency: str) -> float:
        if currency.upper() == "ZMW":
            return round(amount, 2)

        from config import USD_TO_ZMW_RATE
        return round(amount * USD_TO_ZMW_RATE, 2)

    @staticmethod
    def initiate_payment(org: Organization, plan_name: str, gateway: str, extra_data: Dict) -> Dict:
        """
        Main entry point for starting a payment.
        Returns instruction/data for the frontend.
        """
        AuditAgent.log_event(
            "PAYMENT_REQUEST_CREATION_STARTED",
            org.id,
            {"plan": plan_name, "gateway": str(gateway).upper()},
        )
        replace_active = bool(extra_data.get("replace_active"))
        existing_active_payment = PaymentAgent._find_existing_active_payment(org.id)
        if existing_active_payment:
            if replace_active:
                PaymentAgent.cancel_payment(
                    existing_active_payment,
                    requested_by=org.id,
                    reason="replaced_by_new_request",
                )
            else:
                AuditAgent.log_event(
                    "PAYMENT_DUPLICATE_BLOCKED",
                    org.id,
                    {
                        "payment_id": existing_active_payment.payment_id,
                        "status": existing_active_payment.status.value,
                        "gateway": existing_active_payment.gateway.value if hasattr(existing_active_payment.gateway, "value") else existing_active_payment.gateway,
                    },
                )
                raise DuplicateActivePaymentError(existing_active_payment)

        amount, currency = PaymentAgent._resolve_plan_charge(plan_name)
        payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        
        if gateway.upper() == "LIPILA":
            return PaymentAgent._initiate_lipila(org, plan_name, amount, currency, extra_data, payment_id)
        elif gateway.upper() == "BANK":
            return PaymentAgent._generate_invoice(org, plan_name, amount, currency, payment_id)
        elif gateway.upper() == "STRIPE":
            return PaymentAgent._initiate_stripe(org, plan_name, amount, currency, payment_id)
        else:
            raise ValueError(f"Unsupported gateway: {gateway}")

    @staticmethod
    def _initiate_lipila(org: Organization, plan: str, amount: float, currency: str, data: Dict, payment_id: str) -> Dict:
        """
        Triggers real Lipila STK Push (MoMo).
        Zambia Market: Airtel, MTN, Zamtel.
        """
        phone = data.get("phone_number")
        if not phone:
            raise ValueError("Phone number required for Mobile Money")
        logger.debug(f"DEBUG: RAW PHONE INPUT: {phone}")

        from config import LIPILA_SECRET_KEY, LIPILA_BASE_URL
        if not LIPILA_SECRET_KEY:
            raise ValueError(f"Lipila API key not configured in the backend environment.")

        amount_zmw = PaymentAgent._amount_in_zmw(amount, currency)
        lipila_base_url = PaymentAgent._resolve_lipila_base_url(LIPILA_BASE_URL)
        callback_url = PaymentAgent._resolve_callback_url()

        formatted_phone = PaymentAgent._normalize_zambian_phone_number(phone)

        payload = {
            "referenceId": payment_id,
            "amount": amount_zmw,
            "narration": f"Mifi-Pro: {plan} Plan Activation",
            "accountNumber": formatted_phone,
            "currency": "ZMW",
            "email": f"{org.id}@mifi.pro",
        }

        headers = PaymentAgent._build_lipila_headers(LIPILA_SECRET_KEY, callback_url)

        try:
            logger.debug(f"DEBUG: LIPILA PAYLOAD: {payload}")
            response = requests.post(
                f"{lipila_base_url}/collections/mobile-money",
                json=payload,
                headers=headers,
                timeout=30
            )
            logger.debug(f"DEBUG: LIPILA RESPONSE STATUS: {response.status_code}")
            logger.debug(f"DEBUG: LIPILA RESPONSE BODY: {response.text}")
            response.raise_for_status()
            resp_data = response.json()
            gateway_summary = PaymentAgent._summarize_lipila_status(resp_data)
            
            # Use Lipila's identifier/tx_id
            tx_id = resp_data.get("externalId") or resp_data.get("referenceId") or f"LPL-{secrets.token_hex(6).upper()}"
            
        except Exception as e:
            logger.error(f"LIPILA ERROR: {str(e)}")
            if 'response' in locals():
                logger.error(f"LIPILA ERROR BODY: {response.text}")
            error_detail = response.text if 'response' in locals() and response.text else str(e)
            AuditAgent.log_event("PAYMENT_GATEWAY_ERROR", org.id, {"gateway": "LIPILA", "error": str(e), "body": error_detail})
            raise GatewayError(f"Failed to connect to Lipila: {error_detail}")

        # Generate invoice_id
        invoice_id = f"INV-{datetime.now().year}-{secrets.token_hex(3).upper()}"

        payment = Payment(
            payment_id=payment_id,
            org_id=org.id,
            plan=plan,
            amount=amount_zmw,
            currency="ZMW",
            gateway=PaymentGateway.LIPILA,
            status=AppPaymentStatus.PROMPT_SENT,
            phone_number=formatted_phone,
            transaction_id=tx_id,
            invoice_id=invoice_id,
            metadata={
                **gateway_summary,
                "raw_phone_input": phone,
                "retry_state": "active",
                "retry_job_active": False,
            },
        )
        PaymentAgent._append_lifecycle_event(payment, "REQUEST_CREATED", {"gateway": "LIPILA", "plan": plan})
        PaymentAgent._append_lifecycle_event(payment, "PROMPT_SENT", {"gateway": "LIPILA", "phone_number": formatted_phone})
        Database.save_payment(payment)
        
        PaymentAgent._mark_org_payment_pending(org, payment)
        
        AuditAgent.log_event("PAYMENT_PROMPT_SENT", org.id, {
            "gateway": "LIPILA",
            "amount": amount_zmw,
            "currency": "ZMW",
            "phone": formatted_phone,
            "payment_id": payment_id,
            "lipila_tx_id": tx_id
        })

        # Generate Initial Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Initial invoice generation failed: {inv_err}")

        return PaymentAgent._serialize_payment(payment)

    @staticmethod
    def _generate_invoice(org: Organization, plan: str, amount: float, currency: str, payment_id: str) -> Dict:
        """
        Generates an Enterprise Invoice for Bank Transfer.
        """
        ref_code = secrets.token_hex(4).upper()
        invoice_id = f"INV-{datetime.now().year}-{secrets.token_hex(3).upper()}"
        
        payment = Payment(
            payment_id=payment_id,
            org_id=org.id,
            plan=plan,
            amount=amount,
            currency=currency,
            gateway=PaymentGateway.BANK_TRANSFER,
            status=AppPaymentStatus.PENDING,
            reference_code=ref_code,
            invoice_id=invoice_id,
            metadata={
                "retry_state": "active",
                "retry_job_active": False,
            },
        )
        PaymentAgent._append_lifecycle_event(payment, "REQUEST_CREATED", {"gateway": "BANK_TRANSFER", "plan": plan})
        PaymentAgent._append_lifecycle_event(payment, "PENDING", {"gateway": "BANK_TRANSFER"})
        Database.save_payment(payment)
        
        PaymentAgent._mark_org_payment_pending(org, payment)
        
        AuditAgent.log_event("INVOICE_GENERATED", org.id, {
            "invoice_id": invoice_id,
            "ref_code": ref_code,
            "amount": amount
        })

        # Generate PDF Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"ERROR: PDF Invoice generation failed: {inv_err}")

        return PaymentAgent._serialize_payment(payment)

    @staticmethod
    def _initiate_stripe(org: Organization, plan: str, amount: float, currency: str, payment_id: str) -> Dict:
        """
        [MODIFIED] Now uses LIPILA CARD payments instead of Stripe.
        Kept name '_initiate_stripe' to match existing routing logic for now.
        """
        # We process this as a Lipila Card transaction
        return PaymentAgent._initiate_lipila_card(org, plan, amount, currency, payment_id)

    @staticmethod
    def _initiate_lipila_card(org: Organization, plan: str, amount: float, currency: str, payment_id: str) -> Dict:
        """
        Initiates a Card Payment via Lipila (Visa/Mastercard).
        Endpoint: /collections/card (Inferred)
        """
        from config import LIPILA_SECRET_KEY, LIPILA_BASE_URL
        if not LIPILA_SECRET_KEY:
             raise ValueError("Lipila API key not configured")

        amount_zmw = PaymentAgent._amount_in_zmw(amount, currency)
        lipila_base_url = PaymentAgent._resolve_lipila_base_url(LIPILA_BASE_URL)
        callback_url = PaymentAgent._resolve_callback_url()
        public_url = (os.getenv("SERVER_PUBLIC_URL") or "").strip().rstrip("/")
        return_url = f"{public_url}/usage-billing?status=success" if public_url else None

        # Lipila Card Payload (Standard Assumption)
        # Lipila Card Payload (Nested Structure based on Error)
        payload = {
            "customerInfo": {
                "email": f"{org.id}@mifi.pro",
                "phoneNumber": "260970000000", # Fixed key name
                "firstName": org.name or "Valued",
                "lastName": "Customer",
                "country": "ZM",
                "city": "Lusaka",
                "address": "N/A",
                "zip": "10101"
            },
            "collectionRequest": {
                "referenceId": payment_id,
                "amount": amount_zmw,
                "currency": "ZMW", 
                "narration": f"Mifi-Pro: {plan} Plan",
                "accountNumber": "260970000000" # Required by API
                # "metadata": {"org_id": org.id, "plan": plan} 
            }
        }
        if return_url:
            payload["collectionRequest"]["returnUrl"] = return_url
        if callback_url:
            payload["collectionRequest"]["callbackUrl"] = callback_url

        headers = PaymentAgent._build_lipila_headers(LIPILA_SECRET_KEY)

        try:
            # Note: This is an inferred endpoint. If 404, we need docs.
            response = requests.post(
                f"{lipila_base_url}/collections/card",
                json=payload,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            # Expecting a redirect URL
            checkout_url = data.get("cardRedirectionUrl") or data.get("checkoutUrl")
            
            if not checkout_url:
                raise ValueError(f"Lipila did not return a checkout URL. Response Keys: {list(data.keys())}")

        except requests.exceptions.HTTPError as e:
            # Capture the actual validation error from Lipila
            error_body = e.response.text
            logger.error(f"LIPILA CARD API ERROR BODY: {error_body}")
            AuditAgent.log_event("PAYMENT_GATEWAY_ERROR", org.id, {"gateway": "LIPILA_CARD", "error": str(e), "body": error_body})
            raise GatewayError(f"Lipila Card Error: {error_body}")
            
        # Generate invoice_id
        invoice_id = f"INV-{datetime.now().year}-{secrets.token_hex(3).upper()}"

        # Create Pending Payment Record
        payment = Payment(
            payment_id=payment_id,
            org_id=org.id,
            plan=plan,
            amount=amount_zmw,
            currency="ZMW",
            gateway=PaymentGateway.LIPILA,
            status=AppPaymentStatus.PENDING,
            transaction_id=data.get("externalId") or data.get("referenceId"),
            invoice_id=invoice_id,
            metadata={
                "retry_state": "active",
                "retry_job_active": False,
            },
        )
        PaymentAgent._append_lifecycle_event(payment, "REQUEST_CREATED", {"gateway": "CARD", "plan": plan})
        PaymentAgent._append_lifecycle_event(payment, "PENDING", {"gateway": "CARD"})
        Database.save_payment(payment)
        
        PaymentAgent._mark_org_payment_pending(org, payment)

        # Generate Initial Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Initial invoice generation failed: {inv_err}")

        return PaymentAgent._serialize_payment(payment, {"checkout_url": checkout_url})

    @staticmethod
    def handle_webhook(gateway: str, payload: Dict):
        """
        Processes async notifications from payment providers.
        """
        logger.info(f"WEBHOOK RECEIVED ({gateway}): {payload}") # DEBUG LOG

        # 1. Identify Payment
        # Lipila uses 'referenceId' for our pay-xxxx ID, 'externalId' for their tx ID
        # and 'identifier' for their internal reference.
        ref_id = payload.get("referenceId")
        tx_id = payload.get("externalId") or payload.get("identifier")
        
        logger.debug(f"DEBUG: WEBHOOK LOOKUP - ref_id: {ref_id}, tx_id: {tx_id}")
        
        payment = None
        if ref_id:
            payment = Database.get_payment(ref_id)
        
        if not payment and tx_id:
            payment = Database.get_payment_by_transaction_id(tx_id)
            
        if not payment:
            logger.error(f"ERROR: Received webhook for unknown transaction. ref_id: {ref_id}, tx_id: {tx_id}")
            return False

        # Update external transaction ID if available
        ext_id = payload.get("externalId")
        if ext_id and not payment.transaction_id:
            payment.transaction_id = ext_id

        payment.metadata = {
            **(payment.metadata or {}),
            **PaymentAgent._summarize_lipila_status(payload),
        }
        PaymentAgent._append_lifecycle_event(
            payment,
            "WEBHOOK_RECEIVED",
            {"gateway": gateway, "gateway_status": payload.get("status"), "message": payload.get("message")},
        )

        # Idempotency Check: Don't process if already successful.
        if payment.status == AppPaymentStatus.SUCCESS:
            logger.info(f"INFO: Payment {payment.payment_id} already processed successfully. Skipping.")
            return True

        next_status = PaymentAgent._status_from_gateway_summary(payload.get("status"), payload.get("message"))
        if payment.status in TERMINAL_PAYMENT_STATUSES and next_status != AppPaymentStatus.SUCCESS:
            PaymentAgent._append_lifecycle_event(
                payment,
                "WEBHOOK_IGNORED",
                {
                    "reason": "terminal_status_already_reached",
                    "current_status": payment.status.value,
                    "next_status": next_status.value,
                    "gateway_status": payload.get("status"),
                },
            )
            Database.save_payment(payment)
            return True

        if next_status == AppPaymentStatus.SUCCESS:
            previous_status = payment.status
            payment.status = AppPaymentStatus.SUCCESS
            PaymentAgent._activate_org_plan(payment)
            if previous_status in {AppPaymentStatus.CANCELLING, AppPaymentStatus.CANCELLED}:
                AuditAgent.log_event(
                    "PAYMENT_COMPLETED_AFTER_CANCEL_REQUEST",
                    payment.org_id,
                    {"payment_id": payment.payment_id, "previous_status": previous_status.value},
                )
        elif next_status == AppPaymentStatus.FAILED:
            payment.status = AppPaymentStatus.FAILED
            PaymentAgent._handle_failure(payment)
        elif next_status == AppPaymentStatus.EXPIRED:
            payment.status = AppPaymentStatus.EXPIRED
            PaymentAgent._invalidate_retry_state(payment, "gateway_expired")
            PaymentAgent._set_org_after_unsuccessful_resolution(payment, PaymentStatus.UNPAID)
        elif next_status == AppPaymentStatus.CANCELLED:
            payment = PaymentAgent._finalize_cancelled_payment(payment, "gateway_cancelled", "webhook")
            return True
        else:
            if payment.status == AppPaymentStatus.CANCELLING:
                PaymentAgent._append_lifecycle_event(
                    payment,
                    "WEBHOOK_IGNORED",
                    {"reason": "cancel_still_in_progress", "gateway_status": payload.get("status")},
                )
                Database.save_payment(payment)
                return True
            payment.status = AppPaymentStatus.PROMPT_SENT

        PaymentAgent._append_lifecycle_event(payment, "WEBHOOK_PROCESSED", {"status": payment.status.value, "gateway_status": payload.get("status")})
        Database.save_payment(payment)

        # REGENERATE INVOICE WITH 'PAID' STATUS
        try:
            org = Database.get_organization(payment.org_id)
            if org:
                payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
                Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Paid invoice regeneration failed: {inv_err}")

        return True

    @staticmethod
    def cancel_payment(payment: Payment, requested_by: str, reason: str = "user_cancelled") -> Dict[str, Any]:
        if payment.status in TERMINAL_PAYMENT_STATUSES:
            return PaymentAgent._serialize_payment(
                payment,
                {"message": "Payment request is already resolved and cannot be cancelled again."},
            )

        if payment.status == AppPaymentStatus.CANCELLING:
            return PaymentAgent._serialize_payment(
                payment,
                {"message": "Cancellation is already in progress for this payment request."},
            )

        metadata = dict(payment.metadata or {})
        cancel_requested_at = datetime.now(timezone.utc)
        metadata["cancel_requested_at"] = cancel_requested_at.isoformat()
        metadata["cancel_deadline_at"] = (cancel_requested_at + PaymentAgent._cancellation_grace_period()).isoformat()
        metadata["cancel_requested_by"] = requested_by
        metadata["cancel_reason"] = reason
        metadata["provider_cancel_supported"] = False
        payment.metadata = metadata
        PaymentAgent._invalidate_retry_state(payment, reason)
        if payment.gateway == PaymentGateway.LIPILA:
            payment.status = AppPaymentStatus.CANCELLING
            PaymentAgent._append_lifecycle_event(payment, "CANCELLING", {"requested_by": requested_by, "reason": reason})
            Database.save_payment(payment)
            AuditAgent.log_event(
                "PAYMENT_CANCELLATION_REQUESTED",
                payment.org_id,
                {"payment_id": payment.payment_id, "requested_by": requested_by, "reason": reason},
            )
            return PaymentAgent._serialize_payment(payment)

        AuditAgent.log_event(
            "PAYMENT_CANCELLATION_REQUESTED",
            payment.org_id,
            {"payment_id": payment.payment_id, "requested_by": requested_by, "reason": reason},
        )
        payment = PaymentAgent._finalize_cancelled_payment(payment, reason, "cancel_endpoint")
        return PaymentAgent._serialize_payment(payment)

    @staticmethod
    def _activate_org_plan(payment: Payment):
        """
        CONFIRMED PAYMENT ACTIVATION.
        Strictly activates production access only after this point.
        """
        org = Database.get_organization(payment.org_id)
        if not org: return

        # Update Org Fields
        try:
            org.plan = BillingPlan(str(payment.plan).upper())
        except Exception:
            org.plan = payment.plan
        org.payment_status = PaymentStatus.PAID
        org.last_payment_id = payment.payment_id
        org.billing_status = "ACTIVE"
        
        # Switch to PRODUCTION environment if it's a paid plan
        if payment.plan.upper() != "SANDBOX":
            org.environment = "PRODUCTION"
            
        org.current_period_start = datetime.now(timezone.utc)
        org.current_period_end = org.current_period_start + timedelta(days=30)
        
        Database.save_organization(org)
        
        AuditAgent.log_event("PLAN_ACTIVATED", org.id, {
            "plan": payment.plan,
            "payment_id": payment.payment_id,
            "gateway": payment.gateway,
            "payment_status": payment.status.value,
        })

    @staticmethod
    def _handle_failure(payment: Payment):
        org = Database.get_organization(payment.org_id)
        if not org: return
        
        org.payment_status = PaymentStatus.FAILED
        if org.last_payment_id == payment.payment_id:
            org.last_payment_id = None
        Database.save_organization(org)

        PaymentAgent._invalidate_retry_state(payment, "payment_failed")
        PaymentAgent._append_lifecycle_event(payment, "FAILED", {"reason": "gateway_failed"})
        Database.save_payment(payment)
        
        AuditAgent.log_event("PLAN_ACTIVATION_FAILED", org.id, {
            "payment_id": payment.payment_id,
            "reason": "Payment Failed"
        })
