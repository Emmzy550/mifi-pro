
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from agents.auth_agent import AuthAgent
    print("Import successful.")
    
    # Test Token Creation
    print("Attempting to create access token...")
    token = AuthAgent.create_access_token({"sub": "test@example.com"})
    print(f"SUCCESS: Token: {token[:20]}...")
    
except Exception as e:
    print(f"CRASH: {e}")
    import traceback
    traceback.print_exc()
