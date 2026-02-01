import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database
from agents.audit_agent import AuditAgent

def list_all_logs():
    print("=== Listing Recent Audit Logs ===")
    logs = AuditAgent.list_logs(limit=20)
    for log in logs:
        etype = log.get('event_type')
        if etype == "PAYMENT_GATEWAY_ERROR":
            print(f"🔴 [{log.get('timestamp')}] {etype}: {log.get('details')}")
        else:
            print(f"   [{log.get('timestamp')}] {etype}")

if __name__ == "__main__":
    list_all_logs()
