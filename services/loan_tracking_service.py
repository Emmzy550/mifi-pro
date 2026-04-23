import math
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from models.assessment import Assessment
from models.borrower import Borrower
from models.loan import Loan, LoanStatus
from models.loan_tracking import (
    CollectionChannel,
    IncomeCycle,
    InstallmentStatus,
    LoanCollectionEvent,
    LoanCollectionEventType,
    LoanInstallment,
    LoanTrackingEventCreate,
    LoanTrackingProfile,
    LoanTrackingSetupRequest,
    RepaymentFrequency,
    TrackingLane,
)


class LoanTrackingService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _round_money(value: float) -> float:
        return round(float(value or 0.0) + 1e-9, 2)

    @staticmethod
    def _enum_value(value) -> Optional[str]:
        return getattr(value, "value", value)

    @classmethod
    def _employment_value(cls, borrower: Optional[Borrower]) -> str:
        raw = cls._enum_value(getattr(borrower, "employment_type", ""))
        return str(raw or "").strip().lower()

    @classmethod
    def _coerce_date(cls, value) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                return None

    @classmethod
    def _default_first_due_date(
        cls,
        disbursed_date: date,
        repayment_frequency: RepaymentFrequency,
        term_days: int,
    ) -> str:
        frequency = cls._enum_value(repayment_frequency)
        if frequency == RepaymentFrequency.DAILY:
            due = disbursed_date + timedelta(days=1)
        elif frequency == RepaymentFrequency.WEEKLY:
            due = disbursed_date + timedelta(days=7)
        elif frequency == RepaymentFrequency.BIWEEKLY:
            due = disbursed_date + timedelta(days=14)
        elif frequency == RepaymentFrequency.MARKET_DAY:
            due = disbursed_date + timedelta(days=7)
        elif frequency == RepaymentFrequency.SEASONAL:
            due = disbursed_date + timedelta(days=max(30, min(term_days, 90)))
        else:
            due = disbursed_date + timedelta(days=30)
        return due.isoformat()

    @classmethod
    def infer_income_cycle(cls, borrower: Optional[Borrower]) -> IncomeCycle:
        employment = cls._employment_value(borrower)
        if employment == "farmer":
            return IncomeCycle.SEASONAL
        if employment in {"trader", "gig", "self_employed"}:
            return IncomeCycle.WEEKLY
        return IncomeCycle.MONTHLY

    @classmethod
    def infer_repayment_frequency(cls, borrower: Optional[Borrower]) -> RepaymentFrequency:
        employment = cls._employment_value(borrower)
        if employment == "farmer":
            return RepaymentFrequency.SEASONAL
        if employment == "trader":
            return RepaymentFrequency.MARKET_DAY
        if employment == "gig":
            return RepaymentFrequency.WEEKLY
        if employment == "self_employed":
            return RepaymentFrequency.BIWEEKLY
        return RepaymentFrequency.MONTHLY

    @classmethod
    def infer_collection_channel(
        cls,
        borrower: Optional[Borrower],
        disbursement_method: Optional[str],
    ) -> CollectionChannel:
        method = str(disbursement_method or "").strip().upper()
        employment = cls._employment_value(borrower)
        has_phone = bool(getattr(borrower, "phone", None))

        if "MOBILE" in method or "MOMO" in method:
            return CollectionChannel.MOBILE_MONEY
        if employment == "salaried":
            return CollectionChannel.PAYROLL_DEDUCTION
        if has_phone:
            return CollectionChannel.MOBILE_MONEY
        return CollectionChannel.BANK_TRANSFER

    @classmethod
    def infer_tracking_lane(
        cls,
        repayment_frequency: RepaymentFrequency,
        income_cycle: IncomeCycle,
        preferred_collection_channel: CollectionChannel,
    ) -> TrackingLane:
        if repayment_frequency == RepaymentFrequency.SEASONAL or income_cycle == IncomeCycle.SEASONAL:
            return TrackingLane.HARVEST_BRIDGE
        if repayment_frequency == RepaymentFrequency.MARKET_DAY:
            return TrackingLane.MARKET_DAY_SWEEP
        if preferred_collection_channel in {CollectionChannel.MOBILE_MONEY, CollectionChannel.USSD}:
            return TrackingLane.MOBILE_MONEY_FASTLANE
        if income_cycle == IncomeCycle.MONTHLY:
            return TrackingLane.PAYDAY_LOCKSTEP
        return TrackingLane.FIELD_COLLECTION

    @classmethod
    def cadence_fit(cls, profile: Optional[LoanTrackingProfile]) -> str:
        if not profile:
            return "UNKNOWN"

        repayment_frequency = cls._enum_value(profile.repayment_frequency)
        strong_fit = {
            IncomeCycle.DAILY: {RepaymentFrequency.DAILY, RepaymentFrequency.WEEKLY},
            IncomeCycle.WEEKLY: {
                RepaymentFrequency.WEEKLY,
                RepaymentFrequency.BIWEEKLY,
                RepaymentFrequency.MARKET_DAY,
            },
            IncomeCycle.MONTHLY: {RepaymentFrequency.MONTHLY},
            IncomeCycle.SEASONAL: {RepaymentFrequency.SEASONAL},
            IncomeCycle.MIXED: {
                RepaymentFrequency.WEEKLY,
                RepaymentFrequency.BIWEEKLY,
                RepaymentFrequency.MONTHLY,
            },
        }
        medium_fit = {
            IncomeCycle.DAILY: {RepaymentFrequency.BIWEEKLY},
            IncomeCycle.WEEKLY: {RepaymentFrequency.MONTHLY},
            IncomeCycle.MONTHLY: {RepaymentFrequency.BIWEEKLY},
            IncomeCycle.SEASONAL: {RepaymentFrequency.MONTHLY},
            IncomeCycle.MIXED: {RepaymentFrequency.MARKET_DAY, RepaymentFrequency.SEASONAL},
        }

        if repayment_frequency in strong_fit.get(profile.income_cycle, set()):
            return "HIGH"
        if repayment_frequency in medium_fit.get(profile.income_cycle, set()):
            return "MEDIUM"
        return "LOW"

    @classmethod
    def estimate_installment_count(
        cls,
        term_days: int,
        repayment_frequency: RepaymentFrequency,
    ) -> int:
        frequency = cls._enum_value(repayment_frequency)
        term = max(int(term_days or 30), 1)
        if frequency == RepaymentFrequency.DAILY:
            return max(term, 1)
        if frequency == RepaymentFrequency.WEEKLY:
            return max(math.ceil(term / 7), 1)
        if frequency == RepaymentFrequency.BIWEEKLY:
            return max(math.ceil(term / 14), 1)
        if frequency == RepaymentFrequency.MARKET_DAY:
            return max(math.ceil(term / 7), 1)
        if frequency == RepaymentFrequency.SEASONAL:
            if term <= 120:
                return 1
            if term <= 210:
                return 2
            if term <= 300:
                return 3
            return 4
        return max(math.ceil(term / 30), 1)

    @classmethod
    def build_tracking_profile(
        cls,
        loan: Loan,
        assessment: Optional[Assessment],
        borrower: Optional[Borrower],
        overrides: Optional[LoanTrackingSetupRequest] = None,
    ) -> LoanTrackingProfile:
        override_data = overrides.model_dump(exclude_none=True) if overrides else {}
        existing = loan.tracking_profile
        disbursed_date = cls._coerce_date(loan.disbursed_at) or cls._now().date()

        term_days = (
            override_data.get("term_days")
            or getattr(existing, "term_days", None)
            or getattr(loan, "term_days", None)
            or getattr(assessment, "recommended_duration_days", None)
            or getattr(assessment, "requested_duration_days", None)
            or 30
        )
        repayment_frequency = (
            override_data.get("repayment_frequency")
            or getattr(existing, "repayment_frequency", None)
            or cls.infer_repayment_frequency(borrower)
        )
        income_cycle = (
            override_data.get("income_cycle")
            or getattr(existing, "income_cycle", None)
            or cls.infer_income_cycle(borrower)
        )
        preferred_collection_channel = (
            override_data.get("preferred_collection_channel")
            or getattr(existing, "preferred_collection_channel", None)
            or cls.infer_collection_channel(borrower, loan.disbursement_method)
        )
        first_due_date = (
            override_data.get("first_due_date")
            or getattr(existing, "first_due_date", None)
            or cls._default_first_due_date(disbursed_date, repayment_frequency, term_days)
        )
        collection_anchor_day = (
            override_data.get("collection_anchor_day")
            or getattr(existing, "collection_anchor_day", None)
        )
        if not collection_anchor_day:
            first_due = cls._coerce_date(first_due_date)
            if first_due:
                if repayment_frequency == RepaymentFrequency.MARKET_DAY:
                    collection_anchor_day = first_due.strftime("%A")
                elif repayment_frequency == RepaymentFrequency.MONTHLY:
                    collection_anchor_day = f"Day {first_due.day}"
        tracking_lane = cls.infer_tracking_lane(
            repayment_frequency=repayment_frequency,
            income_cycle=income_cycle,
            preferred_collection_channel=preferred_collection_channel,
        )
        community_cycle_label = (
            override_data.get("community_cycle_label")
            or getattr(existing, "community_cycle_label", None)
        )
        if not community_cycle_label:
            lane = cls._enum_value(tracking_lane)
            if lane == TrackingLane.MARKET_DAY_SWEEP:
                community_cycle_label = "Market-day collection sweep"
            elif lane == TrackingLane.HARVEST_BRIDGE:
                community_cycle_label = "Seasonal harvest bridge"
            elif lane == TrackingLane.PAYDAY_LOCKSTEP:
                community_cycle_label = "Payroll and payday cadence"
            elif lane == TrackingLane.MOBILE_MONEY_FASTLANE:
                community_cycle_label = "Mobile-money fast lane"
            else:
                community_cycle_label = "Field collection rhythm"

        return LoanTrackingProfile(
            currency=override_data.get("currency") or getattr(existing, "currency", None) or loan.currency or "ZMW",
            term_days=int(term_days),
            repayment_frequency=repayment_frequency,
            first_due_date=str(first_due_date),
            grace_period_days=(
                override_data.get("grace_period_days")
                if override_data.get("grace_period_days") is not None
                else getattr(existing, "grace_period_days", 3)
            ),
            income_cycle=income_cycle,
            preferred_collection_channel=preferred_collection_channel,
            tracking_lane=tracking_lane,
            collection_anchor_day=collection_anchor_day,
            seasonal_start_month=override_data.get("seasonal_start_month", getattr(existing, "seasonal_start_month", None)),
            seasonal_end_month=override_data.get("seasonal_end_month", getattr(existing, "seasonal_end_month", None)),
            community_cycle_label=community_cycle_label,
            officer_notes=override_data.get("officer_notes", getattr(existing, "officer_notes", None)),
            generated_at=cls._now(),
        )

    @classmethod
    def generate_schedule(cls, loan: Loan, profile: LoanTrackingProfile) -> List[LoanInstallment]:
        total_interest = float(loan.amount or 0.0) * (float(loan.interest_rate or 0.0) / 100.0) * (
            int(profile.term_days) / 365.0
        )
        total_due = cls._round_money(float(loan.amount or 0.0) + total_interest)
        count = cls.estimate_installment_count(profile.term_days, profile.repayment_frequency)
        principal_base = cls._round_money(float(loan.amount or 0.0) / count)
        interest_base = cls._round_money(total_interest / count)

        first_due = cls._coerce_date(profile.first_due_date) or cls._now().date()
        installments: List[LoanInstallment] = []
        principal_assigned = 0.0
        interest_assigned = 0.0

        step_days = {
            RepaymentFrequency.DAILY: 1,
            RepaymentFrequency.WEEKLY: 7,
            RepaymentFrequency.BIWEEKLY: 14,
            RepaymentFrequency.MONTHLY: 30,
            RepaymentFrequency.MARKET_DAY: 7,
        }.get(profile.repayment_frequency, max(round(profile.term_days / max(count, 1)), 30))

        for index in range(count):
            if index == count - 1:
                principal_due = cls._round_money(float(loan.amount or 0.0) - principal_assigned)
                interest_due = cls._round_money(total_interest - interest_assigned)
            else:
                principal_due = principal_base
                interest_due = interest_base

            due_date = first_due + timedelta(days=step_days * index)
            principal_assigned += principal_due
            interest_assigned += interest_due

            installments.append(
                LoanInstallment(
                    installment_id=f"{loan.loan_id}-INS-{index + 1:02d}",
                    due_date=due_date.isoformat(),
                    amount_due=cls._round_money(principal_due + interest_due),
                    principal_due=principal_due,
                    interest_due=interest_due,
                    amount_collected=0.0,
                    status=InstallmentStatus.UPCOMING,
                    paid_at=None,
                    payment_references=[],
                )
            )

        remainder = cls._round_money(total_due - sum(item.amount_due for item in installments))
        if installments and abs(remainder) >= 0.01:
            installments[-1].amount_due = cls._round_money(installments[-1].amount_due + remainder)
            if remainder > 0:
                installments[-1].interest_due = cls._round_money(installments[-1].interest_due + remainder)
            else:
                installments[-1].principal_due = cls._round_money(installments[-1].principal_due + remainder)

        return installments

    @classmethod
    def _apply_payment_to_schedule(
        cls,
        schedule: List[LoanInstallment],
        event: LoanCollectionEvent,
    ) -> None:
        remaining = cls._round_money(event.amount)
        if remaining <= 0:
            return

        applied = 0.0
        for installment in schedule:
            balance = cls._round_money(installment.amount_due - installment.amount_collected)
            if balance <= 0:
                continue
            slice_amount = min(balance, remaining)
            installment.amount_collected = cls._round_money(installment.amount_collected + slice_amount)
            remaining = cls._round_money(remaining - slice_amount)
            applied = cls._round_money(applied + slice_amount)
            if event.reference and event.reference not in installment.payment_references:
                installment.payment_references.append(event.reference)
            if installment.amount_collected >= installment.amount_due - 0.01:
                installment.status = InstallmentStatus.PAID
                installment.paid_at = event.occurred_at
            else:
                installment.status = InstallmentStatus.PARTIAL
            if remaining <= 0:
                break

        if applied > 0:
            event.metadata["applied_amount"] = applied
        if remaining > 0:
            event.metadata["unapplied_amount"] = remaining

    @classmethod
    def _refresh_installment_statuses(
        cls,
        loan: Loan,
        schedule: List[LoanInstallment],
    ) -> None:
        profile = loan.tracking_profile
        grace_days = int(getattr(profile, "grace_period_days", 0) or 0)
        today = cls._now().date()

        for installment in schedule:
            if installment.amount_collected >= installment.amount_due - 0.01:
                installment.status = InstallmentStatus.PAID
                continue

            due_date = cls._coerce_date(installment.due_date) or today
            if due_date + timedelta(days=grace_days) < today:
                installment.status = InstallmentStatus.MISSED
            elif due_date <= today:
                installment.status = (
                    InstallmentStatus.PARTIAL
                    if installment.amount_collected > 0
                    else InstallmentStatus.DUE
                )
            else:
                installment.status = (
                    InstallmentStatus.PARTIAL
                    if installment.amount_collected > 0
                    else InstallmentStatus.UPCOMING
                )

    @classmethod
    def replay_collection_history(cls, loan: Loan) -> Loan:
        if not loan.tracking_profile:
            return loan

        schedule = [item.model_copy(deep=True) for item in (loan.repayment_schedule or [])]
        if not schedule:
            schedule = cls.generate_schedule(loan, loan.tracking_profile)

        for installment in schedule:
            installment.amount_collected = 0.0
            installment.status = InstallmentStatus.UPCOMING
            installment.paid_at = None
            installment.payment_references = []

        payment_events = sorted(
            [event for event in (loan.collection_history or []) if event.event_type == LoanCollectionEventType.PAYMENT],
            key=lambda item: item.occurred_at,
        )
        for event in payment_events:
            cls._apply_payment_to_schedule(schedule, event)

        cls._refresh_installment_statuses(loan, schedule)
        loan.repayment_schedule = schedule
        loan.tracking_last_updated_at = cls._now()
        return loan

    @classmethod
    def ensure_tracking(
        cls,
        loan: Loan,
        assessment: Optional[Assessment],
        borrower: Optional[Borrower],
        overrides: Optional[LoanTrackingSetupRequest] = None,
    ) -> Loan:
        profile = cls.build_tracking_profile(loan, assessment, borrower, overrides)
        loan.currency = profile.currency
        loan.term_days = profile.term_days
        loan.tracking_profile = profile
        loan.repayment_schedule = cls.generate_schedule(loan, profile)
        cls.replay_collection_history(loan)
        return loan

    @classmethod
    def record_event(
        cls,
        loan: Loan,
        payload: LoanTrackingEventCreate,
        recorded_by: str,
    ) -> LoanCollectionEvent:
        event = LoanCollectionEvent(
            event_id=f"LTE-{uuid.uuid4().hex[:10].upper()}",
            loan_id=loan.loan_id,
            organization_id=loan.organization_id,
            event_type=payload.event_type,
            amount=cls._round_money(payload.amount),
            currency=loan.currency or getattr(loan.tracking_profile, "currency", "ZMW"),
            channel=payload.channel,
            occurred_at=payload.occurred_at or cls._now(),
            recorded_at=cls._now(),
            recorded_by=recorded_by,
            reference=payload.reference,
            note=payload.note,
            promise_date=payload.promise_date,
            metadata=payload.metadata or {},
        )
        loan.collection_history.append(event)
        if loan.tracking_profile:
            cls.replay_collection_history(loan)

        summary = cls.summarize(loan)
        if summary["tracker_state"] == "PAID_OUT" and loan.status not in {LoanStatus.PAID, LoanStatus.DEFAULTED}:
            loan.status = LoanStatus.PAID
            loan.closed_at = cls._now()
        return event

    @classmethod
    def _derive_tracker_state(
        cls,
        loan: Loan,
        outstanding_balance: float,
        days_past_due: int,
        missed_installments: int,
        broken_promise: bool,
        cadence_fit: str,
        schedule: List[LoanInstallment],
    ) -> str:
        loan_status = cls._enum_value(loan.status)
        if loan_status == LoanStatus.DEFAULTED:
            return "RECOVERY"
        if not loan.tracking_profile:
            return "UNCONFIGURED"
        if loan_status == LoanStatus.PAID or outstanding_balance <= 0.01:
            return "PAID_OUT"
        if broken_promise or days_past_due >= 30 or missed_installments >= 2:
            return "RECOVERY"
        if days_past_due >= 7 or missed_installments >= 1 or cadence_fit == "LOW":
            return "AT_RISK"
        if any(item.status in {InstallmentStatus.DUE, InstallmentStatus.PARTIAL} for item in schedule):
            return "WATCH"
        next_due = next((item for item in schedule if item.status != InstallmentStatus.PAID), None)
        if next_due:
            due_date = cls._coerce_date(next_due.due_date)
            if due_date and (due_date - cls._now().date()).days <= 3:
                return "WATCH"
        return "ON_TRACK"

    @classmethod
    def _build_recommended_action(
        cls,
        loan: Loan,
        tracker_state: str,
        broken_promise: bool,
        cadence_fit: str,
        next_due_date: Optional[str],
    ) -> str:
        profile = loan.tracking_profile
        lane = cls._enum_value(getattr(profile, "tracking_lane", None))
        if tracker_state == "PAID_OUT":
            return "Close the file and decide whether the borrower is ready for a renewal offer."
        if tracker_state == "UNCONFIGURED":
            return "Set a repayment cadence before the first collection cycle starts."
        if broken_promise:
            return "Broken promise detected. Escalate from soft reminder to officer-led recovery action."
        if tracker_state == "RECOVERY":
            if lane == TrackingLane.MOBILE_MONEY_FASTLANE:
                return "Run a mobile-money retry and document the outcome before dispatching a field visit."
            if lane == TrackingLane.HARVEST_BRIDGE:
                return "Review seasonal timing and restructure only if the harvest window has clearly slipped."
            return "Schedule a documented recovery visit and capture the borrower response on the ledger."
        if tracker_state == "AT_RISK":
            if cadence_fit == "LOW":
                return "The repayment cadence does not fit the borrower's income rhythm. Rework the plan before arrears deepen."
            if lane == TrackingLane.MARKET_DAY_SWEEP:
                return "Queue the next reminder to land before the borrower's trading cycle or market day."
            return "Follow up before the next missed installment and confirm the collection channel still works."
        if tracker_state == "WATCH" and next_due_date:
            return f"Upcoming installment due on {next_due_date}. Send a reminder through the preferred collection lane."
        return "Loan is on track. Keep monitoring the next collection checkpoint."

    @classmethod
    def differentiators(cls, loan: Loan) -> List[str]:
        profile = loan.tracking_profile
        if not profile:
            return ["Tracking setup is still pending for this loan."]

        lane = cls._enum_value(profile.tracking_lane)
        differentiators = []
        if lane == TrackingLane.MOBILE_MONEY_FASTLANE:
            differentiators.append("Mobile-money-first collections with fast visibility into failed retries.")
        if lane == TrackingLane.MARKET_DAY_SWEEP:
            differentiators.append("Repayment reminders aligned to trading and market-day cash-flow cycles.")
        if lane == TrackingLane.PAYDAY_LOCKSTEP:
            differentiators.append("Salary-cycle tracking that keeps officers ahead of payday slippage.")
        if lane == TrackingLane.HARVEST_BRIDGE:
            differentiators.append("Seasonal grace logic that separates true delinquency from crop-timing delays.")
        if lane == TrackingLane.FIELD_COLLECTION:
            differentiators.append("Field collection notes sit beside the repayment ledger, not outside it.")

        cadence_fit = cls.cadence_fit(profile)
        if cadence_fit == "HIGH":
            differentiators.append("Cadence-fit scoring shows the repayment plan matches the borrower's cash rhythm.")
        elif cadence_fit == "LOW":
            differentiators.append("Cadence-fit logic has flagged a mismatch between the plan and the cash-flow pattern.")

        return differentiators[:3]

    @classmethod
    def summarize(
        cls,
        loan: Loan,
        borrower: Optional[Borrower] = None,
        assessment: Optional[Assessment] = None,
    ) -> Dict[str, object]:
        schedule = loan.repayment_schedule or []
        today = cls._now().date()
        profile = loan.tracking_profile
        payment_events = sorted(
            [event for event in (loan.collection_history or []) if event.event_type == LoanCollectionEventType.PAYMENT],
            key=lambda item: item.occurred_at,
        )
        total_payment_amount = cls._round_money(sum(event.amount for event in payment_events))
        total_due = cls._round_money(sum(item.amount_due for item in schedule)) if schedule else cls._round_money(float(loan.amount or 0.0))
        total_collected = cls._round_money(sum(item.amount_collected for item in schedule)) if schedule else total_payment_amount
        outstanding_balance = cls._round_money(max(total_due - total_collected, 0.0))

        due_installments = [
            item for item in schedule if (cls._coerce_date(item.due_date) or today) <= today
        ]
        expected_collected = cls._round_money(sum(item.amount_due for item in due_installments))
        overdue_installments = []
        overdue_amount = 0.0
        grace_days = int(getattr(profile, "grace_period_days", 0) or 0)
        for item in schedule:
            due_date = cls._coerce_date(item.due_date) or today
            balance = cls._round_money(item.amount_due - item.amount_collected)
            if balance <= 0:
                continue
            if due_date + timedelta(days=grace_days) < today:
                overdue_installments.append(item)
                overdue_amount = cls._round_money(overdue_amount + balance)

        earliest_overdue = min(
            (cls._coerce_date(item.due_date) for item in overdue_installments),
            default=None,
        )
        days_past_due = (today - earliest_overdue).days if earliest_overdue else 0
        next_due_installment = next(
            (item for item in schedule if item.amount_collected < item.amount_due - 0.01),
            None,
        )
        next_due_date = next_due_installment.due_date if next_due_installment else None

        all_events = sorted(loan.collection_history or [], key=lambda item: item.occurred_at)
        last_payment = payment_events[-1] if payment_events else None
        last_event = all_events[-1] if all_events else None
        last_contact_at = last_event.occurred_at if last_event else loan.disbursed_at or loan.created_at
        recent_contact_gap_days = (
            (today - cls._coerce_date(last_contact_at)).days if cls._coerce_date(last_contact_at) else None
        )

        mobile_money_amount = cls._round_money(
            sum(
                event.amount
                for event in payment_events
                if event.channel in {CollectionChannel.MOBILE_MONEY, CollectionChannel.USSD}
            )
        )
        channel_mix = Counter(
            cls._enum_value(event.channel) or "OTHER" for event in payment_events
        )

        latest_promise = next(
            (
                event
                for event in sorted(
                    [item for item in (loan.collection_history or []) if item.event_type == LoanCollectionEventType.PROMISE_TO_PAY],
                    key=lambda item: item.occurred_at,
                    reverse=True,
                )
                if event.promise_date
            ),
            None,
        )
        broken_promise = False
        if latest_promise:
            promise_date = cls._coerce_date(latest_promise.promise_date)
            latest_payment_after_promise = next(
                (
                    event
                    for event in reversed(payment_events)
                    if event.occurred_at >= latest_promise.occurred_at
                ),
                None,
            )
            broken_promise = bool(
                promise_date
                and promise_date < today
                and latest_payment_after_promise is None
            )

        cadence_fit = cls.cadence_fit(profile)
        tracker_state = cls._derive_tracker_state(
            loan=loan,
            outstanding_balance=outstanding_balance,
            days_past_due=days_past_due,
            missed_installments=len(overdue_installments),
            broken_promise=broken_promise,
            cadence_fit=cadence_fit,
            schedule=schedule,
        )

        collection_efficiency = 1.0
        if expected_collected > 0:
            collection_efficiency = min(total_collected / expected_collected, 1.5)

        return {
            "loan_id": loan.loan_id,
            "loan_status": cls._enum_value(loan.status),
            "borrower_name": getattr(borrower, "name", None) or getattr(assessment, "borrower_name", None),
            "borrower_id": loan.borrower_id,
            "assessment_id": loan.assessment_id,
            "currency": loan.currency or getattr(profile, "currency", "ZMW"),
            "tracking_lane": cls._enum_value(getattr(profile, "tracking_lane", None)) if profile else None,
            "cadence_fit": cadence_fit,
            "tracker_state": tracker_state,
            "installment_count": len(schedule),
            "installments_paid": len([item for item in schedule if item.status == InstallmentStatus.PAID]),
            "missed_installments": len(overdue_installments),
            "days_past_due": days_past_due,
            "next_due_date": next_due_date,
            "total_due": total_due,
            "total_collected": total_collected,
            "expected_collected_to_date": expected_collected,
            "outstanding_balance": outstanding_balance,
            "overdue_amount": overdue_amount,
            "collection_efficiency": round(collection_efficiency, 3),
            "payment_event_count": len(payment_events),
            "mobile_money_share": round(
                (mobile_money_amount / total_payment_amount) if total_payment_amount > 0 else 0.0,
                3,
            ),
            "last_payment_at": last_payment.occurred_at if last_payment else None,
            "last_contact_at": last_contact_at,
            "recent_contact_gap_days": recent_contact_gap_days,
            "broken_promise": broken_promise,
            "preferred_collection_channel": cls._enum_value(getattr(profile, "preferred_collection_channel", None)) if profile else None,
            "income_cycle": cls._enum_value(getattr(profile, "income_cycle", None)) if profile else None,
            "community_cycle_label": getattr(profile, "community_cycle_label", None) if profile else None,
            "collection_anchor_day": getattr(profile, "collection_anchor_day", None) if profile else None,
            "channel_mix": dict(channel_mix),
            "recommended_action": cls._build_recommended_action(
                loan=loan,
                tracker_state=tracker_state,
                broken_promise=broken_promise,
                cadence_fit=cadence_fit,
                next_due_date=next_due_date,
            ),
            "differentiators": cls.differentiators(loan),
        }

    @classmethod
    def portfolio_snapshot(
        cls,
        loans: List[Loan],
        borrower_lookup: Optional[Dict[str, Borrower]] = None,
        assessment_lookup: Optional[Dict[str, Assessment]] = None,
    ) -> Dict[str, object]:
        borrower_lookup = borrower_lookup or {}
        assessment_lookup = assessment_lookup or {}
        items = []
        total_outstanding = 0.0
        total_due = 0.0
        mobile_money_weight = 0.0
        payment_weight = 0
        cadence_fit_hits = 0

        counts = {
            "tracked_loans": 0,
            "unconfigured": 0,
            "on_track": 0,
            "watch": 0,
            "at_risk": 0,
            "recovery": 0,
            "paid_out": 0,
        }

        for loan in loans:
            borrower = borrower_lookup.get(loan.borrower_id)
            assessment = assessment_lookup.get(loan.assessment_id)
            summary = cls.summarize(loan, borrower=borrower, assessment=assessment)
            items.append(
                {
                    "loan_id": loan.loan_id,
                    "assessment_id": loan.assessment_id,
                    "borrower_id": loan.borrower_id,
                    "borrower_name": summary.get("borrower_name"),
                    "amount": loan.amount,
                    "currency": loan.currency,
                    "status": cls._enum_value(loan.status),
                    "disbursed_at": loan.disbursed_at,
                    "tracking_profile": loan.tracking_profile.model_dump(mode="json") if loan.tracking_profile else None,
                    "tracking_summary": summary,
                }
            )

            if loan.tracking_profile:
                counts["tracked_loans"] += 1
            else:
                counts["unconfigured"] += 1

            state = summary["tracker_state"]
            if state == "ON_TRACK":
                counts["on_track"] += 1
            elif state == "WATCH":
                counts["watch"] += 1
            elif state == "AT_RISK":
                counts["at_risk"] += 1
            elif state == "RECOVERY":
                counts["recovery"] += 1
            elif state == "PAID_OUT":
                counts["paid_out"] += 1

            total_outstanding = cls._round_money(total_outstanding + float(summary["outstanding_balance"]))
            total_due = cls._round_money(total_due + float(summary["total_due"]))
            payment_count = int(summary["payment_event_count"])
            payment_weight += payment_count
            mobile_money_weight += float(summary["mobile_money_share"]) * payment_count
            if summary["cadence_fit"] == "HIGH":
                cadence_fit_hits += 1

        severity_rank = {
            "RECOVERY": 4,
            "AT_RISK": 3,
            "WATCH": 2,
            "ON_TRACK": 1,
            "PAID_OUT": 0,
            "UNCONFIGURED": -1,
        }
        items.sort(
            key=lambda item: (
                severity_rank.get(item["tracking_summary"]["tracker_state"], -2),
                item["tracking_summary"]["days_past_due"],
                item["tracking_summary"]["outstanding_balance"],
            ),
            reverse=True,
        )

        return {
            "portfolio": {
                "total_loans": len(loans),
                **counts,
                "mobile_money_share": round(
                    mobile_money_weight / payment_weight if payment_weight > 0 else 0.0,
                    3,
                ),
                "cadence_fit_rate": round(
                    cadence_fit_hits / counts["tracked_loans"] if counts["tracked_loans"] > 0 else 0.0,
                    3,
                ),
                "total_outstanding": total_outstanding,
                "total_due": total_due,
            },
            "items": items,
        }
