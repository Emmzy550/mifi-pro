import os
import sys

# Ensure output is flushed immediately
def log(msg):
    print(msg, flush=True)

log("Starting provision_user script...")

try:
    from agents.auth_agent import AuthAgent
    from utils.db import Database
    from models.user import User, UserRole
    from models.organization import Organization, OrgStatus, BillingPlan
    import uuid
    log("Imports successful.")
except Exception as e:
    log(f"Import failed: {e}")
    sys.exit(1)

def provision_user(email, password, role=UserRole.SUPER_ADMIN):
    log(f"\n--- Provisioning User: {email} ---")
    try:
        log("Initializing Database...")
        db = Database.get_db()
        log("Database initialized.")
        
        # 1. Ensure PLATFORM_OWNER organization exists
        log("Checking for PLATFORM_OWNER organization...")
        plat_org = Database.get_organization("PLATFORM_OWNER")
        if not plat_org:
            log("Creating PLATFORM_OWNER organization...")
            plat_org = Organization(
                id="PLATFORM_OWNER",
                name="Loan Officer AI Platform",
                plan_name=BillingPlan.ENTERPRISE,
                monthly_limit=1000000,
                status=OrgStatus.ACTIVE
            )
            Database.save_organization(plat_org)
            log("Created PLATFORM_OWNER org.")
        else:
            log("PLATFORM_OWNER org exists.")

        # 2. Check for existing user in Firestore
        log(f"Checking for existing user record in Firestore...")
        existing_user = Database.get_user_by_email(email)
        
        # 3. Create/Sync with Firebase Auth
        log(f"Syncing with Firebase Authentication...")
        try:
            firebase_uid = AuthAgent.create_firebase_user(email, password, "Admin User")
            log(f"Firebase Auth synced. UID: {firebase_uid}")
        except Exception as e:
            log(f"Error syncing with Firebase Auth: {e}")
            return

        # 4. Create/Update Firestore record with matching UID
        if existing_user:
            old_id = existing_user.id
            if old_id != firebase_uid:
                log(f"Updating Firestore User ID from {old_id} to match Firebase UID {firebase_uid}")
                
                new_user = User(
                    id=firebase_uid,
                    organization_id=existing_user.organization_id,
                    email=existing_user.email,
                    password_hash=existing_user.password_hash,
                    full_name=existing_user.full_name,
                    role=role
                )
                Database.save_user(new_user)
                
                db.collection("users").document(old_id).delete()
                log("Firestore record migrated successfully.")
            else:
                log("Firestore record already correctly mapped to Firebase UID.")
                existing_user.role = role
                Database.save_user(existing_user)
        else:
            log(f"Creating new Super Admin record in Firestore...")
            pwd_hash = AuthAgent.get_password_hash(password)
            new_user = User(
                id=firebase_uid,
                organization_id="PLATFORM_OWNER",
                email=email,
                password_hash=pwd_hash,
                full_name="Platform Admin",
                role=role
            )
            Database.save_user(new_user)
            log("Created new Super Admin record.")

        log(f"\n[SUCCESS] User Provisioned and Ready")
        log(f"Email: {email}")
        log(f"Password: {password}")
        log(f"Role: {role}")

    except Exception as e:
        log(f"An error occurred during provisioning: {e}")

if __name__ == "__main__":
    email = "admin@platform.com"
    password = "admin123"
    
    provision_user(email, password)
