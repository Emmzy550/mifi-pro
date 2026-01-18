
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from utils.db import Database
from agents.auth_agent import AuthAgent

borrower_id = "BOR-B49E3622"
print(f"Checking Borrower: {borrower_id}")
b = Database.get_borrower(borrower_id)

if b:
    print(f"Found Borrower. Organization ID: {b.organization_id}")
else:
    print("Borrower NOT FOUND.")

# Check API Keys
print("\nChecking Default API Key (mfi-admin-key):")
user = AuthAgent._check_legacy_keys("mfi-admin-key")
print(f"Key Org: {user.organization_id}")
