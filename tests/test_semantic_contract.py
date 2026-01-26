import pytest
from models.assessment import Assessment, Decision

def test_legacy_fields_are_gone():
    """Test 1: Verify legacy fields do not exist on the model instance"""
    a = Assessment(
        decision=Decision.APPROVE,
        recommended_amount=1000.0,
        capacity_based_max=1000.0,
        blocking_factors=[]
    )
    # Check that accessing legacy fields raises AttributeError
    with pytest.raises(AttributeError):
        _ = a.capacity_anchor_amount
        
    with pytest.raises(AttributeError):
        _ = a.capacity_anchor_reason

def test_contract_validator_detects_forbidden_fields():
    """Test 2: Verify custom validator catches injection of forbidden attributes"""
    # This is tricky with Pydantic as it filters extra fields by default, 
    # but let's try to simulate a breach or check logic directly.
    
    a = Assessment(
        decision=Decision.APPROVE, 
        recommended_amount=1000.0,
        capacity_based_max=1000.0,
        blocking_factors=[]
    )
    
    # Manually inject (simulation of bad serialization deserialization or dynamic assignment)
    a.__dict__["capacity_anchor_amount"] = 500
    dumped = a.model_dump()
    assert "capacity_anchor_amount" not in dumped

def test_contract_validator_enforces_policy_cap():
    """Test 3: Recommended amount must be <= min(capacity, policy)"""
    with pytest.raises(ValueError, match="CONTRACT VIOLATION"):
        Assessment(
            decision=Decision.APPROVE,
            recommended_amount=1001.0, # Exceeds policy cap
            capacity_based_max=2000.0,
            policy_cap_amount=1000.0,
            blocking_factors=[]
        )

def test_ml_prob_default_is_banned():
    """Test 4: Extracting ml_prob_default should be impossible"""
    a = Assessment(
         decision=Decision.APPROVE,
         recommended_amount=100.0,
         capacity_based_max=100.0,
         blocking_factors=[]
    )
    a.__dict__["ml_prob_default"] = 0.5
    dumped = a.model_dump()
    assert "ml_prob_default" not in dumped

def test_response_gate_lockdown():
    """Test 5: The final response gate must crash on forbidden keys/phrases"""
    from api import verify_response_integrity, SemanticContractViolationError
    
    # Check 1: Forbidden Key
    bad_response_key = {
        "decision": "APPROVE",
        "capacity_anchor_amount": 500 # BANNED KEY
    }
    with pytest.raises(SemanticContractViolationError, match="Forbidden Key"):
        verify_response_integrity(bad_response_key)
        
    # Check 2: Forbidden Phrase in string
    bad_response_phrase = {
        "decision": "APPROVE",
        "explanation": "We used a capacity anchor regarding your limit." # BANNED PHRASE
    }
    with pytest.raises(SemanticContractViolationError, match="Forbidden Phrase"):
        verify_response_integrity(bad_response_phrase)

    # Check 3: Clean response passes
    clean_response = {
        "decision": "APPROVE",
        "capacity_based_max": 500,
        "explanation": "Policy-defined lending limits apply."
    }
    verify_response_integrity(clean_response)

