import uuid
from typing import List

import config
import lending_config.capacity_config as cap_config
from models.assessment import Assessment
from models.borrower import Borrower
from models.decision_counterfactual import DecisionCounterfactual, CounterfactualOutcome
from utils.db import Database
from utils.policy_context import policy_value


class DecisionCounterfactualAgent:
    DISCLAIMER = "These insights describe how system policies operate. They do not guarantee approval."

    @staticmethod
    def _format_value(value) -> str:
        if value is None:
            return "N/A"
        if hasattr(value, "value"):
            return str(value.value)
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        return str(value)

    @staticmethod
    def _risk_threshold_for_level(level: str) -> float:
        level_upper = (level or "").upper()
        if level_upper == "LOW":
            return float(policy_value("risk_low_max", config.RISK_LEVEL_THRESHOLDS.get("LOW", (0.0, 0.3))[1]))
        if level_upper == "MEDIUM":
            return float(policy_value("risk_medium_max", config.RISK_LEVEL_THRESHOLDS.get("MEDIUM", (0.3, 0.6))[1]))
        return float(policy_value("risk_high_max", config.RISK_LEVEL_THRESHOLDS.get("HIGH", (0.6, 1.0))[1]))

    @staticmethod
    def _normalize_risk_level(risk_level) -> str:
        if hasattr(risk_level, "value"):
            return str(risk_level.value).upper()
        return str(risk_level).upper()

    @staticmethod
    def _build_counterfactuals(assessment: Assessment, borrower: Borrower) -> List[DecisionCounterfactual]:
        final_outcome = (assessment.final_decision_metadata or {}).get("officer_decision", assessment.decision)
        if final_outcome == "APPROVE":
            return []

        blocking = set((assessment.blocking_factors or []) + (assessment.decision_reason_codes or []))
        metadata = assessment.decision_metadata or {}
        counterfactuals: List[DecisionCounterfactual] = []

        def add_counterfactual(
            factor_name: str,
            current_value,
            required_value,
            policy_rule_id: str,
            impact_description: str,
            outcome_if_met: CounterfactualOutcome
        ):
            counterfactuals.append(DecisionCounterfactual(
                id=f"CF-{uuid.uuid4().hex[:10].upper()}",
                decision_id=assessment.assessment_id,
                factor_name=factor_name,
                current_value=DecisionCounterfactualAgent._format_value(current_value),
                required_value=DecisionCounterfactualAgent._format_value(required_value),
                policy_rule_id=policy_rule_id,
                impact_description=impact_description,
                outcome_if_met=outcome_if_met,
                model_version=config.ML_MODEL_VERSION,
                policy_version=assessment.policy_version
            ))

        if "DURATION_POLICY_VIOLATION" in blocking:
            add_counterfactual(
                factor_name="Requested duration (days)",
                current_value=assessment.requested_duration_days,
                required_value=policy_value("min_duration_days", cap_config.MIN_DURATION_DAYS),
                policy_rule_id="MIN_DURATION_DAYS",
                impact_description="Meeting minimum duration allows the system to evaluate standard capacity rules.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        if "INSUFFICIENT_TRANSACTION_HISTORY" in blocking:
            add_counterfactual(
                factor_name="Verified transaction count",
                current_value=assessment.transaction_count,
                required_value=policy_value("min_transaction_count", cap_config.MIN_TRANSACTION_COUNT),
                policy_rule_id="MIN_TRANSACTION_COUNT",
                impact_description="Additional verified transactions enable a full capacity assessment.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        if "INSUFFICIENT_OBSERVATION_WINDOW" in blocking:
            add_counterfactual(
                factor_name="Verified history days",
                current_value=assessment.history_days,
                required_value=policy_value("min_history_days", cap_config.MIN_HISTORY_DAYS),
                policy_rule_id="MIN_HISTORY_DAYS",
                impact_description="A longer verified history window allows the system to reassess risk and capacity.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        if "HIGH_RISK_SCORE" in blocking or "POLICY_RISK_THRESHOLD_EXCEEDED" in blocking:
            medium_threshold = DecisionCounterfactualAgent._risk_threshold_for_level("MEDIUM")
            add_counterfactual(
                factor_name="Risk score",
                current_value=assessment.risk_score,
                required_value=medium_threshold,
                policy_rule_id="RISK_LEVEL_THRESHOLD_MEDIUM",
                impact_description="A lower risk score moves the application into a lower risk tier for review.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        if "CALCULATED_AMOUNT_ZERO" in blocking or assessment.capacity_based_max == 0:
            add_counterfactual(
                factor_name="Observed deposit volume",
                current_value=assessment.observed_deposit_volume,
                required_value=policy_value("min_capacity_threshold", cap_config.MIN_CAPACITY_THRESHOLD),
                policy_rule_id="MIN_CAPACITY_THRESHOLD",
                impact_description="Meeting the minimum deposit volume enables a non-zero capacity calculation.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        if assessment.recommended_amount and assessment.requested_amount and assessment.recommended_amount < assessment.requested_amount:
            multiplier = cap_config.get_capacity_multiplier(DecisionCounterfactualAgent._normalize_risk_level(assessment.risk_level))
            required_volume = assessment.requested_amount / multiplier
            add_counterfactual(
                factor_name="Observed deposit volume",
                current_value=assessment.observed_deposit_volume,
                required_value=round(required_volume, 2),
                policy_rule_id="CAPACITY_MULTIPLIER",
                impact_description="Higher verified deposit volume increases the capacity-based maximum eligible amount.",
                outcome_if_met=CounterfactualOutcome.APPROVE if final_outcome != "REJECT" else CounterfactualOutcome.REFER
            )

        if assessment.starter_loan_applied:
            add_counterfactual(
                factor_name="Verified history days",
                current_value=assessment.history_days,
                required_value=policy_value("starter_history_threshold_days", cap_config.STARTER_HISTORY_THRESHOLD_DAYS),
                policy_rule_id="STARTER_HISTORY_THRESHOLD_DAYS",
                impact_description="A longer verified history window may remove starter loan caps.",
                outcome_if_met=CounterfactualOutcome.REFER
            )

        return counterfactuals

    @staticmethod
    def get_or_compute(assessment: Assessment, borrower: Borrower, force: bool = False) -> List[DecisionCounterfactual]:
        existing = Database.list_decision_counterfactuals(assessment.assessment_id)
        if existing and not force:
            return existing

        if force and existing:
            Database.delete_decision_counterfactuals(assessment.assessment_id)

        counterfactuals = DecisionCounterfactualAgent._build_counterfactuals(assessment, borrower)
        for cf in counterfactuals:
            Database.save_decision_counterfactual(cf)
        return counterfactuals
