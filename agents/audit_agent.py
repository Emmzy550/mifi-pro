from datetime import datetime
from utils.db import Database
from typing import Dict, Any

class AuditAgent:
    """
    Maintains a permanent audit ledger of all AI Agent activities.
    """

    @classmethod
    def log_event(cls, event_type: str, actor: str, details: Dict[str, Any]):
        """
        Saves an audit event to Firestore.
        Automatically extracts 'org' from details if present to enable tenancy filtering.
        """
        db = Database.get_db()
        event_id = f"LOG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{actor[:5]}"
        
        # Extract organization_id for indexing if available
        org_id = details.get("org") or details.get("organization_id") or "SYSTEM"

        log_entry = {
            "event_id": event_id,
            "timestamp": datetime.now(),
            "event_type": event_type,
            "actor": actor,
            "organization_id": org_id,
            "details": details
        }
        
        db.collection("audit_logs").document(event_id).set(log_entry)
        print(f"AUDIT LOG: {event_type} by {actor} (Org: {org_id})")

    @classmethod
    def list_org_logs(cls, organization_id: str, limit: int = 50) -> list:
        """
        Retrieves audit logs specific to an organization.
        """
        db = Database.get_db()
        # Query: where organization_id == X
        query = db.collection("audit_logs").where("organization_id", "==", organization_id)
        
        # Stream and simple sort/limit (since composite indexes might be missing)
        try:
            docs = query.stream()
            results = [doc.to_dict() for doc in docs]
            # Sort by timestamp descending in memory for V1
            results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return results[:limit]
        except Exception as e:
            print(f"Error fetching audit logs: {e}")
            return []

    @classmethod
    def list_logs(cls, limit: int = 50) -> list:
        db = Database.get_db()
        docs = db.collection("audit_logs").order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        return [doc.to_dict() for doc in docs]
