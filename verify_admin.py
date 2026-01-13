
import requests
import sys

# Helper colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

BASE_URL = "http://localhost:8001"
# We must use a separate port or restart the server. 
# Assuming I will restart 'main.py' on 8001 for testing, or rely on existing running one (but code changed!).
# Since I need to restart, I will use 8001.

def log(msg, success=None):
    if success is True:
        print(f"{GREEN}[PASS]{RESET} {msg}")
    elif success is False:
        print(f"{RED}[FAIL]{RESET} {msg}")
    else:
        print(f"[INFO] {msg}")

def run_test():
    # 2. Route Existence Check
    # We expect 401 Unauthorized (because we provide no token)
    # If we get 404, then the router is NOT mounted.
    try:
        resp = requests.get(f"{BASE_URL}/admin/organizations")
        if resp.status_code == 401 or resp.status_code == 403:
            log("Admin Route '/admin/organizations' is MOUNTED and SECURED (Got 401/403)", True)
        elif resp.status_code == 404:
            log("Admin Route '/admin/organizations' NOT FOUND (404)", False)
        else:
            log(f"Unexpected Status: {resp.status_code}", False)
            
    except Exception as e:
        log(f"Connection failed: {e}", False)
        
if __name__ == "__main__":
    run_test()
