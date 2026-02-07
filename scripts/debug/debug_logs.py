from agents.audit_agent import AuditAgent
import json

def debug_logs():
    org_id = "ORG-44141161"
    logs = AuditAgent.list_org_logs(org_id, limit=10)
    print(f"--- Debug Logs for {org_id} ---")
    for l in logs:
        print(f"Time: {l.get('timestamp')}")
        print(f"Event: {l.get('event_type')}")
        print(f"Actor: {l.get('actor')}")
        print(f"Details: {json.dumps(l.get('details'), indent=2)}")
        print("-" * 30)

if __name__ == "__main__":
    debug_logs()
