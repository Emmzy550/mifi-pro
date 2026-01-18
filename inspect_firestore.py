from utils.db import Database

db = Database.get_db()

print("=== All Usage Records in Firestore ===\n")
all_docs = list(db.collection("usage_records").stream())

for doc in all_docs:
    print(f"Doc ID: {doc.id}")
    data = doc.to_dict()
    for key, value in data.items():
        print(f"  {key}: {value} (type: {type(value).__name__})")
    print()

print(f"\nTotal: {len(all_docs)} records")
