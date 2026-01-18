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
        Determines the loan recommendation and terms with CAPACITY ANCHORING.
        
        CRITICAL CHANGE (Bank-Grade):
        All loan amounts are now HARD-CAPPED at capacity_based_max.
        This limit cannot be bypassed by ML, risk scores, or any other factor.
        
        DECISION LOGIC:
        1. Check for critical flags → REJECT
        2. Enforce capacity_based_max (NON-NEGOTIABLE)
        3. Check for starter loan eligibility
        4. Apply risk-based adjustments to interest rates
        5. Validate explanation consistency
        
        Args:
            risk_data: Output from RiskAgent.evaluate()
            borrower: Borrower profile with loan request
            
        Returns:
            Dictionary containing:
            - decision: APPROVE/CONDITIONAL/REJECT
            - recommended_amount: Loan amount (capacity-constrained)
            - recommended_interest_rate: APR based on risk
            - decision_metadata: Audit trail of all decision factors
        """
        import lending_config.capacity_config as cap_config
        
        flag = None
        risk_level = risk_data["risk_level"]
        flags = risk_data["flags"]
        risk_score = risk_data["risk_score"]
        capacity_validation = risk_data["capacity_validation"]
        
        # Extract capacity metrics
        capacity_based_max = capacity_validation["capacity_based_max"]
        starter_loan_applied = capacity_validation["starter_loan_applied"]
        observed_deposit_volume = capacity_validation["observed_deposit_volume"]
        
        # Start with optimistic defaults
        decision = Decision.APPROVE
        recommended_amount = borrower.loan_amount_requested
        interest_rate = config.BASE_INTEREST_RATE
        
        # Track decision metadata for audit trail
        decision_metadata = {
            "requested_amount": borrower.loan_amount_requested,
            "capacity_based_max": capacity_based_max,
            "capacity_anchor_amount": capacity_validation.get("capacity_anchor_amount", 0.0),
            "capacity_anchor_reason": capacity_validation.get("capacity_anchor_reason", "POLICY_DEFAULT"),
            "starter_loan_applied": starter_loan_applied,
            "observed_deposit_volume": observed_deposit_volume,
            "transaction_count": capacity_validation.get("transaction_count", 0),
            "deposit_transaction_count": capacity_validation.get("audit_trail", {}).get("deposit_volume_calculation", {}).get("deposit_count", 0),
            "deposit_source": "MOBILE_MONEY_DEPOSITS_ONLY",
            "observation_window_days": capacity_validation.get("observation_window_days", 30),
            "policy_version": "v1.2.0-human-first",
            "blocking_factors": [],
            "adjustments_applied": []
        }
        
        # ====================================================================
        # RULE 1: HARD REJECTION (Critical Flags or Invalid Capacity)
        # ====================================================================
        if any("CRITICAL" in f.upper() for f in flags) or risk_level == "HIGH" or any("OBSERVATION_WINDOW" in f.upper() for f in flags):
            is_insufficient_window = any("OBSERVATION_WINDOW" in f.upper() for f in flags)
            
            if is_insufficient_window:
                decision = Decision.WAIT
                decision_metadata["capacity_anchor_reason"] = "INSUFFICIENT_OBSERVATION_WINDOW"
                decision_metadata["blocking_factors"].append("INSUFFICIENT_OBSERVATION_WINDOW")
            else:
                decision = Decision.REJECT
                critical_flags = [f for f in flags if "CRITICAL" in f.upper()]
                decision_metadata["blocking_factors"].extend([f.upper() for f in critical_flags])
                if risk_level == "HIGH":
                    decision_metadata["blocking_factors"].append("HIGH_RISK_SCORE")

            recommended_amount = 0
            interest_rate = 0
            print(f"DEBUG: Outcome: {decision}")
        
        # ====================================================================
        # RULE 2: CAPACITY-BASED MAXIMUM (NON-NEGOTIABLE ANCHOR)
        # ====================================================================
        # This is the CORE of bank-grade lending
        # NO OTHER FACTOR can override this limit
        
        elif capacity_based_max > 0:
            # Apply hard cap to requested amount
            if recommended_amount > capacity_based_max:
                decision_metadata["blocking_factors"].append("CAPACITY_SAFETY_LIMIT")
                decision_metadata["adjustments_applied"].append({
                    "type": "CAPACITY_CAP",
                    "original": recommended_amount,
                    "capped_to": capacity_based_max,
                    "reason": f"Exceeded safety limit based on observed transaction activity"
                })
                recommended_amount = capacity_based_max
                
                # Force CONDITIONAL if we reduced the amount
                if decision == Decision.APPROVE:
                    decision = Decision.CONDITIONAL
            
            # ====================================================================
            # RULE 3: STARTER LOAN POLICY
            # ====================================================================
            if starter_loan_applied:
                decision = Decision.CONDITIONAL
                interest_rate = config.BASE_INTEREST_RATE + cap_config.STARTER_INTEREST_PREMIUM
                
                # Check for Micro-Starter Exception specifically
                is_micro_starter = capacity_validation.get("micro_loan_exception", False)
                
                if is_micro_starter:
                    # Add flag to risk_data flags so ExplanationAgent sees it
                    starter_flag = "STARTER_LOAN_APPROVED_LIMITED_HISTORY"
                    if starter_flag not in risk_data["flags"]:
                        risk_data["flags"].append(starter_flag)
                        
                    decision_metadata["blocking_factors"].append("MICRO_STARTER_POLICY_CAP")
                    decision_metadata["adjustments_applied"].append({
                        "type": "MICRO_STARTER_LOAN",
                        "premium_added": cap_config.STARTER_INTEREST_PREMIUM,
                        "micro_cap": cap_config.MICRO_LOAN_CAP,
                        "micro_multiplier": cap_config.MICRO_MULTIPLIER,
                        "reason": "Approved under Micro-Starter exception due to limited history"
                    })
                else:
                    decision_metadata["blocking_factors"].append("STARTER_LOAN_CAP")
                    decision_metadata["adjustments_applied"].append({
                        "type": "STARTER_LOAN",
                        "premium_added": cap_config.STARTER_INTEREST_PREMIUM,
                        "reason": "Approved under Starter Loan policy due to limited history or deposit activity"
                    })
                
                print(f"DEBUG: Starter loan for {borrower.id}: "
                      f"${recommended_amount:.0f} at {interest_rate}%" + 
                      (" (MICRO)" if is_micro_starter else ""))
            
            # ====================================================================
            # RULE 4: RISK-BASED ADJUSTMENTS
            # ====================================================================
            # These can adjust interest rates but NOT amounts (already capped)
            
            elif any("WARNING" in f.upper() for f in flags) or risk_level == "MEDIUM":
                decision = Decision.CONDITIONAL
                
                # Apply additional haircut for medium risk (on top of capacity cap)
                risk_adjusted_amount = recommended_amount * config.CONDITIONAL_AMOUNT_MULTIPLIER
                if risk_adjusted_amount < recommended_amount:
                    decision_metadata["adjustments_applied"].append({
                        "type": "RISK_HAIRCUT",
                        "original": recommended_amount,
                        "adjusted_to": risk_adjusted_amount,
                        "multiplier": config.CONDITIONAL_AMOUNT_MULTIPLIER
                    })
                    recommended_amount = risk_adjusted_amount
                    # Update capacity anchor if risk further constrained it
                    decision_metadata["capacity_anchor_amount"] = recommended_amount
                    decision_metadata["capacity_anchor_reason"] = "RISK_ADJUSTED_LIMIT"
                    decision_metadata["blocking_factors"].append("MEDIUM_RISK_HAIRCUT")
                
                # Increase interest rate for risk premium
                interest_rate = config.CONDITIONAL_INTEREST_RATE
                
                print(f"DEBUG: Conditional approval for {borrower.id}: "
                      f"${recommended_amount:.0f} at {interest_rate}% (medium risk)")
            
            elif any("CAUTION" in f.upper() for f in flags):
                decision = Decision.CONDITIONAL
                interest_rate = config.CAUTION_INTEREST_RATE
                decision_metadata["adjustments_applied"].append({
                    "type": "BEHAVIORAL_CAUTION",
                    "rate_adjustment": "BASE + CAUTION_PREMIUM"
                })
                
                print(f"DEBUG: Conditional approval for {borrower.id}: "
                      f"${recommended_amount:.0f} at {interest_rate}% (behavioral caution)")
            
            else:
                # Full approval - within capacity, no flags
                decision = Decision.APPROVE
                interest_rate = config.BASE_INTEREST_RATE
                
                print(f"DEBUG: Approving {borrower.id}: "
                      f"${recommended_amount:.0f} at {interest_rate}%")
        
        else:
            # No capacity available (should have been rejected in RiskAgent)
            decision = Decision.REJECT
            recommended_amount = 0
            interest_rate = 0
            decision_metadata["adjustments_applied"].append("NO_CAPACITY_AVAILABLE")
            decision_metadata["blocking_factors"].append("INSUFFICIENT_TRANSACTION_HISTORY")
        
        # ====================================================================
        # RULE 5: FINAL VALIDATION & POLISH
        # ====================================================================
        # Policy: Lack of time ≠ bad behavior (Decision MUST be WAIT or CONDITIONAL)
        if "INSUFFICIENT_OBSERVATION_WINDOW" in decision_metadata["blocking_factors"]:
            if decision == Decision.REJECT:
                decision = Decision.WAIT

        # Ensure we never exceed capacity_based_max
        if recommended_amount > capacity_based_max and capacity_based_max > 0:
            print(f"WARNING: Amount {recommended_amount} exceeds capacity {capacity_based_max}. Forcing cap.")
            recommended_amount = capacity_based_max
            decision_metadata["adjustments_applied"].append("SAFETY_CAP_ENFORCED")
        
        return {
            "decision": decision,
            "recommended_amount": round(recommended_amount, 2),
            "recommended_interest_rate": interest_rate,
            "decision_metadata": decision_metadata
        }

