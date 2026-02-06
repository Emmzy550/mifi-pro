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
from utils.policy_context import policy_value, policy_label, policy_version_id

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
    def recommend(risk_data: dict, borrower: Borrower, requested_duration_days: int) -> dict:
        """
        Determines the loan recommendation and terms with STRICT DECISION INVARIANTS.
        
        CRITICAL CHANGE (Bank-Grade):
        - All loan amounts are HARD-CAPPED at capacity_based_max.
        - All loan durations are HARD-CAPPED at policy maximums.
        - Outcomes are strictly APPROVE, REJECT, or REFER.
        
        Args:
            risk_data: Output from RiskAgent.evaluate()
            borrower: Borrower profile with loan request
            requested_duration_days: Loan duration in days
            
        Returns:
            Dictionary containing:
            - decision: APPROVE/REJECT/REFER
            - recommended_amount: Loan amount (or None for REFER)
            - recommended_duration_days: Approved duration (or None for REJECT/REFER)
            - recommended_interest_rate: APR based on risk and duration
            - interest_rate_basis: Breakdown of rate calculation
            - decision_metadata: Audit trail of all decision factors
        """
        import lending_config.capacity_config as cap_config
        
        risk_level = risk_data["risk_level"]
        flags = risk_data["flags"]
        capacity_validation = risk_data["capacity_validation"]
        
        # Extract capacity metrics
        capacity_based_max = capacity_validation["capacity_based_max"]
        starter_loan_applied = capacity_validation["starter_loan_applied"]
        observed_deposit_volume = capacity_validation["observed_deposit_volume"]
        
        # Start with optimistic defaults
        decision = Decision.APPROVE
        recommended_amount = borrower.loan_amount_requested
        
        # Track decision metadata for audit trail
        decision_metadata = {
            "requested_amount": borrower.loan_amount_requested,
            "requested_duration_days": requested_duration_days,
            "capacity_based_max": capacity_based_max,
            "policy_cap_amount": None,
            "policy_cap_reason": None,
            "starter_loan_applied": starter_loan_applied,
            "observed_deposit_volume": observed_deposit_volume,
            "transaction_count": capacity_validation.get("transaction_count", 0),
            "deposit_transaction_count": capacity_validation.get("audit_trail", {}).get("deposit_volume_calculation", {}).get("deposit_count", 0),
            "deposit_source": "MOBILE_MONEY_DEPOSITS_ONLY",
            "observation_window_days": capacity_validation.get("observation_window_days", 30),
            "policy_version": policy_label("v1.5.0-duration-handling"),
            "policy_version_id": policy_version_id("unknown"),
            "blocking_factors": [],
            "adjustments_applied": []
        }
        
        # ====================================================================
        # RULE 1: DURATION POLICY ENFORCEMENT
        # ====================================================================
        
        min_duration_days = int(policy_value("min_duration_days", cap_config.MIN_DURATION_DAYS))
        max_duration_days = int(policy_value("max_duration_days", cap_config.MAX_DURATION_DAYS))
        starter_max_duration = int(policy_value("starter_loan_max_duration_days", cap_config.STARTER_LOAN_MAX_DURATION_DAYS))

        if requested_duration_days < min_duration_days:
            decision = Decision.REJECT
            decision_metadata["blocking_factors"].append("DURATION_POLICY_VIOLATION")
            decision_metadata["duration_rejection_reason"] = (
                f"Requested duration ({requested_duration_days} days) below minimum ({min_duration_days} days)"
            )
            return {
                "decision": decision,
                "recommended_amount": 0.0,
                "recommended_duration_days": None,
                "recommended_interest_rate": 0.0,
                "interest_rate_basis": None,
                "decision_metadata": decision_metadata
            }

        # Calculate recommended duration
        max_allowed_duration = max_duration_days
        if starter_loan_applied:
            max_allowed_duration = min(max_allowed_duration, starter_max_duration)

        recommended_duration = min(requested_duration_days, max_allowed_duration)

        # Track duration adjustments
        if recommended_duration < requested_duration_days:
            if starter_loan_applied:
                decision_metadata["adjustments_applied"].append({
                    "type": "DURATION_ADJUSTED_STARTER_POLICY",
                    "requested": requested_duration_days,
                    "recommended": recommended_duration,
                    "reason": "Starter loan policy limits duration to build repayment history"
                })
            else:
                decision_metadata["adjustments_applied"].append({
                    "type": "DURATION_POLICY_CAP_APPLIED",
                    "requested": requested_duration_days,
                    "recommended": recommended_duration,
                    "reason": f"Duration capped at policy maximum of {max_duration_days} days"
                })

        # ====================================================================
        # RULE 2: HARD REJECTION / REFERRAL
        # ====================================================================
        
        # 2A. INSUFFICIENT DATA → REFER (Manual Review)
        is_insufficient_window = any("OBSERVATION_WINDOW" in f.upper() for f in flags)
        
        if is_insufficient_window:
            decision = Decision.REFER
            decision_metadata["blocking_factors"].append("INSUFFICIENT_OBSERVATION_WINDOW")
            
            return {
                "decision": decision,
                "recommended_amount": None,
                "recommended_duration_days": None,
                "recommended_interest_rate": 0,
                "interest_rate_basis": None,
                "decision_metadata": decision_metadata
            }
            
        # 2B. CRITICAL RISK → REJECT
        if any("CRITICAL" in f.upper() for f in flags) or risk_level == "HIGH":
            decision = Decision.REJECT
            critical_flags = [f for f in flags if "CRITICAL" in f.upper()]
            decision_metadata["blocking_factors"].extend([f.upper() for f in critical_flags])
            
            if risk_level == "HIGH":
                decision_metadata["blocking_factors"].append("HIGH_RISK_SCORE")
                
            if not decision_metadata["blocking_factors"]:
                 decision_metadata["blocking_factors"].append("POLICY_RISK_THRESHOLD_EXCEEDED")

            return {
                "decision": decision,
                "recommended_amount": 0.0,
                "recommended_duration_days": None,
                "recommended_interest_rate": 0.0,
                "interest_rate_basis": None,
                "decision_metadata": decision_metadata
            }
        
        # ====================================================================
        # RULE 3: CAPACITY-BASED APPROVAL (With Caps)
        # ====================================================================
        
        if capacity_based_max > 0:
            # Apply hard cap to requested amount
            if recommended_amount > capacity_based_max:
                decision_metadata["adjustments_applied"].append({
                    "type": "CAPACITY_CAP",
                    "original": recommended_amount,
                    "capped_to": capacity_based_max,
                    "reason": "Exceeded safety limit based on observed transaction activity"
                })
                recommended_amount = capacity_based_max
            
            # Risk Haircut for Medium Risk
            if any("WARNING" in f.upper() for f in flags) or risk_level == "MEDIUM":
                risk_adjusted_amount = recommended_amount * config.CONDITIONAL_AMOUNT_MULTIPLIER
                if risk_adjusted_amount < recommended_amount:
                    decision_metadata["adjustments_applied"].append({
                        "type": "RISK_HAIRCUT",
                        "original": recommended_amount,
                        "adjusted_to": risk_adjusted_amount,
                        "multiplier": config.CONDITIONAL_AMOUNT_MULTIPLIER
                    })
                    recommended_amount = risk_adjusted_amount
                    
                    if decision_metadata["policy_cap_amount"] is None:
                        decision_metadata["policy_cap_amount"] = recommended_amount
                        decision_metadata["policy_cap_reason"] = f"RISK_HAIRCUT_{risk_level}"
            
            # Clean Approval (no more amount adjustments needed)
            decision = Decision.APPROVE
        else:
            decision = Decision.REJECT
            recommended_amount = 0
            decision_metadata["blocking_factors"].append("INSUFFICIENT_TRANSACTION_HISTORY")
            return {
                "decision": decision,
                "recommended_amount": 0.0,
                "recommended_duration_days": None,
                "recommended_interest_rate": 0.0,
                "interest_rate_basis": None,
                "decision_metadata": decision_metadata
            }

        # ====================================================================
        # RULE 4: INTEREST RATE CALCULATION (Explainable)
        # ====================================================================
        
        rate_adjustments = []
        final_rate = config.BASE_INTEREST_RATE

        # Risk-based adjustment
        if any("WARNING" in f.upper() for f in flags) or risk_level == "MEDIUM":
            premium = config.CONDITIONAL_INTEREST_RATE - config.BASE_INTEREST_RATE
            rate_adjustments.append({"type": "MEDIUM_RISK_PREMIUM", "value": premium})
            final_rate += premium
        elif any("CAUTION" in f.upper() for f in flags):
            premium = config.CAUTION_INTEREST_RATE - config.BASE_INTEREST_RATE
            rate_adjustments.append({"type": "CAUTION_PREMIUM", "value": premium})
            final_rate += premium

        # Starter loan premium
        if starter_loan_applied:
            rate_adjustments.append({"type": "STARTER_LOAN_PREMIUM", "value": cap_config.STARTER_INTEREST_PREMIUM})
            final_rate += cap_config.STARTER_INTEREST_PREMIUM

        # Duration-based adjustment
        if recommended_duration <= cap_config.SHORT_TENOR_THRESHOLD_DAYS:
            rate_adjustments.append({"type": "SHORT_TENOR_DISCOUNT", "value": -cap_config.SHORT_TENOR_DISCOUNT})
            final_rate -= cap_config.SHORT_TENOR_DISCOUNT
        elif recommended_duration >= cap_config.LONG_TENOR_THRESHOLD_DAYS:
            rate_adjustments.append({"type": "LONG_TENOR_PREMIUM", "value": cap_config.LONG_TENOR_PREMIUM})
            final_rate += cap_config.LONG_TENOR_PREMIUM

        interest_rate_basis = {
            "base_rate": config.BASE_INTEREST_RATE,
            "adjustments": rate_adjustments,
            "final_rate": final_rate
        }

        # FINAL SAFETY CHECK
        if decision == Decision.APPROVE and recommended_amount <= 0:
             decision = Decision.REJECT
             decision_metadata["blocking_factors"].append("CALCULATED_AMOUNT_ZERO")
             recommended_amount = 0

        return {
            "decision": decision,
            "recommended_amount": round(recommended_amount, 2) if recommended_amount else None,
            "recommended_duration_days": int(recommended_duration) if decision == Decision.APPROVE else None,
            "recommended_interest_rate": final_rate,
            "interest_rate_basis": interest_rate_basis,
            "decision_metadata": decision_metadata
        }

