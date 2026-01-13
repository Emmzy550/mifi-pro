"""
BillingAgent - Handles usage tracking, billing limits, and metering.
Foundation for future payment integration.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from models.organization import Organization, BillingPlan
from models.usage_log import UsageLog
from utils.db import Database

# Billing plan configurations
BILLING_PLANS = {
    "sandbox": {
        "monthly_limit": 10,
        "unit_cost": 0.00,  # Free
        "name": "Sandbox (Free)"
    },
    "starter": {
        "monthly_limit": 5000,
        "unit_cost": 0.05,
        "name": "Starter"
    },
    "professional": {
        "monthly_limit": 25000,
        "unit_cost": 0.04,
        "name": "Professional"
    },
    "enterprise": {
        "monthly_limit": 100000,
        "unit_cost": 0.03,
        "name": "Enterprise"
    }
}

class BillingAgent:
    """
    Handles billing operations including usage tracking, limits, and cycle management.
    """
    
    @staticmethod
    def check_billing_cycle(org: Organization) -> Organization:
        """
        Check if billing cycle has ended and reset if needed.
        
        Args:
            org: Organization to check
            
        Returns:
            Updated organization (if cycle was reset)
        """
        now = datetime.now(timezone.utc)
        
        # Check if cycle has ended
        if now > org.billing_cycle_end:
            # Reset billing cycle
            org.usage_count = 0
            org.billing_cycle_start = now
            org.billing_cycle_end = now + timedelta(days=30)
            
            # Save updated organization
            Database.save_organization(org)
            
            print(f"[BILLING] Reset billing cycle for org {org.id}")
        
        return org
    
    @staticmethod
    def check_billing_limit(org: Organization) -> tuple[bool, Optional[Dict]]:
        """
        Check if organization has exceeded billing limit.
        
        Args:
            org: Organization to check
            
        Returns:
            Tuple of (is_allowed, error_response)
            - is_allowed: True if usage is under limit
            - error_response: Dict with error details if limit exceeded, None otherwise
        """
        # Check if billing is suspended
        if org.billing_status.value == "suspended":
            return False, {
                "error": "Account suspended",
                "message": "Your account has been suspended. Please contact support to reactivate.",
                "billing_status": "suspended"
            }
        
        # Check usage limit
        if org.usage_count >= org.monthly_limit:
            return False, {
                "error": "Billing limit exceeded",
                "message": f"You have reached your monthly assessment limit of {org.monthly_limit:,}. Please upgrade your plan or contact support.",
                "current_usage": org.usage_count,
                "monthly_limit": org.monthly_limit,
                "plan_name": org.plan_name.value
            }
        
        return True, None
    
    @staticmethod
    def meter_usage(
        org: Organization,
        api_key_id: str,
        endpoint: str,
        assessment_id: Optional[str] = None,
        user_email: Optional[str] = None
    ) -> UsageLog:
        """
        Record billable usage and increment usage count.
        Only call this AFTER successful assessment (HTTP 200).
        """
        try:
            # Calculate cost
            units = 1  # Always 1 for assessments
            cost = BillingAgent.calculate_cost(org, units)
            print(f"DEBUG: Metering usage for {org.id}. Type of org: {type(org)}")
            
            # Create usage log
            print("DEBUG: Creating UsageLog object...")
            usage_log = UsageLog(
                log_id=f"LOG-{uuid.uuid4().hex[:8].upper()}",
                org_id=org.id,
                api_key_id=api_key_id,
                endpoint=endpoint,
                units=units,
                cost=cost,
                assessment_id=assessment_id,
                user_email=user_email
            )
            print("DEBUG: UsageLog object created successfully.")
            
            # Save usage log to database
            print("DEBUG: Saving UsageLog to DB...")
            Database.save_usage_log(usage_log)
            print("DEBUG: UsageLog saved successfully.")
            
            # Increment usage count
            org.usage_count += units
            Database.save_organization(org)
            print(f"DEBUG: Organization usage count updated: {org.usage_count}")
            
            print(f"[BILLING] Metered usage for {org.id}: {org.usage_count}/{org.monthly_limit} (${cost:.2f})")
            
            return usage_log
        except Exception as e:
            print(f"🔥 BILLING CRASH in meter_usage: {e}")
            import traceback
            traceback.print_exc()
            raise e
    
    @staticmethod
    def calculate_cost(org: Organization, units: int = 1) -> float:
        """
        Calculate cost for given units based on organization's plan.
        
        Args:
            org: Organization
            units: Number of billable units (default 1)
            
        Returns:
            Cost in USD
        """
        return org.unit_cost * units
    
    @staticmethod
    def get_usage_summary(org: Organization) -> Dict:
        """
        Get usage summary for dashboard display.
        
        Args:
            org: Organization
            
        Returns:
            Dict with usage summary
        """
        # Ensure cycle is current
        org = BillingAgent.check_billing_cycle(org)
        
        # Calculate estimated cost
        estimated_cost = BillingAgent.calculate_cost(org, org.usage_count)
        
        # Calculate percentage used
        percent_used = (org.usage_count / org.monthly_limit * 100) if org.monthly_limit > 0 else 0
        
        # Get plan details
        plan_config = BILLING_PLANS.get(org.plan_name.value, {})
        
        return {
            "plan_name": org.plan_name.value,
            "plan_display_name": plan_config.get("name", org.plan_name.value),
            "usage_count": org.usage_count,
            "monthly_limit": org.monthly_limit,
            "percent_used": round(percent_used, 1),
            "unit_cost": org.unit_cost,
            "estimated_cost": round(estimated_cost, 2),
            "billing_status": org.billing_status.value,
            "cycle_start": org.billing_cycle_start.isoformat(),
            "cycle_end": org.billing_cycle_end.isoformat(),
            "days_remaining": (org.billing_cycle_end - datetime.now(timezone.utc)).days
        }
    
    @staticmethod
    def get_plan_config(plan_name: str) -> Dict:
        """
        Get configuration for a specific billing plan.
        
        Args:
            plan_name: Plan name (sandbox, starter, professional, enterprise)
            
        Returns:
            Plan configuration dict
        """
        return BILLING_PLANS.get(plan_name, BILLING_PLANS["sandbox"])
    
    # TODO: Future payment integration points
    # TODO: def process_payment(org: Organization, amount: float) -> bool:
    #       """Process payment via Stripe/Paystack"""
    
    # TODO: def generate_invoice(org: Organization, start_date, end_date) -> Invoice:
    #       """Generate PDF invoice for billing period"""
    
    # TODO: def send_usage_alert(org: Organization, threshold: float):
    #       """Send email when usage reaches threshold (e.g., 80%)"""
    
    # TODO: def handle_payment_failure(org: Organization):
    #       """Handle failed payment - send notifications, suspend if needed"""
    
    # TODO: def upgrade_plan(org: Organization, new_plan: str, prorate: bool = True):
    #       """Upgrade plan with optional pro-rating"""
