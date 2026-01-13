"""
Decision Agent - Loan Recommendation Engine
============================================

This agent translates risk assessment into actionable loan decisions.

DECISION TYPES:
1. APPROVE: Low risk, meets all criteria
2. CONDITIONAL: Medium risk, requires adjusted terms
3. REJECT: High risk or critical policy violations

All decisions are deterministic given the same risk inputs.
"""

from models.assessment import Decision
from models.borrower import Borrower
import config

class DecisionAgent:
    """
    Agent responsible for recommending final loan decisions.
    
    Combines risk evaluation with business policy to determine:
    - Approval status (APPROVE/CONDITIONAL/REJECT)
    - Recommended loan amount
    - Interest rate
    
    WHY THIS AGENT EXISTS:
    - Separates risk assessment from business decisions
    - Allows policy changes without touching risk logic
    - Provides clear decision rules for audit trail
    """
    
    @staticmethod
    def recommend(risk_data: dict, borrower: Borrower) -> dict:
        """
        Determines the loan recommendation and terms.
        
        DECISION LOGIC:
        1. Check for critical flags → REJECT
        2. Check for warnings or medium risk → CONDITIONAL
        3. Check for caution flags → CONDITIONAL with slight rate increase
        4. Otherwise → APPROVE
        
        TERM ADJUSTMENTS:
        - Interest rates vary by risk level (config-driven)
        - Loan amounts reduced for medium-risk borrowers (haircut)
        - High-risk borrowers get zero amount (rejection)
        
        Args:
            risk_data: Output from RiskAgent.evaluate()
            borrower: Borrower profile with loan request
            
        Returns:
            Dictionary containing:
            - decision: APPROVE/CONDITIONAL/REJECT
            - recommended_amount: Loan amount (may be reduced)
            - recommended_interest_rate: APR based on risk
        """
        risk_level = risk_data["risk_level"]
        flags = risk_data["flags"]
        risk_score = risk_data["risk_score"]
        
        # Start with optimistic defaults
        # WHY: Innocent until proven risky (but rules will override)
        decision = Decision.APPROVE
        recommended_amount = borrower.loan_amount_requested
        interest_rate = config.BASE_INTEREST_RATE
        
        # ====================================================================
        # DECISION RULE 1: HARD REJECTION
        # ====================================================================
        # WHY: Critical flags indicate fundamental inability to repay
        # EXAMPLES: Income too low, DTI too high, negative cash flow
        
        if any("CRITICAL" in f.upper() for f in flags) or risk_level == "HIGH":
            decision = Decision.REJECT
            recommended_amount = 0
            interest_rate = 0
            
            # Log rejection reason for audit trail
            critical_flags = [f for f in flags if "CRITICAL" in f.upper()]
            print(f"DEBUG: Rejecting borrower {borrower.id} due to: {critical_flags}")
        
        # ====================================================================
        # DECISION RULE 2: CONDITIONAL APPROVAL (WARNINGS)
        # ====================================================================
        # WHY: Warnings indicate manageable risk with adjusted terms
        # STRATEGY: Reduce exposure (lower amount) and increase pricing (higher rate)
        
        elif any("WARNING" in f.upper() for f in flags) or risk_level == "MEDIUM":
            decision = Decision.CONDITIONAL
            
            # Apply haircut to requested amount
            # WHY: Reduces lender exposure for medium-risk borrowers
            recommended_amount = borrower.loan_amount_requested * config.CONDITIONAL_AMOUNT_MULTIPLIER
            
            # Increase interest rate for risk premium
            # WHY: Compensates lender for elevated default probability
            interest_rate = config.CONDITIONAL_INTEREST_RATE
            
            print(f"DEBUG: Conditional approval for {borrower.id}: "
                  f"${recommended_amount:.0f} at {interest_rate}% (reduced from ${borrower.loan_amount_requested:.0f})")
            
        # ====================================================================
        # DECISION RULE 3: CONDITIONAL APPROVAL (BEHAVIORAL CAUTIONS)
        # ====================================================================
        # WHY: Behavioral flags are softer signals than financial red flags
        # STRATEGY: Slight rate increase but no amount reduction
        
        elif any("CAUTION" in f.upper() for f in flags):
            decision = Decision.CONDITIONAL
            
            # Keep requested amount (behavioral concerns don't warrant haircut)
            recommended_amount = borrower.loan_amount_requested
            
            # Slight rate increase for behavioral risk
            # WHY: Between base and conditional rates
            interest_rate = config.CAUTION_INTEREST_RATE
            
            print(f"DEBUG: Conditional approval for {borrower.id}: "
                  f"${recommended_amount:.0f} at {interest_rate}% (behavioral caution)")
        
        # ====================================================================
        # DECISION RULE 4: FULL APPROVAL
        # ====================================================================
        # WHY: No flags, low risk → approve as requested
        # This is the "happy path" for strong borrowers
        
        else:
            decision = Decision.APPROVE
            recommended_amount = borrower.loan_amount_requested
            interest_rate = config.BASE_INTEREST_RATE
            
            print(f"DEBUG: Approving {borrower.id}: "
                  f"${recommended_amount:.0f} at {interest_rate}%")
        
        return {
            "decision": decision,
            "recommended_amount": round(recommended_amount, 2),
            "recommended_interest_rate": interest_rate
        }

