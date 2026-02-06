from typing import Dict, Any, Optional
from models.assessment import Assessment

class QueryAgent:
    """
    Deterministic query handler for the "Ask Why" capability.
    Answers specific questions using ONLY the structured facts in an Assessment.
    No LLM hallucination. No new data.
    """
    
    @staticmethod
    def answer(assessment: Assessment, question_type: str) -> Dict[str, Any]:
        """
        Maps a question type to a factual answer from the assessment.
        """
        question_type = (question_type or "").upper().strip()
        
        # Mapping question types to data retrieval logic
        answers = {
            "WHY_DECISION": QueryAgent._handle_why_decision(assessment),
            "WHY_REJECTED": QueryAgent._handle_why_rejected(assessment),
            "WHY_APPROVED": QueryAgent._handle_why_approved(assessment),
            "WHY_REFERRED": QueryAgent._handle_why_referred(assessment),
            "WHY_CAPPED": QueryAgent._handle_why_capped(assessment),
            "WHAT_POLICY": QueryAgent._handle_what_policy(assessment),
            "DATA_QUALITY": QueryAgent._handle_data_quality(assessment),
            "DATA_USED": QueryAgent._handle_data_used(assessment),
            "WHAT_NEXT": QueryAgent._handle_what_next(assessment),
            "WHAT_WOULD_CHANGE": QueryAgent._handle_what_change(assessment)
        }
        
        return answers.get(question_type, {
            "answer": "I can only answer specific, predefined questions based on this decision record.",
            "available_questions": list(answers.keys())
        })

    @staticmethod
    def _decision_value(decision: Any) -> str:
        if hasattr(decision, "value"):
            return str(decision.value)
        value = str(decision)
        return value.replace("Decision.", "")

    @staticmethod
    def _humanize_code(value: str) -> str:
        if not value:
            return ""
        tokens = str(value).replace("Decision.", "").split("_")
        keep_upper = {"DTI", "NRC", "SMS", "USSD", "ML", "API"}
        normalized = []
        for token in tokens:
            if token.upper() in keep_upper:
                normalized.append(token.upper())
            else:
                normalized.append(token.lower().capitalize())
        return " ".join(normalized)

    @staticmethod
    def _clean_reason_list(values: Optional[list]) -> list:
        if not values:
            return []
        cleaned = []
        for value in values:
            text = QueryAgent._humanize_code(value)
            text = " ".join(text.split())
            if text:
                cleaned.append(text)
        return cleaned

    @staticmethod
    def _dedupe_preserve(items: list) -> list:
        seen = set()
        output = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            output.append(item.strip())
        return output

    @staticmethod
    def _handle_why_decision(assessment: Assessment) -> Dict[str, Any]:
        decision = QueryAgent._decision_value(assessment.decision)
        sentences = [f"Decision: {decision}."]
        source_fields = ["decision"]

        primary = QueryAgent._clean_reason_list(assessment.blocking_factors)
        secondary = QueryAgent._clean_reason_list(assessment.decision_reason_codes)

        if primary:
            display_reasons = QueryAgent._dedupe_preserve(primary)
            source_fields.append("blocking_factors")
        elif secondary:
            display_reasons = QueryAgent._dedupe_preserve(secondary)
            source_fields.append("decision_reason_codes")
        else:
            display_reasons = []

        if display_reasons:
            if len(display_reasons) > 5:
                display_reasons = display_reasons[:5]
            sentences.append(f"Primary factors: {'; '.join(display_reasons)}.")
            if primary and secondary:
                secondary_only = [
                    r for r in secondary
                    if r.lower() not in {p.lower() for p in primary}
                ]
                if secondary_only:
                    sentences.append("Additional policy tags are recorded in the decision file.")
                    source_fields.append("decision_reason_codes")

        if assessment.policy_cap_reason:
            sentences.append(f"Policy cap applied: {QueryAgent._humanize_code(assessment.policy_cap_reason)}.")
            source_fields.append("policy_cap_reason")

        if assessment.data_quality_score is not None:
            sentences.append(f"Data quality score: {assessment.data_quality_score:.2f}.")
            source_fields.append("data_quality_score")

        if len(sentences) == 1:
            sentences.append("Decision followed standard policy thresholds for this application.")
            source_fields.append("policy_version")

        return {
            "answer": " ".join(sentences),
            "source_fields": list(sorted(set(source_fields)))
        }

    @staticmethod
    def _handle_why_rejected(assessment: Assessment) -> Dict[str, Any]:
        if QueryAgent._decision_value(assessment.decision) != "REJECT":
            return {
                "answer": f"This decision is {QueryAgent._decision_value(assessment.decision)}, so rejection reasons do not apply.",
                "source_fields": ["decision"]
            }
        reasons = assessment.blocking_factors or assessment.decision_reason_codes or []
        reason_text = ", ".join(QueryAgent._humanize_code(r) for r in reasons) if reasons else "policy thresholds were not met"
        return {
            "answer": f"The application was rejected because {reason_text}.",
            "source_fields": ["blocking_factors", "decision_reason_codes"]
        }

    @staticmethod
    def _handle_why_approved(assessment: Assessment) -> Dict[str, Any]:
        if QueryAgent._decision_value(assessment.decision) not in ["APPROVE", "CONDITIONAL"]:
            return {
                "answer": f"This decision is {QueryAgent._decision_value(assessment.decision)}, so approval reasons do not apply.",
                "source_fields": ["decision"]
            }
        reasons = []
        if assessment.policy_cap_reason:
            reasons.append(f"Policy cap applied: {assessment.policy_cap_reason}")
        if assessment.capacity_based_max:
            reasons.append(f"Capacity-based limit: {assessment.capacity_based_max}")
        if not reasons:
            reasons.append("The request met policy thresholds and capacity checks.")
        return {
            "answer": "Approval is based on: " + "; ".join(reasons),
            "source_fields": ["policy_cap_reason", "capacity_based_max"]
        }

    @staticmethod
    def _handle_why_referred(assessment: Assessment) -> Dict[str, Any]:
        if QueryAgent._decision_value(assessment.decision) != "REFER":
            return {
                "answer": f"This decision is {QueryAgent._decision_value(assessment.decision)}, so referral reasons do not apply.",
                "source_fields": ["decision"]
            }
        reasons = assessment.blocking_factors or []
        if not reasons:
            reasons = ["manual review required based on available data constraints"]
        return {
            "answer": f"The application was referred for manual review due to: {', '.join(QueryAgent._humanize_code(r) for r in reasons)}.",
            "source_fields": ["blocking_factors"]
        }

    @staticmethod
    def _handle_why_capped(assessment: Assessment) -> Dict[str, Any]:
        recommended_amount = assessment.recommended_amount
        requested_amount = assessment.requested_amount

        # Guard against None values in non-approval decisions
        if recommended_amount is None or requested_amount is None:
            return {
                "answer": "This decision does not include a capped loan amount."
            }

        if recommended_amount >= requested_amount:
            return {
                "answer": "Your loan was not capped; you were approved for the full requested amount based on your transaction activity."
            }
        
        reasons = []
        blocking_factors = assessment.blocking_factors or []
        if "CAPACITY_SAFETY_LIMIT" in blocking_factors:
            reasons.append(f"our safety limit of ${assessment.capacity_based_max:,.0f} based on verified deposit volume")
        if "STARTER_LOAN_CAP" in blocking_factors:
            reasons.append("the initial starter loan policy for new accounts")
        if "MEDIUM_RISK_HAIRCUT" in blocking_factors:
            reasons.append("a risk adjustment to ensure the loan remains affordable")
                
        reason_str = " and ".join(reasons) if reasons else "institutional safety policies"
        
        return {
            "answer": f"Your loan was capped at ${assessment.recommended_amount:,.0f} due to {reason_str}.",
            "fact": f"Policy Limit: ${assessment.policy_cap_amount:,.0f} ({assessment.policy_cap_reason})" if assessment.policy_cap_amount else f"Capacity Limit: ${assessment.capacity_based_max:,.0f}"
        }

    @staticmethod
    def _handle_what_policy(assessment: Assessment) -> Dict[str, Any]:
        return {
            "answer": f"This decision was made under policy version {assessment.policy_version}.",
            "details": f"Primary Constraint: {assessment.policy_cap_reason or 'Affordability'}. Capacity Multiplier: {assessment.metrics.get('capacity_multiplier_used', 'N/A')}x."
        }

    @staticmethod
    def _handle_data_quality(assessment: Assessment) -> Dict[str, Any]:
        if assessment.data_quality_score is None:
            return {
                "answer": "This decision record does not include a data quality score.",
                "source_fields": ["data_quality_score"]
            }
        impact = None
        if assessment.decision_metadata:
            impact = assessment.decision_metadata.get("data_quality_impact")
        return {
            "answer": f"Data quality score is {assessment.data_quality_score:.2f}. {impact or ''}".strip(),
            "source_fields": ["data_quality_score", "decision_metadata"]
        }

    @staticmethod
    def _handle_data_used(assessment: Assessment) -> Dict[str, Any]:
        data_used = assessment.data_used or {}
        provenance = assessment.data_provenance or {}
        sources = data_used.get("data_sources", []) or provenance.get("data_sources", [])
        tx_days = data_used.get("transaction_days")
        tx_count = data_used.get("transaction_count")
        return {
            "answer": f"Data sources: {', '.join(sources) if sources else 'Not specified'}. "
                      f"Transaction days: {tx_days if tx_days is not None else 'N/A'}, "
                      f"Transaction count: {tx_count if tx_count is not None else 'N/A'}.",
            "source_fields": ["data_used", "data_provenance"]
        }

    @staticmethod
    def _handle_what_next(assessment: Assessment) -> Dict[str, Any]:
        next_step = "Review your assessment in the dashboard."
        if assessment.customer_message and isinstance(assessment.customer_message, dict):
            next_step = assessment.customer_message.get("next_steps") or next_step
        elif assessment.customer_view:
            lines = assessment.customer_view.split('\n')
            for line in lines:
                if "Next Step:" in line:
                    next_step = line.replace("Next Step:", "").strip()
                
        return {
            "answer": f"The recommended next step is: {next_step}",
            "actionable": True
        }

    @staticmethod
    def _handle_what_change(assessment: Assessment) -> Dict[str, Any]:
        if assessment.decision == "APPROVE":
            return {"answer": "You are already approved. Maintaining consistent transaction activity will help you access higher limits in the future."}
            
        factors = []
        if "INSUFFICIENT_TRANSACTION_HISTORY" in assessment.blocking_factors:
            factors.append("continuing to use your account to build a longer record of transaction activity (minimum 30-90 days)")
        if "HIGH_RISK_SCORE" in assessment.blocking_factors:
            factors.append("improving the balance between your deposits and expenses")
            
        if not factors:
            factors.append("increasing your verified deposit volume over the next 3-6 months")
            
        return {
            "answer": f"To improve future decisions, we recommend " + " and ".join(factors) + ".",
            "timeframe": "3-6 months"
        }
