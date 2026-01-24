import sys
import os
import io

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from models.assessment import Assessment
from datetime import datetime, timezone

def test_manual_core_logic():
    print("=== Testing Core Assessment Logic Refactoring ===")
    
    # Create mock borrower
    borrower = Borrower(
        id="BOR-MAN-001",
        organization_id="ORG-TEST",
        name="Manual Test",
        phone="+260970000000",
        employment_type="trader",
        monthly_income=5000,
        monthly_expenses=2000,
        existing_debt=0,
        loan_amount_requested=1000,
        loan_purpose="Stock"
    )
    
    # Mock transactional data (Small volume for starter loan testing)
    mobile_money_history = [
        {"transaction_id": "TX-1", "amount": 200, "type": "DEPOSIT", "timestamp": datetime.now(timezone.utc).isoformat(), "direction": "INFLOW"}
    ]
    
    from api import _run_assessment_core
    import asyncio
    
    async def run():
        assessment = await _run_assessment_core(
            borrower=borrower,
            requested_duration_days=30,
            mobile_money_history=mobile_money_history,
            assessment_source="MANUAL_UI"
        )
        
        print(f"Decision: {assessment.decision}")
        if assessment.decision == "REJECT":
            print(f"Rejection Reason: {assessment.explanation}")
            
        print(f"Recommended Amount: {assessment.recommended_amount}")
        print(f"Audit View Present: {'Yes' if assessment.audit_view else 'No'}")
        
        assert assessment.borrower_id == borrower.id
        assert assessment.decision in ["APPROVE", "REJECT", "REFER", "CONDITIONAL"]
        
        # In REJECT cases, recommended_amount is often None or 0
        if assessment.decision == "APPROVE":
            assert assessment.recommended_amount is not None
            assert assessment.recommended_amount <= 1000 
        
        print("PASS: Core Logic Refactoring Verified (End-to-end result achieved)")

    asyncio.run(run())

if __name__ == "__main__":
    try:
        test_manual_core_logic()
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
