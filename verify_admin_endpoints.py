import requests
import json

BASE_URL = "http://localhost:8000"
# We need a super admin token. 
# Since I don't have one easily, I'll bypass by checking the code or assuming current auth works.
# But wait, local verification is easier if I just hit the API and see if it 404s.

def check_endpoints():
    # 1. Check Stats
    # Note: These will likely 401/403 without a token, but we want to see if they exist (not 404).
    endpoints = [
        "/admin/organizations",
        "/admin/platform/stats",
        "/admin/organizations/DEFAULT_ORG/details"
    ]
    
    for ep in endpoints:
        resp = requests.get(f"{BASE_URL}{ep}")
        print(f"GET {ep}: {resp.status_code}")
        if resp.status_code == 200:
            print(json.dumps(resp.json(), indent=2))
        elif resp.status_code == 404:
            print("FAILED: Endpoint not found!")

if __name__ == "__main__":
    check_endpoints()
