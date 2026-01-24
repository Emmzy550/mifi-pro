import requests
import json

BASE_URL = "http://localhost:8000"

def test_payment_upgrade():
    import pytest
    pytest.skip("Skipping integration test requiring live server")
    # 1. Login to get token
    login_resp = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "admin@acme.com", "password": "admin123"}
    )
    if login_resp.status_code != 200:
        print(f"❌ Login failed: {login_resp.text}")
        return
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Try upgrade with gateway
    print("\nAttempting upgrade with 'mpesa' gateway...")
    upgrade_data = {
        "plan": "growth",
        "gateway": "mpesa"
    }
    
    resp = requests.post(
        f"{BASE_URL}/billing/upgrade",
        json=upgrade_data,
        headers=headers
    )
    
    if resp.status_code == 200:
        print(f"✅ Upgrade successful: {resp.json()['message']}")
    else:
        print(f"❌ Upgrade failed ({resp.status_code}): {resp.text}")

    # 3. Check Audit Logs via platform stats (or just rely on the 200)
    # The endpoint returns the gateway in the message now.

if __name__ == "__main__":
    test_payment_upgrade()
