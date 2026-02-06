
from utils.db import Database
from force_activate_production import force_activate
import os

print("Searching for try@gmail.com...")
# Ensure we can connect
db = Database.get_db()
users = db.collection('users').where('email', '==', 'try@gmail.com').stream()

count = 0
for u in users:
    count += 1
    data = u.to_dict()
    org_id = data.get('org_id')
    print(f"Found User: {data.get('email')} -> Org: {org_id}")
    if org_id:
        force_activate(org_id)
    else:
        print("WARNING: User found but no Org ID.")

if count == 0:
    print("No user found with email try@gmail.com. Please check spelling or database sync.")

print("DONE")
