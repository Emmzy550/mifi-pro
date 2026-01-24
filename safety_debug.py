from models.borrower import Borrower
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from utils.db import Database

# Use Mock DB
Database._db = None 

def test_safety_logic():
    print("--- Debugging Safety Logic ---")
    
    # 1. High Debt Borrower (90% DTI)
    borrower = Borrower(
        id="BOR-FAIL",
        name="High Debt",
        phone="+260900000001",
        employment_type="trader",
        monthly_income=1000.0,
        monthly_expenses=200.0,
        existing_debt=900.0, # 90% DTI
        loan_amount_requested=100.0,
        loan_purpose="Emergency"
    )
    
    print("\n[Step 1] Risk Evaluation")
    risk_results = RiskAgent.evaluate(borrower)
    print(f"Risk Score: {risk_results['risk_score']}")
    print(f"Risk Level: {risk_results['risk_level']}")
    print(f"Flags: {risk_results['flags']}")
    
    print("\n[Step 2] Decision Recommendation")
    decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
    print(f"Decision: {decision_results['decision']}")
    print(f"Recommended Amount: {decision_results['recommended_amount']}")

if __name__ == "__main__":
    test_safety_logic()
