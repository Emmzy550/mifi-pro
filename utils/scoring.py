"""
Scoring Utility
Computes a normalized risk score (0-1).
0 = Perfect (Low Risk), 1 = Critical (High Risk).
"""

from models.borrower import Borrower
from typing import List

def calculate_risk_score(borrower: Borrower, flags: List[str] = None) -> float:
    """
    Computes a risk score based on financial fundamentals and policy flags.
    Higher values indicate higher risk.
    """
    score = 0.0
    income = borrower.monthly_income
    
    # 1. Debt-to-Income Penalty (Weight: 0.3)
    if income > 0:
        dti = borrower.existing_debt / income
        score += min(dti / 0.5, 1.0) * 0.3
    else:
        score += 0.3
        
    # 2. Expense-to-Income Penalty (Weight: 0.2)
    if income > 0:
        eti = borrower.monthly_expenses / income
        score += min(eti / 0.8, 1.0) * 0.2
    else:
        score += 0.2
        
    # 3. Policy Flag Penalties (Weight: 0.5)
    if flags:
        # Each flag adds risk
        flag_penalty = len(flags) * 0.15
        score += min(flag_penalty, 0.5)
        
    return round(max(0.0, min(1.0, score)), 2)

def derive_risk_level(score: float) -> str:
    """Maps score to categorical level."""
    if score < 0.3:
        return "LOW"
    elif score < 0.7:
        return "MEDIUM"
    else:
        return "HIGH"
