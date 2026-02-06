import sys
import os
import uuid
from datetime import datetime, timezone

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower, IDType, EmploymentType
from models.assessment import Assessment, RiskLevel, Decision
from agents.decision_export_agent import DecisionExportAgent
import asyncio

async def test_pdf_export_improvement():
    print("=== Testing PDF Export Improvement ===")
    
    # 1. Create Mock Borrower
    borrower = Borrower(
        id=f"BOR-PDF-TEST-{uuid.uuid4().hex[:4]}",
        organization_id="ORG-TEST",
        name="PDF Layout Tester",
        phone="+260970000001",
        employment_type=EmploymentType.SALARIED,
        monthly_income=12500.50,
        monthly_expenses=4200.00,
        existing_debt=1000.00,
        loan_amount_requested=5000.00,
        loan_purpose="Business Expansion",
        national_id="123456/11/1",
        id_provided=True,
        id_type=IDType.NRC
    )
    
    # 2. Create Mock Assessment
    assessment = Assessment(
        assessment_id=f"ASM-{uuid.uuid4().hex[:6].upper()}",
        borrower_id=borrower.id,
        organization_id=borrower.organization_id,
        decision=Decision.APPROVE,
        risk_level=RiskLevel.LOW,
        risk_score=0.264, # 0-1 scale
        recommended_amount=5000.00,
        recommended_duration_days=90,
        recommended_interest_rate=15.0,
        decision_summary="Applicant shows strong transaction history and high behavioral stability. Debt-to-income ratio is well within safe thresholds for the requested amount.",
        metrics={
            "dti_ratio": 0.32,
            "behavioral_stability": 0.85,
            "expense_ratio": 0.45
        },
        flags=[],
        final_decision_metadata={
            "officer_decision": "APPROVE",
            "final_amount": 5000.00,
            "final_duration": 90,
            "final_interest_rate": 15.0
        },
        policy_version="1.4.2"
    )
    
    # 3. Generate Export
    print(f"Generating PDF for {borrower.name}...")
    exports = DecisionExportAgent.generate_exports(
        assessment=assessment,
        borrower=borrower,
        generated_by="System Test Agent",
        force=True
    )
    
    print(f"Total exports returned: {len(exports)}")
    for exp in exports:
        print(f"- Type: {exp.export_type.value}, Status: {exp.status.value}, Error: {exp.error or 'None'}")

    pdf_export = next((e for e in exports if e.export_type.value == "PDF" and e.status.value == "READY"), None)
    if pdf_export:
        print(f"✓ PDF Export Generated: {pdf_export.file_path}")
        print(f"✓ File Hash: {pdf_export.file_hash}")
        
        # In a real shell, the user would open this file. 
        # I will check if file exists.
        if os.path.exists(pdf_export.file_path):
            print("✓ File exists on disk.")
        else:
            print("✗ File NOT found on disk!")
    else:
        print("✗ PDF Export NOT generated!")

    print("\nPDF EXPORT VERIFICATION COMPLETE!")

if __name__ == "__main__":
    asyncio.run(test_pdf_export_improvement())
