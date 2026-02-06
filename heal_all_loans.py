
import asyncio
import uuid
from utils.db import Database
from models.loan import Loan, LoanStatus
from models.assessment import Decision

def heal_all():
    print("Starting global self-healing sweep...")
    assessments = Database.list_assessments()
    loans = Database.list_loans()
    existing_asmt_ids = {l.assessment_id for l in loans}
    
    count = 0
    for ass in assessments:
        if ass.assessment_id in existing_asmt_ids:
            continue
            
        # Determine if it's an approval
        is_approved = False
        decision_str = str(ass.decision).split('.')[-1].upper()
        if decision_str == "APPROVE":
            is_approved = True
        
        meta = ass.final_decision_metadata or {}
        m_decision = meta.get("officer_decision") or meta.get("decision")
        if m_decision:
            if str(m_decision).split('.')[-1].upper() == "APPROVE":
                is_approved = True
        
        if is_approved:
            print(f"  Healting ASMT: {ass.assessment_id} (Org: {ass.organization_id})")
            
            amount = meta.get("final_amount") or ass.recommended_amount or 0.0
            rate = meta.get("final_interest_rate") or ass.recommended_interest_rate or 0.0
            
            new_loan = Loan(
                loan_id=f"LOAN-{uuid.uuid4().hex[:8].upper()}",
                assessment_id=ass.assessment_id,
                borrower_id=ass.borrower_id,
                organization_id=ass.organization_id,
                amount=float(amount),
                interest_rate=float(rate),
                status=LoanStatus.PENDING_DISBURSEMENT
            )
            Database.save_loan(new_loan)
            count += 1
            
    print(f"Finished. Created {count} missing loan records.")

if __name__ == "__main__":
    heal_all()
