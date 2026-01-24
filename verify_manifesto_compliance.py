import sys
import os
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from agents.query_agent import QueryAgent
from models.assessment import Assessment
from models.alternative_data import AlternativeData, MobileMoneyTransaction

def test_human_first_compliance():
    print("=" * 70)
    print("HUMAN-FIRST MANIFESTO VERIFICATION")
    print("=" * 70)
    
    # Setup: Borrower with limited history (Starter Loan case)
    borrower = Borrower(
        id="BOR-MANIFESTO-001",
        name="John Human",
        phone="+254700000000",
        loan_amount_requested=2500,
        monthly_income=5000,
        monthly_expenses=2000,
        employment_type="trader",
        loan_purpose="Business Growth"
    )
    
    # Transactions: 10 days of history (below starter threshold)
    now = datetime.now(timezone.utc)
    transactions = [
        MobileMoneyTransaction(transaction_id=f"TX-{i}", amount=300, type="DEPOSIT", timestamp=now)
        for i in range(5)
    ]
    
    from unittest.mock import patch
    with patch('utils.db.Database.get_alternative_data') as mock_alt:
        mock_alt.return_value = AlternativeData(borrower_id=borrower.id, mobile_money_history=transactions)
        
        # 1. Pipeline Execution
        risk_results = RiskAgent.evaluate(borrower)
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
        explanation_results = ExplanationAgent.generate(risk_results, decision_results, borrower)
        
        # 2. Structural Integrity (Structured Messages)
        print("\n[1] Checking Structured Message Sections...")
        assert "customer_message" in explanation_results, "Missing customer_message"
        assert "internal_notes" in explanation_results, "Missing internal_notes"
        
        cm = explanation_results["customer_message"]
        assert all(k in cm for k in ["summary", "key_reasons", "next_steps"]), "Missing sections in customer_message"
        
        inotes = explanation_results["internal_notes"]
        assert all(k in inotes for k in ["rationale", "policy_context", "guidance"]), "Missing sections in internal_notes"
        
        print("✅ Structured message dictionaries (Customer/Internal) generated successfully.")
        
        # 3. Dignity & Machine Marker Audit
        print("\n[2] Checking Dignity & Machine Marker Pass...")
        # Check for brackets in any part of the customer message
        for key, text in cm.items():
            if "[" in text or "]" in text:
                print(f"❌ ERROR: Machine marker found in customer_message section '{key}': {text}")
                assert False, f"Machine markers (brackets) prohibited in customer-facing text."
        
        prohibited = ["bad", "fail", "poor", "inadequate", "behavior", "reject", "conditional"] 
        for key, text in cm.items():
            lower_text = text.lower()
            for word in prohibited:
                if word in lower_text:
                    print(f"⚠️  Warning: Potential non-dignified or system-like word '{word}' found in Customer Message '{key}'.")
        
        print("Customer Message Preview:")
        print(f"  Summary: {cm['summary']}")
        print(f"  Reasons: {cm['key_reasons']}")
        print(f"  Steps:   {cm['next_steps']}")
        
        # 4. Blocking Factors Assertion
        print("\n[3] Checking Blocking Factors...")
        factors = explanation_results.get("blocking_factors", [])
        
        found = any(f in factors for f in ["STARTER_LOAN_CAP", "INSUFFICIENT_TRANSACTION_HISTORY", "CAPACITY_SAFETY_LIMIT", "HIGH_RISK_SCORE"])
        if not found:
            print(f"❌ ERROR: Expected factors not found in {factors}")
            
        assert found, f"Missing expected blocking factor in {factors}"
        print("✅ Blocking factors correctly identified.")
        
        # 5. "Ask Why" Deterministic Query Test
        print("\n[4] Testing 'Ask Why' Deterministic Query System...")
        # Build assessment object
        assessment = Assessment(
            assessment_id="ASMT-QUERY-TEST",
            borrower_id="BOR-001",
            risk_score=risk_results["risk_score"],
            risk_level=risk_results["risk_level"],
            decision=decision_results["decision"],
            recommended_amount=decision_results["recommended_amount"],
            recommended_interest_rate=decision_results["recommended_interest_rate"],
            requested_amount=borrower.loan_amount_requested,
            decision_summary=explanation_results["decision_summary"],
            customer_message=explanation_results["customer_message"],
            internal_notes=explanation_results["internal_notes"],
            customer_view=explanation_results["customer_view"],
            officer_view=explanation_results["officer_view"],
            audit_view=explanation_results["audit_view"],
            blocking_factors=explanation_results["blocking_factors"],
            explanation=explanation_results["explanation"],
            explanation_source="engine",
            metrics=risk_results["metrics"]
        )
        
        # Test Query 1: Why Capped?
        q1 = QueryAgent.answer(assessment, "WHY_CAPPED")
        print(f"Q: Why was this loan capped?\nA: {q1['answer']}")
        assert "$" in q1["answer"], "Answer should contain amount"
        
        # Test Query 2: What Policy?
        q2 = QueryAgent.answer(assessment, "WHAT_POLICY")
        print(f"Q: What policy applied?\nA: {q2['answer']}")
        assert "v1.2.0-human-first" in q2["answer"], "Incorrect policy version reported"
        
        print("\n✅ Verification Complete: System is Human-First compliant.")
        print("=" * 70)

if __name__ == "__main__":
    try:
        test_human_first_compliance()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
