import requests
import time

BASE_URL = "http://localhost:8000"

def test_api_key_policy():
    print("--- Testing API Key Policy ---")
    
    # 1. Login to get token (OAuth2 uses form data)
    login_resp = requests.post(f"{BASE_URL}/auth/login", data={
        "username": "mwape@gmail.com",
        "password": "password123"
    })
    if login_resp.status_code != 200:
        print(f"FAILED: Login failed. {login_resp.text}")
        return
    
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Try to create two Sandbox keys
    print("\n[Test] Creating first Sandbox key...")
    resp1 = requests.post(f"{BASE_URL}/api-keys/create", headers=headers, json={
        "name": "Sandbox 1",
        "environment": "SANDBOX"
    })
    print(f"Status: {resp1.status_code}")
    
    print("\n[Test] Creating second Sandbox key (Should fail 409)...")
    resp2 = requests.post(f"{BASE_URL}/api-keys/create", headers=headers, json={
        "name": "Sandbox 2",
        "environment": "SANDBOX"
    })
    print(f"Status: {resp2.status_code}")
    if resp2.status_code == 409:
        print("PASS: Correctly blocked duplicate Sandbox key.")
    else:
        print(f"FAIL: Unexpected status code {resp2.status_code}")

    # 3. Try to create Production key (Should fail 402 if billing not active)
    print("\n[Test] Creating Production key without billing (Should fail 402)...")
    resp3 = requests.post(f"{BASE_URL}/api-keys/create", headers=headers, json={
        "name": "Prod 1",
        "environment": "PRODUCTION"
    })
    print(f"Status: {resp3.status_code}")
    if resp3.status_code == 402:
        print("PASS: Correctly blocked Production key without active billing.")
    else:
         print(f"FAIL: Unexpected status code {resp3.status_code}")

    # 4. Cleanup: Revoke keys for next run
    print("\n[Cleanup] Revoking keys...")
    list_resp = requests.get(f"{BASE_URL}/api-keys", headers=headers)
    for k in list_resp.json():
        if k["status"] == "ACTIVE":
            requests.post(f"{BASE_URL}/api-keys/revoke", headers=headers, json={"key_hash": k["key_hash"]})
            print(f"Revoked {k['name']}")

if __name__ == "__main__":
    time.sleep(2) # Wait for server
    test_api_key_policy()
