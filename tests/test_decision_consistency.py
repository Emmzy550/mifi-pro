import pytest
from models.assessment import Assessment, Decision, RiskLevel

def test_approve_invariant():
    """Test 1: APPROVE decision must have positive amount and no blocking factors"""
    # 1. Valid Approval
    a = Assessment(
        decision=Decision.APPROVE,
        recommended_amount=1000.0,
        blocking_factors=[],
        risk_level=RiskLevel.LOW,
        risk_score=0.1,
        capacity_based_max=2000.0,
        decision_summary="Application approved based on policy compliance."
    )
    assert a.recommended_amount > 0
    assert a.blocking_factors == []
    assert "approved based on policy compliance" in a.decision_summary

    # 2. Invalid Approval (Zero Amount)
    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
        Assessment(
            decision=Decision.APPROVE,
            recommended_amount=0.0,
            blocking_factors=[]
        )

    # 3. Invalid Approval (Blocking Factors)
    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
        Assessment(
            decision=Decision.APPROVE,
            recommended_amount=1000.0,
            capacity_based_max=2000.0,
            blocking_factors=["SOME_BLOCK"]
        )

def test_reject_invariant():
    """Test 2: REJECT decision must have zero amount and blocking factors"""
    # 1. Valid Reject
    a = Assessment(
        decision=Decision.REJECT,
        recommended_amount=0.0,
        blocking_factors=["HIGH_RISK"],
        risk_level=RiskLevel.HIGH
    )
    assert a.recommended_amount == 0
    assert len(a.blocking_factors) > 0

    # 2. Invalid Reject (Positive Amount)
    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
        Assessment(
            decision=Decision.REJECT,
            recommended_amount=100.0,
            blocking_factors=["HIGH_RISK"]
        )
        
    # 3. Invalid Reject (No Blocking Factors)
    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
        Assessment(
            decision=Decision.REJECT,
            recommended_amount=0.0,
            blocking_factors=[]
        )

def test_refer_invariant():
    """Test 3: REFER decision must have no amount"""
    # 1. Valid Refer (None amount)
    a = Assessment(
        decision=Decision.REFER,
        recommended_amount=None,
        blocking_factors=["INSUFFICIENT_DATA"]
    )
    assert a.recommended_amount is None

    # 2. Invalid Refer (Has Amount)
    with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
        Assessment(
            decision=Decision.REFER,
            recommended_amount=100.0,
            blocking_factors=["INSUFFICIENT_DATA"]
        )
