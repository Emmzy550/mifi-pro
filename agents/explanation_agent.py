from typing import Dict, Any

class ExplanationAgent:
    """
    Agent responsible for translating technical signals into human language.
    Provides transparency for lenders and borrowers.
    """
    @staticmethod
    def generate(risk_results: Dict[str, Any], decision_results: Dict[str, Any], borrower: Any = None) -> Dict[str, Any]:
        """
        Translates technical risk signals into persona-based explanations.
        Returns a dictionary containing:
        - decision_summary: Clear one-sentence verdict
        - customer_view: Actionable and respectful
        - officer_view: Professional and policy-focused
        - audit_view: Technical and auditable
        - blocking_factors: List of constraints
        """
        decision = decision_results["decision"]
        risk_score = risk_results["risk_score"]
        risk_level = risk_results["risk_level"]
        flags = risk_results["flags"]
        metrics = risk_results["metrics"]
        
        decision_metadata = decision_results.get("decision_metadata", {})
        blocking_factors = decision_metadata.get("blocking_factors", [])
        policy_version = decision_metadata.get("policy_version", "v1.2.0-human-first")
        
        # Initial Rationale components
        summary = ""
        policy_justification = ""
        customer_summary = ""
        action_item = ""
        
        # =========================================================
        # SECTION 1: EXECUTIVE SUMMARY
        # =========================================================
        requested_amt = borrower.loan_amount_requested if borrower else None
        
        is_starter = "STARTER_LOAN_APPROVED_LIMITED_HISTORY" in flags
        is_equality = requested_amt is not None and abs(requested_amt - decision_results['recommended_amount']) < 0.01

        if decision == "APPROVE" or decision == "CONDITIONAL" or decision == "WAIT":
            is_insufficient_window = (decision_metadata.get("capacity_anchor_reason") == "INSUFFICIENT_OBSERVATION_WINDOW" or 
                                     any("OBSERVATION_WINDOW" in f.upper() for f in blocking_factors))
            
            if is_insufficient_window and decision == "WAIT":
                summary = "Application deferred due to insufficient observation window (verified income present)."
                customer_summary = "We’ve successfully verified your income, but we need to observe account activity over a longer period."
                
                win_days = decision_metadata.get('observation_window_days', 0)
                win_str = "1 day" if win_days == 1 else f"{win_days} days"
                
                policy_justification = f"Income verified but observation window ({win_str}) is below the required 30-day threshold."
                action_item = "Please continue using your account and feel free to reapply once you have 30 days of consistent activity."
            
            if decision == "APPROVE" and not is_insufficient_window:
                decision_summary = "Application recommended for approval based on policy compliance."
                if is_equality:
                    summary = "This applicant demonstrates a stable financial profile with favorable behavioral indicators."
                    customer_summary = "Great news! Your application meets our standard criteria, and we're happy to recommend approval for the full amount."
                    policy_justification = f"The requested amount is within the system's policy-defined capacity anchor of ${decision_results['recommended_amount']:,.0f}."
                    action_item = "No further action needed from the borrower at this time."
                elif requested_amt:
                    summary = f"This applicant demonstrates stable financial activity. Requested: ${requested_amt:,.0f} | Recommended: ${decision_results['recommended_amount']:,.0f}."
                    customer_summary = f"We've reviewed your activity and can offer you a loan of ${decision_results['recommended_amount']:,.0f}."
                    policy_justification = f"The recommended amount was anchored to the institutional safety limit of ${decision_results['recommended_amount']:,.0f}."
                    action_item = "Review the modified loan amount and accept if it meets your needs."
                else:
                    summary = "This applicant demonstrates a stable financial profile with favorable behavioral indicators."
                    customer_summary = "Your financial profile shows consistent activity supporting this approval."
            
            elif decision == "WAIT":
                decision_summary = "Application deferred to allow for further observation."
                if not is_insufficient_window:
                     summary = "Request parked for more data."
                     customer_summary = "We're currently reviewing your request and will update you shortly."

            elif decision == "CONDITIONAL":
                decision_summary = "Approved with modifications to align with institutional safety policies."
                
                if is_starter:
                    recommended_amt = decision_results['recommended_amount']
                    deposit_volume = metrics.get("observed_deposit_volume", 0)
                    
                    if is_equality:
                        summary = "Applicant approved for conditional entry-level credit."
                        customer_summary = "Welcome! Since you're new to our system, we've approved you for a starter loan to help you build your record."
                        policy_justification = f"Approved under Micro-Starter policy with loan size capped at the policy limit of ${recommended_amt:,.0f}."
                        action_item = "Repay this starter loan on time to unlock higher limits in the future."
                    elif deposit_volume > 0:
                        summary = f"Applicant approved for conditional entry-level credit. Requested: ${requested_amt:,.0f} | Recommended: ${recommended_amt:,.0f}."
                        customer_summary = f"We've started you with a loan of ${recommended_amt:,.0f} while you establish your transaction history with us."
                        policy_justification = f"The amount was restricted to the policy anchor of ${recommended_amt:,.0f} per Micro-Starter guidelines."
                        action_item = "Consistent transaction activity will help us increase your limits over time."
                    else:
                        summary = "Applicant approved for conditional entry-level credit based on minimum safety bounds."
                        customer_summary = "We've approved a small starter loan to help us begin understanding your credit journey."
                        policy_justification = "Amount restricted to starter limits due to limited verifiable deposit history."
                        action_item = "Start building your credit history with this initial loan."
                elif requested_amt:
                    recommended_amt = decision_results['recommended_amount']
                    summary = f"This applicant shows acceptable risk with adjusted terms. Requested: ${requested_amt:,.0f} | Recommended: ${recommended_amt:,.0f}."
                    customer_summary = f"We can offer you a loan of ${recommended_amt:,.0f} at this time to ensure it remains comfortable for your budget."
                    policy_justification = f"The requested amount was adjusted to the policy anchor of ${recommended_amt:,.0f} to align with safety requirements."
                    action_item = "Consider the adjusted amount and interest rate provided."
                else:
                    summary = "Conditional approval recommended with adjusted terms."
                    customer_summary = "We've offered modified terms that align with our safety guidelines."
        else:
            decision_summary = "Application declined as it does not currently meet policy thresholds."
            
            is_insufficient_window = (decision_metadata.get("capacity_anchor_reason") == "INSUFFICIENT_OBSERVATION_WINDOW" or 
                                     any("OBSERVATION_WINDOW" in f.upper() for f in blocking_factors))
            
            if is_insufficient_window:
                summary = "Application deferred due to insufficient observation window (verified income present)."
                customer_summary = "We’ve successfully verified your income, but we need to observe account activity over a longer period."
                
                win_days = decision_metadata.get('observation_window_days', 0)
                win_str = "1 day" if win_days == 1 else f"{win_days} days"
                
                policy_justification = f"Income verified but observation window ({win_str}) is below the required 30-day threshold."
                action_item = "Please continue using your account and feel free to reapply once you have 30 days of consistent activity."
            elif metrics.get("observed_deposit_volume", 0) == 0:
                summary = "Application declined due to insufficient financial history."
                customer_summary = "We weren't able to find enough recent transaction activity to establish a lending limit at this time."
                policy_justification = "No verifiable deposit activity was found within the required observation window."
                action_item = "Ensure you have at least 30 days of consistent activity before reapplying."
            elif requested_amt:
                summary = f"This applicant's risk profile exceeds institutional safety thresholds."
                customer_summary = "We aren't able to approve this request right now as it doesn't meet our current policy requirements."
                policy_justification = "Application does not meet minimum eligibility criteria for a capacity anchor."
                action_item = "Feel free to reapply in 3-6 months as your transaction record grows."
            else:
                summary = "Application does not meet safety thresholds."
                customer_summary = "We cannot proceed with this application at the present time."
        
        # ---------------------------------------------------------
        # ASSEMBLE VIEWS (STRICT SEPARATION OF CONCERNS)
        # ---------------------------------------------------------
        
        # 1. CUSTOMER MESSAGE (Structured, Respectful, No Jargon)
        customer_message = {
            "summary": customer_summary,
            "key_reasons": "We've evaluated your transaction patterns to ensure the loan amount is comfortable for your current budget.",
            "next_steps": action_item
        }
        
        # Refine key reasons based on decision for customer
        if decision == "REJECT":
            if metrics.get("observed_deposit_volume", 0) == 0:
                customer_message["key_reasons"] = "We couldn't verify enough recent deposit activity to establish a limit today."
            else:
                customer_message["key_reasons"] = "Your current transaction activity doesn't quite meet our safety thresholds for this particular request."
        elif is_starter:
            customer_message["key_reasons"] = "As you're establishing your record with us, we've started with a safe limit that can grow over time."

        # 2. INTERNAL DECISION NOTES (For Officers & Risk Teams)
        officer_guidance = []
        if decision == "APPROVE":
            officer_guidance.append("Proceed with standard documentation.")
        elif decision == "CONDITIONAL":
            officer_guidance.append(f"Offer ${decision_results['recommended_amount']:,.0f} at {decision_results.get('recommended_interest_rate'):.1f}%.")
            officer_guidance.append("Monitor repayment performance closely.")
        else:
            officer_guidance.append("Decline politely. Suggest reapplication after history improves.")

        internal_notes = {
            "rationale": summary,
            "policy_context": policy_justification,
            "guidance": " ".join(officer_guidance)
        }

        # 3. BACKWARD COMPATIBLE VIEWS
        # Customer View (Simple string)
        customer_view = f"{customer_message['summary']} {customer_message['key_reasons']} {customer_message['next_steps']}"
        customer_view = customer_view.replace("[", "").replace("]", "") # Strip any accidental machine markers
        
        # Officer View (Technical string)
        officer_view_str = (
            f"DECISION: {decision} ({risk_level} RISK)\n"
            f"Rationale: {internal_notes['rationale']}\n"
            f"Policy: {internal_notes['policy_context']}\n"
            f"Guidance: {internal_notes['guidance']}\n"
            f"Blocking Factors: {', '.join(blocking_factors) if blocking_factors else 'None'}\n"
            f"Risk Score: {risk_score * 100:.1f}%"
        )
        
        # Audit View (Technical justification)
        audit_view = (
            f"POLICY_VERSION: {policy_version}\n"
            f"DECISION: {decision}\n"
            f"ANCHOR_AMOUNT: {decision_metadata.get('capacity_anchor_amount', 0)}\n"
            f"ANCHOR_REASON: {decision_metadata.get('capacity_anchor_reason', 'N/A')}\n"
            f"OBSERVED_DEPOSIT_VOLUME: {metrics.get('observed_deposit_volume', 0):.2f}\n"
            f"TRANSACTION_COUNT: {metrics.get('transaction_count', 0)}\n"
            f"DTI_RATIO: {metrics.get('dti_ratio', 'N/A')}\n"
            f"RISK_SCORE: {risk_score:.4f}\n"
            f"BLOCKING_FACTORS: {blocking_factors}\n"
            f"JUSTIFICATION: {policy_justification}"
        )

        # Behavioral intelligence
        behavioral_stability = metrics.get("behavioral_stability", 0)
        deposit_consistency = metrics.get("income_consistency_score", 0) 
        
        if behavioral_stability > 0 or deposit_consistency > 0:
            behavioral_text = "\n\n[BEHAVIORAL INTELLIGENCE]\n"
            if deposit_consistency > 0:
                consistency_desc = "Excellent" if deposit_consistency > 0.8 else ("Good" if deposit_consistency > 0.6 else "Fair")
                behavioral_text += f"  - Deposit Consistency: {consistency_desc}\n"
            
            if behavioral_stability > 0:
                stability_desc = "High" if behavioral_stability > 0.7 else ("Moderate" if behavioral_stability > 0.5 else "Low")
                behavioral_text += f"  - Transaction Stability: {stability_desc}\n"
            
            officer_view_str += behavioral_text
            audit_view += f"\nBEHAVIORAL_STABILITY: {behavioral_stability:.2f}\nDEPOSIT_CONSISTENCY: {deposit_consistency:.2f}"

        # Final result structure
        result = {
            "decision_summary": decision_summary,
            "customer_message": customer_message,
            "internal_notes": internal_notes,
            "customer_view": "".join(c for c in customer_view if ord(c) < 128),
            "officer_view": "".join(c for c in officer_view_str if ord(c) < 128),
            "audit_view": "".join(c for c in audit_view if ord(c) < 128),
            "blocking_factors": blocking_factors,
            "explanation": "".join(c for c in officer_view_str if ord(c) < 128), # Legacy fallback
            "explanation_source": "engine_deterministic" # Locked V1 Policy
        }

        # V1/V2: Deterministic Policy Lock - NO LLM REPHRASING ALLOWED
        # Compliance requires that narratives are 100% predictable based on inputs.
        
        return result
