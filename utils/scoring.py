import logging
logger = logging.getLogger(__name__)
"""
Scoring Utility
Computes a normalized risk score (0-1).
0 = Perfect (Low Risk), 1 = Critical (High Risk).
"""

from models.borrower import Borrower
from typing import List
from utils.policy_context import policy_value

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
    low_max = float(policy_value("risk_low_max", 0.3))
    med_max = float(policy_value("risk_medium_max", 0.6))
    if score < low_max:
        return "LOW"
    elif score < med_max:
        return "MEDIUM"
    else:
        return "HIGH"

def validate_decision_consistency(risk_score: float, risk_level: str, decision: str, flags: List[str] = None) -> str:
    """
    Senior Risk-Audit Guard:
    Enforces logical alignment between risk assessment and final decision.
    Prevents unsafe approvals and non-rational rejections.
    """
    normalized_decision = decision.upper()
    normalized_risk = risk_level.upper()
    
    # 1. SAFETY GATE: HIGH RISK -> MUST BE REJECT OR WAIT
    if normalized_risk == "HIGH" and normalized_decision not in ["REJECT", "WAIT"]:
        # Log consistency failure for audit trail
        logger.error(f"CRITICAL CONSISTENCY FAILURE: Attempted {normalized_decision} for HIGH risk ({risk_score}). Force REJECT.")
        return "REJECT" # Safe Fallback
    
    # 2. RATIONALITY GATE: LOW RISK -> NOT REJECT WITHOUT CAUSE
    if normalized_risk == "LOW" and normalized_decision == "REJECT":
        has_critical_flag = any("CRITICAL" in f.upper() for f in (flags or []))
        if not has_critical_flag:
             logger.error(f"CONSISTENCY WARNING: LOW risk ({risk_score}) rejected without critical flags. Moving to WAIT.")
             return "WAIT" # Fallback to human review
             
    # 3. POLICY GATE: MEDIUM RISK -> NO PURE APPROVAL
    if normalized_risk == "MEDIUM" and normalized_decision == "APPROVE":
        logger.info(f"CONSISTENCY ENFORCEMENT: MEDIUM risk upgraded to CONDITIONAL.")
        return "CONDITIONAL"
        
    # 4. WAIT LOGIC VALIDATION
    if normalized_decision == "WAIT":
        # Confirm there is a data-related reason for WAIT
        data_reasons = ["OBSERVATION", "CONFIDENCE", "INSUFFICIENT", "HISTORY", "UPLOAD"]
        is_justified = any(any(reason in f.upper() for reason in data_reasons) for f in (flags or []))
        if not is_justified:
             # If we are waiting but don't know why, it's logically inconsistent
             logger.warning("CONSISTENCY WARNING: Decision is WAIT but no data-confidence flags detected.")
             
    return normalized_decision