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
        question_type = question_type.upper()
        
        # Mapping question types to data retrieval logic
        answers = {
            "WHY_CAPPED": QueryAgent._handle_why_capped(assessment),
            "WHAT_POLICY": QueryAgent._handle_what_policy(assessment),
            "WHAT_NEXT": QueryAgent._handle_what_next(assessment),
            "WHAT_WOULD_CHANGE": QueryAgent._handle_what_change(assessment)
        }
        
        return answers.get(question_type, {
            "answer": "I'm sorry, I can only answer specific questions about policy, caps, and next steps.",
            "available_questions": list(answers.keys())
        })

    @staticmethod
    def _handle_why_capped(assessment: Assessment) -> Dict[str, Any]:
        if assessment.recommended_amount >= assessment.requested_amount:
            return {"answer": "Your loan was not capped; you were approved for the full requested amount based on your transaction activity."}
        
        reasons = []
        if "CAPACITY_SAFETY_LIMIT" in assessment.blocking_factors:
                reasons.append(f"our safety limit of ${assessment.capacity_based_max:,.0f} based on verified deposit volume")
        if "STARTER_LOAN_CAP" in assessment.blocking_factors:
                reasons.append("the initial starter loan policy for new accounts")
        if "MEDIUM_RISK_HAIRCUT" in assessment.blocking_factors:
                reasons.append("a risk adjustment to ensure the loan remains affordable")
                
        reason_str = " and ".join(reasons) if reasons else "institutional safety policies"
        
        return {
            "answer": f"Your loan was capped at ${assessment.recommended_amount:,.0f} due to {reason_str}.",
            "fact": f"Capacity Anchor: ${assessment.capacity_anchor_amount:,.0f} ({assessment.capacity_anchor_reason})"
        }

    @staticmethod
    def _handle_what_policy(assessment: Assessment) -> Dict[str, Any]:
        return {
            "answer": f"This decision was made under policy version {assessment.policy_version}.",
            "details": f"Primary Policy: {assessment.capacity_anchor_reason}. Capacity Multiplier: {assessment.metrics.get('capacity_multiplier_used', 'N/A')}x."
        }

    @staticmethod
    def _handle_what_next(assessment: Assessment) -> Dict[str, Any]:
        # Extract next steps from the customer_view or known patterns
        lines = assessment.customer_view.split('\n')
        next_step = "Review your assessment in the dashboard."
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
