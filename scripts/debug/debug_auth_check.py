
import requests
import sys

try:
    # 1. Check Health
    print("Checking /docs...")
    r = requests.get("http://localhost:8000/docs", timeout=2)
    print(f"Docs Status: {r.status_code}")

    # 2. Check Auth Login (Expected 401 or 400 if missing data)
    print("Checking /auth/login...")
    payload = {"username": "mwape@gmail.com", "password": "WRONG_PASSWORD"}
    r = requests.post("http://localhost:8000/auth/login", data=payload, timeout=5)
    print(f"Auth Status: {r.status_code}")
    print(f"Auth Response: {r.text}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
