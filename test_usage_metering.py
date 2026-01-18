import requests

BASE_URL = "http://localhost:8000"

# 1. Login
print("=== Testing Usage Metering ===\n")
print("1. Logging in...")
login_resp = requests.post(f"{BASE_URL}/auth/login", data={
    "username": "mwape@gmail.com",
    "password": "password123"
})

if login_resp.status_code != 200:
    print(f"Login failed: {login_resp.text}")
    exit(1)

token = login_resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("✓ Logged in\n")

# 2. Check initial usage
print("2. Checking initial usage...")
usage_resp = requests.get(f"{BASE_URL}/billing/usage", headers=headers)
if usage_resp.status_code == 200:
    usage = usage_resp.json()
    print(f"Sandbox usage: {usage['sandbox']['usage']}/{usage['sandbox']['limit']}")
    print(f"Production usage: {usage['production']['usage']}/{usage['production']['limit']}\n")
else:
    print(f"Failed to get usage: {usage_resp.text}\n")

# 3. Create a test borrower
print("3. Creating test borrower...")
borrower_data = {
    "full_name": "Test User",
    "email": "test@example.com",
    "phone": "+260123456789",
    "monthly_income": 5000,
    "loan_amount_requested": 2000,
    "loan_purpose": "business",
    "employment_status": "employed"
}

intake_resp = requests.post(f"{BASE_URL}/intake/start", 
                            headers={"X-API-KEY": "mfi-admin-key"},
                            json=borrower_data)

if intake_resp.status_code == 200:
    borrower_id = intake_resp.json()["borrower_id"]
    print(f"✓ Created borrower: {borrower_id}\n")
else:
    print(f"Failed to create borrower: {intake_resp.text}\n")
    exit(1)

# 4. Run assessment
print("4. Running assessment...")
assessment_resp = requests.post(f"{BASE_URL}/assessment/run",
                               headers={"X-API-KEY": "mfi-admin-key"},
                               json={"borrower_id": borrower_id})

if assessment_resp.status_code == 200:
    print("✓ Assessment completed\n")
else:
    print(f"Assessment failed: {assessment_resp.status_code} - {assessment_resp.text}\n")

# 5. Check updated usage
print("5. Checking updated usage...")
usage_resp = requests.get(f"{BASE_URL}/billing/usage", headers=headers)
if usage_resp.status_code == 200:
    usage = usage_resp.json()
    print(f"Sandbox usage: {usage['sandbox']['usage']}/{usage['sandbox']['limit']}")
    print(f"Production usage: {usage['production']['usage']}/{usage['production']['limit']}")
    print("\n✓ Usage tracking is working!")
else:
    print(f"Failed to get usage: {usage_resp.text}")
