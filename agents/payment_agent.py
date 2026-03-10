import logging
logger = logging.getLogger(__name__)

import uuid
import secrets
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List
import requests
from models.organization import Organization, BillingPlan, PaymentStatus
from models.payment import Payment, PaymentGateway, PaymentStatus as AppPaymentStatus
from utils.db import Database
from pricing_config import PLAN_CONFIG
from agents.audit_agent import AuditAgent
from agents.invoice_agent import InvoiceAgent

class GatewayError(Exception):
    """Custom exception for external payment gateway failures."""
    pass

class PaymentAgent:
    """
    Handles production payment integrations: Lipila (MoMo), Bank Transfer, and Stripe.
    Enforces Zambia-first localization and webhook-ready workflows.
    """
    GatewayError = GatewayError

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
    def _build_lipila_client_feedback(
        payment_status: AppPaymentStatus,
        gateway_summary: Dict,
        phone_number: Optional[str],
    ) -> Dict[str, Optional[str]]:
        normalized_phone = (phone_number or "").strip() or gateway_summary.get("raw", {}).get("accountNumber")
        gateway_message = gateway_summary.get("gateway_message")

        if payment_status == AppPaymentStatus.PAID:
            return {
                "message": gateway_message or "Payment confirmed successfully.",
                "instructions": f"Payment confirmed for {normalized_phone}." if normalized_phone else "Payment confirmed successfully.",
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
            "message": gateway_message or "Payment request accepted by Lipila. Waiting for mobile-money confirmation.",
            "instructions": (
                f"Payment request created for {normalized_phone}. Confirm on your phone once your mobile-money provider shows the approval prompt."
                if normalized_phone
                else "Payment request created. Confirm on your phone once your mobile-money provider shows the approval prompt."
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
    def _status_from_gateway_value(status_value: Optional[str]) -> AppPaymentStatus:
        normalized = str(status_value or "").strip().lower()
        if normalized in {"successful", "success", "paid", "completed"}:
            return AppPaymentStatus.PAID
        if normalized in {"failed", "cancelled", "canceled", "declined", "rejected"}:
            return AppPaymentStatus.FAILED
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
        if payment.gateway != PaymentGateway.LIPILA:
            return {
                "payment_id": payment.payment_id,
                "status": payment.status.value,
                "gateway_status": payment.metadata.get("gateway_status"),
                "gateway_message": payment.metadata.get("gateway_message"),
                "payment_type": payment.metadata.get("payment_type"),
                "provider_reference": payment.transaction_id,
            }

        try:
            gateway_payload = PaymentAgent._check_lipila_collection_status(payment.payment_id)
        except requests.exceptions.HTTPError as exc:
            error_body = exc.response.text if exc.response is not None else str(exc)
            raise GatewayError(f"Failed to refresh Lipila status: {error_body}")
        except requests.exceptions.RequestException as exc:
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

        next_status = PaymentAgent._status_from_gateway_value(gateway_summary.get("gateway_status"))
        if next_status == AppPaymentStatus.PAID and payment.status != AppPaymentStatus.PAID:
            payment.status = AppPaymentStatus.PAID
            PaymentAgent._activate_org_plan(payment)
        elif next_status == AppPaymentStatus.FAILED and payment.status != AppPaymentStatus.FAILED:
            payment.status = AppPaymentStatus.FAILED
            PaymentAgent._handle_failure(payment)
        else:
            payment.status = next_status

        Database.save_payment(payment)
        client_feedback = PaymentAgent._build_lipila_client_feedback(payment.status, gateway_summary, payment.phone_number)

        return {
            "payment_id": payment.payment_id,
            "status": payment.status.value,
            "gateway_status": gateway_summary.get("gateway_status"),
            "gateway_message": gateway_summary.get("gateway_message"),
            "payment_type": gateway_summary.get("payment_type"),
            "provider_reference": payment.transaction_id,
            "identifier": gateway_summary.get("identifier"),
            "message": client_feedback.get("message"),
            "instructions": client_feedback.get("instructions"),
            "phone_number": client_feedback.get("phone_number"),
        }

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
            status=AppPaymentStatus.PENDING,
            phone_number=formatted_phone,
            transaction_id=tx_id,
            invoice_id=invoice_id,
            metadata={
                **gateway_summary,
                "raw_phone_input": phone,
            },
        )
        
        Database.save_payment(payment)
        
        # Update Org to PENDING
        org.payment_status = PaymentStatus.PENDING
        org.last_payment_id = payment.payment_id
        Database.save_organization(org)
        
        AuditAgent.log_event("PAYMENT_INITIATED", org.id, {
            "gateway": "LIPILA",
            "amount": amount_zmw,
            "currency": "ZMW",
            "phone": formatted_phone,
            "payment_id": payment_id,
            "lipila_tx_id": tx_id
        })

        client_feedback = PaymentAgent._build_lipila_client_feedback(payment.status, gateway_summary, formatted_phone)

        # Generate Initial Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Initial invoice generation failed: {inv_err}")

        return {
            "status": "PENDING",
            "message": client_feedback.get("message"),
            "payment_id": payment_id,
            "amount": amount_zmw,
            "currency": "ZMW",
            "gateway_status": gateway_summary.get("gateway_status"),
            "payment_type": gateway_summary.get("payment_type"),
            "provider_reference": tx_id,
            "instructions": client_feedback.get("instructions"),
            "phone_number": client_feedback.get("phone_number"),
        }

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
            invoice_id=invoice_id
        )
        
        Database.save_payment(payment)
        
        # Update Org to PENDING
        org.payment_status = PaymentStatus.PENDING
        org.last_payment_id = payment.payment_id
        Database.save_organization(org)
        
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

        return {
            "status": "PENDING",
            "message": "Invoice generated successfully.",
            "payment_id": payment_id,
            "amount": amount,
            "currency": currency,
            "invoice": {
                "id": invoice_id,
                "amount": amount,
                "currency": currency,
                "reference": ref_code,
                "bank_details": "Standard Chartered Bank (Zambia) - 01234567890"
            }
        }

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
            invoice_id=invoice_id
        )
        Database.save_payment(payment)
        
        org.payment_status = PaymentStatus.PENDING
        Database.save_organization(org)

        # Generate Initial Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Initial invoice generation failed: {inv_err}")

        return {
            "status": "PENDING",
            "message": "Redirecting to Lipila Secure Checkout...",
            "payment_id": payment_id,
            "amount": amount_zmw,
            "currency": "ZMW",
            "checkout_url": checkout_url
        }

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

        # Idempotency Check: Don't process if already PAID
        if payment.status == AppPaymentStatus.PAID:
            logger.info(f"INFO: Payment {payment.payment_id} already processed successfully. Skipping.")
            return True

        next_status = PaymentAgent._status_from_gateway_value(payload.get("status"))
        if next_status == AppPaymentStatus.PAID:
            payment.status = AppPaymentStatus.PAID
            PaymentAgent._activate_org_plan(payment)
        elif next_status == AppPaymentStatus.FAILED:
            payment.status = AppPaymentStatus.FAILED
            PaymentAgent._handle_failure(payment)
        else:
            payment.status = AppPaymentStatus.PENDING

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
            "gateway": payment.gateway
        })

    @staticmethod
    def _handle_failure(payment: Payment):
        org = Database.get_organization(payment.org_id)
        if not org: return
        
        org.payment_status = PaymentStatus.FAILED
        Database.save_organization(org)
        
        AuditAgent.log_event("PLAN_ACTIVATION_FAILED", org.id, {
            "payment_id": payment.payment_id,
            "reason": "Payment Failed"
        })
