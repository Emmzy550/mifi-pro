
from utils.db import Database
from models.assessment import Assessment

def probe_assessment(id):
    ass = Database.get_assessment(id)
    if not ass:
        print(f"FAILED: Assessment {id} not found in Database")
        return
    
    print(f"Found Assessment: {ass.assessment_id}")
    print(f"  Organization: {ass.organization_id}")
    print(f"  Main Decision: {ass.decision}")
    print(f"  Has Metadata: {ass.final_decision_metadata is not None}")
    
    if ass.final_decision_metadata:
        print(f"  Metadata Type: {type(ass.final_decision_metadata)}")
        print(f"  Metadata Keys: {list(ass.final_decision_metadata.keys())}")
        print(f"  Metadata Decision: {ass.final_decision_metadata.get('officer_decision') or ass.final_decision_metadata.get('decision')}")
    
    # Check if a loan exists
    loans = Database.list_loans(organization_id=ass.organization_id)
    existing = [l for l in loans if l.assessment_id == id]
    print(f"  Existing Loans: {[l.loan_id for l in existing]}")

if __name__ == "__main__":
    probe_assessment('ASMT-CFB52429')
