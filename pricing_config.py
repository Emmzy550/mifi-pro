
from models.organization import BillingPlan

# Detailed billing plan configurations
PLAN_CONFIG = {
    "SANDBOX": {
        "monthly_limit": 10,
        "price": 0,
        "name": "Sandbox",
        "production_access": False,
        "currency": "USD",
        "features": []
    },
    "STARTER": {
        "monthly_limit": 1000,
        "price": 1,
        "name": "Starter",
        "production_access": True,
        "currency": "USD",
        "features": ["email_support"]
    },
    "GROWTH": {
        "monthly_limit": 5000,
        "price": 149,
        "name": "Growth",
        "production_access": True,
        "currency": "USD",
        "features": ["priority_support", "behavioral_intelligence"]
    },
    "ENTERPRISE": {
        "monthly_limit": None, # Unlimited or Custom
        "price": None, # Negotiated
        "name": "Enterprise",
        "production_access": True,
        "currency": "USD",
        "features": ["sla_support", "custom_rules"]
    }
}
