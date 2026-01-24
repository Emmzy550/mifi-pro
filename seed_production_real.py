import os
import firebase_admin
from firebase_admin import credentials, firestore
from models.organization import Organization, OrgStatus

# Set environment variable to point to the service account key
os.environ["FIREBASE_SERVICE_ACCOUNT"] = "c:\\Users\\SwiftVib Electronics\\Borrower\\loan_officer_ai\\serviceAccountKey.json"

# Wait, the path above might be wrong based on list_dir. It's in the current CWD.
current_dir = os.path.dirname(os.path.abspath(__file__))
key_path = os.path.join(current_dir, "serviceAccountKey.json")

print(f"Connecting to Firebase with key: {key_path}")

if not firebase_admin._apps:
    creds = credentials.Certificate(key_path)
    firebase_admin.initialize_app(creds)

db = firestore.client()

def seed_org(org_id, name):
    print(f"Seeding {org_id}...")
    org_ref = db.collection("organizations").document(org_id)
    org_data = {
        "id": org_id,
        "name": name,
        "status": "ACTIVE",
        "plan": "sandbox",
        "feature_flags": {
            "ENABLE_ML_RISK_SCORING": True,
            "ENABLE_BEHAVIORAL_V2": True,
            "ENABLE_LLM_EXPLANATIONS": False
        },
        "webhook_url": None,
        "webhook_secret": None,
        "monthly_limit": 1000,
        "created_at": firestore.SERVER_TIMESTAMP
    }
    org_ref.set(org_data, merge=True)
    print(f"Success: {org_id} seeded.")

if __name__ == "__main__":
    seed_org("DEFAULT_ORG", "Standard Lender")
    seed_org("MFI_B_ZAMBIA", "Zambia MFI")
    print("Production seeding complete.")
