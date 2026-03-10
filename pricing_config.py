
from models.organization import BillingPlan

# Detailed billing plan configurations
PLAN_CONFIG = {
    "SANDBOX": {
        "monthly_limit": 10,
        "user_limit": 2,
        "price": 0,
        "name": "Sandbox",
        "production_access": False,
        "currency": "USD",
        "features": []
    },
    "STARTER": {
        "monthly_limit": 30,
        "user_limit": 2,
        "price": 600,
        "name": "Starter",
        "production_access": True,
        "currency": "ZMW",
        "description": "SACCOs & small lenders — under 30 loans per month.",
        "features": [
            "30 assessments/month",
            "2 loan officer seats",
            "Bank statement parsing",
            "Rules-based decision engine",
            "PDF Credit Decision Summary",
            "Sealed audit trail",
            "Email support"
        ]
    },
    "STANDARD": {
        "monthly_limit": 100,
        "user_limit": 5,
        "price": 1800,
        "name": "Standard",
        "production_access": True,
        "currency": "ZMW",
        "description": "Growing MFIs — more volume, more officers, full compliance tools.",
        "features": [
            "100 assessments/month",
            "5 loan officer seats",
            "Everything in Starter",
            "Full compliance audit logs",
            "Policy Studio access",
            "Portfolio Overview dashboard",
            "PAR 30/60/90 tracking",
            "Priority support"
        ]
    },
    "GROWTH": {
        "monthly_limit": None,
        "user_limit": None,
        "price": 4500,
        "name": "Growth",
        "production_access": True,
        "currency": "ZMW",
        "description": "Larger MFIs — high volumes, multiple branches or officers.",
        "features": [
            "Unlimited assessments",
            "Unlimited officer seats",
            "Everything in Standard",
            "Decision Copilot AI",
            "Custom policy configuration",
            "Dedicated onboarding support",
            "SLA guarantee"
        ]
    },
    "ENTERPRISE": {
        "monthly_limit": None, # Unlimited or Custom
        "user_limit": None, # Unlimited or Custom
        "price": None, # Negotiated
        "name": "Enterprise",
        "production_access": True,
        "currency": "ZMW",
        "features": ["sla_support", "custom_rules"]
    }
}
