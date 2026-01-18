
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from utils.db import Database
from agents.auth_agent import AuthAgent

# 1. Check Borrower
borrower_id = "BOR-B49E3622"
print(f"--- CHECKING BORROWER {borrower_id} ---")
b = Database.get_borrower(borrower_id)
if b:
    print(f"Borrower Org: {b.organization_id}")
else:
    print("Borrower NOT FOUND")

# 2. Check Key (Partial hash check or just check logic)
# We can't easily check the raw key from the screenshot without typing it all,
# but we can list keys for the dashboard user's org.
dashboard_org = "ORG-44141161"
print(f"\n--- CHECKING KEYS FOR ORG {dashboard_org} ---")
keys = Database.list_api_keys(dashboard_org)
for k in keys:
    print(f"Key Prefix: {k.key_prefix} | Env: {k.environment} | Status: {k.status}")

print(f"\n--- DIAGNOSIS ---")
if b and b.organization_id != dashboard_org:
    print(f"MISMATCH DETECTED: Borrower is in {b.organization_id}, but your keys are for {dashboard_org}.")
