"""
Capacity Guardrails Test Suite
================================

Tests to verify that the bank-grade capacity-based lending system
is more conservative than a human loan officer and correctly enforces
all capacity limits.

These tests implement the "Human-Override Simulation" requirement.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower
from agents.capacity_agent import CapacityAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from models.alternative_data import AlternativeData, MobileMoneyTransaction
from datetime import datetime, timedelta, timezone


class CapacityGuardrailsTests:
    """Test suite for capacity-based lending guardrails."""
    
    @staticmethod
    def test_low_capacity_high_request():
        """
        Scenario: Borrower with $50/month asking for $15,000
        Expected: recommended_amount <= $500
        Expected: decision != APPROVE
        """
        print("\n=== TEST 1: Low Capacity, High Request ===")
        
        # Create borrower requesting $15,000
        borrower = Borrower(
            id="BOR-TEST-001",
            organization_id="TEST_ORG",
            name="Test Borrower",
            phone="+254700000000",
            employment_type="trader",
            monthly_income=5000,  # Stated
            monthly_expenses=4000,
            existing_debt=0,
            loan_amount_requested=15000,  # Requesting $15k
            loan_purpose="Business"
        )
        
        # Create minimal transaction history showing only $50/month actual inflow
        transactions = []
        now = datetime.now(timezone.utc)
        for i in range(6):  # 6 transactions over 60 days
            transactions.append(MobileMoneyTransaction(
                transaction_id=f"TX-{i}",
                amount=50 if i % 2 == 0 else 20,  # $50 deposits, $20 expenses
                type="DEPOSIT" if i % 2 == 0 else "PAYMENT",
                timestamp=now - timedelta(days=i*10)
            ))
        
        # Simulate capacity check (we'll mock the database return)
        from unittest.mock import patch
        
        with patch('utils.db.Database.get_alternative_data') as mock_alt_data:
            mock_alt_data.return_value = AlternativeData(
                borrower_id=borrower.id,
                airtime_usage_avg=0,
                mobile_money_history=transactions
            )
            
            # Run risk evaluation
            risk_results = RiskAgent.evaluate(borrower)
            
            # Get decision
            decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
            
            # ASSERTIONS
            recommended = decision_results["recommended_amount"]
            decision = decision_results["decision"]
            
            print(f"Requested: ${borrower.loan_amount_requested}")
            print(f"Observed Deposit Volume: ${risk_results['metrics'].get('observed_deposit_volume', 0)}")
            print(f"Capacity Max: ${risk_results['metrics'].get('capacity_based_max', 0)}")
            print(f"Recommended: ${recommended}")
            print(f"Decision: {decision}")
            
            assert recommended <= 500, f"FAIL: Recommended {recommended} exceeds conservative limit of 500"
            assert decision != "APPROVE", f"FAIL: Should not fully approve with such low capacity"
            
            print("✅ PASS: System correctly limited amount to capacity")
    
    @staticmethod
    def test_insufficient_transaction_history():
        """
        Scenario: Only 3 transactions
        Expected: REJECT with reason "Insufficient transaction history"
        """
        print("\n=== TEST 2: Insufficient Transaction History ===")
        
        borrower = Borrower(
            id="BOR-TEST-002",
            organization_id="TEST_ORG",
            name="Sparse Data Borrower",
            phone="+254700000001",
            employment_type="salaried",
            monthly_income=10000,
            monthly_expenses=5000,
            existing_debt=0,
            loan_amount_requested=5000,
            loan_purpose="Emergency"
        )
        
        # Only 3 transactions - below minimum
        transactions = []
        now = datetime.now(timezone.utc)
        for i in range(3):
            transactions.append(MobileMoneyTransaction(
                transaction_id=f"TX-SPARSE-{i}",
                amount=1000,
                type="DEPOSIT",
                timestamp=now - timedelta(days=i*5)
            ))
        
        from unittest.mock import patch
        
        with patch('utils.db.Database.get_alternative_data') as mock_alt_data:
            mock_alt_data.return_value = AlternativeData(
                borrower_id=borrower.id,
                mobile_money_history=transactions
            )
            
            risk_results = RiskAgent.evaluate(borrower)
            decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
            
            decision = decision_results["decision"]
            flags = risk_results["flags"]
            
            print(f"Transaction Count: {risk_results['metrics'].get('transaction_count', 0)}")
            print(f"Decision: {decision}")
            print(f"Flags: {flags}")
            
            # Should be rejected or referred due to insufficient data
            assert decision in ["REJECT", "REFER"], f"FAIL: Should reject or refer with insufficient transactions"
            assert any("insufficient" in str(f).lower() for f in flags), "FAIL: Missing transaction history flag"
            
            print("✅ PASS: System correctly rejected sparse data")
    
    @staticmethod
    def test_starter_loan_policy():
        """
        Scenario: 60 days history, $3000 monthly inflow
        Expected: Starter loan cap applied
        Expected: Interest premium added
        """
        print("\n=== TEST 3: Starter Loan Policy ===")
        
        borrower = Borrower(
            id="BOR-TEST-003",
            organization_id="TEST_ORG",
            name="New Borrower",
            phone="+254700000002",
            employment_type="trader",
            monthly_income=8000,
            monthly_expenses=3000,
            existing_debt=0,
            loan_amount_requested=2000,
            loan_purpose="Stock"
        )
        
        # 60 days of history (below 90-day threshold)
        transactions = []
        now = datetime.now(timezone.utc)
        for i in range(10):
            transactions.append(MobileMoneyTransaction(
                transaction_id=f"TX-NEW-{i}",
                amount=300,
                type="DEPOSIT" if i % 3 != 2 else "PAYMENT",
                timestamp=now - timedelta(days=i*6)
            ))
        
        from unittest.mock import patch
        import lending_config.capacity_config as cap_config
        
        with patch('utils.db.Database.get_alternative_data') as mock_alt_data:
            mock_alt_data.return_value = AlternativeData(
                borrower_id=borrower.id,
                mobile_money_history=transactions
            )
            
            risk_results = RiskAgent.evaluate(borrower)
            decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
            
            starter_applied = risk_results['metrics'].get('starter_loan_applied', False)
            recommended = decision_results["recommended_amount"]
            interest_rate = decision_results["recommended_interest_rate"]
            
            print(f"History Days: {risk_results['metrics'].get('history_days', 0)}")
            print(f"Starter Loan Applied: {starter_applied}")
            print(f"Recommended: ${recommended}")
            print(f"Interest Rate: {interest_rate}%")
            print(f"Starter Cap: ${cap_config.STARTER_LOAN_CAP}")
            
            assert starter_applied, "FAIL: Starter loan should be applied for <90 day history"
            assert recommended <= cap_config.STARTER_LOAN_CAP, f"FAIL: Exceeded starter cap"
            
            print("✅ PASS: Starter loan policy correctly enforced")
    
    @staticmethod
    def test_capacity_cannot_be_exceeded():
        """
        Scenario: Verify capacity_based_max is NEVER exceeded
        Expected: recommended_amount <= capacity_based_max always
        """
        print("\n=== TEST 4: Capacity is Absolute Limit ===")
        
        borrower = Borrower(
            id="BOR-TEST-004",
            organization_id="TEST_ORG",
            name="Cap Test Borrower",
            phone="+254700000003",
            employment_type="salaried",
            monthly_income=20000,  # Stated high income
            monthly_expenses=5000,
            existing_debt=0,
            loan_amount_requested=50000,  # Requesting very high amount
            loan_purpose="Business Expansion"
        )
        
        # Actual transaction history shows only $2000/month
        transactions = []
        now = datetime.now(timezone.utc)
        for i in range(20):
            transactions.append(MobileMoneyTransaction(
                transaction_id=f"TX-CAP-{i}",
                amount=200 if i % 4 == 0 else 50,
                type="DEPOSIT" if i % 4 == 0 else "PAYMENT",
                timestamp=now - timedelta(days=i*5)
            ))
        
        from unittest.mock import patch
        
        with patch('utils.db.Database.get_alternative_data') as mock_alt_data:
            mock_alt_data.return_value = AlternativeData(
                borrower_id=borrower.id,
                mobile_money_history=transactions
            )
            
            risk_results = RiskAgent.evaluate(borrower)
            decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
            
            capacity_max = risk_results['metrics'].get('capacity_based_max', 0)
            recommended = decision_results["recommended_amount"]
            
            print(f"Requested: ${borrower.loan_amount_requested}")
            print(f"Capacity Max: ${capacity_max}")
            print(f"Recommended: ${recommended}")
            
            assert recommended <= capacity_max, f"FAIL: Recommended {recommended} exceeds capacity {capacity_max}"
            assert recommended < borrower.loan_amount_requested, "FAIL: Should reduce high request"
            
            print("✅ PASS: Capacity limit absolutely enforced")

    @staticmethod
    def test_explanation_consistency():
        """
        Scenario: Verify ExplanationValidator repairs missing capacity mentions
        Expected: Explanation contains capacity justification after repair
        """
        print("\n=== TEST 5: Explanation Consistency & Repair ===")
        
        from utils.explanation_validator import ExplanationValidator
        from models.assessment import Assessment
        
        assessment = Assessment(
            assessment_id="ASMT-EX-001",
            borrower_id="BOR-001",
            organization_id="ORG-TEST",
            risk_score=0.2,
            risk_level="LOW",
            decision="CONDITIONAL",
            requested_amount=5000,
            requested_duration_days=30,
            recommended_amount=1000,
            recommended_duration_days=30,
            recommended_interest_rate=15.0,
            decision_timestamp=datetime.now(timezone.utc),
            explanation="We liked your application but we can only give you 1000.",
            observed_deposit_volume=400,
            capacity_based_max=1000
        )
        
        # Repaired explanation should add capacity mention
        repaired = ExplanationValidator.auto_repair_explanation(assessment)
        print(f"Original: {assessment.explanation}")
        print(f"Repaired: {repaired}")
        
        assert "capacity" in repaired.lower() or "deposit" in repaired.lower(), "FAIL: Repair did not add capacity justification"
        
        # Validation should pass now
        assessment.explanation = repaired
        assert ExplanationValidator.validate(assessment), "FAIL: Validation failed for repaired explanation"
        
        print("✅ PASS: Explanation correctly repaired and validated")


def run_all_tests():
    """Run all capacity guardrail tests."""
    print("=" * 70)
    print("CAPACITY GUARDRAILS TEST SUITE")
    print("Bank-Grade Lending System Verification")
    print("=" * 70)
    
    tests = CapacityGuardrailsTests()
    
    try:
        tests.test_low_capacity_high_request()
        tests.test_insufficient_transaction_history()
        tests.test_starter_loan_policy()
        tests.test_capacity_cannot_be_exceeded()
        tests.test_explanation_consistency()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("System is more conservative than a human loan officer")
        print("=" * 70)
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
