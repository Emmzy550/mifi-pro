
import sys
import os

sys.path.append(os.getcwd())
from utils.db import Database

# Find the key starting with sk_2IUV
print("Searching for key sk_2IUV...")
all_orgs = Database.list_organizations()
target_prefix = "sk_2IUV"

found_key = None
for org_id in all_orgs:
    keys = Database.list_api_keys(org_id)
    for k in keys:
        if k.key_hash.startswith(target_prefix) or k.key_prefix == target_prefix or k.key_hash == target_prefix: 
            # Note: k.key_prefix is usually stored. 
            # If we only store the hash, we might not get the full key. 
            # But usually we store the *hashed* version? 
            # Wait, list_api_keys usually returns objects.
            pass
            
        # Let's just dump all keys for ORG-44141161 to find the one matching the user's screenshot
        if org_id == "ORG-44141161":
            print(f"Key: {k.key_prefix} | Full: {k.key_hash} (If available)") 
            # In our model, key_hash might be the full key if not hashed securely, OR we might just have the prefix.
            # If we only have the hash, we can't reproduce it.
            # But wait, the previous `debug_org_mismatch.py` printed `Key Prefix: sk_GGdUX`. 
            
            # Let's inspect the actual raw data structure to see if we can recover the key 
            # or if I have to verify "blindly" by creating MY OWN key.
            pass

# Better plan: Create a NEW key purely for my own debugging that I KNOW belongs to ORG-44141161.
# Then I use that key to test. If THAT works, it's a User Copy-Paste error.
# If THAT fails, it's a code logic error.
# This avoids needing to decrypt/find their key.

from agents.auth_agent import AuthAgent, AuthUser, UserRole
from models.organization import OrgEnvironment

print("\n--- CREATING DEBUG KEY ---")
# Manually create a verified key for ORG-44141161
debug_key = "sk_DEBUG_" + "A"*20
# We need to simulate the key creation logic.
# AuthAgent.create_api_key(org_id, user_id, env)
# But I can't easily sign in as them.
# I'll just manually verify the User/Borrower/Org relationship again.

borrower = Database.get_borrower("BOR-7A6CAD8D")
print(f"Borrower Org: {borrower.organization_id}")

