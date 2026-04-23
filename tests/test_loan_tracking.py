import asyncio
import os
import uuid
from datetime import date, datetime, timedelta

from api import (
    confirm_disbursement,
    get_loan_tracker_detail,
    get_loan_tracker_workspace,
    loan_disburse,
    record_loan_tracking_event,
    setup_loan_tracking,
)
from models.assessment import Assessment, Decision, RiskLevel
from models.borrower import Borrower, EmploymentType
from models.loan_tracking import (
    CollectionChannel,
    IncomeCycle,
    LoanCollectionEventType,
    LoanTrackingEventCreate,
    LoanTrackingSetupRequest,
    RepaymentFrequency,
)
from models.user import User, UserRole
from services.borrower_profile_service import BorrowerProfileService
from utils.db import Database, MockFirestore


def _bootstrap_temp_db():
    original_db_file = MockFirestore.DB_FILE
    original_db = Database._db
    temp_dir = os.path.join(os.getcwd(), "artifacts")
    os.makedirs(temp_dir, exist_ok=True)
    temp_db_file = os.path.join(temp_dir, f"test_loan_tracking_{uuid.uuid4().hex}.json")
    MockFirestore.DB_FILE = temp_db_file
    Database._db = MockFirestore()
    return original_db, original_db_file, temp_db_file


def _teardown_temp_db(original_db, original_db_file, temp_db_file):
    Database._db = original_db
    MockFirestore.DB_FILE = original_db_file
    if os.path.exists(temp_db_file):
        os.remove(temp_db_file)


def _seed_user_borrower_assessment():
    user = User(
        id="USR-TRACK-1",
        organization_id="ORG-TRACK",
        email="officer@example.com",
        password_hash="hash",
        role=UserRole.OFFICER,
        full_name="Field Officer"
    )
    borrower = Borrower(
        id="BOR-TRACK-1",
        organization_id="ORG-TRACK",
        name="Amina Trader",
        phone="+260971234567",
        employment_type=EmploymentType.TRADER,
        monthly_income=6500,
        monthly_expenses=3200,
        existing_debt=400,
        loan_amount_requested=3000,
        loan_purpose="Market inventory"
    )
    assessment = Assessment(
        assessment_id="ASMT-TRACK-1",
        borrower_id=borrower.id,
        borrower_name=borrower.name,
        organization_id="ORG-TRACK",
        risk_score=0.31,
        risk_level=RiskLevel.LOW,
        decision=Decision.APPROVE,
        requested_amount=3000,
        requested_duration_days=35,
        recommended_amount=3000,
        recommended_duration_days=35,
        recommended_interest_rate=24,
        decision_reason_codes=["STRONG_CAPACITY"],
        explanation="Healthy trading cash flow.",
        decision_summary="Approve with market-cycle collections.",
        blocking_factors=[],
    )
    Database.save_user(user)
    Database.save_borrower(borrower)
    Database.save_assessment(assessment)
    return user, borrower, assessment


def test_confirm_disbursement_infers_market_day_mobile_money_tracking_for_traders():
    original_db, original_db_file, temp_db_file = _bootstrap_temp_db()
    try:
        user, _, assessment = _seed_user_borrower_assessment()

        loan = asyncio.run(loan_disburse(assessment_id=assessment.assessment_id, user=user))
        asyncio.run(
            confirm_disbursement(
                loan_id=loan.loan_id,
                amount=3000,
                method="MOBILE_MONEY",
                reference="MM-1001",
                tracking=None,
                user=user,
            )
        )

        saved = Database.get_loan(loan.loan_id)
        assert saved is not None
        assert saved.tracking_profile is not None
        assert saved.tracking_profile.repayment_frequency == RepaymentFrequency.MARKET_DAY
        assert saved.tracking_profile.preferred_collection_channel == CollectionChannel.MOBILE_MONEY
        assert saved.tracking_profile.tracking_lane.value == "MARKET_DAY_SWEEP"
        assert len(saved.repayment_schedule) >= 4
    finally:
        _teardown_temp_db(original_db, original_db_file, temp_db_file)


def test_tracker_events_shift_from_broken_promise_to_paid_out():
    original_db, original_db_file, temp_db_file = _bootstrap_temp_db()
    try:
        user, _, assessment = _seed_user_borrower_assessment()

        loan = asyncio.run(loan_disburse(assessment_id=assessment.assessment_id, user=user))
        asyncio.run(
            confirm_disbursement(
                loan_id=loan.loan_id,
                amount=3000,
                method="MOBILE_MONEY",
                reference="MM-1002",
                tracking=None,
                user=user,
            )
        )

        setup_payload = LoanTrackingSetupRequest(
            term_days=28,
            repayment_frequency=RepaymentFrequency.WEEKLY,
            first_due_date=(date.today() - timedelta(days=14)).isoformat(),
            grace_period_days=1,
            income_cycle=IncomeCycle.WEEKLY,
            preferred_collection_channel=CollectionChannel.MOBILE_MONEY,
        )
        setup_detail = asyncio.run(setup_loan_tracking(loan_id=loan.loan_id, payload=setup_payload, user=user))
        assert setup_detail["tracking_profile"]["repayment_frequency"] == "WEEKLY"

        broken_promise_detail = asyncio.run(
            record_loan_tracking_event(
                loan_id=loan.loan_id,
                payload=LoanTrackingEventCreate(
                    event_type=LoanCollectionEventType.PROMISE_TO_PAY,
                    amount=0,
                    promise_date=(date.today() - timedelta(days=1)).isoformat(),
                    note="Borrower promised to pay after market close.",
                ),
                user=user,
            )
        )
        assert broken_promise_detail["tracking_summary"]["broken_promise"] is True
        assert broken_promise_detail["tracking_summary"]["tracker_state"] == "RECOVERY"

        total_due = float(broken_promise_detail["tracking_summary"]["total_due"])
        paid_detail = asyncio.run(
            record_loan_tracking_event(
                loan_id=loan.loan_id,
                payload=LoanTrackingEventCreate(
                    event_type=LoanCollectionEventType.PAYMENT,
                    amount=total_due,
                    channel=CollectionChannel.MOBILE_MONEY,
                    reference="MM-SETTLE-1",
                    note="Full settlement via wallet collection.",
                ),
                user=user,
            )
        )
        assert paid_detail["tracking_summary"]["tracker_state"] == "PAID_OUT"
        assert paid_detail["tracking_summary"]["mobile_money_share"] == 1.0

        saved = Database.get_loan(loan.loan_id)
        assert saved is not None
        assert saved.status.value == "PAID"

        detail = asyncio.run(get_loan_tracker_detail(loan_id=loan.loan_id, user=user))
        workspace = asyncio.run(get_loan_tracker_workspace(user=user))
        assert detail["tracking_summary"]["tracker_state"] == "PAID_OUT"
        assert workspace["portfolio"]["tracked_loans"] == 1
        assert workspace["portfolio"]["paid_out"] == 1
        assert workspace["portfolio"]["mobile_money_share"] == 1.0
    finally:
        _teardown_temp_db(original_db, original_db_file, temp_db_file)


def test_borrower_directory_handles_mixed_naive_and_aware_activity_timestamps():
    original_db, original_db_file, temp_db_file = _bootstrap_temp_db()
    try:
        user, borrower, assessment = _seed_user_borrower_assessment()
        assessment.decision_timestamp = datetime.now().replace(tzinfo=None)
        Database.save_assessment(assessment)

        loan = asyncio.run(loan_disburse(assessment_id=assessment.assessment_id, user=user))
        asyncio.run(
            confirm_disbursement(
                loan_id=loan.loan_id,
                amount=3000,
                method="MOBILE_MONEY",
                reference="MM-1003",
                tracking=None,
                user=user,
            )
        )

        directory = BorrowerProfileService.list_directory(organization_id=borrower.organization_id)

        assert len(directory) == 1
        assert directory[0].borrower_id == borrower.id
        assert directory[0].last_activity_at is not None
    finally:
        _teardown_temp_db(original_db, original_db_file, temp_db_file)
