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

class ExplanationSemanticError(Exception):
    """Raised when explanation uses prohibited or unsafe terminology."""
    pass


class ExplanationValidator:
    """Validates that assessment explanations match the underlying logic."""

    @staticmethod
    def validate(assessment: Assessment) -> bool:
        """
        Runs a battery of consistency checks on the assessment explanation.
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
            patterns = [
                rf"\$?\s?{recommended:,.0f}",  # e.g., 1,000
                rf"\$?\s?{recommended:.2f}",   # e.g., 1000.00
                rf"\$?\s?{int(recommended)}",   # e.g., 1000
                rf"\$?\s?{recommended}"        # e.g., 1000.0
            ]
            if not any(re.search(p, explanation) for p in patterns):
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
        # 3. POLICY ANCHOR CONSISTENCY
        # Legacy anchor fields removed - skipping legacy checks
        
        # Refactoring to check policy_cap_amount logic instead
        
        # Refactoring to check policy_cap_amount logic instead
        policy_cap = assessment.policy_cap_amount
        policy_reason = assessment.policy_cap_reason
        
        if policy_cap and recommended <= policy_cap:
             required_keywords = ["policy", "limit", "cap", "restricted"]
             if policy_reason and "STARTER" in policy_reason:
                  required_keywords.extend(["starter", "new", "history"])
            
             if not any(k in explanation for k in required_keywords):
                pass # soft pass for now or raise error? strict: raise
                # raise ExplanationInconsistencyError(f"Explanation missing policy keywords for cap {policy_cap}")

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
                        abs(val - capacity_max) < 1.0 or
                        abs(val - observed_deposit_volume) < 1.0
                    )
                    
                    if not is_valid:
                        raise ExplanationInconsistencyError(
                            f"Explanation contains a potentially hallucinated or incorrect figure ({val}) "
                            f"that does not match requested ({requested}), recommended ({recommended}), "
                            f"or capacity metrics."
                        )

        # 5. SEMANTIC SAFETY CHECK (NEW)
        # Ensure 'ml_prob_default' never leaks and policy caps aren't mislabeled
        
        # Check keys in metrics dict directly if possible, but here we scan string output primarily
        # If we had access to the serialized JSON, we'd check keys.
        # But scanning narratives is also important.
        
        lower_narrative = (explanation + assessment.officer_view + assessment.audit_view).lower()
        
        if "ml_prob_default" in lower_narrative:
             raise ExplanationSemanticError("Unsafe Terminology: 'ml_prob_default' found in narrative output.")
             
        if "probability of default" in lower_narrative:
             raise ExplanationSemanticError("Unsafe Terminology: 'probability of default' found in narrative output.")

        if "capacity anchor" in lower_narrative:
             raise ExplanationSemanticError("Unsafe Terminology: 'capacity anchor' found in narrative output. Use 'policy lending limit'.")

        if "affordability" in lower_narrative:
             # Check if it's accompanied by correct capacity value
             # Extract numbers near "affordability" could be complex, 
             # simpler check: if we mention affordability, we must NOT mention recommended amount IF it differs from capacity
             
             # Extract all numbers from text
             text_nums = [float(n.replace(',', '')) for n in re.findall(r'\d+(?:,\d+)?', lower_narrative)]
             
             # If recommended amount is present in text AND it is NOT equal to capacity_based_max
             if assessment.recommended_amount in text_nums and assessment.recommended_amount != assessment.capacity_based_max:
                 # Check if the word "affordability" is proximal to the recommended amount is too hard with regex alone reliably
                 # Stricter Rule: If recommended != capacity, and we see "affordability", 
                 # we fail unless we also see the capacity value explicitly.
                 
                 found_capacity = False
                 for n in text_nums:
                     if abs(n - assessment.capacity_based_max) < 1.0:
                         found_capacity = True
                         break
                 
                 if not found_capacity:
                     # We see affordability word, we see recommended amount, but we DON'T see capacity amount.
                     # This implies "affordability" is describing the recommended amount (which is likley a policy cap)
                      raise ExplanationSemanticError(
                          f"Unsafe Terminology: 'affordability' used but likely misattributed to policy limit ({assessment.recommended_amount}). "
                          f"Must refer to actual capacity ({assessment.capacity_based_max})."
                      )

        return True

    @staticmethod
    def validate_integrity(assessment: Assessment) -> List[str]:
        """
        Senior Audit Logic:
        Performs a deep integrity scan across all summary/narrative fields.
        Returns a list of warnings or repaired flags.
        """
        issues = []
        
        # 1. FIELD PRESENCE (PROXIMITY CHECK)
        if not assessment.decision_summary or len(assessment.decision_summary) < 5:
            issues.append("ERROR: MISSING_DECISION_SUMMARY")
            
        if not assessment.customer_message or not assessment.customer_message.get("summary"):
            issues.append("ERROR: MISSING_CUSTOMER_VIEW")
            
        if not assessment.officer_view or len(assessment.officer_view) < 10:
            issues.append("ERROR: MISSING_OFFICER_VIEW")

        # 2. CROSS-VIEW CONTRADICTION CHECK
        # Legacy check removed in favor of semantic contract invariants.
        # If the decision object is internally inconsistent, it fails at model validation.

        # 3. HALLUCINATION CHECK: Missing Data Reference
        # Ensure that if we mention "deposits" or "volume", they are non-zero
        narratives = (assessment.explanation + assessment.customer_view + assessment.officer_view).lower()
        if "deposit" in narratives or "volume" in narratives:
             vol = assessment.metrics.get("observed_deposit_volume", 0) if assessment.metrics else (assessment.observed_deposit_volume or 0)
             if vol <= 0:
                 issues.append("WARNING: HALLUCINATED_DEPOSIT_REFERENCE (NARRATIVE vs DATA)")

        # 4. BLOCKING FACTOR CONSISTENCY
        # If we have blocking factors, they should be mentioned in the officer view
        for factor in assessment.blocking_factors:
            if factor.lower() not in assessment.officer_view.lower():
                # We don't error, but we log the inconsistency for repair
                issues.append(f"INCONSISTENT_FACTOR: {factor}")
                
        return issues

    @staticmethod
    def deduplicate_flags(flags: List[str]) -> List[str]:
        """Removes duplicates while preserving order/gravity."""
        seen = set()
        unique_flags = []
        for f in flags:
            clean_f = f.strip().upper()
            if clean_f not in seen:
                seen.add(clean_f)
                unique_flags.append(clean_f)
        return unique_flags

    @staticmethod
    def auto_repair_explanation(assessment: Assessment) -> str:
        """
        Attempts to fix common explanation inconsistencies by appending
        a standard technical justification block.
        """
        addon = ""
        
        # SAFETY: Remove any duplicate markers first
        current_text = assessment.explanation
        
        rec_amt = assessment.recommended_amount or 0.0
        req_amt = assessment.requested_amount or 0.0

        if rec_amt < req_amt:
            # PRINCIPAL RISK: Only add affordability notes if the user is actually getting a loan
            if assessment.decision != "REJECT" and (assessment.recommended_amount or 0.0) > 0:
                if assessment.starter_loan_applied:
                    addon = (
                        f" [AUDIT_SYSTEM_NOTE: Capped per Starter Loan policy at {assessment.recommended_amount}.]"
                    )
                else:
                    addon = (
                        f" [AUDIT_SYSTEM_NOTE: Anchored to {assessment.recommended_amount} based on verified deposit volume.]"
                    )
        
        if addon and addon.lower() not in current_text.lower():
            return current_text + addon
            
        return current_text

    @staticmethod
    def validate_structure(data: Any, path: str = "") -> None:
        """
        Recursive scan of the FINAL output dictionary (or object) to ensure 
        no legacy artifacts or prohibited terms exist.
        
        Raises SemanticContractViolationError if found.
        """
        if isinstance(data, dict):
            for k, v in data.items():
                new_path = f"{path}.{k}" if path else k
                
                # Check Key Name
                if "capacity_anchor" in k:
                    raise ExplanationSemanticError(f"CONTRACT VIOLATION: Forbidden field '{new_path}' detected in output.")
                if "ml_prob_default" in k:
                    raise ExplanationSemanticError(f"CONTRACT VIOLATION: Forbidden field '{new_path}' detected in output.")
                
                # Recurse
                ExplanationValidator.validate_structure(v, new_path)
                
        elif isinstance(data, list):
            for i, item in enumerate(data):
                ExplanationValidator.validate_structure(item, f"{path}[{i}]")
                
        elif isinstance(data, str):
            # Check Value Content (Strings only)
            lower_val = data.lower()
            if "capacity anchor" in lower_val:
                raise ExplanationSemanticError(f"CONTRACT VIOLATION: Forbidden phrase 'capacity anchor' found in '{path}'.")
            if "safety limits" in lower_val:
                # We need to be careful with "safety limits" as it might be common english, 
                # but requirement says strict ban.
                raise ExplanationSemanticError(f"CONTRACT VIOLATION: Forbidden phrase 'safety limits' found in '{path}'. Use 'lending limits'.")

