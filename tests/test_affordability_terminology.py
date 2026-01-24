import pytest
from models.assessment import Assessment, Decision, RiskLevel
from utils.explanation_validator import ExplanationValidator, ExplanationSemanticError

def test_correct_affordability_usage():
    """
    Case: Affordability used correctly referring to capacity_based_max.
    """
    a = Assessment(
        decision=Decision.APPROVE,
        recommended_amount=500.0,
        capacity_based_max=1000.0, # Capacity is higher
        policy_cap_amount=500.0,
        policy_cap_reason="STARTER_LIMIT",
        explanation="We approved $500 based on policy limits. Your actual affordability is $1,000 based on deposits.",
        decision_summary="Approved with policy cap.",
        customer_view="Approved $500.",
        officer_view="Policy cap applied.",
        blocking_factors=[]
    )
    # Should pass because 1000 is present
    assert ExplanationValidator.validate(a) is True

def test_incorrect_affordability_misattribution():
    """
    Case: Affordability word used, but only the policy amounts are present.
    Implies they called the policy limit "affordability".
    """
    a = Assessment(
        decision=Decision.APPROVE,
        recommended_amount=500.0,
        capacity_based_max=1000.0,
        policy_cap_amount=500.0,
        # ERROR: Calling the $500 limit "affordability"
        explanation="We approved an affordability capacity of $500.", 
        decision_summary="Approved.",
        customer_view="Approved.",
        officer_view="Notes.",
        blocking_factors=[]
    )
    
    with pytest.raises(ExplanationSemanticError, match="Unsafe Terminology"):
        ExplanationValidator.validate(a)

def test_policy_limit_terminology_success():
    """
    Case: Using correct "Policy Limit" terminology for the capped amount.
    """
    a = Assessment(
        decision=Decision.APPROVE,
        recommended_amount=500.0,
        capacity_based_max=1000.0,
        explanation="We approved a policy-defined lending limit of $500.",
        decision_summary="Approved.",
        customer_view="Approved.",
        officer_view="Approved.",
        blocking_factors=[]
    )
    assert ExplanationValidator.validate(a) is True
