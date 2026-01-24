import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone
from models.borrower import Borrower
from models.assessment import Assessment, Decision
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.capacity_agent import CapacityAgent
from utils.scoring import validate_decision_consistency
from api import filter_assessment_for_role

# ============================================================================
# AUDIT TEST SUITE: SCENARIO VERIFICATION
# ============================================================================

@pytest.fixture
def mock_borrower():
    return Borrower(
        id="BOR-TEST-001",
        name="Test Borrower",
        monthly_income=50000,
        monthly_expenses=20000,
        existing_debt=5000,
        loan_amount_requested=15000,
        organization_id="DEFAULT_ORG"
    )

def test_scenario_a_short_history_wait():
    """Scenario A: 7 days history -> Result: WAIT."""
    # Create transactions with only 7 days span
    now = datetime.now(timezone.utc)
    # Using real objects where possible, mocking dates
    class MockTx:
        def __init__(self, amount, date):
            self.amount = amount
            self.date = date
            self.direction = "INFLOW"
            self.type = "DEPOSIT"
            self.confidence_weight = 0.9
            self.timestamp = date

    transactions = [
        MockTx(5000, now - timedelta(days=i))
        for i in [0, 3, 7]
    ]
    
    with patch('utils.db.Database.get_alternative_data', return_value=None):
        capacity_results = CapacityAgent.calculate_demonstrated_capacity(
            "BOR-001", "LOW", 15000, external_transactions=transactions
        )
        
        # Audit requirement: Should flag as insufficient observation
        assert capacity_results["insufficient_observation"] is True
        
        # Risk Agent should flag it
        risk_results = RiskAgent.evaluate(
            MagicMock(loan_amount_requested=15000, monthly_income=50000, monthly_expenses=10000, existing_debt=0), 
            external_behavioral_results={"transactions": transactions}
        )
        assert any("INSUFFICIENT_OBSERVATION_WINDOW" in f for f in risk_results["flags"])
        
        # Decision Agent should set to WAIT
        decision_results = DecisionAgent.recommend(risk_results, MagicMock(loan_amount_requested=15000), 30)
        assert decision_results["decision"] == Decision.REFER

def test_scenario_c_force_high_risk_reject():
    """Scenario C: Force HIGH RISK -> Verify decision is REJECT through Consistency Guard."""
    risk_results = {
        "risk_level": "HIGH",
        "risk_score": 0.85,
        "flags": ["CRITICAL: HIGH_DTI"],
        "metrics": {"capacity_based_max": 2000, "observed_deposit_volume": 1000},
        "capacity_validation": {
            "capacity_based_max": 2000, 
            "observed_deposit_volume": 1000,
            "starter_loan_applied": False,
            "insufficient_observation": False
        }
    }
    borrower = MagicMock(loan_amount_requested=5000)
    
    # Even if rules somehow approved it, the Consistency Guard must override to REJECT
    decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
    assert decision_results["decision"] == Decision.REJECT

def test_scenario_d_role_based_filtering():
    """Scenario D: Verify audit_view is missing for Borrowers, present for Compliance."""
    assessment = Assessment(
        assessment_id="ASMT-ROLE-TEST",
        borrower_id="BOR-TEST",
        decision=Decision.APPROVE,
        requested_amount=1000,
        requested_duration_days=30,
        recommended_amount=1000,
        recommended_duration_days=30,
        decision_timestamp=datetime.now(timezone.utc),
        audit_view="SENSITIVE_AUDIT_DATA",
        officer_view="TECHNICAL_OFFICER_DATA",
        customer_view="FRIENDLY_CUSTOMER_DATA",
        customer_message={"summary": "Approved!"},
        capacity_based_max=2000.0
    )
    
    # 1. Filter for BORROWER (or generic portal user)
    borrower_view = filter_assessment_for_role(assessment, "BORROWER")
    assert "audit_view" not in borrower_view
    assert "officer_view" not in borrower_view
    assert "customer_view" in borrower_view
    assert borrower_view["customer_view"] == "FRIENDLY_CUSTOMER_DATA"
    
    # 2. Filter for OFFICER
    officer_view = filter_assessment_for_role(assessment, "OFFICER")
    assert "audit_view" not in officer_view
    assert "officer_view" in officer_view
    assert "risk_level" in officer_view
    
    # 3. Filter for COMPLIANCE (Admins)
    compliance_view = filter_assessment_for_role(assessment, "COMPLIANCE")
    assert "audit_view" in compliance_view
    assert "officer_view" in compliance_view
    assert compliance_view["audit_view"] == "SENSITIVE_AUDIT_DATA"

def test_scenario_e_no_history_reject():
    """Scenario E: No transaction history -> Result: REJECT."""
    with patch('utils.db.Database.get_alternative_data', return_value=None):
        capacity_results = CapacityAgent.calculate_demonstrated_capacity(
            "BOR-EMPTY", "LOW", 5000, external_transactions=[]
        )
        assert capacity_results["is_valid"] is False
        assert "No transaction history" in capacity_results["rejection_reason"]
