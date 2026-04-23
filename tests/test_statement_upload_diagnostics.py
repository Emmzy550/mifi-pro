from agents.behavioral_agent_v2 import BehavioralAgentV2
from agents.capacity_agent import CapacityAgent
from agents.risk_agent import RiskAgent
from agents.explanation_agent import ExplanationAgent
from models.borrower import Borrower
from models.document import BankStatementSummary, StatementPeriod, Transaction


def test_statement_summary_overrides_noisy_spending_spike_detection():
    transactions = [
        Transaction(
            date="2026-01-01",
            amount=500.0,
            direction="INFLOW",
            description="Parsed salary fragment",
            confidence=0.9,
            currency="ZMW",
        ),
        Transaction(
            date="2026-01-02",
            amount=2500.0,
            direction="OUTFLOW",
            description="Parsed debit fragment",
            confidence=0.9,
            currency="ZMW",
        ),
    ]
    summary = BankStatementSummary(
        total_money_in=10000.0,
        total_money_out=6000.0,
        statement_period=StatementPeriod(start="2025-11-04", end="2026-01-04"),
    )

    results = BehavioralAgentV2.analyze_transactions(transactions, statement_summary=summary)

    assert "SUSPICIOUS_SPENDING_SPIKE (User Upload)" not in results["early_warnings"]
    assert results["observation_window_days"] == 61


def test_starter_policy_explanation_uses_decision_metadata():
    risk_results = {
        "risk_score": 0.35,
        "risk_level": "MEDIUM",
        "flags": [],
        "metrics": {"starter_loan_applied": True},
        "data_source": "USER_UPLOADED_STATEMENT",
    }
    decision_results = {
        "decision": "APPROVE",
        "recommended_amount": 700.0,
        "recommended_duration_days": 30,
        "recommended_interest_rate": 20.0,
        "decision_metadata": {
            "starter_loan_applied": True,
            "capacity_based_max": 1000.0,
            "requested_duration_days": 30,
            "starter_policy_reasons": [
                "verified history spans 61 days, below the 90-day starter threshold"
            ],
        },
    }

    borrower = type(
        "BorrowerStub",
        (),
        {"loan_amount_requested": 5000.0},
    )()

    explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)

    assert "starter loan" in explanation["customer_message"]["summary"].lower()
    assert "61 days" in explanation["internal_notes"]["policy_context"]


def test_capacity_uses_statement_period_for_history_days():
    transactions = [
        Transaction(
            date="2025-11-04",
            amount=1000.0,
            direction="INFLOW",
            description="Credit",
            confidence=0.9,
            currency="ZMW",
        ),
        Transaction(
            date="2026-01-29",
            amount=300.0,
            direction="OUTFLOW",
            description="Noisy parsed tail row",
            confidence=0.9,
            currency="ZMW",
        ),
        Transaction(
            date="2025-12-10",
            amount=1200.0,
            direction="INFLOW",
            description="Credit",
            confidence=0.9,
            currency="ZMW",
        ),
        Transaction(
            date="2025-12-20",
            amount=200.0,
            direction="OUTFLOW",
            description="Debit",
            confidence=0.9,
            currency="ZMW",
        ),
        Transaction(
            date="2026-01-02",
            amount=900.0,
            direction="INFLOW",
            description="Credit",
            confidence=0.9,
            currency="ZMW",
        ),
    ]
    summary = BankStatementSummary(
        total_money_in=20816.19,
        total_money_out=19193.01,
        statement_period=StatementPeriod(start="2025-11-04", end="2026-01-04"),
    )

    results = CapacityAgent.calculate_demonstrated_capacity(
        borrower_id="BOR-TEST",
        risk_level="LOW",
        requested_amount=5000.0,
        external_transactions=transactions,
        statement_summary=summary,
    )

    assert results["history_days"] == 61
    assert results["statement_period_days"] == 61


def test_verified_income_applies_to_affordability_rules(monkeypatch):
    import config

    monkeypatch.setattr(config, "ENABLE_ML_RISK_SCORING", False)

    borrower = Borrower(
        id="BOR-VERIFY",
        organization_id="ORG-TEST",
        name="Test Borrower",
        phone="+260000000000",
        employment_type="salaried",
        monthly_income=1000.0,
        monthly_expenses=500.0,
        existing_debt=0.0,
        loan_amount_requested=5000.0,
        loan_purpose="Working capital",
    )
    transactions = [
        Transaction(date="2025-11-04", amount=1000.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
        Transaction(date="2025-11-20", amount=200.0, direction="OUTFLOW", description="Bills", confidence=0.9, currency="ZMW"),
        Transaction(date="2025-12-04", amount=1000.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
        Transaction(date="2025-12-20", amount=250.0, direction="OUTFLOW", description="Groceries", confidence=0.9, currency="ZMW"),
        Transaction(date="2026-01-04", amount=1000.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
    ]
    summary = BankStatementSummary(
        total_money_in=3000.0,
        total_money_out=450.0,
        statement_period=StatementPeriod(start="2025-11-04", end="2026-01-04"),
    )

    risk_results = RiskAgent.evaluate(
        borrower,
        external_behavioral_results={
            "transactions": transactions,
            "verified_monthly_income": 5564.5,
            "verified_income_source": "PAYSLIP",
            "statement_summary": summary,
            "behavioral_stability": 0.7,
            "saving_trend": 0.7,
            "utility_compliance": 0.7,
            "early_warnings": [],
        },
    )

    assert "CRITICAL: INSUFFICIENT_AFFORDABILITY" not in risk_results["flags"]
    assert risk_results["metrics"]["verified_monthly_income"] == 5564.5
    assert risk_results["metrics"]["risk_income_source"] == "PAYSLIP"


def test_duration_aware_affordability_requests_cap_instead_of_reject(monkeypatch):
    import config

    monkeypatch.setattr(config, "ENABLE_ML_RISK_SCORING", False)

    borrower = Borrower(
        id="BOR-DURATION",
        organization_id="ORG-TEST",
        name="Short Tenor Borrower",
        phone="+260000000000",
        employment_type="salaried",
        monthly_income=6100.0,
        monthly_expenses=0.0,
        existing_debt=0.0,
        loan_amount_requested=5000.0,
        loan_purpose="Working capital",
    )
    transactions = [
        Transaction(date="2025-11-04", amount=2500.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
        Transaction(date="2025-12-04", amount=2500.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
        Transaction(date="2026-01-04", amount=2500.0, direction="INFLOW", description="Salary", confidence=0.9, currency="ZMW"),
    ]
    summary = BankStatementSummary(
        total_money_in=7500.0,
        total_money_out=1200.0,
        statement_period=StatementPeriod(start="2025-11-04", end="2026-01-04"),
    )

    risk_results = RiskAgent.evaluate(
        borrower,
        external_behavioral_results={
            "transactions": transactions,
            "statement_summary": summary,
            "behavioral_stability": 0.7,
            "saving_trend": 0.7,
            "utility_compliance": 0.7,
            "early_warnings": [],
        },
        requested_duration_days=30,
    )

    assert "CRITICAL: INSUFFICIENT_AFFORDABILITY" not in risk_results["flags"]
    assert "WARNING: AFFORDABILITY_CAP_REQUIRED" in risk_results["flags"]
    assert risk_results["metrics"]["affordability_cap_required"] is True
    assert risk_results["metrics"]["affordable_amount"] == 1830.0
