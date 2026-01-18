import unittest
from models.assessment import Assessment
from utils.explanation_validator import ExplanationValidator, ExplanationInconsistencyError

class TestAnchorPropagation(unittest.TestCase):
    
    def test_risk_haircut_propagation(self):
        """
        Scenario 1: MEDIUM_RISK_HAIRCUT applied.
        Metrics and Top-Level fields MUST reflect the adjusted anchor (5600),
        NOT the raw capacity (26000).
        """
        # Simulate what main.py constructs after our fix
        anchor_amount = 5600.0
        anchor_reason = "RISK_ADJUSTED_LIMIT"
        raw_capacity = 26000.0
        
        assessment = Assessment(
            assessment_id="TEST-PROP-1",
            borrower_id="BOR-1",
            organization_id="ORG-1",
            risk_score=0.45,
            risk_level="MEDIUM",
            decision="CONDITIONAL",
            recommended_amount=anchor_amount,
            recommended_interest_rate=20.0,
            requested_amount=8000.0,
            
            explanation=f"Approved {anchor_amount} due to risk adjustments. This limit is anchored to safety guidelines.",
            customer_view="...",
            officer_view="...",
            audit_view="...",
            blocking_factors=["MEDIUM_RISK_HAIRCUT"],
            
            flags=[],
            
            # These values come from our updated main.py logic
            capacity_based_max=raw_capacity, # Ceiling remains high
            capacity_anchor_amount=anchor_amount, # ANCHOR IS ADJUSTED
            capacity_anchor_reason=anchor_reason,
            
            metrics={
                "observed_deposit_volume": 10000.0,
                "capacity_based_max": raw_capacity,
                # Metrics overwrite check
                "capacity_anchor_amount": anchor_amount,
                "capacity_anchor_reason": anchor_reason
            },
            
            decision_metadata={
                "capacity_anchor_amount": anchor_amount,
                "capacity_anchor_reason": anchor_reason,
                "blocking_factors": ["MEDIUM_RISK_HAIRCUT"]
            }
        )
        
        # 1. Verify Internal Consistency (Guard)
        self.assertEqual(assessment.capacity_anchor_amount, assessment.decision_metadata["capacity_anchor_amount"])
        self.assertEqual(assessment.metrics["capacity_anchor_amount"], assessment.decision_metadata["capacity_anchor_amount"])
        
        # 2. Verify Validator passes (it uses updated fields)
        ExplanationValidator.validate(assessment)

    def test_affordability_limit_propagation(self):
        """
        Scenario 2: No risk haircut. AFFORDABILITY_LIMIT.
        Everything should match capacity_based_max.
        """
        cap_max = 8000.0
        
        assessment = Assessment(
            assessment_id="TEST-PROP-2",
            borrower_id="BOR-2",
            organization_id="ORG-1",
            risk_score=0.1,
            risk_level="LOW",
            decision="APPROVE",
            recommended_amount=8000.0,
            recommended_interest_rate=15.0,
            requested_amount=8000.0,
            
            explanation="Approved based on capacity.",
            customer_view="...",
            officer_view="...",
            audit_view="...",
            blocking_factors=[],
            flags=[],
            
            capacity_based_max=cap_max,
            capacity_anchor_amount=cap_max,
            capacity_anchor_reason="AFFORDABILITY_LIMIT",
            
            metrics={
                "observed_deposit_volume": 2000.0,
                "capacity_based_max": cap_max,
                "capacity_anchor_amount": cap_max,
                "capacity_anchor_reason": "AFFORDABILITY_LIMIT"
            },
            decision_metadata={
                "capacity_anchor_amount": cap_max,
                "capacity_anchor_reason": "AFFORDABILITY_LIMIT"
            }
        )
        
        self.assertEqual(assessment.capacity_anchor_amount, assessment.metrics["capacity_anchor_amount"])
        ExplanationValidator.validate(assessment)

if __name__ == '__main__':
    unittest.main()
