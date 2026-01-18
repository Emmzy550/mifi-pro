"""
Risk Agent - Core Risk Evaluation Engine
=========================================

This agent orchestrates all risk assessment components:
1. Rule-based evaluation (ALWAYS active)
2. ML-based prediction (optional, controlled by feature flag)
3. Behavioral intelligence (optional, controlled by feature flag)

CRITICAL SAFETY PRINCIPLE:
Rules ALWAYS override ML predictions when critical flags are present.
This ensures regulatory compliance and protects against ML errors.
"""

import sys
import os
from typing import Dict, Any

# Fix for direct execution: ensure project root is in path
if __name__ == "__main__" or __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.borrower import Borrower
import config

# Import agents based on feature flags
from agents.ml_risk_agent import MLRiskAgent
from utils.db import Database
from rules.lending_rules import (
    check_income_stability, 
    check_dti_ratio, 
    check_affordability,
    check_critical_flags
)
from utils.scoring import calculate_risk_score, derive_risk_level

# Conditionally import behavioral agent based on version
if config.ENABLE_BEHAVIORAL_V2:
    try:
        from agents.behavioral_agent_v2 import BehavioralAgentV2 as BehavioralAgent
        print("[OK] Using BehavioralAgentV2 (enhanced)")
    except ImportError:
        # Fallback to V1 if V2 not yet implemented
        from agents.behavioral_agent import BehavioralAgent
        print("[WARN] BehavioralAgentV2 not found, using V1")
else:
    from agents.behavioral_agent import BehavioralAgent


class RiskAgent:
    """
    Agent responsible for evaluating borrower risk.
    
    Combines multiple risk signals:
    - Deterministic rules (DTI, affordability, income stability)
    - ML predictions (probability of default)
    - Behavioral patterns (alternative data analysis)
    
    The final risk score is an ensemble, but rules have veto power.
    """
    
    @staticmethod
    def evaluate(borrower: Borrower, external_behavioral_results: Dict[str, Any] = None) -> dict:
        """
        Runs the complete risk evaluation suite.
        ...
        Args:
            borrower: Borrower profile
            external_behavioral_results: Optional results from user-uploaded data (Pilot pipeline)
        """
        flags = []
        data_source = "INTERNAL_HISTORY" # Default
        
        # ... (Step 1 Rules same) ...
        # [OMITTED for brevity in tool call, relying on Context matches]
        # ====================================================================
        # STEP 1: DETERMINISTIC RULES (Foundational Risk)
        # ====================================================================
        # Check basic financial health
        if not check_income_stability(borrower):
            flags.append("Warning: Income instability detected")
            
        if check_dti_ratio(borrower) > config.MAX_DEBT_TO_INCOME_RATIO:
            flags.append("High Risk: Debt-to-Income ratio exceeds 50%")
            
        is_affordable, _ = check_affordability(borrower)
        if not is_affordable:
            flags.append("Critical: Estimated unability to repay")
            
        # Check specific regulatory/policy flags
        _, critical_flags_list = check_critical_flags(borrower)
        flags.extend(critical_flags_list)
        
        # Calculate Base Score
        rule_score = calculate_risk_score(borrower, flags)
        
        # Base metrics for display (Using stated income for DTI/Expense Context)
        metrics = {
            "dti_ratio": round(borrower.existing_debt / borrower.monthly_income, 2) if borrower.monthly_income > 0 else 1.0,
            "expense_ratio": round(borrower.monthly_expenses / borrower.monthly_income, 2) if borrower.monthly_income > 0 else 1.0,
        }

        # ====================================================================
        # STEP 2: ML PREDICTION (OPTIONAL - V4)
        # ====================================================================
        ml_prob = 0.0
        ml_feature_importance = []
        
        if config.ENABLE_ML_RISK_SCORING:
            try:
                # We need to pass alt_data if we have it, but here we might not have it yet 
                # unless passed in external_behavioral_results. 
                # For now, we pass None to ML or fetching it from DB if needed.
                # Simplified: Just pass borrower for V1.
                ml_result = MLRiskAgent.predict(borrower)
                if "error" not in ml_result:
                    ml_prob = ml_result["prob_default"]
                    ml_feature_importance = ml_result["feature_importance"]
                    print(f"DEBUG: ML Prediction: {ml_prob}")
                else:
                    print(f"WARN: ML Prediction failed: {ml_result['error']}")
            except Exception as e:
                print(f"ERROR: ML Agent failed: {e}")

        # ====================================================================
        # STEP 3: BEHAVIORAL INTELLIGENCE (OPTIONAL - V2)
        # ====================================================================
        behavioral_results = {
            "behavioral_stability": 0.0,
            "saving_trend": 0.0,
            "utility_compliance": 0.0,
            "early_warnings": []
        }
        
        try:
            if external_behavioral_results:
                # PILOT PIPELINE: Use uploaded data analysis
                print("INFO: Using USER-UPLOADED behavioral data (Pilot)")
                behavioral_results = external_behavioral_results
                data_source = "USER_UPLOADED_STATEMENT"
            else:
                # STANDARD PIPELINE: Fetch from DB
                alt_data = Database.get_alternative_data(borrower.id)
                if alt_data:
                    behavioral_results = BehavioralAgent.analyze(alt_data)
            
            # Add behavioral warnings to flags
            if behavioral_results.get("early_warnings"):
                prefixed_warnings = [f"CAUTION: {w}" for w in behavioral_results["early_warnings"]]
                flags.extend(prefixed_warnings)
                
        except Exception as e:
            print(f"WARNING: Behavioral analysis failed: {e}")

        # ... (Ensemble Logic) ...
        
        if any("CRITICAL" in f for f in flags):
             final_score = 1.0
             override_applied = True
             override_reason = "Critical lending policy violation detected"
        else:
            # Calculate Penalty
            flag_count = len(behavioral_results.get("early_warnings", []))
            behavioral_penalty = flag_count * config.BEHAVIORAL_PENALTY_PER_FLAG
            
            # APPLY CAP for User Uploaded Data
            if data_source == "USER_UPLOADED_STATEMENT":
                original_penalty = behavioral_penalty
                behavioral_penalty = min(behavioral_penalty, config.MAX_BEHAVIORAL_IMPACT_CAP)
                if original_penalty > behavioral_penalty:
                    print(f"INFO: Behavioral penalty capped from {original_penalty} to {behavioral_penalty} (Pilot Safety)")
            
            # ... (Rest of logic) ...

            
            if config.ENABLE_ML_RISK_SCORING and ml_prob > 0:
                # Weighted ensemble
                final_score = (config.RULE_WEIGHT * rule_score) + (config.ML_WEIGHT * ml_prob)
                final_score += behavioral_penalty
                override_applied = False
                override_reason = None
            else:
                # Rule-only mode (ML disabled or unavailable)
                final_score = rule_score + behavioral_penalty
                override_applied = False
                override_reason = None
        
        # Cap score at 1.0
        final_score = min(final_score, 1.0)
        final_level = derive_risk_level(final_score)

        # ====================================================================
        # STEP 5: CAPACITY VALIDATION (BANK-GRADE GUARDRAILS)
        # ====================================================================
        # WHY: Anchor all decisions to demonstrated financial capacity
        # NOTE: This step has VETO POWER over all previous analysis
        
        # STEP 5: CAPACITY VALIDATION (BANK-GRADE GUARDRAILS)
        from agents.capacity_agent import CapacityAgent
        capacity_results = CapacityAgent.calculate_demonstrated_capacity(
            borrower_id=borrower.id,
            risk_level=final_level,
            requested_amount=borrower.loan_amount_requested,
            external_transactions=external_behavioral_results.get("transactions") if external_behavioral_results else None
        )
        
        # Merge metrics
        metrics.update({
            "observed_deposit_volume": capacity_results.get("observed_deposit_volume", 0.0),
            "transaction_count": capacity_results.get("transaction_count", 0),
            "history_days": capacity_results.get("history_days", 0),
            "observation_window_days": capacity_results.get("observation_window_days", 0),
            "capacity_based_max": capacity_results.get("capacity_based_max", 0.0)
        })

        # GOVERNANCE: Handle Insufficient Observation Window
        if capacity_results.get("insufficient_observation"):
            # POLICY: Lack of time != Bad behavior
            if final_score > 0.6:
                final_score = 0.6
                final_level = "MEDIUM"
                flags.append("INFO: Risk capped due to limited observation window")
            
            # Always add the policy flag so DecisionAgent knows to WAIT
            flags.append("INSUFFICIENT_OBSERVATION_WINDOW: Transactions detected but span less than 30 days")
            
            # Clean up any legacy critical messages
            if any("CRITICAL" in f for f in flags if "HISTORY" in f):
                flags = [f for f in flags if not ("CRITICAL" in f and "HISTORY" in f)]

        # Hard reject if capacity validation fails (unless it's just a time issue)
        if not capacity_results["is_valid"]:
            # If it's an observation window issue, we already handled it above (is_valid was set to True in CapacityAgent for this case)
            # This block now only handles real hard rejects (0 transactions, etc.)
            final_score = 1.0  # Force HIGH risk
            final_level = "HIGH"
            flags.append(f"CRITICAL: {capacity_results['rejection_reason']}")
            override_applied = True
            override_reason = capacity_results["rejection_reason"]
            
            print(f"CAPACITY REJECTION: {capacity_results['rejection_reason']}")
        
        # Add capacity metrics to output
        metrics.update({
            "observed_deposit_volume": capacity_results["observed_deposit_volume"],
            "transaction_count": capacity_results["transaction_count"],
            "history_days": capacity_results["history_days"],
            "capacity_based_max": capacity_results["capacity_based_max"],
            "capacity_anchor_amount": capacity_results["capacity_anchor_amount"],
            "capacity_anchor_reason": capacity_results["capacity_anchor_reason"],
            "capacity_multiplier_used": capacity_results["capacity_multiplier_used"],
            "starter_loan_applied": capacity_results["starter_loan_applied"],
            "micro_loan_exception": capacity_results.get("micro_loan_exception", False),
            "micro_starter_audit": capacity_results.get("audit_trail", {}).get("micro_starter"),
            "capacity_data_source": capacity_results["data_source"]
        })
        
        # ====================================================================
        # STEP 6: RETURN COMPREHENSIVE RESULTS
        # ====================================================================
        # WHY: Transparency for loan officers and audit trail for regulators
        
        return {
            # Final decision inputs
            "risk_score": final_score,
            "risk_level": final_level,
            "flags": list(set(flags)),  # Deduplicate
            
            # Detailed metrics for transparency
            "metrics": {
                **metrics,
                "ml_prob_default": ml_prob,
                "ml_feature_importance": ml_feature_importance,
                "behavioral_stability": behavioral_results["behavioral_stability"],
                "saving_trend": behavioral_results["saving_trend"],
                "utility_compliance": behavioral_results["utility_compliance"],
                "behavioral_status": behavioral_results.get("behavioral_status", "UNKNOWN")
            },
            
            # Component scores for comparison
            "rule_based_score": rule_score,
            "ml_based_score": ml_prob,
            
            # Governance metadata
            "data_source": data_source,
            "override_applied": override_applied,
            "override_reason": override_reason,
            "config_snapshot": config.get_config_snapshot(),
            
            # Capacity validation results (for DecisionAgent)
            "capacity_validation": capacity_results
        }

