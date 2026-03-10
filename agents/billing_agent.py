import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, List
from models.organization import Organization, BillingPlan, BillingStatus, OrgEnvironment
from models.usage_record import UsageRecord
from models.usage_log import UsageLog
from utils.db import Database
from pricing_config import PLAN_CONFIG
from agents.audit_agent import AuditAgent
import logging
logger = logging.getLogger(__name__)

PLATFORM_OWNER_ASSESSMENT_LIMIT = 100000

class BillingAgent:
    """
    Handles environment-isolated billing and usage tracking.
    Usage is strictly tied to Organization + Environment.
    """
    
    @staticmethod
    def check_usage_period(record: UsageRecord) -> UsageRecord:
        """Resets usage if the period has ended."""
        now = datetime.now(timezone.utc)
        if now > record.period_end:
            record.assessment_count = 0
            record.period_start = now
            record.period_end = now + timedelta(days=30)
            Database.save_usage_record(record)
        return record

    @staticmethod
    def get_plan_limit(org: Organization) -> int:
        """Get effective monthly limit, respecting custom overrides."""
        if org.monthly_limit is not None:
            return org.monthly_limit
        
        # Fallback to plan default
        plan_name = org.plan.value if hasattr(org.plan, 'value') else str(org.plan)
        # Handle case sensitivity or missing plan
        config = PLAN_CONFIG.get(plan_name.upper(), PLAN_CONFIG["SANDBOX"])
        limit = config["monthly_limit"]
        
        # If limit is None (Enterprise/Unlimited), return a large number for comparison
        if limit is None:
            return float('inf')
            
        return limit

    @staticmethod
    def check_billing_limit(org: Organization, environment: OrgEnvironment) -> tuple[bool, Optional[Dict]]:
        """
        Enforce billing rules:
        1. Non-active organizations cannot use PRODUCTION.
        2. SANDBOX is capped (default 10).
        3. PRODUCTION is capped by plan.
        """
        # Load Usage Record
        record = Database.get_usage_record(org.id, environment)
        record = BillingAgent.check_usage_period(record)
        
        # DEBUG LOGGING (Temporary)
        logger.info(f"[BILLING_CHECK] Org: {org.id}, Env: {environment}, Usage: {record.assessment_count}, OrgLimit: {org.monthly_limit}")

        # Rule 1: PRODUCTION requires ACTIVE billing status
        # Note: Enterprise might be "ACTIVE" billing status even if custom check
        if environment == OrgEnvironment.PRODUCTION:
            # Check config for production access
            plan_name = org.plan.value if hasattr(org.plan, 'value') else str(org.plan)
            config = PLAN_CONFIG.get(plan_name.upper(), PLAN_CONFIG["SANDBOX"])
            
            if not config.get("production_access", False):
                 return False, {
                    "error": "Upgrade Required",
                    "code": 402,
                    "message": "Your current plan does not support Production access. Upgrade to Starter, Standard, or Growth to unlock live decision processing."
                }

            # Enforce strict PaymentStatus.PAID for production
            from models.organization import PaymentStatus
            if org.payment_status != PaymentStatus.PAID:
                 return False, {
                    "error": "Payment Required",
                    "code": 402,
                    "message": "You’re currently using the sandbox. Complete payment to unlock live decision processing.",
                    "payment_status": org.payment_status
                }

            if org.billing_status not in [BillingStatus.ACTIVE, BillingStatus.FREE]: 
                 if org.billing_status != BillingStatus.ACTIVE:
                     return False, {
                        "error": "Account Suspended",
                        "code": 402,
                        "message": "Production usage requires an active billing plan and valid payment status."
                    }
        
        # Rule 2: Enforce Limits
        # Sandbox limit comes from Config directly (usually 10)
        # Production limit comes from get_plan_limit (supports custom)
        
        limit = 0
        if environment == OrgEnvironment.SANDBOX:
             # Platform owner gets a higher sandbox ceiling.
             if org.id == "PLATFORM_OWNER":
                 limit = PLATFORM_OWNER_ASSESSMENT_LIMIT
             else:
                 # Use org.monthly_limit if set (Super Admin override), else default sandbox config.
                 limit = org.monthly_limit if org.monthly_limit is not None else PLAN_CONFIG["SANDBOX"]["monthly_limit"]
        else:
             limit = BillingAgent.get_plan_limit(org)
        
        if record.assessment_count >= limit:
            if environment == OrgEnvironment.SANDBOX:
                AuditAgent.log_event("USAGE_LIMIT_REACHED", org.id, {"environment": "SANDBOX"})
                return False, {
                    "error": "SANDBOX_LIMIT_REACHED",
                    "code": 429,
                    "message": "Sandbox usage limit reached. Upgrade to Production to continue.",
                    "upgrade_required": True
                }
            else:
                AuditAgent.log_event("USAGE_LIMIT_REACHED", org.id, {"environment": "PRODUCTION"})
                return False, {
                    "error": "Plan Limit Reached",
                    "code": 429,
                    "message": f"Your {org.plan.value} plan limit of {limit} assessments has been reached."
                }

        return True, None

    @staticmethod
    def meter_usage(
        org: Organization,
        environment: OrgEnvironment,
        api_key_id: str,
        endpoint: str,
        assessment_id: Optional[str] = None
    ) -> UsageLog:
        """Increments environment-specific usage count."""

        
        # Record Log for Audit
        usage_log = UsageLog(
            log_id=f"LOG-{uuid.uuid4().hex[:8].upper()}",
            org_id=org.id,
            api_key_id=api_key_id,
            endpoint=endpoint,
            units=1,
            cost=0.0, # Handled by subscription logic/external
            assessment_id=assessment_id
        )
        Database.save_usage_log(usage_log)

        # Update Usage Record
        record = Database.get_usage_record(org.id, environment)
        record.assessment_count += 1
        record.last_updated = datetime.now(timezone.utc)
        Database.save_usage_record(record)
        
        return usage_log

    @staticmethod
    def get_full_usage_summary(org: Organization) -> Dict:
        """Aggregation for the Usage & Billing dashboard."""
        
        # Force reload of DB in case of external updates (Mock Mode)
        Database.reload_db()

        # Refactored to use direct lookups instead of list query (avoid index issues)
        sandbox = Database.get_usage_record(org.id, OrgEnvironment.SANDBOX)
        production = Database.get_usage_record(org.id, OrgEnvironment.PRODUCTION)

        
        # Refresh Org to get latest limits/plan updates
        fresh_org = Database.get_organization(org.id) or org

        plan_name = fresh_org.plan.value if hasattr(fresh_org.plan, 'value') else str(fresh_org.plan)
        plan_config = PLAN_CONFIG.get(plan_name.upper(), PLAN_CONFIG["SANDBOX"])

        effective_limit = BillingAgent.get_plan_limit(fresh_org)
        if effective_limit == float('inf'):
            effective_limit = 1000000000  # Return large number for frontend "Unlimited" check

        # Fix: Support Sandbox overrides in summary
        # If a custom limit is set on the org, it applies to Sandbox too (for now)
        logger.debug(f"DEBUG: BillingAgent loaded org {fresh_org.id} with monthly_limit: {fresh_org.monthly_limit}")
        sandbox_limit = (
            PLATFORM_OWNER_ASSESSMENT_LIMIT
            if fresh_org.id == "PLATFORM_OWNER"
            else (
                fresh_org.monthly_limit
                if fresh_org.monthly_limit is not None
                else PLAN_CONFIG["SANDBOX"]["monthly_limit"]
            )
        )
        
        return {
            "sandbox": {
                "usage": sandbox.assessment_count,
                "limit": sandbox_limit,
                "status": "Free"
            },
            "production": {
                "usage": production.assessment_count,
                "limit": effective_limit,
                "status": fresh_org.billing_status.value
            },
            "current_plan": fresh_org.plan.value if hasattr(fresh_org.plan, 'value') else str(fresh_org.plan),
            "billing_status": fresh_org.billing_status.value,
            "payment_status": fresh_org.payment_status.value if hasattr(fresh_org.payment_status, 'value') else fresh_org.payment_status,
            "period_end": fresh_org.current_period_end.isoformat()
        }
