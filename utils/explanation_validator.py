"""
Explanation Validator - Decision-to-Narrative Consistency
==========================================================

This utility ensures that the natural language explanation provided
to the borrower is numerically consistent with the actual capacity-based
decision.

PRINCIPLE:
A bank-grade system must not only be right, it must be EXPLAINABLE.
If the recommendation is reduced due to capacity, the explanation MUST
state this clearly and reference the numbers.

VALIDATION RULES:
1. If amount < requested, explanation must justify the reduction.
2. If capacity-based limit applied, explanation must mention capacity/inflow.
3. If starter loan policy applied, explanation must mention new borrower status.
4. Numerical values in explanation must match decision metrics.
"""

import re
from typing import Dict, Any, List, Optional
from models.assessment import Assessment


class ExplanationInconsistencyError(Exception):
    """Raised when an explanation does not numerically justify the decision."""
    pass


class ExplanationValidator:
    """Validates that assessment explanations match the underlying logic."""

    @staticmethod
    def validate(assessment: Assessment) -> bool:
        """
        Runs a battery of consistency checks on the assessment explanation.
        
        Args:
            assessment: The fully populated assessment object.
            
        Returns:
            True if consistent, raises ExplanationInconsistencyError otherwise.
        """
        explanation = assessment.explanation.lower()
        requested = assessment.requested_amount
        recommended = assessment.recommended_amount
        # FIX: Validator should use metrics as canonical truth for consistency
        observed_deposit_volume = assessment.metrics.get("observed_deposit_volume", 0) if assessment.metrics else (assessment.observed_deposit_volume or 0)
        capacity_max = assessment.capacity_based_max or 0
        
        # 1. AMOUNT REDUCTION CHECK
        # If we gave them less than they asked for, we MUST tell them why and mention the new amount.
        if recommended < requested:
            keywords = [
                "reduced", "cap", "limit", "capacity", "maximum", 
                "eligibility", "threshold", "starter", "adjusted", 
                "deposit", "volume", "anchor", "affordable", "history"
            ]
            if not any(word in explanation for word in keywords):
                raise ExplanationInconsistencyError(
                    "Recommendation was reduced but explanation does not justify the reduction. "
                    f"Requested: {requested}, Recommended: {recommended}"
                )
            
            # REQUIREMENT: Recommended amount must be explicitly mentioned in figures if reduced
            amount_pattern = rf"\$?\s?{recommended:,.0f}"
            if not re.search(amount_pattern, explanation) and not re.search(rf"\$?\s?{recommended:.2f}", explanation):
                # Check if it's in the officer_view specifically if assessment has views
                # for now we check main explanation
                 raise ExplanationInconsistencyError(
                    f"Recommendation was modified to {recommended}, but this figure is not explicitly mentioned in the narrative."
                )
            
        # 1b. PROHIBITED TERMINOLOGY CHECK (Regulator-Safe)
        prohibited = ["income", "earnings", "salary", "pay", "earns"]
        for word in prohibited:
            pattern = re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE)
            if pattern.search(explanation):
                raise ExplanationInconsistencyError(
                    f"Explanation contains prohibited regulator-unsafe terminology: '{word}'. "
                    "Must use 'deposit volume' or 'transaction activity' instead."
                )

        # 2. SENTIMENT CONSISTENCY CHECK
        # Ensures words like "approval" don't appear in REJECTED assessments
        if assessment.decision == "REJECT":
            reject_prohibited = ["congratulations", "happy to recommend", "meets our standard", "approved"]
            for word in reject_prohibited:
                 if word in explanation:
                     raise ExplanationInconsistencyError(
                         f"REJECTED assessment contains contradictory positive sentiment: '{word}'"
                     )
        
        # 3. POLICY ANCHOR CONSISTENCY
        anchor_reason = assessment.capacity_anchor_reason
        anchor_amount = assessment.capacity_anchor_amount or 0.0
        
        if anchor_amount > 0 and recommended <= anchor_amount and recommended < requested:
            required_keywords = ["capacity", "deposit", "anchor", "limit", "maximum"]
            if anchor_reason == "RISK_ADJUSTED_LIMIT":
                required_keywords.extend(["risk", "adjusted", "safety", "policy"])
            elif anchor_reason == "STARTER_LOAN_CAP":
                required_keywords.extend(["starter", "history", "new"])
                
            if not any(k in explanation for k in required_keywords):
                raise ExplanationInconsistencyError(
                    f"Decision anchored by {anchor_reason} to {anchor_amount}, but explanation "
                    f"missing relevant keywords ({required_keywords})."
                )

        # 4. STRICT NUMERICAL MATCH
        # Ensure any mentioned limits match actual calculated capacity or recommended amount
        numbers_in_text = re.findall(r'\d+(?:,\d+)?', explanation)
        if numbers_in_text:
            numeric_vals = [float(n.replace(',', '')) for n in numbers_in_text]
            for val in numeric_vals:
                if val > 100: 
                    # If they mention a "limit" or "capacity", it must match our math
                    is_valid = (
                        abs(val - requested) < 1.0 or 
                        abs(val - recommended) < 1.0 or 
                        abs(val - anchor_amount) < 1.0 or
                        abs(val - capacity_max) < 1.0 or
                        abs(val - observed_deposit_volume) < 1.0
                    )
                    
                    if not is_valid:
                        raise ExplanationInconsistencyError(
                            f"Explanation contains a potentially hallucinated or incorrect figure ({val}) "
                            f"that does not match requested ({requested}), recommended ({recommended}), "
                            f"or capacity metrics."
                        )

        return True

    @staticmethod
    def auto_repair_explanation(assessment: Assessment) -> str:
        """
        Attempts to fix common explanation inconsistencies by appending
        a standard technical justification block.
        """
        addon = ""
        
        if assessment.recommended_amount < assessment.requested_amount:
            # PRINCIPAL RISK: Only add affordability notes if the user is actually getting a loan
            if assessment.decision != "REJECT" and assessment.recommended_amount > 0:
                if assessment.starter_loan_applied:
                    addon = (
                        f" NOTE: As a new borrower, you have been offered a starter loan to help establish "
                        f"your repayment history. Your amount is currently capped at {assessment.recommended_amount}."
                    )
                else:
                    addon = (
                        f" NOTE: Your loan amount has been anchored to the institutional safety limit based "
                        f"on your observed deposit volume of {assessment.observed_deposit_volume:.2f}."
                    )
        
        if addon and addon.lower() not in assessment.explanation.lower():
            return assessment.explanation + addon
            
        return assessment.explanation
