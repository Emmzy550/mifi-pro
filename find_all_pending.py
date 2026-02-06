
from utils.db import Database
from datetime import datetime

print("Searching for ALL PENDING payments...")
db = Database.get_db()
payments = db.collection('payments').where('status', '==', 'PENDING').stream()

count = 0
for p in payments:
    count += 1
    pd = p.to_dict()
    print(f"Payment: {p.id}")
    print(f"  Org: {pd.get('org_id')}")
    print(f"  Amount: {pd.get('amount')} {pd.get('currency')}")
    print(f"  Gateway: {pd.get('gateway')}")
    print(f"  Date: {pd.get('timestamp')}")
    print("-" * 20)

if count == 0:
    print("No pending payments found.")
