
import sys
import os
import requests
from datetime import datetime, timedelta
from jose import jwt

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


SECRET_KEY = "CHANGE_THIS_IN_PRODUCTION_SECRET_KEY"
ALGORITHM = "HS256"

BASE_URL = "http://localhost:8000"
TARGET_EMAIL = "mwape@gmail.com"


def create_debug_token():
    expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode = {"sub": TARGET_EMAIL, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def debug_billing_endpoint():
    
    token = create_debug_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/billing/usage", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            import json
            print(json.dumps(data, indent=2))
        else:
            print(f"Error: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_billing_endpoint()
