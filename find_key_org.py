from utils.db import Database
from agents.auth_agent import AuthAgent

def find_key_info():
    # Attempt to find the key by prefix first if hash is tricky
    db = Database.get_db()
    keys = db.collection("api_keys").stream()
    
    found = False
    for k in keys:
        data = k.to_dict()
        if data.get("key_prefix") == "sk_oqP0Ug": # The prefix is usually 8 chars, sk_ + 6
             print(f"MATCH FOUND!")
             print(f"Prefix: {data.get('key_prefix')}")
             print(f"Org ID: {data.get('organization_id')}")
             found = True
             break
    
    if not found:
        # Check matching by full hash if prefix search failed (maybe prefix is different)
        # Actually, let's just print all prefixes to be safe
        print("No exact prefix match. Listing all keys:")
        keys = db.collection("api_keys").stream()
        for k in keys:
             data = k.to_dict()
             print(f"Prefix: {data.get('key_prefix')} -> Org: {data.get('organization_id')}")

if __name__ == "__main__":
    find_key_info()
