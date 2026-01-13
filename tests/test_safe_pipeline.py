
import unittest
from datetime import datetime
from utils.transaction_parser import TransactionParser, Transaction
from agents.behavioral_agent_v2 import BehavioralAgentV2
from agents.risk_agent import RiskAgent
from agents.explanation_agent import ExplanationAgent
from models.borrower import Borrower
import config

class TestSafePipeline(unittest.TestCase):
    
    def setUp(self):
        self.parser = TransactionParser()
        self.borrower = Borrower(
            id="TEST-BOR-001",
            name="Test User",
            monthly_income=5000,
            monthly_expenses=2000,
            loan_amount_requested=1000,
            employment_type="salaried",
            loan_purpose="business",
            phone="1234567890"
        )
        
    def test_csv_parsing(self):
        """Test parsing of a simple CSV"""
        csv_content = b"Date,Amount,Description\n2025-01-01,5000,Salary\n2025-01-05,-200,Food"
        txs = self.parser.parse(csv_content, "test.csv")
        
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0].amount, 5000)
        self.assertEqual(txs[0].source_type, "USER_UPLOADED")
        self.assertEqual(txs[0].confidence_weight, 0.6)
        
    def test_behavioral_analysis_impact_cap(self):
        """Verify that uploaded data impact on risk score is capped"""
        # Create transactions that would trigger MANY warnings
        txs = []
        for i in range(10):
            # Create a spending spike pattern
            txs.append(Transaction(
                transaction_id=str(i),
                date=datetime.now(),
                amount=10000, # Huge outflow
                direction="OUTFLOW",
                description="Spike",
                source_type="USER_UPLOADED",
                confidence_weight=0.6
            ))
            
        # Analyze
        results = BehavioralAgentV2.analyze_transactions(txs)
        # Force some warnings manually if analyze logic is strict
        results["early_warnings"] = ["WARNING_1", "WARNING_2", "WARNING_3", "WARNING_4", "WARNING_5"]
        
        # Evaluate Risk with external results
        risk_result = RiskAgent.evaluate(self.borrower, external_behavioral_results=results)
        
        # Check logic: 5 warnings * 0.1 penalty = 0.5 penalty
        # But CAP is 0.2
        # So score should increase by MAX 0.2 from baseline
        
        # Baseline score (rule only for this borrower)
        # Income=5000, Exp=2000 => Affordable. DTI=0.
        # Should be low risk base.
        base_result = RiskAgent.evaluate(self.borrower)
        base_score = base_result["rule_based_score"]
        
        final_score = risk_result["risk_score"]
        
        penalty_applied = final_score - base_score
        
        print(f"Base Score: {base_score}, Final Score: {final_score}, Penalty: {penalty_applied}")
        
        # Allow small float error
        self.assertLessEqual(penalty_applied, config.MAX_BEHAVIORAL_IMPACT_CAP + 0.01)
        
    def test_explanation_transparency(self):
        """Verify explanation clearly states data source"""
        risk_result = {
            "risk_score": 0.5,
            "risk_level": "MEDIUM",
            "flags": [],
            "metrics": {},
            "data_source": "USER_UPLOADED_STATEMENT"
        }
        decision_result = {
            "decision": "CONDITIONAL",
            "recommended_amount": 500,
            "recommended_interest_rate": 20.0
        }
        
        explanation = ExplanationAgent.generate(risk_result, decision_result, self.borrower)
        
        self.assertIn("Data Source: User-provided transaction statement", explanation)
        self.assertIn("subject to verification", explanation)

if __name__ == '__main__':
    unittest.main()
