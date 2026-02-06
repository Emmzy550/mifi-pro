from utils.db import Database
from models.assessment import Assessment, RiskLevel, Decision
from models.borrower import Borrower, EmploymentType
import uuid
from datetime import datetime, timezone
import os

# Force local behavior
os.environ["K_SERVICE"] = "" 

def test_manual_visibility_fix():
    # 1. Simulate Public Intake (Borrower created in DEFAULT_ORG)
    public_org_id = "DEFAULT_ORG"
    borrower_id = f"BOR-PUBLIC-{uuid.uuid4().hex[:4].upper()}"
    
    borrower = Borrower(
        id=borrower_id,
        organization_id=public_org_id,
        name="Public Borrower",
        phone="123456789",
        employment_type=EmploymentType.SALARIED,
        monthly_income=5000.0,
        monthly_expenses=2000.0,
        loan_amount_requested=1000.0,
        loan_purpose="Public Intake"
    )
    
    print(f"STEP 1: Saving public borrower {borrower.id} in {public_org_id}")
    Database.save_borrower(borrower)
    
    # 2. Simulate Officer Action (Officer from ORG-ALPHA runs manual assessment)
    officer_org_id = "ORG-ALPHA"
    
    # --- SIMULATING UPDATED api.py LOGIC ---
    loaded_borrower = Database.get_borrower(borrower_id)
    print(f"STEP 2: Officer from {officer_org_id} loaded borrower {loaded_borrower.id} (Org: {loaded_borrower.organization_id})")
    
    # FIX APPLIED HERE:
    if loaded_borrower.organization_id != officer_org_id:
        if loaded_borrower.organization_id == "DEFAULT_ORG":
            print(f"FIX: Migrating borrower {loaded_borrower.id} to {officer_org_id}")
            loaded_borrower.organization_id = officer_org_id
            Database.save_borrower(loaded_borrower)
    
    # Then it calls _run_assessment_core which does this:
    assessment = Assessment(
        assessment_id=f"ASMT-{uuid.uuid4().hex[:8].upper()}",
        borrower_id=loaded_borrower.id,
        organization_id=loaded_borrower.organization_id, # Now it uses the updated org!
        requested_amount=loaded_borrower.loan_amount_requested,
        requested_duration_days=30,
        decision_timestamp=datetime.now(timezone.utc),
        risk_score=0.2,
        risk_level=RiskLevel.LOW,
        decision=Decision.APPROVE,
        assessment_source="MANUAL_UI",
        recommended_amount=1000.0,
        recommended_duration_days=30,
        recommended_interest_rate=15.0
    )
    
    print(f"STEP 3: Saving assessment {assessment.assessment_id} (Org: {assessment.organization_id})")
    Database.save_assessment(assessment)
    
    # 4. Simulate Dashboard View
    print(f"STEP 4: Querying assessments for Officer's Org: {officer_org_id}")
    results = Database.get_assessments_by_org(officer_org_id)
    
    print(f"RESULT: Found {len(results)} assessments for {officer_org_id}")
    
    if len(results) > 0 and any(a.assessment_id == assessment.assessment_id for a in results):
        print("SUCCESS: Assessment is now visible to the officer!")
    else:
        print("FAILURE: Assessment still invisible!")

if __name__ == "__main__":
    test_manual_visibility_fix()
