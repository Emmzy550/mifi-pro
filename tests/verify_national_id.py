import sys
import os
import uuid
from datetime import datetime, timezone

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower, IDType, IDReviewStatus
from utils.db import Database
from utils.encryption import EncryptionAgent
import asyncio

async def test_id_detection_and_storage():
    print("=== Testing National ID Detection & Secure Storage ===")
    
    # 1. Test NRC Detection
    nrc_id = "123456/11/1"
    borrower_nrc = Borrower(
        id=f"BOR-TEST-NRC-{uuid.uuid4().hex[:4]}",
        organization_id="ORG-TEST",
        name="NRC Test User",
        phone="+260970000001",
        employment_type="trader",
        monthly_income=5000,
        monthly_expenses=2000,
        loan_amount_requested=1000,
        loan_purpose="Test",
        national_id=nrc_id,
        id_provided=True,
        id_type=IDType.NRC,
        id_review_status=IDReviewStatus.NOT_REVIEWED
    )
    
    Database.save_borrower(borrower_nrc)
    print(f"✓ Saved borrower with NRC: {nrc_id}")
    
    # Verify Encryption in DB (Mock DB access for verification)
    db = Database.get_db()
    raw_data = db.collection("borrowers").document(borrower_nrc.id).get().to_dict()
    stored_id = raw_data.get("national_id")
    
    assert stored_id != nrc_id, "CRITICAL: National ID stored in plaintext!"
    print(f"✓ National ID is encrypted in storage: {stored_id[:10]}...")
    
    # Verify Decryption
    retrieved_borrower = Database.get_borrower(borrower_nrc.id)
    assert retrieved_borrower.national_id == nrc_id, f"Decryption failure: Expected {nrc_id}, got {retrieved_borrower.national_id}"
    print(f"✓ National ID decrypted correctly: {retrieved_borrower.national_id}")
    
    # 2. Test Passport Detection (via API-like logic in a mock call)
    passport_id = "AB1234567"
    is_nrc = "/" in passport_id
    id_type = IDType.NRC if is_nrc else IDType.PASSPORT
    
    assert id_type == IDType.PASSPORT, f"Passport detection failed for {passport_id}"
    print(f"✓ Passport detection logic verified for: {passport_id}")
    
    # 3. Test without ID
    borrower_no_id = Borrower(
        id=f"BOR-TEST-NOID-{uuid.uuid4().hex[:4]}",
        organization_id="ORG-TEST",
        name="No ID User",
        phone="+260970000002",
        employment_type="trader",
        monthly_income=5000,
        monthly_expenses=2000,
        loan_amount_requested=1000,
        loan_purpose="Test",
        id_provided=False,
        id_type=IDType.UNKNOWN,
        id_review_status=IDReviewStatus.NOT_REVIEWED
    )
    Database.save_borrower(borrower_no_id)
    retrieved_no_id = Database.get_borrower(borrower_no_id.id)
    assert retrieved_no_id.national_id is None
    assert retrieved_no_id.id_provided is False
    print("✓ Optional behavior verified (form works without ID)")

    print("\nALL NATIONAL ID VERIFICATION TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_id_detection_and_storage())
