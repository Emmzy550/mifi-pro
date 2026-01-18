import unittest
from models.assessment import Assessment
from utils.explanation_validator import ExplanationValidator, ExplanationInconsistencyError

class TestExplanationConsistency(unittest.TestCase):
    def test_medium_risk_haircut_consistency(self):
        """
        Test that a medium risk haircut (Decision == CONDITIONAL) with an explanation 
        referencing 'risk' or 'adjusted' passes validation, even if 'capacity' isn't mentioned.
        """
        assessment = Assessment(
            assessment_id="TEST-001",
            borrower_id="BOR-001",
            organization_id="ORG-1",
            risk_score=0.45,
            risk_level="MEDIUM",
            decision="CONDITIONAL",
            recommended_amount=5600.0,
            recommended_interest_rate=20.0,
            requested_amount=8000.0,
            
            # Explanation focuses on adjustment/safety, NOT capacity
            explanation="Conditional approval recommended with adjusted terms. We've offered modified terms that align with our safety guidelines.",
            customer_view="We've offered modified terms that align with our safety guidelines.",
            officer_view="Rationale: Adjusted terms.",
            audit_view="...",
            blocking_factors=["MEDIUM_RISK_HAIRCUT"],
            
            flags=[],
            metrics={
                "observed_deposit_volume": 10000.0,
                "transaction_count": 10,
                "dti_ratio": 0.0,
                "capacity_based_max": 10000.0 # High capacity, but reduced due to risk
            },
            capacity_based_max=10000.0,
            capacity_anchor_reason="RISK_ADJUSTED_LIMIT",
            capacity_anchor_amount=5600.0,
            observed_deposit_volume=10000.0,
            transaction_count=10,
            history_days=90,
            
            decision_metadata={
                "capacity_anchor_reason": "RISK_ADJUSTED_LIMIT",
                "blocking_factors": ["MEDIUM_RISK_HAIRCUT"]
            }
        )
        
        # This should PASS without error
        try:
            ExplanationValidator.validate(assessment)
        except ExplanationInconsistencyError as e:
            self.fail(f"Validation failed for valid Medium Risk Haircut: {e}")

if __name__ == '__main__':
    unittest.main()
