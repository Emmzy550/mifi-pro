"""
Quick test to demonstrate the enhanced ExplanationAgent output.
"""
import sys
sys.path.insert(0, '.')

from agents.explanation_agent import ExplanationAgent

# Sample test case: High-risk borrower
risk_results = {
    "risk_score": 72,
    "risk_level": "HIGH",
    "flags": ["HIGH_DEBT_TO_INCOME", "INSUFFICIENT_INCOME", "MISSED_UTILITY_PAYMENT"],
    "metrics": {
        "ml_prob_default": 0.68,
        "ml_feature_importance": [
            {"feature": "debt_to_income_ratio", "impact": 0.35},
            {"feature": "monthly_income", "impact": -0.22},
            {"feature": "payment_history_score", "impact": 0.18}
        ]
    }
}

decision_results = {
    "decision": "REJECT",
    "recommended_amount": 0,
    "recommended_interest_rate": 0
}

print("=" * 80)
print("ENHANCED EXPLANATION AGENT - TEST OUTPUT")
print("=" * 80)
print("\n")

explanation = ExplanationAgent.generate(risk_results, decision_results)
print(explanation)

print("\n\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
