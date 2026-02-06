import logging
logger = logging.getLogger(__name__)

import uuid
import secrets
import os
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

    @staticmethod
    def initiate_payment(org: Organization, plan_name: str, gateway: str, extra_data: Dict) -> Dict:
        """
        Main entry point for starting a payment.
        Returns instruction/data for the frontend.
        """
        plan_config = PLAN_CONFIG.get(plan_name.upper())
        if not plan_config:
            raise ValueError(f"Invalid plan: {plan_name}")

        amount = plan_config["price"]
        payment_id = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        
        if gateway.upper() == "LIPILA":
            return PaymentAgent._initiate_lipila(org, plan_name, amount, extra_data, payment_id)
        elif gateway.upper() == "BANK":
            return PaymentAgent._generate_invoice(org, plan_name, amount, payment_id)
        elif gateway.upper() == "STRIPE":
            return PaymentAgent._initiate_stripe(org, plan_name, amount, payment_id)
        else:
            raise ValueError(f"Unsupported gateway: {gateway}")

    @staticmethod
    def _initiate_lipila(org: Organization, plan: str, amount: float, data: Dict, payment_id: str) -> Dict:
        """
        Triggers real Lipila STK Push (MoMo).
        Zambia Market: Airtel, MTN, Zamtel.
        """
        phone = data.get("phone_number")
        if not phone:
            raise ValueError("Phone number required for Mobile Money")
        logger.debug(f"DEBUG: RAW PHONE INPUT: {phone}")

        from config import LIPILA_SECRET_KEY, LIPILA_BASE_URL, USD_TO_ZMW_RATE
        if not LIPILA_SECRET_KEY:
            raise ValueError(f"Lipila API key not configured in the backend environment.")

        # Convert USD amount to ZMW for Mobile Money
        amount_zmw = round(amount * USD_TO_ZMW_RATE, 2)

        # Lipila Collections API call
        public_url = os.getenv("SERVER_PUBLIC_URL", "http://your-server-public-url.com")
        webhook_url = f"{public_url}/billing/webhook/lipila"
        
        # Format phone number for Zambia (Lipila expects 260...)
        formatted_phone = phone.replace("+", "")
        if formatted_phone.startswith("0"):
            formatted_phone = "260" + formatted_phone[1:]
        elif not formatted_phone.startswith("260") and len(formatted_phone) == 9:
            formatted_phone = "260" + formatted_phone

        payload = {
            "referenceId": payment_id,
            "amount": amount_zmw,
            "narration": f"Mifi-Pro: {plan} Plan Activation",
            "accountNumber": formatted_phone,
            "currency": "ZMW",
            "email": org.id + "@mifi.pro",
            "callbackUrl": webhook_url
        }

        headers = {
            "x-api-key": LIPILA_SECRET_KEY,
            "Content-Type": "application/json",
            "accept": "application/json"
        }

        try:
            logger.debug(f"DEBUG: LIPILA PAYLOAD: {payload}")
            response = requests.post(
                f"{LIPILA_BASE_URL}/collections/mobile-money",
                json=payload,
                headers=headers,
                timeout=30
            )
            logger.debug(f"DEBUG: LIPILA RESPONSE STATUS: {response.status_code}")
            logger.debug(f"DEBUG: LIPILA RESPONSE BODY: {response.text}")
            response.raise_for_status()
            resp_data = response.json()
            
            # Use Lipila's identifier/tx_id
            tx_id = resp_data.get("externalId") or resp_data.get("referenceId") or f"LPL-{secrets.token_hex(6).upper()}"
            
        except Exception as e:
            logger.error(f"LIPILA ERROR: {str(e)}")
            if 'response' in locals():
                logger.error(f"LIPILA ERROR BODY: {response.text}")
            AuditAgent.log_event("PAYMENT_GATEWAY_ERROR", org.id, {"gateway": "LIPILA", "error": str(e)})
            raise GatewayError(f"Failed to connect to Lipila: {str(e)}")

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
            phone_number=phone,
            transaction_id=tx_id,
            invoice_id=invoice_id
        )
        
        Database.save_payment(payment)
        
        # Update Org to PENDING
        org.payment_status = PaymentStatus.PENDING
        org.last_payment_id = payment.payment_id
        Database.save_organization(org)
        
        AuditAgent.log_event("PAYMENT_INITIATED", org.id, {
            "gateway": "LIPILA",
            "amount": amount,
            "phone": phone,
            "payment_id": payment_id,
            "lipila_tx_id": tx_id
        })

        # Generate Initial Invoice
        try:
            payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
            Database.save_payment(payment)
        except Exception as inv_err:
            logger.error(f"WARNING: Initial invoice generation failed: {inv_err}")

        return {
            "status": "PENDING",
            "message": "STK Push initiated. Please check your phone to confirm payment.",
            "payment_id": payment_id,
            "instructions": f"A prompt has been sent to {phone}. Confirm with your PIN."
        }

    @staticmethod
    def _generate_invoice(org: Organization, plan: str, amount: float, payment_id: str) -> Dict:
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
            currency="USD",
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
            "invoice": {
                "id": invoice_id,
                "amount": amount,
                "reference": ref_code,
                "bank_details": "Standard Chartered Bank (Zambia) - 01234567890"
            }
        }

    @staticmethod
    def _initiate_stripe(org: Organization, plan: str, amount: float, payment_id: str) -> Dict:
        """
        [MODIFIED] Now uses LIPILA CARD payments instead of Stripe.
        Kept name '_initiate_stripe' to match existing routing logic for now.
        """
        # We process this as a Lipila Card transaction
        return PaymentAgent._initiate_lipila_card(org, plan, amount, payment_id)

    @staticmethod
    def _initiate_lipila_card(org: Organization, plan: str, amount: float, payment_id: str) -> Dict:
        """
        Initiates a Card Payment via Lipila (Visa/Mastercard).
        Endpoint: /collections/card (Inferred)
        """
        from config import LIPILA_SECRET_KEY, LIPILA_BASE_URL, USD_TO_ZMW_RATE
        if not LIPILA_SECRET_KEY:
             raise ValueError("Lipila API key not configured")

        # Convert USD amount to ZMW
        amount_zmw = round(amount * USD_TO_ZMW_RATE, 2)

        public_url = os.getenv("SERVER_PUBLIC_URL", "http://your-server-public-url.com")
        webhook_url = f"{public_url}/billing/webhook/lipila"
        return_url = f"{public_url}/usage-billing?status=success" # Where user goes after payment

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
                "returnUrl": return_url,
                "callbackUrl": webhook_url,
                "accountNumber": "260970000000" # Required by API
                # "metadata": {"org_id": org.id, "plan": plan} 
            }
        }

        headers = {
            "x-api-key": LIPILA_SECRET_KEY,
            "Content-Type": "application/json",
            "accept": "application/json"
        }

        try:
            # Note: This is an inferred endpoint. If 404, we need docs.
            response = requests.post(
                f"{LIPILA_BASE_URL}/collections/card",
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

        # Idempotency Check: Don't process if already PAID
        if payment.status == AppPaymentStatus.PAID:
            logger.info(f"INFO: Payment {payment.payment_id} already processed successfully. Skipping.")
            return True

        # 2. Update Status
        # Lipila status is 'Successful'
        status_val = payload.get("status", "").lower()
        success = status_val in ["successful", "success"]
        if success:
            payment.status = AppPaymentStatus.PAID
            # ACTIVATE PLAN
            PaymentAgent._activate_org_plan(payment)
        else:
            payment.status = AppPaymentStatus.FAILED
            # REVERT ORG ROLE (handled by activation logic)
            PaymentAgent._handle_failure(payment)

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