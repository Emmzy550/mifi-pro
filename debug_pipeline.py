from models.borrower import Borrower
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from models.alternative_data import AlternativeData
from utils.db import Database
import os

def debug_pipeline():
    print("--- Debugging AI Pipeline ---")
    
    # 1. Setup mock borrower
    borrower = Borrower(
        id="BOR-DEBUG",
        name="Debug User",
        phone="+260900000000",
        employment_type="trader",
        monthly_income=300.0,
        monthly_expenses=150.0,
        existing_debt=0.0,
        loan_amount_requested=500.0,
        loan_purpose="Debug"
    )
    
    # 2. Risk Agent
    print("Running RiskAgent...")
    risk_results = RiskAgent.evaluate(borrower)
    print(f"Risk Results: {risk_results}")
    
    # 3. Decision Agent
    print("Running DecisionAgent...")
    decision_results = DecisionAgent.recommend(risk_results, borrower)
    print(f"Decision Results: {decision_results}")
    
    # 4. Explanation Agent
    print("Running ExplanationAgent...")
    try:
        explanation = ExplanationAgent.generate(risk_results, decision_results)
        print(f"Explanation: {explanation}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pipeline()
