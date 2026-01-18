
import unittest
from datetime import datetime
from models.assessment import Assessment
from utils.explanation_validator import ExplanationValidator, ExplanationInconsistencyError

class TestPolicyConsistency(unittest.TestCase):
    def test_risk_haircut_consistency(self):
        """
        Policy Consistency Test:
        Verifies that an explanation is valid even if it describes a complex
        interaction between deposit capacity and risk haircuts, as long as it
        accurately reflects the final decision.
        """
        # Scenario: 
        # Requested: 50,000
        # Deposit Capacity: 26,000 (referenced in math)
        # Risk Haircut: 5,600 (final anchor)
        # Explanation: Mentions capacity was limited by risk policy to 5,600.
        
        assessment = Assessment(
            assessment_id="TEST-POLICY-001",
            borrower_id="BOR-TEST",
            decision="CONDITIONAL",
            requested_amount=50000.0,
            recommended_amount=5600.0, # Fits risk haircut
            
            # Policy Anchor
            capacity_anchor_amount=5600.0,
            capacity_anchor_reason="RISK_ADJUSTED_LIMIT",
            
            # Underlying Math (ignored by relaxed validator if explanation fits anchor)
            capacity_based_max=26000.0, 
            observed_deposit_volume=90000.0,
            
            # Explanation accurately reflects the final anchor
            explanation=(
                "Based on our risk adjustment policy, your limit has been set to 5,600 "
                "to ensure responsible borrowing, despite higher theoretical capacity."
            ),
            
            risk_level="MEDIUM",
            flags=[]
        )
        
        # ACT: Validate
        try:
            is_valid = ExplanationValidator.validate(assessment)
            self.assertTrue(is_valid)
            print("\n[PASS] Risk haircut explanation passed validation (Policy Safe)")
        except ExplanationInconsistencyError as e:
            self.fail(f"Validation incorrectly flagged policy-consistent explanation: {e}")

    def test_calculation_divergence_allowed(self):
        """
        Verifies that mentioning intermediate numbers (capacity) is allowed
        as long as the final decision is justified.
        """
        assessment = Assessment(
            assessment_id="TEST-POLICY-002",
            borrower_id="BOR-TEST",
            decision="CONDITIONAL",
            requested_amount=10000.0,
            recommended_amount=5600.0,
            
            capacity_anchor_amount=5600.0,
            capacity_anchor_reason="RISK_ADJUSTED_LIMIT",
            
            capacity_based_max=8000.0, # Different from anchor
            observed_deposit_volume=20000.0,
            
            # Explanation mentions the breakdown
            explanation=(
                "While your transaction volume suggests a capacity of 8,000, "
                "our safety policy caps this loan at 5,600."
            ),
            
            risk_level="MEDIUM",
            flags=[]
        )
        
        # ACT: Validate
        try:
            ExplanationValidator.validate(assessment)
            print("[PASS] Explanation with intermediate math context passed validation")
        except ExplanationInconsistencyError as e:
            self.fail(f"Validation incorrectly flagged explanation with context: {e}")

if __name__ == "__main__":
    unittest.main()
