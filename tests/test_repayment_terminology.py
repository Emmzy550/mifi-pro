
import unittest
from models.assessment import Assessment
from utils.explanation_validator import ExplanationValidator, ExplanationInconsistencyError

class TestRepaymentTerminology(unittest.TestCase):
    def test_repayment_is_allowed(self):
        """
        Verifies that 'repayment' is allowed, even though it contains 'pay'.
        """
        assessment = Assessment(
            assessment_id="TEST-TERM-001",
            borrower_id="BOR-TEST",
            decision="APPROVE",
            requested_amount=1000.0,
            recommended_amount=1000.0,
            
            capacity_anchor_amount=1000.0,
            capacity_anchor_reason="POLICY_DEFAULT",
            capacity_based_max=5000.0,
            observed_deposit_volume=5000.0,
            
            # Explanation contains "repayment"
            explanation=(
                "We are pleased to approve your loan. Please ensure timely repayment to build history."
            ),
            
            risk_level="LOW",
            flags=[]
        )
        
        # ACT: Validate
        try:
            ExplanationValidator.validate(assessment)
            print("[PASS] 'repayment' was correctly allowed.")
        except ExplanationInconsistencyError as e:
            self.fail(f"Validation incorrectly flagged 'repayment': {e}")

    def test_pay_is_prohibited(self):
        """
        Verifies that the word 'pay' by itself is still prohibited.
        """
        assessment = Assessment(
            assessment_id="TEST-TERM-002",
            borrower_id="BOR-TEST",
            decision="APPROVE",
            requested_amount=1000.0,
            recommended_amount=1000.0,
            
            capacity_anchor_amount=1000.0,
            capacity_anchor_reason="POLICY_DEFAULT",
            capacity_based_max=5000.0,
            observed_deposit_volume=5000.0,
            
            # Explanation contains "pay"
            explanation=(
                "We determined you have enough pay to afford this loan."
            ),
            
            risk_level="LOW",
            flags=[]
        )
        
        # ACT: Validate
        with self.assertRaises(ExplanationInconsistencyError) as context:
            ExplanationValidator.validate(assessment)
        
        print(f"[PASS] 'pay' was correctly blocked: {context.exception}")

if __name__ == "__main__":
    unittest.main()
