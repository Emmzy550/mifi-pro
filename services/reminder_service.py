from datetime import datetime, time, timedelta, timezone
from string import Template
from typing import Any, Dict, List, Optional, Tuple

from models.assessment import Assessment
from models.borrower import Borrower
from models.borrower_communication import (
    BorrowerCommunicationRecord,
    BorrowerContactPreference,
    CommunicationDeliveryStatus,
    CommunicationSenderType,
    ReminderChannel,
    ReminderPreviewRequest,
    ReminderPreviewResponse,
    ReminderScheduleItem,
    ReminderScheduleStatus,
    ReminderSendRequest,
    ReminderType,
)
from models.loan import Loan
from models.loan_tracking import LoanCollectionEventType
from services.loan_tracking_service import LoanTrackingService
from services.messaging_service import MessagingService


DEFAULT_RULES: Dict[ReminderType, Dict[str, Any]] = {
    ReminderType.UPCOMING_REPAYMENT: {"days_before_due": 2},
    ReminderType.DUE_TODAY: {"day_offset": 0},
    ReminderType.MISSED_PAYMENT: {"days_after_due": 1, "repeat_after_days": 3},
    ReminderType.PROMISE_TO_PAY_FOLLOW_UP: {"day_offset": 0},
    ReminderType.MANUAL: {},
    ReminderType.GENERAL_FOLLOW_UP: {},
}


MESSAGE_TEMPLATES: Dict[Tuple[ReminderType, ReminderChannel], Dict[str, str]] = {
    (ReminderType.UPCOMING_REPAYMENT, ReminderChannel.SMS): {
        "key": "upcoming_sms_v1",
        "body": "Hello ${first_name}, this is a reminder from ${institution_name}. Your ${loan_id} installment of ${amount_due} is due on ${due_date}. Outstanding balance: ${outstanding_balance}. Contact ${officer_name} if you need support.",
    },
    (ReminderType.DUE_TODAY, ReminderChannel.SMS): {
        "key": "due_today_sms_v1",
        "body": "Hello ${first_name}, your ${loan_id} repayment of ${amount_due} is due today (${due_date}). Please pay via ${preferred_channel}. Outstanding balance: ${outstanding_balance}. - ${institution_name}",
    },
    (ReminderType.MISSED_PAYMENT, ReminderChannel.SMS): {
        "key": "missed_sms_v1",
        "body": "Hello ${first_name}, we have not received the expected payment for ${loan_id}. Amount due: ${amount_due}. Arrears: ${arrears_amount}. Please contact ${officer_name} at ${contact_number}.",
    },
    (ReminderType.PROMISE_TO_PAY_FOLLOW_UP, ReminderChannel.SMS): {
        "key": "promise_follow_up_sms_v1",
        "body": "Hello ${first_name}, this is a follow-up on your promise to pay for ${loan_id} on ${promise_to_pay_date}. Outstanding balance is ${outstanding_balance}. Please confirm your payment plan with ${institution_name}.",
    },
    (ReminderType.MANUAL, ReminderChannel.SMS): {
        "key": "manual_sms_v1",
        "body": "Hello ${first_name}, this is ${officer_name} from ${institution_name} following up on your loan ${loan_id}. Please contact us on ${contact_number}.",
    },
    (ReminderType.GENERAL_FOLLOW_UP, ReminderChannel.SMS): {
        "key": "general_follow_up_sms_v1",
        "body": "Hello ${first_name}, ${institution_name} is checking in about your account ${loan_id}. Please contact ${officer_name} on ${contact_number} for assistance.",
    },
    (ReminderType.UPCOMING_REPAYMENT, ReminderChannel.WHATSAPP): {
        "key": "upcoming_whatsapp_v1",
        "body": "Hello ${first_name}. ${institution_name} is reminding you that ${amount_due} is due on ${due_date} for loan ${loan_id}. Outstanding balance: ${outstanding_balance}.",
    },
    (ReminderType.DUE_TODAY, ReminderChannel.WHATSAPP): {
        "key": "due_today_whatsapp_v1",
        "body": "Hello ${first_name}. Your payment for loan ${loan_id} is due today. Amount due: ${amount_due}. Kindly confirm once paid.",
    },
    (ReminderType.MISSED_PAYMENT, ReminderChannel.WHATSAPP): {
        "key": "missed_whatsapp_v1",
        "body": "Hello ${first_name}. We noticed a missed repayment on loan ${loan_id}. Arrears currently stand at ${arrears_amount}. Please reply to arrange next steps.",
    },
    (ReminderType.PROMISE_TO_PAY_FOLLOW_UP, ReminderChannel.WHATSAPP): {
        "key": "promise_follow_up_whatsapp_v1",
        "body": "Hello ${first_name}. We are following up on your promise to pay for loan ${loan_id} on ${promise_to_pay_date}. Please update us if the date has changed.",
    },
    (ReminderType.MANUAL, ReminderChannel.WHATSAPP): {
        "key": "manual_whatsapp_v1",
        "body": "Hello ${first_name}. ${officer_name} from ${institution_name} is following up on loan ${loan_id}. Please let us know how best to support repayment.",
    },
    (ReminderType.GENERAL_FOLLOW_UP, ReminderChannel.WHATSAPP): {
        "key": "general_follow_up_whatsapp_v1",
        "body": "Hello ${first_name}. This is a general follow-up from ${institution_name} regarding loan ${loan_id}. Please contact ${officer_name} on ${contact_number}.",
    },
}


class ReminderService:
    @staticmethod
    def _first_name(full_name: Optional[str]) -> str:
        return str(full_name or "Borrower").strip().split(" ")[0] or "Borrower"

    @staticmethod
    def _format_money(value: Optional[float], currency: str = "ZMW") -> str:
        if value is None:
            return "Not available"
        return f"{currency} {float(value):,.2f}"

    @staticmethod
    def _channel_from_preference(
        preference: Optional[BorrowerContactPreference],
        loan: Optional[Loan],
    ) -> ReminderChannel:
        if preference and preference.preferred_channel:
            return preference.preferred_channel
        profile = getattr(loan, "tracking_profile", None)
        preferred_collection_channel = getattr(profile, "preferred_collection_channel", None)
        raw_channel = str(getattr(preferred_collection_channel, "value", preferred_collection_channel)).upper()
        if raw_channel in {"MOBILE_MONEY", "USSD"}:
            return ReminderChannel.SMS
        return ReminderChannel.SMS

    @staticmethod
    def _recipient_number(
        borrower: Borrower,
        preference: Optional[BorrowerContactPreference],
        override_number: Optional[str] = None,
    ) -> str:
        return str(override_number or getattr(preference, "preferred_number", None) or borrower.phone or "").strip()

    @staticmethod
    def _resolve_active_loan(
        loans: List[Loan],
        loan_id: Optional[str] = None,
    ) -> Optional[Loan]:
        if loan_id:
            return next((loan for loan in loans if loan.loan_id == loan_id), None)
        active_loans = [
            loan for loan in loans if str(getattr(loan.status, "value", loan.status)).upper() in {"ACTIVE", "DISBURSED", "PENDING_DISBURSEMENT"}
        ]
        return active_loans[0] if active_loans else (loans[0] if loans else None)

    @classmethod
    def _build_context(
        cls,
        borrower: Borrower,
        institution_name: str,
        officer_name: str,
        contact_number: str,
        loan: Optional[Loan],
        assessment: Optional[Assessment],
        preference: Optional[BorrowerContactPreference],
        promise_to_pay_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        summary = LoanTrackingService.summarize(loan, borrower=borrower, assessment=assessment) if loan else {}
        next_due_amount = None
        if loan and loan.repayment_schedule:
            next_installment = next(
                (item for item in loan.repayment_schedule if float(item.amount_collected or 0) < float(item.amount_due or 0) - 0.01),
                None,
            )
            if next_installment:
                next_due_amount = next_installment.amount_due

        return {
            "borrower_first_name": cls._first_name(borrower.name),
            "first_name": cls._first_name(borrower.name),
            "borrower_name": borrower.name,
            "loan_id": getattr(loan, "loan_id", None) or getattr(assessment, "assessment_id", None) or borrower.id,
            "due_date": summary.get("next_due_date") or "Not set",
            "amount_due": cls._format_money(next_due_amount, getattr(loan, "currency", "ZMW")),
            "outstanding_balance": cls._format_money(summary.get("outstanding_balance"), getattr(loan, "currency", "ZMW")),
            "arrears_amount": cls._format_money(summary.get("overdue_amount"), getattr(loan, "currency", "ZMW")),
            "promise_to_pay_date": promise_to_pay_date or "",
            "institution_name": institution_name,
            "officer_name": officer_name or "Loan Officer",
            "contact_number": contact_number or borrower.phone,
            "preferred_channel": getattr(preference, "preferred_channel", None) or summary.get("preferred_collection_channel") or "your usual payment channel",
        }

    @classmethod
    def preview_message(
        cls,
        borrower: Borrower,
        institution_name: str,
        officer_name: str,
        contact_number: str,
        request: ReminderPreviewRequest,
        loans: List[Loan],
        assessments: List[Assessment],
        preference: Optional[BorrowerContactPreference],
    ) -> ReminderPreviewResponse:
        loan = cls._resolve_active_loan(loans, request.loan_id)
        assessment = next((item for item in assessments if item.assessment_id == request.assessment_id), None)
        if assessment is None and loan:
            assessment = next((item for item in assessments if item.assessment_id == loan.assessment_id), None)

        template = MESSAGE_TEMPLATES[(request.reminder_type, request.channel)]
        context = cls._build_context(
            borrower=borrower,
            institution_name=institution_name,
            officer_name=officer_name,
            contact_number=contact_number,
            loan=loan,
            assessment=assessment,
            preference=preference,
            promise_to_pay_date=request.promise_to_pay_date,
        )
        body = Template(template["body"]).safe_substitute(context)
        recipient_number = cls._recipient_number(borrower, preference, request.recipient_number)
        return ReminderPreviewResponse(
            borrower_id=borrower.id or "",
            loan_id=getattr(loan, "loan_id", None),
            assessment_id=getattr(assessment, "assessment_id", None),
            recipient_number=recipient_number,
            channel=request.channel,
            reminder_type=request.reminder_type,
            template_key=template["key"],
            template_version="2026-03",
            generated_message=body,
            placeholders=context,
            can_edit_message=True,
        )

    @classmethod
    def send_reminder(
        cls,
        communication_id: str,
        borrower: Borrower,
        institution_name: str,
        officer_name: str,
        contact_number: str,
        request: ReminderSendRequest,
        loans: List[Loan],
        assessments: List[Assessment],
        preference: Optional[BorrowerContactPreference],
        organization_id: str,
        triggered_by: Dict[str, Optional[str]],
        automated: bool = False,
    ) -> BorrowerCommunicationRecord:
        preview = cls.preview_message(
            borrower=borrower,
            institution_name=institution_name,
            officer_name=officer_name,
            contact_number=contact_number,
            request=request,
            loans=loans,
            assessments=assessments,
            preference=preference,
        )
        message_body = request.custom_message.strip() if request.custom_message and request.custom_message.strip() else preview.generated_message
        result = MessagingService.send(
            channel=preview.channel.value,
            phone_number=preview.recipient_number,
            message=message_body,
            metadata={
                "borrower_id": borrower.id,
                "loan_id": preview.loan_id,
                "assessment_id": preview.assessment_id,
                "reminder_type": preview.reminder_type.value,
            },
        )
        status = CommunicationDeliveryStatus(str(result.get("status", "FAILED")).upper())
        failure_reason = result.get("message") if status == CommunicationDeliveryStatus.FAILED else None
        return BorrowerCommunicationRecord(
            communication_id=communication_id,
            organization_id=organization_id,
            borrower_id=borrower.id or "",
            borrower_name=borrower.name,
            assessment_id=preview.assessment_id,
            loan_id=preview.loan_id,
            related_promise_date=request.promise_to_pay_date,
            reminder_type=preview.reminder_type,
            channel=preview.channel,
            recipient_number=preview.recipient_number,
            sender_type=CommunicationSenderType.SYSTEM if automated else CommunicationSenderType.OFFICER,
            automated=automated,
            template_key=preview.template_key,
            template_version=preview.template_version,
            message_body=message_body,
            message_preview=message_body[:180],
            delivery_status=status,
            failure_reason=failure_reason,
            provider=result.get("provider"),
            provider_message_id=result.get("provider_id"),
            triggered_by_user_id=triggered_by.get("user_id"),
            triggered_by_name=triggered_by.get("name"),
            triggered_by_email=triggered_by.get("email"),
            metadata=preview.placeholders,
            sent_at=datetime.now(timezone.utc),
        )

    @classmethod
    def build_schedule(
        cls,
        borrower: Borrower,
        organization_id: str,
        loans: List[Loan],
        assessments: List[Assessment],
        preference: Optional[BorrowerContactPreference],
    ) -> List[ReminderScheduleItem]:
        items: List[ReminderScheduleItem] = []
        now = datetime.now(timezone.utc)
        for loan in loans:
            loan_status = str(getattr(loan.status, "value", loan.status)).upper()
            if loan_status not in {"ACTIVE", "DISBURSED", "PENDING_DISBURSEMENT"}:
                continue

            assessment = next((item for item in assessments if item.assessment_id == loan.assessment_id), None)
            summary = LoanTrackingService.summarize(loan, borrower=borrower, assessment=assessment)
            channel = cls._channel_from_preference(preference, loan)
            currency = loan.currency or "ZMW"
            next_due_date_raw = summary.get("next_due_date")
            next_due_date = LoanTrackingService._coerce_date(next_due_date_raw)
            if next_due_date:
                schedule_date = datetime.combine(
                    next_due_date - timedelta(days=DEFAULT_RULES[ReminderType.UPCOMING_REPAYMENT]["days_before_due"]),
                    time(hour=8, minute=30),
                    tzinfo=timezone.utc,
                )
                items.append(
                    ReminderScheduleItem(
                        schedule_id=f"{loan.loan_id}-UPCOMING",
                        borrower_id=borrower.id or "",
                        organization_id=organization_id,
                        loan_id=loan.loan_id,
                        assessment_id=loan.assessment_id,
                        reminder_type=ReminderType.UPCOMING_REPAYMENT,
                        channel=channel,
                        title="Upcoming repayment reminder",
                        description=f"Send {DEFAULT_RULES[ReminderType.UPCOMING_REPAYMENT]['days_before_due']} days before the next installment becomes due.",
                        scheduled_for=schedule_date,
                        template_key=MESSAGE_TEMPLATES[(ReminderType.UPCOMING_REPAYMENT, channel)]["key"],
                        status=ReminderScheduleStatus.DUE if schedule_date <= now else ReminderScheduleStatus.UPCOMING,
                        metadata={"next_due_date": next_due_date_raw},
                    )
                )

                due_today_time = datetime.combine(next_due_date, time(hour=7, minute=30), tzinfo=timezone.utc)
                items.append(
                    ReminderScheduleItem(
                        schedule_id=f"{loan.loan_id}-DUE",
                        borrower_id=borrower.id or "",
                        organization_id=organization_id,
                        loan_id=loan.loan_id,
                        assessment_id=loan.assessment_id,
                        reminder_type=ReminderType.DUE_TODAY,
                        channel=channel,
                        title="Due today reminder",
                        description="Send on the installment due date if the loan is still active.",
                        scheduled_for=due_today_time,
                        template_key=MESSAGE_TEMPLATES[(ReminderType.DUE_TODAY, channel)]["key"],
                        status=ReminderScheduleStatus.DUE if due_today_time <= now else ReminderScheduleStatus.UPCOMING,
                        metadata={"next_due_date": next_due_date_raw},
                    )
                )

            if float(summary.get("overdue_amount") or 0.0) > 0:
                overdue_date = next_due_date or now.date()
                missed_at = datetime.combine(
                    overdue_date + timedelta(days=DEFAULT_RULES[ReminderType.MISSED_PAYMENT]["days_after_due"]),
                    time(hour=9, minute=0),
                    tzinfo=timezone.utc,
                )
                items.append(
                    ReminderScheduleItem(
                        schedule_id=f"{loan.loan_id}-MISSED",
                        borrower_id=borrower.id or "",
                        organization_id=organization_id,
                        loan_id=loan.loan_id,
                        assessment_id=loan.assessment_id,
                        reminder_type=ReminderType.MISSED_PAYMENT,
                        channel=channel,
                        title="Missed payment reminder",
                        description=f"Auto-follow up when arrears of {cls._format_money(summary.get('overdue_amount'), currency)} remain unpaid.",
                        scheduled_for=missed_at,
                        template_key=MESSAGE_TEMPLATES[(ReminderType.MISSED_PAYMENT, channel)]["key"],
                        status=ReminderScheduleStatus.OVERDUE if missed_at < now else ReminderScheduleStatus.UPCOMING,
                        metadata={"arrears_amount": summary.get("overdue_amount")},
                    )
                )

            promise_events = sorted(
                [event for event in (loan.collection_history or []) if event.event_type == LoanCollectionEventType.PROMISE_TO_PAY and event.promise_date],
                key=lambda item: item.occurred_at,
                reverse=True,
            )
            if promise_events:
                latest_promise = promise_events[0]
                promise_date = LoanTrackingService._coerce_date(latest_promise.promise_date)
                if promise_date:
                    promised_time = datetime.combine(promise_date, time(hour=8, minute=0), tzinfo=timezone.utc)
                    items.append(
                        ReminderScheduleItem(
                            schedule_id=f"{loan.loan_id}-PROMISE",
                            borrower_id=borrower.id or "",
                            organization_id=organization_id,
                            loan_id=loan.loan_id,
                            assessment_id=loan.assessment_id,
                            reminder_type=ReminderType.PROMISE_TO_PAY_FOLLOW_UP,
                            channel=channel,
                            title="Promise-to-pay follow-up",
                            description=f"Check in on the promised repayment date of {latest_promise.promise_date}.",
                            scheduled_for=promised_time,
                            template_key=MESSAGE_TEMPLATES[(ReminderType.PROMISE_TO_PAY_FOLLOW_UP, channel)]["key"],
                            status=ReminderScheduleStatus.DUE if promised_time <= now else ReminderScheduleStatus.UPCOMING,
                            metadata={"promise_to_pay_date": latest_promise.promise_date},
                        )
                    )

        items.sort(key=lambda item: item.scheduled_for)
        return items
