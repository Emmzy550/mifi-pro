

import requests
import uuid
import sys
import os
import pytest

# Add root directory to path so we can import models/agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.user import User, UserRole
from models.organization import Organization, BillingPlan, BillingStatus
from utils.db import Database
from agents.auth_agent import AuthAgent

# Helper to register a user and get token
def get_auth_token(email="billing_test@example.com", password="password123"):
    # Ensure user and org exist
    org_id = "ORG-BILLING-TEST"
    
    org = Organization(
        id=org_id,
        name="Billing Test Org",
        plan_name=BillingPlan.STARTER,
        monthly_limit=5000,
        unit_cost=0.05,
        billing_status=BillingStatus.ACTIVE
    )
    Database.save_organization(org)
    
    # Check if user exists, if not create
    if not Database.get_user_by_email(email):
        user = User(
            id=f"USR-{uuid.uuid4().hex[:8]}",
            email=email,
            password_hash=AuthAgent.get_password_hash(password),
            full_name="Billing Tester",
            role=UserRole.ORG_ADMIN,
            organization_id=org_id
        )
        Database.save_user(user)
    
    # Login
    login_url = "http://localhost:8000/auth/login"
    res = requests.post(login_url, data={"username": email, "password": password})
    if res.status_code != 200:
        raise Exception(f"Login failed: {res.text}")
        
    return res.json()["access_token"]

def test_billing_usage_endpoint():
    pytest.skip("Skipping integration test requiring live server")
    try:
        token = get_auth_token()
        headers = {"Authorization": f"Bearer {token}"}
        
        url = "http://localhost:8000/billing/usage"
        print(f"\nRequesting {url}...")
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("[SUCCESS] Billing usage fetched successfully!")
            print(f"Plan: {data.get('plan_name')}")
            print(f"Usage: {data.get('usage_count')}/{data.get('monthly_limit')}")
            
            assert "plan_name" in data
            assert "usage_count" in data
            assert "monthly_limit" in data
            assert "estimated_cost" in data
            
        else:
            print(f"[FAIL] Request failed with status {response.status_code}")
            print(response.text)
            exit(1)
            
    except Exception as e:
        print(f"[ERROR] Test execution failed: {e}")
        exit(1)

if __name__ == "__main__":
    test_billing_usage_endpoint()
