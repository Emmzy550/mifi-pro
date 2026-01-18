from utils.db import Database

def migrate_usage_records():
    """Migrate existing usage records to proper format."""
    print("=== Migrating Usage Records ===\n")
    
    db = Database.get_db()
    
    # Get all existing usage records
    all_docs = list(db.collection("usage_records").stream())
    print(f"Found {len(all_docs)} existing records\n")
    
    for doc in all_docs:
        data = doc.to_dict()
        print(f"Doc ID: {doc.id}")
        print(f"  Current data: {data}")
        
        # Delete old document
        doc.reference.delete()
        print(f"  Deleted old doc")
        
        # Recreate with proper format
        org_id = data.get('organization_id')
        env = data.get('environment', 'SANDBOX')
        count = data.get('assessment_count', 0)
        
        # Ensure environment is a clean string
        if isinstance(env, dict):
            env = env.get('value', 'SANDBOX')
        env_str = str(env).upper()
        
        # Create new doc ID
        new_doc_id = f"{org_id}_{env_str}"
        
        # Update data
        data['environment'] = env_str
        
        # Save with new ID
        db.collection("usage_records").document(new_doc_id).set(data)
        print(f"  Created new doc: {new_doc_id}")
        print(f"  Environment: {env_str}, Count: {count}\n")
    
    print("Migration complete!")

if __name__ == "__main__":
    migrate_usage_records()
