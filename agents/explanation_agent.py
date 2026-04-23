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
        data_quality_score = decision_metadata.get("data_quality_score")
        data_quality_issues = []
        if data_quality_score is not None:
            try:
                import config
                from utils.policy_context import policy_value
                threshold = float(policy_value("data_quality_refer_threshold", config.DATA_QUALITY_REFER_THRESHOLD))
                if data_quality_score < threshold:
                    data_quality_issues.append(f"DATA_QUALITY_BELOW_THRESHOLD:{data_quality_score:.2f}")
            except Exception:
                data_quality_issues.append(f"DATA_QUALITY_SCORE:{data_quality_score}")
        
        # Initial Rationale components
        summary = ""
        policy_justification = ""
        customer_summary = ""
        action_item = ""
        
        # =========================================================
        # SECTION 1: EXECUTIVE SUMMARY
        # =========================================================
        # =========================================================
        # SECTION 1: EXECUTIVE SUMMARY
        # =========================================================
        requested_amt = borrower.loan_amount_requested if borrower else None
        
        is_starter = bool(
            decision_metadata.get("starter_loan_applied") or
            metrics.get("starter_loan_applied") or
            "STARTER_LOAN_APPROVED_LIMITED_HISTORY" in flags
        )
        policy_cap_reason = str(decision_metadata.get("policy_cap_reason") or "")
        is_affordability_cap = policy_cap_reason.startswith("AFFORDABILITY_CAP")
        starter_policy_reasons = decision_metadata.get("starter_policy_reasons") or []
        is_equality = requested_amt is not None and abs(requested_amt - (decision_results.get('recommended_amount') or 0)) < 0.01

        # HANDLE REFER (Manual Review)
        if decision == "REFER":
            decision_summary = "Application deferred for manual review."
            summary = "Automated processing was paused due to data requirements or policy flags."
            
            customer_summary = "We are reviewing your application manually and will contact you shortly."
            action_item = "No immediate action required. Our team will reach out if we need more documents."
            policy_justification = "System could not automatically adjudicate based on available data (e.g., insufficient observation window)."

            is_insufficient_window = any("OBSERVATION_WINDOW" in f.upper() for f in blocking_factors)
            
            if is_insufficient_window:
                win_days = decision_metadata.get('observation_window_days', 0)
                win_str = "1 day" if win_days == 1 else f"{win_days} days"
                policy_justification = f"Income verified but observation window ({win_str}) is below the required 30-day threshold."
                customer_summary = "We verified your income, but we need to see a longer history of activity before proceeding."
                action_item = "Please continue using your account to build history."

        # HANDLE APPROVE (Strict Invariant: amount > 0)
        elif decision == "APPROVE":
            decision_summary = "Application approved based on policy compliance."
            
            # Common policy justification for all approvals
            # FIX: Distinguish between Capacity and Policy Cap
            if decision_metadata.get("policy_cap_amount") and decision_metadata.get("policy_cap_amount") == decision_results['recommended_amount']:
                 policy_justification = f"The amount is capped at the policy limit of ${decision_results['recommended_amount']:,.0f} (Reason: {decision_metadata.get('policy_cap_reason', 'Policy Limit')})."
            else:
                 policy_justification = f"The recommended amount is within the policy-defined lending limit of ${decision_results['recommended_amount']:,.0f}."
            
            action_item = "Review the offer details and accept to proceed."
            
            if is_affordability_cap:
                req_dur = decision_metadata.get("requested_duration_days") or decision_results.get("recommended_duration_days")
                affordable_limit = decision_metadata.get("affordable_amount") or decision_results.get("recommended_amount")
                summary = (
                    f"Applicant approved with a duration-aware cap. Requested: ${requested_amt:,.0f} | "
                    f"Recommended: ${decision_results['recommended_amount']:,.0f}."
                )
                customer_summary = (
                    f"We've approved ${decision_results['recommended_amount']:,.0f} for the requested "
                    f"{req_dur}-day repayment window."
                )
                if affordable_limit and decision_results.get("recommended_amount") is not None:
                    if abs(float(affordable_limit) - float(decision_results["recommended_amount"])) > 0.01:
                        policy_justification = (
                            f"The requested {req_dur}-day repayment window supports up to "
                            f"${float(affordable_limit):,.0f} based on the current disposable budget. "
                            f"A further risk adjustment produced the final offer of "
                            f"${decision_results['recommended_amount']:,.0f}."
                        )
                    else:
                        policy_justification = (
                            f"The requested {req_dur}-day repayment window supports up to "
                            f"${float(affordable_limit):,.0f} based on the current disposable budget, "
                            f"so the request was reduced to that level."
                        )
                if is_starter and starter_policy_reasons:
                    policy_justification += (
                        " Starter policy also remains active because "
                        + "; ".join(starter_policy_reasons)
                        + "."
                    )
            elif is_starter:
                starter_cap_amount = decision_metadata.get("capacity_based_max") or decision_results.get("recommended_amount")
                starter_reason_text = (
                    "; ".join(starter_policy_reasons)
                    if starter_policy_reasons else
                    "limited verified history"
                )
                summary = f"Applicant approved under starter policy. Requested: ${requested_amt:,.0f} | Recommended: ${decision_results['recommended_amount']:,.0f}."
                customer_summary = (
                    f"We've approved a starter loan of ${decision_results['recommended_amount']:,.0f} while you build more verified history."
                )
                if starter_cap_amount and decision_results.get("recommended_amount") is not None:
                    if abs(float(starter_cap_amount) - float(decision_results["recommended_amount"])) > 0.01:
                        policy_justification = (
                            f"Starter-loan policy applied because {starter_reason_text}. "
                            f"The request was first limited to ${float(starter_cap_amount):,.0f} before the final offer of "
                            f"${decision_results['recommended_amount']:,.0f}."
                        )
                    else:
                        policy_justification = (
                            f"Starter-loan policy applied because {starter_reason_text}. "
                            f"The current verified history supports a starter limit of ${float(starter_cap_amount):,.0f}."
                        )
            elif is_equality:
                summary = "This applicant demonstrates a stable financial profile with favorable behavioral indicators."
                customer_summary = "Great news! Your application meets our standard criteria, and we're happy to recommend approval for the full amount."
            else:
                summary = f"Applicant approved with adjusted terms. Requested: ${requested_amt:,.0f} | Recommended: ${decision_results['recommended_amount']:,.0f}."
                customer_summary = f"We've reviewed your request and can offer a loan of ${decision_results['recommended_amount']:,.0f}."
                
                # Logic for Starter/Risk adjustments
                customer_summary = f"We've approved a loan of ${decision_results['recommended_amount']:,.0f} which aligns with our current lending limits for your account."

                # Duration adjustment context for customer
                req_dur = decision_metadata.get("requested_duration_days")
                rec_dur = decision_results.get("recommended_duration_days")
                if req_dur and rec_dur and rec_dur < req_dur:
                    if is_starter:
                        customer_summary += " This loan is approved for a shorter period to help build your repayment history."
                    else:
                        customer_summary += f" We've adjusted your loan term to {rec_dur} days to align with our lending policy."

        # HANDLE REJECT (Strict Invariant: amount == 0)
        else: # REJECT
            decision_summary = "Application declined as it does not currently meet policy thresholds."
            summary = "Application does not meet lending thresholds for approval."
            
            customer_summary = "We cannot proceed with this application at the present time."
            action_item = "Feel free to reapply in 3-6 months as your transaction record grows."
            policy_justification = "Application does not meet minimum eligibility criteria for a capacity assessment."
            
            if metrics.get("observed_deposit_volume", 0) == 0:
                summary = "Application declined due to insufficient financial history."
                customer_summary = "We weren't able to find enough recent transaction activity to establish a lending limit at this time."
                policy_justification = "No verifiable deposit activity was found within the required observation window."
                action_item = "Ensure you have at least 30 days of consistent activity before reapplying."
            elif any("CRITICAL" in f for f in flags):
                summary = "Application declined due to critical policy violations."
                customer_summary = "We cannot approve this request due to specific policy restrictions on your account."

        
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
                customer_message["key_reasons"] = "We couldn't verify enough recent deposit activity to establish a lending limit today."
            else:
                customer_message["key_reasons"] = "Your current transaction activity doesn't quite meet our lending thresholds for this particular request."
        elif is_starter:
            customer_message["key_reasons"] = "As you're establishing your record with us, we've started with a safe lending limit that can grow over time."
        elif is_affordability_cap:
            customer_message["key_reasons"] = "We matched the offer to what fits the requested repayment window using your current budget."

        # 2. INTERNAL DECISION NOTES (For Officers & Risk Teams)
        officer_guidance = []
        if decision == "APPROVE":
            officer_guidance.append("Proceed with standard documentation.")
        elif decision == "REFER":
            officer_guidance.append("Manual review required. Check document completeness.")
        else: # REJECT
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
            f"Risk Score: {risk_score * 100:.1f}%\n"
            f"Data Source: {risk_results.get('data_source', 'Internal Records')}"
        )
        
        # Add Duration to Officer View if adjusted
        req_dur = decision_metadata.get("requested_duration_days")
        rec_dur = decision_results.get("recommended_duration_days")
        if req_dur and rec_dur and req_dur != rec_dur:
            duration_note = f"Requested: {req_dur} days | Recommended: {rec_dur} days"
            duration_adjustments = [a for a in decision_metadata.get("adjustments_applied", []) 
                                   if "DURATION" in str(a.get("type", ""))]
            if duration_adjustments:
                reason = duration_adjustments[0].get("reason", "policy adjustment")
                duration_note += f" ({reason})"
            officer_view_str += f"\nDURATION: {duration_note}"
        
        # Audit View (Technical justification)
        audit_view = (
            f"POLICY_VERSION: {policy_version}\n"
            f"DECISION: {decision}\n"
            f"AFFORDABILITY_CAPACITY: {decision_metadata.get('capacity_based_max', 0)}\n"
            f"AFFORDABLE_AMOUNT: {decision_metadata.get('affordable_amount', 'N/A')}\n"
            f"AFFORDABILITY_RATIO: {decision_metadata.get('affordability_ratio', 'N/A')}\n"
            f"AFFORDABILITY_TERM_MONTHS: {decision_metadata.get('affordability_term_months', 'N/A')}\n"
            f"POLICY_LIMIT: {decision_metadata.get('policy_cap_amount', 'N/A')}\n"
            f"LIMIT_REASON: {decision_metadata.get('policy_cap_reason', 'N/A')}\n"
            f"OBSERVED_DEPOSIT_VOLUME: {metrics.get('observed_deposit_volume', 0):.2f}\n"
            f"TRANSACTION_COUNT: {metrics.get('transaction_count', 0)}\n"
            f"DTI_RATIO: {metrics.get('dti_ratio', 'N/A')}\n"
            f"RISK_SCORE: {risk_score:.4f}\n"
            f"REQUESTED_DURATION_DAYS: {decision_metadata.get('requested_duration_days', 'N/A')}\n"
            f"RECOMMENDED_DURATION_DAYS: {decision_results.get('recommended_duration_days', 'N/A')}\n"
            f"BLOCKING_FACTORS: {blocking_factors}\n"
            f"JUSTIFICATION: {policy_justification}"
        )
        
        if decision_results.get("interest_rate_basis"):
            audit_view += f"\nINTEREST_RATE_BASIS: {decision_results['interest_rate_basis']}"

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

        adverse_action = {
            "decision": decision,
            "policy_constraints": blocking_factors,
            "data_quality_issues": data_quality_issues,
            "primary_reason_codes": blocking_factors if blocking_factors else [],
            "next_steps": action_item
        }

        # Final result structure
        result = {
            "decision_summary": decision_summary,
            "customer_message": customer_message,
            "internal_notes": internal_notes,
            "customer_view": "".join(c for c in customer_view if ord(c) < 128),
            "officer_view": "".join(c for c in officer_view_str if ord(c) < 128),
            "audit_view": "".join(c for c in audit_view if ord(c) < 128),
            "blocking_factors": blocking_factors,
            "adverse_action": adverse_action,
            "explanation": "".join(c for c in officer_view_str if ord(c) < 128), # Legacy fallback
            "explanation_source": "engine_deterministic" # Locked V1 Policy
        }

        # V1/V2: Deterministic Policy Lock - NO LLM REPHRASING ALLOWED
        # Compliance requires that narratives are 100% predictable based on inputs.
        
        return result
