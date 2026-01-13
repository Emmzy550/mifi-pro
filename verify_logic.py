"""
Verification Script (V1)
Simulates the API logic flow to verify the agent pipeline.
"""
import sys
import os

# Add the current directory to sys.path so we can import internal modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from models.borrower import Borrower, EmploymentType
from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent

def run_test(name: str, raw_data: dict):
    with open("verification_results.txt", "a") as f:
        f.write(f"\n--- Testing Profile: {name} ---\n")
        
        # 1. Intake
        try:
            borrower = IntakeAgent.process(raw_data)
            f.write(f"[OK] Intake processed: {borrower.name}\n")
        except Exception as e:
            f.write(f"[FAIL] Intake error: {e}\n")
            return

        # 2. Risk
        risk_results = RiskAgent.evaluate(borrower)
        f.write(f"[OK] Risk Score: {risk_results['risk_score']} ({risk_results['risk_level']})\n")
        f.write(f"     Flags: {risk_results['flags']}\n")

        # 3. Decision
        decision_results = DecisionAgent.recommend(risk_results, borrower)
        f.write(f"[OK] Decision: {decision_results['decision']}\n")
        f.write(f"     Recommended Amount: {decision_results['recommended_amount']}\n")

        # 4. Explanation
        explanation = ExplanationAgent.generate(risk_results, decision_results)
        f.write(f"[OK] Explanation: {explanation}\n")

# Clear the results file first
with open("verification_results.txt", "w") as f:
    f.write("VERIFICATION RESULTS\n")

# Case 1: Ideal Borrower
run_test("Ideal Borrower", {
    "name": "Jane Stable",
    "phone": "0700111222",
    "employment_type": "salaried",
    "monthly_income": 100000.0,
    "monthly_expenses": 30000.0,
    "existing_debt": 5000.0,
    "loan_amount_requested": 50000.0,
    "loan_purpose": "Home improvement"
})

# Case 2: High Debt (Warning)
run_test("High Debt Borrower", {
    "name": "John Indebted",
    "phone": "0700333444",
    "employment_type": "trader",
    "monthly_income": 50000.0,
    "monthly_expenses": 20000.0,
    "existing_debt": 30000.0, # 60% DTI
    "loan_amount_requested": 10000.0,
    "loan_purpose": "Emergency stock"
})

# Case 3: Low Income (Critical Failure)
run_test("Low Income Borrower", {
    "name": "Mary Struggling",
    "phone": "0700555666",
    "employment_type": "gig",
    "monthly_income": 50.0, # Below threshold
    "monthly_expenses": 60.0,
    "existing_debt": 0.0,
    "loan_amount_requested": 5000.0,
    "loan_purpose": "Personal"
})
