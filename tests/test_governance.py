import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from models.assessment import Assessment, RiskLevel, Decision

def test_governance_reject_completeness():
    """
    Test A: REJECT decision must have all mandatory governance fields.
    """
    assessment = Assessment(
        borrower_id="BOR-TEST-REJECT",
        risk_score=0.9,
        risk_level=RiskLevel.HIGH,
        decision=Decision.REJECT,
        requested_amount=5000.0,
        requested_duration_days=30,
        decision_timestamp=datetime.utcnow(),
        recommended_amount=0.0,
        decision_reason_codes=["HIGH_RISK_SCORE", "INSUFFICIENT_AFFORDABILITY"],
        blocking_factors=["Estimated inability to repay"],
        data_used={
            "transaction_days": 30,
            "transaction_count": 50,
            "data_sources": ["MPESA"],
            "data_recency_days": 0
        }
    )
    
    # All mandatory assertions
    assert assessment.decision == Decision.REJECT
    assert assessment.recommended_amount == 0.0
    assert assessment.requested_amount == 5000.0
    assert len(assessment.decision_reason_codes) > 0
    assert "HIGH_RISK_SCORE" in assessment.decision_reason_codes
    assert assessment.decision_timestamp <= datetime.utcnow()
    assert assessment.data_used is not None
    assert assessment.data_used["transaction_count"] == 50
    # Flags should NOT contain semantic error markers
    assert not any("DECISION_NARRATIVE_MISMATCH" in f for f in assessment.flags)

def test_governance_approve_completeness():
    """
    Test B: APPROVE decision must have positive recommended amount and timestamp.
    """
    assessment = Assessment(
        borrower_id="BOR-TEST-APPROVE",
        risk_score=0.1,
        risk_level=RiskLevel.LOW,
        decision=Decision.APPROVE,
        requested_amount=1000.0,
        requested_duration_days=30,
        recommended_amount=1000.0,
        recommended_duration_days=30,
        decision_timestamp=datetime.utcnow(),
        capacity_based_max=1200.0,
        policy_cap_amount=1500.0,
        decision_reason_codes=["STRONG_CAPACITY"],
        data_used={"transaction_days": 180, "transaction_count": 200, "data_sources": ["INTERNAL"], "data_recency_days": 0}
    )
    
    assert assessment.decision == Decision.APPROVE
    assert assessment.recommended_amount > 0
    assert assessment.decision_timestamp is not None
    assert assessment.data_used["transaction_days"] == 180

def test_governance_fail_fast_missing_requested_amount():
    """
    Test C1: Missing requested_amount defaults to 0.0 for legacy compatibility.
    """
    assessment = Assessment(
        borrower_id="BOR-FAIL",
        decision=Decision.REJECT,
        decision_timestamp=datetime.utcnow(),
        recommended_amount=0.0,
        decision_reason_codes=["BAD_SCORE"]
        # requested_amount MISSING
    )
    assert assessment.requested_amount == 0.0

def test_governance_fail_fast_missing_timestamp():
    """
    Test C2: Missing decision_timestamp defaults to now for legacy compatibility.
    """
    assessment = Assessment(
        borrower_id="BOR-FAIL-2",
        decision=Decision.REJECT,
        requested_amount=5000.0,
        recommended_amount=0.0,
        decision_reason_codes=["BAD_SCORE"]
        # decision_timestamp MISSING
    )
    assert assessment.decision_timestamp is not None

def test_governance_fail_fast_reject_without_reason_codes():
    """
    Test C3: REJECT without reason codes OR blocking factors raises error.
    """
    with pytest.raises(ValueError, match="INVARIANT: REJECT must have reason codes or blocking flags"):
        Assessment(
            borrower_id="BOR-FAIL-3",
            decision=Decision.REJECT,
            requested_amount=5000.0,
            requested_duration_days=30,
            decision_timestamp=datetime.utcnow(),
            recommended_amount=0.0,
            policy_version="v1.5.0",
            decision_reason_codes=[],  # Empty
            blocking_factors=[]        # Also empty
        )

def test_governance_fail_fast_invariants():
    """
    Test D: Verify logical invariants (e.g. Approve with > Capacity, Reject with positive amount).
    """
    # Case: Approve amount > Capacity
    with pytest.raises(ValueError, match="CONTRACT VIOLATION"):
        Assessment(
            borrower_id="BOR-INV-1",
            decision=Decision.APPROVE,
            requested_amount=1000.0,
            requested_duration_days=30,
            recommended_amount=2000.0,  # Exceeds capacity
            recommended_duration_days=30,
            capacity_based_max=1000.0,
            decision_timestamp=datetime.utcnow(),
            decision_reason_codes=["OK"]
        )

    # Case: Reject with positive amount
    with pytest.raises(ValueError, match="INVARIANT: REJECT"):
        Assessment(
            borrower_id="BOR-INV-2",
            decision=Decision.REJECT,
            requested_amount=1000.0,
            requested_duration_days=30,
            recommended_amount=100.0,  # Invalid for REJECT
            recommended_duration_days=None,
            decision_timestamp=datetime.utcnow(),
            decision_reason_codes=["BAD"]
        )

