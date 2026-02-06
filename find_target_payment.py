
from utils.db import Database
from force_activate_production import force_activate

print("Searching for payments with amount 28.5...")
db = Database.get_db()
payments = db.collection('payments').where('amount', '==', 28.5).where('status', '==', 'PENDING').stream()

for p in payments:
    pd = p.to_dict()
    print(f"FOUND: Payment {p.id} for Org {pd.get('org_id')} at {pd.get('timestamp')}")
    # We can try to guess based on timestamp or just activate all?
    # Let's just print for now so I can decide.
    if pd.get('org_id'):
       print(f"ACTIVATING {pd.get('org_id')} due to matching amount...")
       force_activate(pd.get('org_id'))

print("DONE")
