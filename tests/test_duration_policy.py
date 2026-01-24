"""
Test cases for loan duration (tenor) policy enforcement.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from models.assessment import Decision, Assessment
from agents.decision_agent import DecisionAgent
from models.borrower import Borrower
import lending_config.capacity_config as cap_config

@pytest.fixture
def mock_borrower():
    return MagicMock(spec=Borrower, id="BOR-1234", loan_amount_requested=1000)

@pytest.fixture
def clean_risk_data():
    return {
        "risk_level": "LOW",
        "flags": [],
        "risk_score": 0.1,
        "capacity_validation": {
            "capacity_based_max": 5000,
            "starter_loan_applied": False,
            "observed_deposit_volume": 2000,
            "audit_trail": {}
        }
    }

@pytest.fixture
def starter_risk_data():
    return {
        "risk_level": "LOW",
        "flags": ["STARTER_LOAN_APPROVED_LIMITED_HISTORY"],
        "risk_score": 0.2,
        "capacity_validation": {
            "capacity_based_max": 1000,
            "starter_loan_applied": True,
            "observed_deposit_volume": 500,
            "audit_trail": {}
        }
    }

def test_approve_duration_unchanged(mock_borrower, clean_risk_data):
    """When requested duration is within policy, it should be approved as-is."""
    requested_days = 30
    result = DecisionAgent.recommend(clean_risk_data, mock_borrower, requested_days)
    
    assert result["decision"] == Decision.APPROVE
    assert result["recommended_duration_days"] == 30
    assert result["recommended_amount"] == 1000

def test_approve_duration_reduced_starter_loan(mock_borrower, starter_risk_data):
    """Starter loans should have duration capped at STARTER_LOAN_MAX_DURATION_DAYS."""
    requested_days = 60
    result = DecisionAgent.recommend(starter_risk_data, mock_borrower, requested_days)
    
    assert result["decision"] == Decision.APPROVE
    assert result["recommended_duration_days"] == cap_config.STARTER_LOAN_MAX_DURATION_DAYS # Should be 30
    assert any(a["type"] == "DURATION_ADJUSTED_STARTER_POLICY" for a in result["decision_metadata"]["adjustments_applied"])

def test_reject_duration_below_minimum(mock_borrower, clean_risk_data):
    """Requests below MIN_DURATION_DAYS should be rejected."""
    requested_days = 3 # Below 7
    result = DecisionAgent.recommend(clean_risk_data, mock_borrower, requested_days)
    
    assert result["decision"] == Decision.REJECT
    assert "DURATION_POLICY_VIOLATION" in result["decision_metadata"]["blocking_factors"]

def test_interest_rate_basis_math(mock_borrower, starter_risk_data):
    """Final rate must equal base_rate + sum(adjustments)."""
    requested_days = 30
    result = DecisionAgent.recommend(starter_risk_data, mock_borrower, requested_days)
    
    basis = result["interest_rate_basis"]
    assert basis is not None
    
    expected_final = basis["base_rate"] + sum(a["value"] for a in basis["adjustments"])
    assert abs(expected_final - basis["final_rate"]) < 0.01

def test_duration_discount_premium(mock_borrower, clean_risk_data):
    """Verify short tenor discount and long tenor premium."""
    # Short tenor discount
    res_short = DecisionAgent.recommend(clean_risk_data, mock_borrower, 15)
    basis_short = res_short["interest_rate_basis"]
    assert any(a["type"] == "SHORT_TENOR_DISCOUNT" for a in basis_short["adjustments"])
    
    # Long tenor premium
    res_long = DecisionAgent.recommend(clean_risk_data, mock_borrower, 200)
    basis_long = res_long["interest_rate_basis"]
    assert any(a["type"] == "LONG_TENOR_PREMIUM" for a in basis_long["adjustments"])

def test_assessment_model_validation():
    """Verify Assessment model enforces duration invariants."""
    # 1. Valid Approval
    asmt = Assessment(
        borrower_id="BOR-1",
        requested_amount=1000,
        requested_duration_days=30,
        decision=Decision.APPROVE,
        recommended_amount=1000,
        recommended_duration_days=30,
        recommended_interest_rate=15.0,
        decision_timestamp=datetime.now()
    )
    assert asmt.recommended_duration_days == 30
    
    # 2. Invalid Approval (Missing Duration)
    with pytest.raises(ValueError, match="APPROVE must have recommended_duration_days > 0"):
        Assessment(
            borrower_id="BOR-1",
            requested_amount=1000,
            requested_duration_days=30,
            decision=Decision.APPROVE,
            recommended_amount=1000,
            recommended_interest_rate=15.0,
            decision_timestamp=datetime.now()
        )

    # 3. Invalid Reject (With Duration)
    with pytest.raises(ValueError, match="REJECT must have recommended_duration_days = None"):
        Assessment(
            borrower_id="BOR-1",
            requested_amount=1000,
            requested_duration_days=30,
            decision=Decision.REJECT,
            recommended_amount=0,
            recommended_duration_days=30,
            recommended_interest_rate=0.0,
            decision_timestamp=datetime.now()
        )
