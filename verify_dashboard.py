import requests
import sys

BASE_URL = "http://127.0.0.1:8000"


def run_test():
    print("🧪 Starting Verification Suite...")
    
    # 1. Login
    print("\n[Testing] Login (Admin)...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", data={
            "username": "admin@acme.com",
            "password": "admin123"
        })
        if resp.status_code != 200:
            print(f"FAILED: Login failed {resp.text}")
            return
        token = resp.json()["access_token"]
        print("✅ Login Success")
    except Exception as e:
        print(f"FAILED: Could not connect to server. Is it running? {e}")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # 1.5 Verify /auth/me (Frontend uses this)
    print("\n[Testing] GET /auth/me...")
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if resp.status_code == 200:
        user_data = resp.json()
        print(f"✅ Success. Authenticated as: {user_data['email']}")
    else:
        print(f"FAILED: /auth/me rejected token. {resp.text}")
        return

    # 2. List API Keys
    print("\n[Testing] List API Keys...")
    resp = requests.get(f"{BASE_URL}/api-keys", headers=headers)
    if resp.status_code == 200:
        keys = resp.json()
        print(f"✅ Success. Found {len(keys)} keys.")
    else:
        print(f"FAILED: {resp.text}")

    # 3. Create API Key
    print("\n[Testing] Create API Key...")
    resp = requests.post(f"{BASE_URL}/api-keys/create", headers=headers, json={
        "name": "Test Key Auto",
        "environment": "SANDBOX"
    })
    if resp.status_code == 200:
        data = resp.json()
        new_key = data["api_key"]
        key_hash = data["key_record"]["key_hash"]
        print(f"✅ Success. Created key: {new_key[:10]}...")
    else:
        print(f"FAILED: {resp.text}")
        return

    # 4. Verify Key Usage (Simulate Client)
    print("\n[Testing] Use New API Key...")
    client_headers = {"X-API-KEY": new_key}
    # Try calling a protected endpoint like /assessments
    # Note: DB might be empty so empty list is expected, but 200 OK is success
    resp = requests.get(f"{BASE_URL}/assessments", headers=client_headers)
    if resp.status_code == 200:
        print("✅ Success. API Key accepted.")
    else:
        print(f"FAILED: Key rejected {resp.status_code} {resp.text}")

    # 5. Revoke Key
    print("\n[Testing] Revoke API Key...")
    revoke_data = {"key_hash": key_hash}
    resp = requests.post(f"{BASE_URL}/api-keys/revoke", headers=headers, json=revoke_data)
    if resp.status_code == 200:
         print("✅ Success. Key revoked.")
    else:
         print(f"FAILED: Revoke failed {resp.text}")

    # 6. Verify Revocation
    print("\n[Testing] Verify Revocation...")
    resp = requests.get(f"{BASE_URL}/assessments", headers=client_headers)
    if resp.status_code == 403:
        print("✅ Success. Revoked key rejected.")
    else:
        print(f"FAILED: Revoked key still worked! {resp.status_code}")

    # 7. Verify Root HTML
    print("\n[Testing] Verify Root serves Dashboard...")
    resp = requests.get(f"{BASE_URL}/")
    if resp.status_code == 200 and "<html" in resp.text:
        print("✅ Success. Root serves HTML.")
    else:
        print(f"FAILED: Root did not serve HTML. Code: {resp.status_code}, Preview: {resp.text[:50]}")

    # 8. Verify Decisions Endpoint
    print("\n[Testing] GET /org/decisions...")
    resp = requests.get(f"{BASE_URL}/org/decisions", headers=headers)
    if resp.status_code == 200:
        decisions = resp.json()
        print(f"✅ Success. Fetched {len(decisions)} decisions.")
    else:
        print(f"FAILED: Could not fetch decisions. Code: {resp.status_code}")

    # 9. Verify Audit Logs Endpoint
    print("\n[Testing] GET /org/audit-logs...")
    resp = requests.get(f"{BASE_URL}/org/audit-logs", headers=headers)
    if resp.status_code == 200:
        logs = resp.json()
        print(f"✅ Success. Fetched {len(logs)} audit logs.")
    else:
        print(f"FAILED: Could not fetch audit logs. Code: {resp.status_code}")

    # 10. Verify Settings Endpoint
    print("\n[Testing] GET /org/settings...")
    resp = requests.get(f"{BASE_URL}/org/settings", headers=headers)
    if resp.status_code == 200:
        settings = resp.json()
        print(f"✅ Success. Fetched settings. Flags: {settings.get('feature_flags')}")
    else:
        print(f"FAILED: Could not fetch settings. Code: {resp.status_code}")

    # 11. Verify Update Settings
    print("\n[Testing] PATCH /org/settings...")
    update_payload = {"feature_flags": {"strict_mode": True, "test_mode": True}}
    resp = requests.patch(f"{BASE_URL}/org/settings", json=update_payload, headers=headers)
    if resp.status_code == 200:
        new_settings = resp.json()
        if new_settings.get("feature_flags", {}).get("strict_mode") is True:
             print(f"✅ Success. Updated 'strict_mode' to True.")
        else:
             print(f"FAILED. Update returned 200 but value didn't change: {new_settings}")
    else:
        print(f"FAILED: Could not update settings. Code: {resp.status_code}")

    print("\n🎉 Verification Complete!")

if __name__ == "__main__":
    run_test()
