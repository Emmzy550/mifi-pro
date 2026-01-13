from utils.db import Database
from agents.auth_agent import AuthAgent

def check_orgs():
    key = 'sk_oqP0UgSEERsmpEWI_yNeiEu47Jl0FJ_Gpp6i7L_r_lA'
    key_hash = AuthAgent.hash_key(key)
    api_key = Database.get_api_key(key_hash)
    borrower = Database.get_borrower('BOR-34C65C76')
    
    print(f"API Key Org: {api_key.organization_id if api_key else 'NOT FOUND'}")
    print(f"Borrower Org: {borrower.organization_id if borrower else 'NOT FOUND'}")

if __name__ == "__main__":
    check_orgs()
