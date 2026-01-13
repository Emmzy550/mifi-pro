from utils.db import Database
from agents.auth_agent import AuthAgent
import asyncio

async def test_auth():
    email = "microfinace@gmail.com" # Example from user screenshot
    user = Database.get_user_by_email(email)
    if not user:
        print(f"User {email} not found. Trying another one.")
        users = Database.list_all_users() 
        if not users:
            print("No users in DB.")
            return
        user = users[0]
        email = user.email

    print(f"Testing Auth for {email}...")
    print(f"Hash in DB: {user.password_hash}")
    
    # We can't know the password, but we can try to re-hash a test password and verify it
    test_pwd = "test-password-123"
    new_hash = AuthAgent.get_password_hash(test_pwd)
    match = AuthAgent.verify_password(test_pwd, new_hash)
    print(f"Local Hashing Check: {match}")
    
    # Try verifying the DB hash with a fake password (should fail)
    match_fail = AuthAgent.verify_password("wrong-password", user.password_hash)
    print(f"DB Hash Negative Check: {not match_fail}")

if __name__ == "__main__":
    asyncio.run(test_auth())
