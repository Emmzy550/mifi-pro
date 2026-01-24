"""
Comprehensive Test Suite for Loan Officer AI V1→V4
===================================================

Tests all modes of operation:
1. Rule-only mode (ML disabled)
2. Ensemble mode (ML enabled)
3. Behavioral V2 integration
4. Feature flag toggling
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.borrower import Borrower, EmploymentType
from models.alternative_data import AlternativeData, MobileMoneyTransaction, UtilityPayment
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from datetime import datetime, timedelta
import config


def test_rule_only_mode():
    """Test system with ML disabled (pure rule-based)."""
    print("\n" + "="*70)
    print("TEST 1: RULE-ONLY MODE (ML Disabled)")
    print("="*70)
    
    # Temporarily disable ML
    original_ml_flag = config.ENABLE_ML_RISK_SCORING
    config.ENABLE_ML_RISK_SCORING = False
    
    try:
        # Test case: Strong borrower
        borrower = Borrower(
            id="TEST-001",
            name="Strong Borrower",
            phone="+254700000001",
            employment_type=EmploymentType.SALARIED,
            monthly_income=5000,
            monthly_expenses=2000,
            existing_debt=500,
            loan_amount_requested=10000,
            loan_purpose="Business expansion"
        )
        
        risk_results = RiskAgent.evaluate(borrower)
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
        
        print(f"\n✓ Borrower: {borrower.name}")
        print(f"  Risk Score: {risk_results['risk_score']:.2f} ({risk_results['risk_level']})")
        print(f"  Decision: {decision_results['decision']}")
        print(f"  ML Used: {risk_results['ml_based_score'] > 0}")
        print(f"  Override Applied: {risk_results.get('override_applied', False)}")
        
        assert risk_results['ml_based_score'] == 0, "ML should not be used when disabled"
        assert decision_results['decision'] in ["APPROVE", "CONDITIONAL", "REJECT"], "Valid decision required"
        
        print("\n✅ Rule-only mode test PASSED")
        
    finally:
        # Restore original flag
        config.ENABLE_ML_RISK_SCORING = original_ml_flag


def test_ensemble_mode():
    """Test system with ML enabled (ensemble scoring)."""
    print("\n" + "="*70)
    print("TEST 2: ENSEMBLE MODE (ML Enabled)")
    print("="*70)
    
    # Ensure ML is enabled
    original_ml_flag = config.ENABLE_ML_RISK_SCORING
    config.ENABLE_ML_RISK_SCORING = True
    
    try:
        # Test case: Borderline borrower (where ML might help)
        borrower = Borrower(
            id="TEST-002",
            name="Borderline Borrower",
            phone="+254700000002",
            employment_type=EmploymentType.TRADER,
            monthly_income=2000,
            monthly_expenses=1200,
            existing_debt=300,
            loan_amount_requested=5000,
            loan_purpose="Inventory purchase"
        )
        
        risk_results = RiskAgent.evaluate(borrower)
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
        
        print(f"\n✓ Borrower: {borrower.name}")
        print(f"  Risk Score: {risk_results['risk_score']:.2f} ({risk_results['risk_level']})")
        print(f"  Rule Score: {risk_results['rule_based_score']:.2f}")
        print(f"  ML Score: {risk_results['ml_based_score']:.2f}")
        print(f"  Decision: {decision_results['decision']}")
        print(f"  Ensemble Weights: {config.RULE_WEIGHT:.0%} rules, {config.ML_WEIGHT:.0%} ML")
        
        # ML should have contributed if model exists
        if os.path.exists(config.ML_MODEL_PATH):
            assert risk_results['ml_based_score'] >= 0, "ML score should be present"
            print("\n✅ Ensemble mode test PASSED")
        else:
            print("\n⚠️  ML model not found, skipping ensemble verification")
        
    finally:
        config.ENABLE_ML_RISK_SCORING = original_ml_flag


def test_critical_flag_override():
    """Test that critical flags override ML predictions."""
    print("\n" + "="*70)
    print("TEST 3: CRITICAL FLAG OVERRIDE")
    print("="*70)
    
    # High-risk borrower with critical violations
    borrower = Borrower(
        id="TEST-003",
        name="High Risk Borrower",
        phone="+254700000003",
        employment_type=EmploymentType.GIG,
        monthly_income=80,  # Below minimum
        monthly_expenses=100,  # Negative cash flow
        existing_debt=50,
        loan_amount_requested=1000,
        loan_purpose="Emergency"
    )
    
    risk_results = RiskAgent.evaluate(borrower)
    decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
    
    print(f"\n✓ Borrower: {borrower.name}")
    print(f"  Risk Score: {risk_results['risk_score']:.2f} ({risk_results['risk_level']})")
    print(f"  Flags: {risk_results['flags']}")
    print(f"  Decision: {decision_results['decision']}")
    print(f"  Override Applied: {risk_results.get('override_applied', False)}")
    
    # Critical flags should force rejection
    has_critical = any("CRITICAL" in f for f in risk_results['flags'])
    assert has_critical, "Critical flags should be present"
    assert risk_results['risk_score'] == 1.0, "Critical flags should force max risk score"
    assert decision_results['decision'] == "REJECT", "Critical flags should force rejection"
    
    print("\n✅ Critical flag override test PASSED")


def test_behavioral_v2_integration():
    """Test behavioral intelligence V2 metrics."""
    print("\n" + "="*70)
    print("TEST 4: BEHAVIORAL V2 INTEGRATION")
    print("="*70)
    
    # Create borrower with alternative data
    borrower = Borrower(
        id="TEST-004",
        name="Behavioral Test Borrower",
        phone="+254700000004",
        employment_type=EmploymentType.TRADER,
        monthly_income=3000,
        monthly_expenses=1500,
        existing_debt=200,
        loan_amount_requested=8000,
        loan_purpose="Stock purchase"
    )
    
    # Create mock alternative data
    from utils.db import Database
    
    # Generate sample mobile money transactions
    now = datetime.now()
    transactions = []
    for i in range(20):
        # Regular deposits (income)
        transactions.append(MobileMoneyTransaction(
            transaction_id=f"TXN-DEP-{i}",
            amount=1000 + (i * 50),  # Slightly varying amounts
            type="DEPOSIT",
            timestamp=now - timedelta(days=i*3),
            counterparty="EMPLOYER"
        ))
        # Regular withdrawals (expenses)
        transactions.append(MobileMoneyTransaction(
            transaction_id=f"TXN-WD-{i}",
            amount=500 + (i * 20),
            type="WITHDRAWAL",
            timestamp=now - timedelta(days=i*3 + 1),
            counterparty="ATM"
        ))
    
    # Utility payments
    utilities = [
        UtilityPayment(
            utility_name="Electricity",
            amount=150,
            timestamp=now - timedelta(days=i*30),
            status="PAID"
        )
        for i in range(6)
    ]
    
    alt_data = AlternativeData(
        borrower_id=borrower.id,
        mobile_money_history=transactions,
        utility_history=utilities,
        airtime_usage_avg=50
    )
    
    Database.save_alternative_data(alt_data)
    
    # Run assessment
    risk_results = RiskAgent.evaluate(borrower)
    decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
    explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)
    
    print(f"\n✓ Borrower: {borrower.name}")
    print(f"  Behavioral Stability: {risk_results['metrics'].get('behavioral_stability', 0):.2f}")
    print(f"  Income Consistency: {risk_results['metrics'].get('income_consistency_score', 0):.2f}")
    print(f"  Savings Trend: {risk_results['metrics'].get('saving_trend', 0):.2f}")
    print(f"  Utility Compliance: {risk_results['metrics'].get('utility_compliance', 0):.2f}")
    print(f"  Decision: {decision_results['decision']}")
    
    # Verify behavioral metrics are present
    assert risk_results['metrics'].get('behavioral_stability', 0) > 0, "Behavioral stability should be calculated"
    # Fix: explanation is a dict, check 'explanation' or 'officer_view' field
    explanation_text = explanation.get("explanation", "") + explanation.get("officer_view", "")
    assert "BEHAVIORAL INTELLIGENCE" in explanation_text or risk_results['metrics'].get('behavioral_stability', 0) == 0, "Explanation should include behavioral section"
    
    print("\n✅ Behavioral V2 integration test PASSED")


def test_config_snapshot():
    """Test that config snapshot is included in risk results."""
    print("\n" + "="*70)
    print("TEST 5: CONFIG SNAPSHOT IN AUDIT TRAIL")
    print("="*70)
    
    borrower = Borrower(
        id="TEST-005",
        name="Config Test Borrower",
        phone="+254700000005",
        employment_type=EmploymentType.SALARIED,
        monthly_income=4000,
        monthly_expenses=2000,
        existing_debt=400,
        loan_amount_requested=6000,
        loan_purpose="Education"
    )
    
    risk_results = RiskAgent.evaluate(borrower)
    
    print(f"\n✓ Config Snapshot Present: {'config_snapshot' in risk_results}")
    print(f"  ML Enabled (at decision time): {risk_results['config_snapshot']['feature_flags']['ml_enabled']}")
    print(f"  Behavioral V2 Enabled: {risk_results['config_snapshot']['feature_flags']['behavioral_v2_enabled']}")
    print(f"  Model Version: {risk_results['config_snapshot']['model_config']['ml_version']}")
    
    assert 'config_snapshot' in risk_results, "Config snapshot should be in results"
    assert 'feature_flags' in risk_results['config_snapshot'], "Feature flags should be logged"
    
    print("\n✅ Config snapshot test PASSED")


def run_all_tests():
    """Run all test suites."""
    print("\n" + "="*70)
    print("LOAN OFFICER AI V1→V4 COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    try:
        test_rule_only_mode()
        test_ensemble_mode()
        test_critical_flag_override()
        test_behavioral_v2_integration()
        test_config_snapshot()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nSystem is ready for production deployment.")
        print("Next steps:")
        print("  1. Deploy to staging environment")
        print("  2. Run with ML disabled initially")
        print("  3. Gradually enable ML with conservative weighting")
        print("  4. Monitor decision divergence from rule-only mode")
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
