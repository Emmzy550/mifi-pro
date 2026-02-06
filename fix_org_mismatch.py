"""
Script to fix organization ID mismatch for assessments.

Problem: Dashboard user has org ORG-C796DDF6 but assessments are stored under different org IDs.
Solution: Update recent assessments to the correct org ID.
"""
import os
import sys

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.db import Database

def analyze_and_fix():
    """Analyze assessment org IDs and optionally fix them."""
    
    # Initialize DB
    db = Database.get_db()
    
    # 1. List all organizations
    print("\n=== Organizations in Database ===")
    orgs = Database.list_organizations()
    for org in orgs:
        print(f"  - {org.id}: {org.name} (Status: {org.status})")
    
    # 2. List all users
    print("\n=== Users in Database ===")
    users = Database.list_all_users()
    for user in users:
        print(f"  - {user.email}: org={user.organization_id}, role={user.role}")
    
    # 3. Count assessments by org
    print("\n=== Assessments by Organization ===")
    all_assessments = Database.list_assessments()
    org_counts = {}
    for a in all_assessments:
        org_id = a.organization_id
        org_counts[org_id] = org_counts.get(org_id, 0) + 1
    
    for org_id, count in sorted(org_counts.items(), key=lambda x: -x[1]):
        print(f"  - {org_id}: {count} assessments")
    
    # 4. Check API keys
    print("\n=== API Keys ===")
    # We can't list all API keys without org ID, so let's check known orgs
    for org in orgs:
        keys = Database.list_api_keys(org.id)
        for key in keys:
            print(f"  - Org: {org.id}, Key: {key.key_prefix}..., Env: {key.environment}, Status: {key.status}")
    
    print("\n=== Recommendation ===")
    print("If your dashboard user is 'wo@gmail.com' with org 'ORG-C796DDF6',")
    print("you need to run assessments with an API key that belongs to that same org.")
    print("\nAlternatively, run this to migrate recent assessments:")
    print("  python fix_org_mismatch.py --migrate ORG-C796DDF6")

def migrate_assessments(target_org_id, limit=50):
    """Migrate recent assessments to the target organization."""
    print(f"\n=== Migrating Recent Assessments to {target_org_id} ===")
    
    db = Database.get_db()
    
    # Get all assessments
    all_assessments = Database.list_assessments()
    
    # Sort by timestamp (most recent first) and take limit
    migrated = 0
    for assessment in all_assessments[:limit]:
        if assessment.organization_id != target_org_id:
            print(f"  Migrating {assessment.assessment_id} from {assessment.organization_id} to {target_org_id}")
            
            # Update in database
            assessment.organization_id = target_org_id
            Database.save_assessment(assessment)
            migrated += 1
    
    print(f"\n✅ Migrated {migrated} assessments to {target_org_id}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--migrate":
        if len(sys.argv) < 3:
            print("Usage: python fix_org_mismatch.py --migrate ORG_ID")
            sys.exit(1)
        target_org = sys.argv[2]
        migrate_assessments(target_org)
    else:
        analyze_and_fix()
