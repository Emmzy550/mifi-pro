import firebase_admin
from firebase_admin import credentials, firestore
import os

print("Starting Firebase Test...", flush=True)

try:
    if not firebase_admin._apps:
        print("Initializing Firebase...", flush=True)
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
        print("Firebase Initialized.", flush=True)
    
    db = firestore.client()
    print("Firestore Client Created.", flush=True)
    
    # Try a simple read
    print("Testing Firestore Read...", flush=True)
    db.collection("organizations").limit(1).get()
    print("Firestore Read Successful.", flush=True)

except Exception as e:
    print(f"Firebase Test Failed: {e}", flush=True)
