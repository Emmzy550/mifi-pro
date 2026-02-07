from config import LIPILA_BASE_URL, LIPILA_SECRET_KEY
import os

print(f"DEBUG: LIPILA_BASE_URL from config: {LIPILA_BASE_URL}")
print(f"DEBUG: LIPILA_SECRET_KEY from config: {LIPILA_SECRET_KEY[:8]}...")
print(f"DEBUG: Environment LIPILA_BASE_URL: {os.getenv('LIPILA_BASE_URL')}")
