from typing import Dict, Any

class ExplanationAgent:
    """
    Agent responsible for translating technical signals into human language.
    Provides transparency for lenders and borrowers.
    """
    @staticmethod
    def generate(risk_results: Dict[str, Any], decision_results: Dict[str, Any], borrower: Any = None) -> tuple[str, str]:
        """
        Translates technical risk signals and ML predictions into structured, professional explanations.
        Returns a well-formatted explanation with clear sections for loan officer review.
        """
        decision = decision_results["decision"]
        risk_score = risk_results["risk_score"]
        risk_level = risk_results["risk_level"]
        flags = risk_results["flags"]
        metrics = risk_results["metrics"]
        
        sections = []
        
        # =========================================================
        # SECTION 1: EXECUTIVE SUMMARY
        # =========================================================
        requested_amt = borrower.loan_amount_requested if borrower else None
        
        if decision == "APPROVE":
            verdict = "[OK] RECOMMENDED FOR APPROVAL"
            if requested_amt and requested_amt == decision_results['recommended_amount']:
                summary = f"This applicant demonstrates a strong financial profile with minimal risk indicators. Approved for requested amount: ${requested_amt:,.0f}."
            elif requested_amt:
                summary = f"This applicant demonstrates a strong financial profile. Requested: ${requested_amt:,.0f} | Recommended: ${decision_results['recommended_amount']:,.0f}."
            else:
                summary = "This applicant demonstrates a strong financial profile with minimal risk indicators."
        elif decision == "CONDITIONAL":
            verdict = "[WARN] CONDITIONAL APPROVAL RECOMMENDED"
            if requested_amt:
                summary = f"This applicant shows acceptable risk with adjusted terms. Requested: ${requested_amt:,.0f} | Recommended: ${decision_results['recommended_amount']:,.0f} at {decision_results['recommended_interest_rate']:.1f}% interest."
            else:
                summary = f"This applicant shows acceptable risk levels with adjusted terms: ${decision_results['recommended_amount']:,.0f} at {decision_results['recommended_interest_rate']:.1f}% interest."
        else:
            verdict = "[REJECT] REJECTION RECOMMENDED"
            if requested_amt:
                summary = f"This applicant's risk profile exceeds institutional safety thresholds. Requested: ${requested_amt:,.0f} | Recommended: $0 (Decline)."
            else:
                summary = "This applicant's risk profile exceeds institutional safety thresholds."
        
        sections.append(f"[DECISION] {verdict}")
        sections.append(f"\n{summary}")
        
        # =========================================================
        # SECTION 2: RISK ASSESSMENT DETAILS
        # =========================================================
        sections.append(f"\n\n[RISK ASSESSMENT]")
        sections.append(f"Overall Risk Score: {risk_score * 100:.1f}% ({risk_level} RISK)")
        
        # Policy Compliance Check
        if flags:
            sections.append(f"\nPolicy Flags Detected ({len(flags)}):")
            for flag in flags:
                flag_readable = flag.replace('_', ' ').title()
                sections.append(f"  - {flag_readable}")
        else:
            sections.append("\n[OK] All institutional lending policies satisfied.")

        # [DECISION RATIONALE] (Mandatory between sections)
        sections.append("\n\n[DECISION RATIONALE]")
        sections.append("The final recommendation prioritizes institutional lending policies and observed borrower behavior, with AI signals used for additional context.")
        
        # =========================================================
        # SECTION 3: BEHAVIORAL INTELLIGENCE (V2 Metrics)
        # =========================================================
        behavioral_stability = metrics.get("behavioral_stability", 0)
        income_consistency = metrics.get("income_consistency_score", 0)
        savings_trend = metrics.get("saving_trend", 0)
        utility_compliance = metrics.get("utility_compliance", 0)
        
        # Only show behavioral section if we have data
        if behavioral_stability > 0 or income_consistency > 0:
            sections.append(f"\n\n[BEHAVIORAL INTELLIGENCE]")
            
            # Transparency Note for Pilot Data
            data_source = risk_results.get("data_source", "INTERNAL_HISTORY")
            if data_source == "USER_UPLOADED_STATEMENT":
                sections.append("Data Source: User-provided transaction statement")
                sections.append("NOTE: Insights based on uploaded data; subject to verification.")
                sections.append("Behavioral signals are advisory and weighted conservatively (max 20% impact).")
                sections.append("") # Spacer
                
            sections.append("Alternative data analysis summary:")
            
            if income_consistency > 0:
                consistency_desc = "Excellent" if income_consistency > 0.8 else ("Good" if income_consistency > 0.6 else "Fair")
                sections.append(f"  - Income Consistency: {consistency_desc}")
            
            if behavioral_stability > 0:
                stability_desc = "High" if behavioral_stability > 0.7 else ("Moderate" if behavioral_stability > 0.5 else "Low")
                sections.append(f"  - Transaction Stability: {stability_desc}")
            
            if savings_trend != 0:
                if savings_trend > 0.1:
                    sections.append(f"  - Savings Behavior: Positive trend observed")
                elif savings_trend < -0.1:
                    sections.append(f"  - Savings Behavior: Negative trend observed")
            
            if utility_compliance > 0:
                compliance_desc = "Excellent" if utility_compliance > 0.9 else ("Good" if utility_compliance > 0.8 else "Fair")
                sections.append(f"  - Utility Payment Compliance: {compliance_desc}")
        
        # Behavioral warnings/alerts
        behavioral_flags = [f for f in flags if "CAUTION" in f or f in ["SUSPICIOUS_SPENDING_SPIKE", "MISSED_UTILITY_PAYMENT", "LOW_UTILITY_COMPLIANCE"]]
        if behavioral_flags:
            sections.append(f"\n\n[WARNING: BEHAVIORAL ALERTS]")
            for flag in behavioral_flags:
                flag_readable = flag.replace('CAUTION: ', '').replace('_', ' ').title()
                sections.append(f"  - {flag_readable}")
            sections.append("These patterns may indicate financial stress or instability.")

        # =========================================================
        # SECTION 4: FORWARD-LOOKING AI SIGNAL (ML Insights)
        # =========================================================
        ml_prob = metrics.get("ml_prob_default")
        if ml_prob is not None:
            sections.append(f"\n\n[FORWARD-LOOKING AI SIGNAL]")
            sections.append("The AI model identifies patterns associated with elevated future repayment risk.")
            sections.append("This signal is advisory and has been evaluated alongside institutional policies and observed borrower behavior.")
            
            # Top influencing factors (SHAP) - Optional but useful if present
            features = metrics.get("ml_feature_importance", [])
            if features:
                sections.append(f"\nModel Context (Top Influencing Factors):")
                for i, feature in enumerate(features[:3], 1):  # Show top 3
                    feature_name = feature['feature'].replace('_', ' ').title()
                    impact = feature['impact']
                    impact_desc = "elevates" if impact > 0 else "reduces"
                    sections.append(f"  {i}. {feature_name} ({impact_desc} forward-looking risk profile)")
        
        # =========================================================
        # SECTION 5: RECOMMENDATIONS FOR LOAN OFFICER
        # =========================================================
        sections.append(f"\n\n[OFFICER GUIDANCE]")
        
        if decision == "APPROVE":
            sections.append("- Proceed with standard loan terms and documentation.")
            sections.append("- Consider this applicant for relationship banking opportunities.")
        elif decision == "CONDITIONAL":
            sections.append(f"- Offer modified terms: ${decision_results['recommended_amount']:,.0f} at {decision_results['recommended_interest_rate']:.1f}% APR.")
            sections.append("- Require additional collateral or guarantor if available.")
            sections.append("- Schedule follow-up review in 6 months for potential term improvement.")
        else:
            sections.append("- Politely decline application with explanation of key concerns.")
            if "HIGH_DEBT_TO_INCOME" in flags or "INSUFFICIENT_INCOME" in flags:
                sections.append("- Suggest applicant reduce existing debt or increase income before reapplying.")
            if "NO_CREDIT_HISTORY" in flags:
                sections.append("- Recommend building credit history through smaller financial products first.")
            sections.append("- Invite reapplication in 3-6 months after addressing identified issues.")
        
        full_text = "".join(sections)
        # Final safety: strip any non-ASCII characters that might trip up Windows terminals
        deterministic_explanation = "".join(c for c in full_text if ord(c) < 128)

        # =========================================================
        # V4: OPTIONAL LLM REPHRASING (VERTEX AI)
        # =========================================================
        import config
        from llm.vertex_client import VertexClient
        from agents.audit_agent import AuditAgent

        if config.ENABLE_LLM_EXPLANATIONS:
            # 1. Prepare structured payload ONLY (NO PII)
            # DO NOT pass Names, IDs, or raw transactions
            payload = {
                "decision": decision,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "recommended_amount": decision_results.get("recommended_amount"),
                "interest_rate": decision_results.get("recommended_interest_rate"),
                "flags": flags,
                "behavioral_summary": {
                    "stability": metrics.get("behavioral_stability"),
                    "income_consistency": metrics.get("income_consistency_score"),
                    "utility_compliance": metrics.get("utility_compliance")
                },
                "policy_result": "PASSED" if not flags else f"DETECTED_{len(flags)}_FLAGS",
                "officer_guidance": sections[-5:] # Last few recommendations
            }

            # 2. Call Vertex AI for rephrasing
            rephrased = VertexClient.rephrase(payload)

            if rephrased:
                # 3. Log LLM usage for audit
                AuditAgent.log_event("LLM_REPHRASE_SUCCESS", "SYSTEM", {
                    "llm_used": True,
                    "llm_provider": "vertex_ai",
                    "llm_role": "explanation_only",
                    "engine_decision_locked": True,
                    "model_name": config.VERTEX_MODEL_NAME
                })
                return rephrased, "vertex_ai"
            else:
                # Fallback logged automatically by VertexClient or manually here
                AuditAgent.log_event("LLM_REPHRASE_FAILED", "SYSTEM", {"reason": "Fallback to engine text"})
        
        return deterministic_explanation, "engine"
