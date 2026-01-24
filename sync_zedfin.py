from agents.auth_agent import AuthAgent
from utils.db import Database
import firebase_admin
from firebase_admin import auth as firebase_auth

def sync_user(email, password):
    print(f"--- Syncing User to Firebase Auth: {email} ---")
    Database.get_db()
    
    try:
        uid = AuthAgent.create_firebase_user(email, password, "Admin User")
        print(f"SUCCESS: User synced to Firebase with UID: {uid}")
        
        # Also update the user ID in Firestore to match the Firebase UID
        # This is what our new code expects (1:1 mapping)
        user = Database.get_user_by_email(email)
        if user:
            old_id = user.id
            if old_id != uid:
                print(f"Updating Firestore User ID from {old_id} to {uid}")
                # We need to create a new doc and delete the old one or just save the new one if Database.save_user handles it
                # Actually, Database.save_user(user) uses user.id as the document ID.
                user.id = uid
                Database.save_user(user)
                
                # Deleting the old one
                db = Database.get_db()
                db.collection("users").document(old_id).delete()
                print("Firestore User ID updated successfully.")
            else:
                print("Firestore User ID already matches Firebase UID.")
        else:
            print("ERROR: User not found in Firestore. Check the email.")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    # Credentials from the user's screenshot
    sync_user("zedfin@gmail.com", "XYmsLKjjFiBowQ")
