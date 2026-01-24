
import firebase_admin
from firebase_admin import credentials, firestore

def list_orgs():
    if not firebase_admin._apps:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    docs = db.collection('organizations').stream()
    
    print(f"{'ID':<25} | {'Name':<20} | {'Plan':<10} | {'Payment':<10}")
    print("-" * 75)
    for d in docs:
        data = d.to_dict()
        print(f"{d.id:<25} | {data.get('name', 'N/A'):<20} | {data.get('plan', 'N/A'):<10} | {data.get('payment_status', 'N/A'):<10}")

if __name__ == "__main__":
    list_orgs()
