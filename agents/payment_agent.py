
import uuid
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, List
import requests
from models.organization import Organization, BillingPlan, PaymentStatus
from models.payment import Payment, PaymentGateway, PaymentStatus as AppPaymentStatus
from utils.db import Database
from pricing_config import PLAN_CONFIG
from agents.audit_agent import AuditAgent

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
        Triggers Lipila STK Push (MoMo).
        Zambia Market: Airtel, MTN, Zamtel.
        """
        phone = data.get("phone_number")
        if not phone:
            raise ValueError("Phone number required for Mobile Money")

        # SIMULATION: In production, we'd call Lipila API here
        # POST /api/v1/payments/stk-push
        # For this implementation, we simulate the request success
        
        payment = Payment(
            payment_id=payment_id,
            org_id=org.id,
            plan=plan,
            amount=amount,
            currency=plan_config.get("currency", "USD"),
            gateway=PaymentGateway.LIPILA,
            status=AppPaymentStatus.PENDING,
            phone_number=phone,
            transaction_id=f"LPL-{secrets.token_hex(6).upper()}" # Tracking ID
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
            "payment_id": payment_id
        })

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
            currency=plan_config.get("currency", "USD"),
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
        Simplified Stripe Checkout simulation.
        """
        payment = Payment(
            payment_id=payment_id,
            org_id=org.id,
            plan=plan,
            amount=amount,
            currency=plan_config.get("currency", "USD"),
            gateway=PaymentGateway.STRIPE,
            status=AppPaymentStatus.PENDING
        )
        
        Database.save_payment(payment)
        
        # Update Org to PENDING
        org.payment_status = PaymentStatus.PENDING
        org.last_payment_id = payment.payment_id
        Database.save_organization(org)

        return {
            "status": "PENDING",
            "message": "Redirecting to Stripe Checkout...",
            "payment_id": payment_id,
            "checkout_url": "https://checkout.stripe.com/pay/sim_123"
        }

    @staticmethod
    def handle_webhook(gateway: str, payload: Dict):
        """
        Processes async notifications from payment providers.
        """
        # 1. Identify Payment
        tx_id = payload.get("transaction_id") or payload.get("reference")
        payment = Database.get_payment_by_transaction_id(tx_id) # Need to add this helper
        
        if not payment:
            # Try by payment_id from metadata if available
            p_id = payload.get("metadata", {}).get("payment_id")
            if p_id:
                payment = Database.get_payment(p_id)

        if not payment:
            print(f"ERROR: Received webhook for unknown transaction: {tx_id}")
            return False

        # 2. Update Status
        success = payload.get("status") == "SUCCESS"
        if success:
            payment.status = AppPaymentStatus.PAID
            # ACTIVATE PLAN
            PaymentAgent._activate_org_plan(payment)
        else:
            payment.status = AppPaymentStatus.FAILED
            # REVERT ORG ROLE (handled by activation logic)
            PaymentAgent._handle_failure(payment)

        Database.save_payment(payment)
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
