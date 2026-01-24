import unittest
from models.assessment import Assessment, Decision
from utils.explanation_validator import ExplanationValidator, ExplanationInconsistencyError

class TestRiskAdjustedValidation(unittest.TestCase):
    
    def test_risk_haircut_valid(self):
        """
        Scenario 1: Requested 8000, capacity_based_max 26000 (high capacity), 
        but anchor_amount is 5600 due to RISK_ADJUSTED_LIMIT.
        Recommended == Anchor (5600).
        Should PASS validation.
        """
        assessment = Assessment(
            assessment_id="TEST-VALID",
            borrower_id="BOR-1",
            organization_id="ORG-1",
            risk_score=0.45,
            risk_level="MEDIUM",
            decision=Decision.APPROVE,
            recommended_amount=5600.0,
            recommended_interest_rate=20.0,
            requested_amount=8000.0,
            
            explanation="We have approved a reduced amount of $5,600 due to risk profile adjustments. Your capacity is higher but policy-defined lending limits apply.",
            customer_view="We have approved a reduced amount of $5,600 due to risk profile adjustments.",
            officer_view="...",
            audit_view="...",
            blocking_factors=[],
            
            flags=[],
            metrics={},
            decision_metadata={
                "capacity_anchor_reason": "RISK_ADJUSTED_LIMIT",
                "capacity_anchor_amount": 5600.0,
                "blocking_factors": ["MEDIUM_RISK_HAIRCUT"]
            },
            # Top level fields used by validator usually? 
            # Validator uses attributes of assessment.
            capacity_based_max=26000.0,

            observed_deposit_volume=10000.0
        )
        # Should not raise
        ExplanationValidator.validate(assessment)

    def test_request_equals_recommended_risk_haircut(self):
        """
        Scenario 2: Requested equals recommended under risk haircut.
        Requested 5600. Recommended 5600.
        Anchor 5600.
        Should PASS.
        """
        assessment = Assessment(
            assessment_id="TEST-EQUAL",
            borrower_id="BOR-2",
            organization_id="ORG-1",
            risk_score=0.45,
            risk_level="MEDIUM",
            decision=Decision.APPROVE,
            recommended_amount=5600.0,
            recommended_interest_rate=20.0,
            requested_amount=5600.0,
            
            explanation="We have approved the full requested amount of $5,600. Adjusted for risk safety.",
            customer_view="...",
            officer_view="...",
            audit_view="...",
            blocking_factors=[],
            
            flags=[],
            metrics={},
            decision_metadata={
                "capacity_anchor_reason": "RISK_ADJUSTED_LIMIT",
                "capacity_anchor_amount": 5600.0
            },
            capacity_based_max=26000.0,

            observed_deposit_volume=10000.0
        )
        ExplanationValidator.validate(assessment)

    def test_anchor_mismatch_raises_inconsistency(self):
        """
        Scenario 3: Recommended amount does not match the explanation.
        Recommended 6000. Explanation says 5,600.
        Should RAISE ExplanationInconsistencyError.
        """
        assessment = Assessment(
            assessment_id="TEST-INVALID",
            borrower_id="BOR-3",
            organization_id="ORG-1",
            risk_score=0.45,
            risk_level="MEDIUM",
            decision=Decision.APPROVE,
            recommended_amount=6000.0, # Mismatch with anchor 5600
            recommended_interest_rate=20.0,
            requested_amount=8000.0,
            
            # valid keywords provided, so Rule 1 and Rule 2 (keywords) would pass
            explanation="We approved $5,600 which is a reduced limit due to risk factors.",
            customer_view="...",
            officer_view="...",
            audit_view="...",
            blocking_factors=[],
            
            flags=[],
            metrics={},
            decision_metadata={
                "capacity_anchor_reason": "RISK_ADJUSTED_LIMIT",
                "capacity_anchor_amount": 5600.0
            },
            capacity_based_max=26000.0,
            # Validation should check this or decision_metadata? 
            # Usually validator checks assessment attributes.

            observed_deposit_volume=10000.0
        )
        
        with self.assertRaises(ExplanationInconsistencyError):
            ExplanationValidator.validate(assessment)

if __name__ == '__main__':
    unittest.main()
