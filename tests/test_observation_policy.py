import sys
import os
from datetime import datetime, timedelta

# Add path to import agents
sys.path.append(os.getcwd())

from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from agents.behavioral_agent_v2 import BehavioralAgentV2
from models.borrower import Borrower, EmploymentType
from models.assessment import Decision
from utils.transaction_parser import Transaction

def create_mock_transactions(count, days):
    txs = []
    base_date = datetime.now()
    # To get exactly X days window, we need base_date and base_date - X days
    for i in range(count):
        # Scale dates to fit within 'days'
        offset = (i / (count - 1)) * days if count > 1 else 0
        date = base_date - timedelta(days=offset)
        txs.append(Transaction(
            transaction_id=f"TX-{i}",
            date=date,
            amount=1000.0,
            direction="INFLOW",
            type="DEPOSIT",
            description="Salary",
            source_type="USER_UPLOADED",
            confidence_weight=0.9
        ))
    return txs

def create_mock_borrower():
    return Borrower(
        id="BOR-TEST",
        name="John Doe",
        phone="+254700000000",
        employment_type=EmploymentType.SALARIED,
        monthly_income=5000.0,
        monthly_expenses=2000.0,
        loan_amount_requested=2000.0,
        loan_purpose="Emergency"
    )

def test_policy():
    borrower = create_mock_borrower()
    
    print("\n=== TEST 1: SHORT HISTORY (5 DAYS) ===")
    short_txs = create_mock_transactions(10, 5)
    behavioral_results = BehavioralAgentV2.analyze_transactions(short_txs)
    
    risk_results = RiskAgent.evaluate(borrower, external_behavioral_results=behavioral_results)
    decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
    explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)
    
    print(f"Risk Level: {risk_results['risk_level']}")
    print(f"Decision: {decision_results['decision']}")
    print(f"Behavioral Status: {risk_results['metrics'].get('behavioral_status')}")
    print(f"Customer Message: {explanation['customer_message']['summary']}")
    print(f"Policy Justification: {explanation['internal_notes']['policy_context']}")
    
    # Assertions for Policy Upgrade (FINAL POLISH)
    assert risk_results['risk_level'] == "MEDIUM"
    assert decision_results['decision'] == Decision.REFER
    assert risk_results['metrics'].get('behavioral_status') == "INSUFFICIENT_DATA"
    assert "verified your income" in explanation['customer_message']['summary']
    assert "5 days" in explanation['internal_notes']['policy_context']
    
    print("\n=== TEST 2: NO HISTORY (0 TX) ===")
    no_txs = []
    behavioral_results_no = BehavioralAgentV2.analyze_transactions(no_txs)
    risk_results_no = RiskAgent.evaluate(borrower, external_behavioral_results=behavioral_results_no)
    decision_results_no = DecisionAgent.recommend(risk_results_no, borrower, 30)
    
    print(f"Risk Level: {risk_results_no['risk_level']}")
    print(f"Decision: {decision_results_no['decision']}")
    
    assert risk_results_no['risk_level'] == "HIGH"
    assert decision_results_no['decision'] == Decision.REJECT

    print("\n=== TEST 3: FULL HISTORY (40 DAYS) ===")
    full_txs = create_mock_transactions(40, 40)
    behavioral_results_full = BehavioralAgentV2.analyze_transactions(full_txs)
    risk_results_full = RiskAgent.evaluate(borrower, external_behavioral_results=behavioral_results_full)
    decision_results_full = DecisionAgent.recommend(risk_results_full, borrower, 30)
    
    print(f"Risk Level: {risk_results_full['risk_level']}")
    print(f"Decision: {decision_results_full['decision']}")
    print(f"Behavioral Status: {risk_results_full['metrics'].get('behavioral_status')}")
    
    assert risk_results_full['risk_level'] != "HIGH"
    assert decision_results_full['decision'] == Decision.APPROVE
    assert risk_results_full['metrics'].get('behavioral_status') == "ANALYSIS_COMPLETE"
    
    print("\n✅ ALL TESTS PASSED")

if __name__ == "__main__":
    test_policy()
