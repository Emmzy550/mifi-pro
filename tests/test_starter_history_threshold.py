from datetime import datetime, timedelta, timezone

import lending_config.capacity_config as cap_config
from agents.capacity_agent import CapacityAgent
from agents.decision_agent import DecisionAgent
from models.alternative_data import MobileMoneyTransaction
from models.borrower import Borrower
from utils.policy_context import reset_policy_context, set_policy_context


def _build_borrower() -> Borrower:
    return Borrower(
        id="BOR-STARTER-THRESHOLD",
        organization_id="ORG-TEST",
        name="Starter Threshold Borrower",
        phone="+260970000000",
        employment_type="trader",
        monthly_income=12000,
        monthly_expenses=2500,
        existing_debt=0,
        loan_amount_requested=2000,
        loan_purpose="Working capital",
    )


def _build_transactions() -> list[MobileMoneyTransaction]:
    now = datetime(2026, 3, 30, tzinfo=timezone.utc)
    transactions: list[MobileMoneyTransaction] = []

    for days_ago in range(0, 100, 10):
        transactions.append(
            MobileMoneyTransaction(
                transaction_id=f"TX-INFLOW-{days_ago}",
                amount=1000,
                type="DEPOSIT",
                timestamp=now - timedelta(days=days_ago),
            )
        )

    transactions.append(
        MobileMoneyTransaction(
            transaction_id="TX-OUTFLOW-100",
            amount=200,
            type="PAYMENT",
            timestamp=now - timedelta(days=100),
        )
    )
    return transactions


def _run_threshold_scenario(threshold_days: int) -> tuple[dict, dict]:
    borrower = _build_borrower()
    policy_token = set_policy_context({"starter_history_threshold_days": threshold_days})
    try:
        capacity = CapacityAgent.calculate_demonstrated_capacity(
            borrower_id=borrower.id,
            risk_level="LOW",
            requested_amount=borrower.loan_amount_requested,
            external_transactions=_build_transactions(),
        )

        risk_data = {
            "risk_level": "LOW",
            "flags": [],
            "capacity_validation": capacity,
            "metrics": {
                "affordable_amount": 10000.0,
                "affordability_ratio": 0.2,
                "affordability_cap_required": False,
                "affordability_term_months": 1.5,
            },
        }
        decision = DecisionAgent.recommend(risk_data, borrower, 45)
        return capacity, decision
    finally:
        reset_policy_context(policy_token)


def test_starter_history_threshold_policy_override_changes_classification():
    default_capacity, _ = _run_threshold_scenario(90)
    stricter_capacity, _ = _run_threshold_scenario(120)

    assert default_capacity["history_days"] == 100
    assert default_capacity["starter_loan_applied"] is False
    assert default_capacity["capacity_based_max"] > cap_config.STARTER_LOAN_CAP

    assert stricter_capacity["history_days"] == 100
    assert stricter_capacity["starter_loan_applied"] is True
    assert stricter_capacity["capacity_based_max"] == cap_config.STARTER_LOAN_CAP


def test_starter_history_threshold_policy_override_changes_decision_terms():
    _, default_decision = _run_threshold_scenario(90)
    _, stricter_decision = _run_threshold_scenario(120)

    assert default_decision["recommended_amount"] == 2000
    assert default_decision["recommended_duration_days"] == 45
    assert default_decision["decision_metadata"]["starter_loan_applied"] is False

    assert stricter_decision["recommended_amount"] == cap_config.STARTER_LOAN_CAP
    assert stricter_decision["recommended_duration_days"] == cap_config.STARTER_LOAN_MAX_DURATION_DAYS
    assert stricter_decision["decision_metadata"]["starter_loan_applied"] is True
    assert stricter_decision["decision_metadata"]["starter_history_threshold_days"] == 120
    assert any(
        "120-day starter threshold" in reason
        for reason in stricter_decision["decision_metadata"]["starter_policy_reasons"]
    )
