from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.assessment import Assessment
from models.borrower import Borrower
from models.borrower_communication import BorrowerCommunicationRecord
from models.borrower_note import BorrowerNote, BorrowerNoteType
from models.borrower_profile import (
    BorrowerApplicationHistoryItem,
    BorrowerBiodata,
    BorrowerDirectoryItem,
    BorrowerDocumentItem,
    BorrowerIdentitySummary,
    BorrowerLoanHistoryItem,
    BorrowerLoanSummary,
    BorrowerProfileOverview,
    BorrowerRepaymentHistoryItem,
    BorrowerRiskSignal,
    BorrowerStatusBadge,
)
from models.loan import Loan
from models.loan_tracking import LoanCollectionEventType
from models.sms_log import SMSLog
from services.loan_tracking_service import LoanTrackingService
from services.reminder_service import ReminderService
from utils.db import Database


class BorrowerProfileService:
    @staticmethod
    def _enum_value(value: Any) -> Optional[str]:
        return getattr(value, "value", value)

    @staticmethod
    def _safe_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        try:
            return parsed.astimezone(timezone.utc)
        except Exception:
            return parsed

    @classmethod
    def _latest_assessment(cls, assessments: List[Assessment]) -> Optional[Assessment]:
        if not assessments:
            return None
        return sorted(
            assessments,
            key=lambda item: cls._safe_datetime(getattr(item, "decision_timestamp", None)) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0]

    @classmethod
    def _latest_assessment_document_summary(cls, assessments: List[Assessment], profile_keys: List[str]) -> Dict[str, Any]:
        for assessment in sorted(
            assessments,
            key=lambda item: cls._safe_datetime(getattr(item, "decision_timestamp", None)) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        ):
            metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
            summaries = metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []
            for summary in summaries:
                if isinstance(summary, dict) and str(summary.get("summary_profile") or "").upper() in profile_keys:
                    return summary
        return {}

    @classmethod
    def _synthesize_borrower(
        cls,
        borrower_id: str,
        organization_id: str,
        assessments: List[Assessment],
        loans: List[Loan],
    ) -> Borrower:
        latest_assessment = cls._latest_assessment(assessments)
        latest_bank_summary = cls._latest_assessment_document_summary(
            assessments,
            ["BANK_STATEMENT_SUMMARY", "MOBILE_MONEY_SUMMARY", "COMBINED_FINANCIAL_SNAPSHOT"],
        )
        latest_payslip_summary = cls._latest_assessment_document_summary(assessments, ["PAYSLIP_SUMMARY"])
        latest_loan = sorted(
            loans,
            key=lambda item: cls._safe_datetime(getattr(item, "disbursed_at", None)) or cls._safe_datetime(getattr(item, "created_at", None)) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[0] if loans else None

        metrics = latest_assessment.metrics if latest_assessment and isinstance(latest_assessment.metrics, dict) else {}
        borrower_name = (
            getattr(latest_assessment, "borrower_name", None)
            or latest_payslip_summary.get("employee_name")
            or latest_bank_summary.get("account_holder_name")
            or f"Borrower {borrower_id[-6:] if borrower_id else 'Profile'}"
        )
        employment_type = (
            metrics.get("employment_type")
            or latest_payslip_summary.get("employment_type")
            or "unknown"
        )
        monthly_income = (
            latest_payslip_summary.get("net_pay")
            or latest_bank_summary.get("estimated_monthly_income")
            or latest_bank_summary.get("average_monthly_inflow")
            or 0.0
        )
        requested_amount = (
            getattr(latest_assessment, "requested_amount", None)
            or getattr(latest_loan, "amount", None)
            or 1.0
        )
        return Borrower(
            id=borrower_id,
            organization_id=organization_id,
            name=str(borrower_name),
            phone=str(metrics.get("phone") or latest_bank_summary.get("phone_number") or ""),
            employment_type=employment_type,
            monthly_income=float(monthly_income or 0.0),
            monthly_expenses=float(metrics.get("monthly_expenses") or 0.0),
            existing_debt=float(metrics.get("existing_debt") or 0.0),
            loan_amount_requested=max(float(requested_amount or 0.0), 1.0),
            loan_purpose=str(metrics.get("loan_purpose") or "Loan relationship on file"),
            national_id=latest_bank_summary.get("id_number") or latest_payslip_summary.get("employee_id"),
        )

    @classmethod
    def resolve_borrower(
        cls,
        borrower_id: str,
        organization_id: Optional[str],
    ) -> Optional[Borrower]:
        borrower = Database.get_borrower(borrower_id)
        if borrower:
            if organization_id and borrower.organization_id != organization_id:
                return None
            return borrower

        assessments = Database.list_assessments_by_borrower(borrower_id=borrower_id, organization_id=organization_id)
        loans = Database.list_loans_by_borrower(borrower_id=borrower_id, organization_id=organization_id)
        if not assessments and not loans:
            return None

        resolved_org_id = organization_id or (assessments[0].organization_id if assessments else loans[0].organization_id)
        return cls._synthesize_borrower(
            borrower_id=borrower_id,
            organization_id=resolved_org_id,
            assessments=assessments,
            loans=loans,
        )

    @classmethod
    def _borrower_registry(
        cls,
        organization_id: Optional[str],
    ) -> Dict[str, Tuple[Borrower, List[Assessment], List[Loan]]]:
        borrowers = Database.list_borrowers(organization_id=organization_id)
        loans = Database.list_loans(organization_id=organization_id)
        assessments = Database.list_assessments(organization_id=organization_id)

        borrower_lookup: Dict[str, Borrower] = {borrower.id: borrower for borrower in borrowers if borrower.id}
        loan_lookup: Dict[str, List[Loan]] = {}
        assessment_lookup: Dict[str, List[Assessment]] = {}

        for loan in loans:
            if loan.borrower_id:
                loan_lookup.setdefault(loan.borrower_id, []).append(loan)
        for assessment in assessments:
            if assessment.borrower_id:
                assessment_lookup.setdefault(assessment.borrower_id, []).append(assessment)

        registry: Dict[str, Tuple[Borrower, List[Assessment], List[Loan]]] = {}
        for borrower_id in sorted(set(borrower_lookup.keys()) | set(loan_lookup.keys()) | set(assessment_lookup.keys())):
            borrower_assessments = assessment_lookup.get(borrower_id, [])
            borrower_loans = loan_lookup.get(borrower_id, [])
            borrower = borrower_lookup.get(borrower_id) or cls._synthesize_borrower(
                borrower_id=borrower_id,
                organization_id=organization_id or (borrower_assessments[0].organization_id if borrower_assessments else borrower_loans[0].organization_id),
                assessments=borrower_assessments,
                loans=borrower_loans,
            )
            registry[borrower_id] = (borrower, borrower_assessments, borrower_loans)
        return registry

    @classmethod
    def _status_badges(cls, borrower: Borrower, loans: List[Loan], assessments: List[Assessment]) -> List[BorrowerStatusBadge]:
        badges: List[BorrowerStatusBadge] = []
        active_loans = [loan for loan in loans if str(cls._enum_value(loan.status)).upper() in {"ACTIVE", "DISBURSED", "PENDING_DISBURSEMENT"}]
        if active_loans:
            badges.append(BorrowerStatusBadge(label="Active borrower", tone="positive"))
        if len(assessments) > 1:
            badges.append(BorrowerStatusBadge(label="Repeat borrower", tone="info"))

        latest_assessment = cls._latest_assessment(assessments)
        if latest_assessment and str(cls._enum_value(latest_assessment.risk_level)).upper() == "HIGH":
            badges.append(BorrowerStatusBadge(label="High risk", tone="warning"))

        overdue_detected = False
        recovery_detected = False
        for loan in active_loans:
            summary = LoanTrackingService.summarize(loan, borrower=borrower)
            if float(summary.get("overdue_amount") or 0.0) > 0:
                overdue_detected = True
            if str(summary.get("tracker_state") or "").upper() == "RECOVERY":
                recovery_detected = True
        if overdue_detected:
            badges.append(BorrowerStatusBadge(label="Delinquent", tone="danger"))
        if recovery_detected:
            badges.append(BorrowerStatusBadge(label="Watchlist", tone="warning"))
        return badges

    @classmethod
    def list_directory(cls, organization_id: Optional[str]) -> List[BorrowerDirectoryItem]:
        items: List[BorrowerDirectoryItem] = []
        for borrower, borrower_assessments, borrower_loans in cls._borrower_registry(organization_id).values():
            latest_assessment = cls._latest_assessment(borrower_assessments)
            summaries = [LoanTrackingService.summarize(loan, borrower=borrower) for loan in borrower_loans]
            active_loans = [
                summary for summary in summaries if str(summary.get("loan_status") or "").upper() in {"ACTIVE", "DISBURSED", "PENDING_DISBURSEMENT"}
            ]
            outstanding_balance = round(sum(float(item.get("outstanding_balance") or 0.0) for item in active_loans), 2)
            needs_attention = any(
                str(item.get("tracker_state") or "").upper() in {"AT_RISK", "RECOVERY", "WATCH"} or float(item.get("overdue_amount") or 0.0) > 0
                for item in summaries
            )
            activity_candidates = [
                cls._safe_datetime(getattr(latest_assessment, "decision_timestamp", None)),
                *[cls._safe_datetime(summary.get("last_contact_at")) for summary in summaries],
            ]
            last_activity = max(
                [candidate for candidate in activity_candidates if candidate is not None],
                default=None,
            )
            latest_tracker_state = next((str(item.get("tracker_state")) for item in summaries if item.get("tracker_state")), None)

            items.append(
                BorrowerDirectoryItem(
                    borrower_id=borrower.id or "",
                    full_name=borrower.name,
                    phone=borrower.phone,
                    employment_type=str(cls._enum_value(getattr(borrower, "employment_type", None)) or "").replace("_", " ").title() or None,
                    active_loans=len(active_loans),
                    past_applications=len(borrower_assessments),
                    outstanding_balance=outstanding_balance,
                    latest_risk_level=str(cls._enum_value(getattr(latest_assessment, "risk_level", None))) if latest_assessment else None,
                    latest_tracker_state=latest_tracker_state,
                    needs_attention=needs_attention,
                    last_activity_at=last_activity,
                    badges=cls._status_badges(borrower, borrower_loans, borrower_assessments),
                )
            )

        items.sort(key=lambda item: (not item.needs_attention, -(item.outstanding_balance or 0), item.full_name.lower()))
        return items

    @classmethod
    def _document_rows(cls, assessments: List[Assessment]) -> List[BorrowerDocumentItem]:
        rows: List[BorrowerDocumentItem] = []
        for assessment in assessments:
            metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
            raw_docs = metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []
            created_at = cls._safe_datetime(getattr(assessment, "created_at", None))
            for idx, raw_item in enumerate(raw_docs):
                if not isinstance(raw_item, dict):
                    continue
                doc_type = str(raw_item.get("document_type") or raw_item.get("summary_profile") or "UNKNOWN")
                summary_profile = str(raw_item.get("summary_profile") or "")
                if "BANK_STATEMENT" in summary_profile:
                    doc_type = "BANK_STATEMENT"
                elif "PAYSLIP" in summary_profile:
                    doc_type = "PAYSLIP"
                elif "NRC" in summary_profile:
                    doc_type = "NRC_ID"
                elif doc_type == "MOBILE_MONEY" or "MOBILE_MONEY" in summary_profile:
                    doc_type = "MOBILE_MONEY"
                one_liner = raw_item.get("raw_text_preview") or raw_item.get("account_holder_name") or raw_item.get("employee_name") or raw_item.get("employer_name")
                rows.append(
                    BorrowerDocumentItem(
                        doc_id=f"{assessment.assessment_id}-DOC-{idx + 1}",
                        assessment_id=assessment.assessment_id,
                        type=doc_type,
                        file_name=raw_item.get("source_filename"),
                        upload_date=created_at,
                        status="PARSED",
                        provider=raw_item.get("bank_name") or raw_item.get("provider") or raw_item.get("employer_name"),
                        period=raw_item.get("statement_period") or raw_item.get("pay_period_end") or raw_item.get("pay_date"),
                        extracted_summary=str(one_liner)[:180] if one_liner else None,
                        secure_file_url=raw_item.get("secure_file_url"),
                        confidence=raw_item.get("confidence") or raw_item.get("quality_score") or raw_item.get("document_confidence"),
                    )
                )

            missing_docs = metrics.get("missing_documents") if isinstance(metrics.get("missing_documents"), list) else []
            for missing_doc in missing_docs:
                rows.append(
                    BorrowerDocumentItem(
                        doc_id=f"{assessment.assessment_id}-MISSING-{missing_doc}",
                        assessment_id=assessment.assessment_id,
                        type=str(missing_doc).upper(),
                        upload_date=created_at,
                        status="MISSING",
                        extracted_summary="Required document was not uploaded for this assessment.",
                    )
                )

        rows.sort(key=lambda item: item.upload_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return rows

    @classmethod
    def _risk_flags(cls, borrower: Borrower, loans: List[Loan], assessments: List[Assessment]) -> List[BorrowerRiskSignal]:
        flags: List[BorrowerRiskSignal] = []
        latest_assessment = cls._latest_assessment(assessments)
        if latest_assessment:
            if str(cls._enum_value(latest_assessment.risk_level)).upper() == "HIGH":
                flags.append(BorrowerRiskSignal(label="Latest assessment rated high risk", severity="HIGH", source="ASSESSMENT"))
            for flag in latest_assessment.flags or []:
                flags.append(BorrowerRiskSignal(label=str(flag).replace("_", " ").title(), severity="MEDIUM", source="ASSESSMENT"))
            for reason in latest_assessment.decision_reason_codes or []:
                flags.append(BorrowerRiskSignal(label=str(reason).replace("_", " ").title(), severity="MEDIUM", source="POLICY"))
            for blocker in latest_assessment.blocking_factors or []:
                flags.append(BorrowerRiskSignal(label=str(blocker), severity="HIGH", source="ASSESSMENT"))
            metrics = latest_assessment.metrics if isinstance(latest_assessment.metrics, dict) else {}
            for document_summary in metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []:
                if not isinstance(document_summary, dict):
                    continue
                for risk_flag in document_summary.get("risk_flags") if isinstance(document_summary.get("risk_flags"), list) else []:
                    flags.append(BorrowerRiskSignal(label=str(risk_flag), severity="MEDIUM", source="DOCUMENT"))

        for loan in loans:
            summary = LoanTrackingService.summarize(loan, borrower=borrower)
            tracker_state = str(summary.get("tracker_state") or "").upper()
            if tracker_state in {"AT_RISK", "RECOVERY"}:
                flags.append(
                    BorrowerRiskSignal(
                        label=f"Collection state is {tracker_state.replace('_', ' ').title()}",
                        severity="HIGH" if tracker_state == "RECOVERY" else "MEDIUM",
                        detail=str(summary.get("recommended_action") or ""),
                        source="LOAN_TRACKER",
                    )
                )
            if bool(summary.get("broken_promise")):
                flags.append(BorrowerRiskSignal(label="Broken promise-to-pay detected", severity="HIGH", source="LOAN_TRACKER"))
            if float(summary.get("overdue_amount") or 0.0) > 0:
                flags.append(BorrowerRiskSignal(label="Current arrears outstanding", severity="HIGH", detail=f"Overdue amount: {summary.get('overdue_amount')}", source="LOAN_TRACKER"))

        unique: Dict[str, BorrowerRiskSignal] = {}
        for flag in flags:
            unique.setdefault(f"{flag.source}:{flag.label}", flag)
        return list(unique.values())[:18]

    @classmethod
    def _note_timeline(cls, borrower_id: str, organization_id: str, loans: List[Loan]) -> List[BorrowerNote]:
        notes = Database.list_borrower_notes(borrower_id=borrower_id, organization_id=organization_id)
        derived_notes: List[BorrowerNote] = []
        for loan in loans:
            for event in loan.collection_history or []:
                if event.event_type != LoanCollectionEventType.NOTE or not event.note:
                    continue
                derived_notes.append(
                    BorrowerNote(
                        note_id=f"{loan.loan_id}-{event.event_id}",
                        borrower_id=borrower_id,
                        organization_id=organization_id,
                        note_type=BorrowerNoteType.COLLECTION,
                        text=event.note,
                        related_loan_id=loan.loan_id,
                        created_by_name=event.recorded_by,
                        created_by_email=event.recorded_by,
                        created_at=event.occurred_at,
                    )
                )
        all_notes = notes + derived_notes
        all_notes.sort(key=lambda item: item.created_at, reverse=True)
        return all_notes

    @classmethod
    def _communication_timeline(
        cls,
        borrower_id: str,
        organization_id: str,
        communications: List[BorrowerCommunicationRecord],
        sms_logs: List[SMSLog],
    ) -> List[BorrowerCommunicationRecord]:
        merged = list(communications)
        existing_ids = {item.communication_id for item in merged}
        for sms in sms_logs:
            communication_id = f"LEGACY-{sms.id}"
            if communication_id in existing_ids:
                continue
            merged.append(
                BorrowerCommunicationRecord(
                    communication_id=communication_id,
                    organization_id=organization_id,
                    borrower_id=borrower_id,
                    assessment_id=sms.assessment_id,
                    reminder_type="MANUAL",
                    channel="SMS",
                    recipient_number=sms.phone_number,
                    sender_type="OFFICER",
                    automated=False,
                    template_key="legacy_assessment_sms",
                    template_version="legacy",
                    message_body=sms.message,
                    message_preview=sms.message[:180],
                    delivery_status=str(sms.status).upper(),
                    provider=sms.provider,
                    provider_message_id=sms.provider_id,
                    triggered_by_user_id=sms.sent_by,
                    metadata={"source": "assessment_sms_log"},
                    created_at=sms.sent_at,
                    sent_at=sms.sent_at,
                )
            )
        merged.sort(key=lambda item: item.sent_at or item.created_at, reverse=True)
        return merged

    @classmethod
    def build_profile(cls, borrower: Borrower, organization_id: str) -> BorrowerProfileOverview:
        all_assessments = Database.list_assessments(organization_id=organization_id)
        assessments = [item for item in all_assessments if item.borrower_id == borrower.id]
        all_loans = Database.list_loans(organization_id=organization_id)
        loans = [item for item in all_loans if item.borrower_id == borrower.id]
        contact_preferences = Database.get_borrower_contact_preference(borrower_id=borrower.id or "", organization_id=organization_id)
        communications = Database.list_borrower_communications(borrower_id=borrower.id or "", organization_id=organization_id)
        sms_logs = Database.list_sms_logs_for_borrower(borrower_id=borrower.id or "", organization_id=organization_id)

        latest_assessment = cls._latest_assessment(assessments)
        bank_summary = cls._latest_assessment_document_summary(assessments, ["BANK_STATEMENT_SUMMARY", "COMBINED_FINANCIAL_SNAPSHOT"])
        mobile_money_summary = cls._latest_assessment_document_summary(assessments, ["MOBILE_MONEY_SUMMARY", "BANK_STATEMENT_SUMMARY"])
        payslip_summary = cls._latest_assessment_document_summary(assessments, ["PAYSLIP_SUMMARY"])
        nrc_summary = cls._latest_assessment_document_summary(assessments, ["NRC_IDENTITY_SUMMARY"])

        active_loans = [loan for loan in loans if str(cls._enum_value(loan.status)).upper() in {"ACTIVE", "DISBURSED", "PENDING_DISBURSEMENT"}]
        closed_loans = [loan for loan in loans if str(cls._enum_value(loan.status)).upper() in {"PAID", "DEFAULTED"}]
        tracker_summaries = [LoanTrackingService.summarize(loan, borrower=borrower) for loan in loans]
        current_arrears_amount = round(sum(float(item.get("overdue_amount") or 0.0) for item in tracker_summaries), 2)
        outstanding_balance = round(sum(float(item.get("outstanding_balance") or 0.0) for item in tracker_summaries), 2)
        total_repaid = round(
            sum(
                float(event.amount or 0.0)
                for loan in loans
                for event in (loan.collection_history or [])
                if event.event_type == LoanCollectionEventType.PAYMENT
            ),
            2,
        )

        identity = BorrowerIdentitySummary(
            borrower_id=borrower.id or "",
            full_name=borrower.name,
            national_id=borrower.national_id or nrc_summary.get("id_number"),
            phone=borrower.phone,
            location=bank_summary.get("address") or mobile_money_summary.get("address"),
            borrower_type=str(cls._enum_value(getattr(borrower, "employment_type", None)) or "").replace("_", " ").title() or None,
            status_badges=cls._status_badges(borrower, loans, assessments),
            contact_preferences=contact_preferences,
        )

        biodata = BorrowerBiodata(
            date_of_birth=nrc_summary.get("date_of_birth"),
            gender=nrc_summary.get("gender"),
            employer_or_business_name=payslip_summary.get("employer_name") or bank_summary.get("employer_name"),
            monthly_income=borrower.monthly_income or payslip_summary.get("net_pay"),
            employment_type=str(cls._enum_value(getattr(borrower, "employment_type", None)) or "").replace("_", " ").title() or None,
        )

        applications = [
            BorrowerApplicationHistoryItem(
                assessment_id=item.assessment_id,
                application_date=cls._safe_datetime(getattr(item, "decision_timestamp", None)),
                product=item.metrics.get("loan_product") if isinstance(item.metrics, dict) else None,
                requested_amount=item.requested_amount,
                recommended_decision=str(cls._enum_value(item.decision)),
                final_decision=(item.final_decision_metadata or {}).get("officer_decision") if isinstance(item.final_decision_metadata, dict) else None,
                status="SEALED" if item.final_decision_metadata else "PENDING_OFFICER",
                officer_name=(item.final_decision_metadata or {}).get("officer_name") if isinstance(item.final_decision_metadata, dict) else None,
                risk_level=str(cls._enum_value(item.risk_level)),
                requested_duration_days=item.requested_duration_days,
            )
            for item in sorted(assessments, key=lambda item: cls._safe_datetime(getattr(item, "decision_timestamp", None)) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        ]

        loan_rows: List[BorrowerLoanHistoryItem] = []
        for loan in sorted(loans, key=lambda item: cls._safe_datetime(getattr(item, "disbursed_at", None)) or cls._safe_datetime(getattr(item, "created_at", None)) or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
            summary = LoanTrackingService.summarize(loan, borrower=borrower)
            term_days = getattr(loan, "term_days", None) or 0
            disbursement_date = cls._safe_datetime(getattr(loan, "disbursed_at", None))
            maturity_date = (disbursement_date + timedelta(days=term_days)).date().isoformat() if disbursement_date and term_days else None
            loan_rows.append(
                BorrowerLoanHistoryItem(
                    loan_id=loan.loan_id,
                    assessment_id=loan.assessment_id,
                    status=str(cls._enum_value(loan.status)),
                    disbursement_date=disbursement_date,
                    maturity_date=maturity_date,
                    installment_pattern=str(cls._enum_value(getattr(getattr(loan, "tracking_profile", None), "repayment_frequency", None))) if getattr(loan, "tracking_profile", None) else None,
                    repayment_progress=0.0 if float(summary.get("total_due") or 0.0) <= 0 else round(float(summary.get("total_collected") or 0.0) / float(summary.get("total_due") or 1.0), 3),
                    outstanding_amount=float(summary.get("outstanding_balance") or 0.0),
                    delinquency_state=str(summary.get("tracker_state") or ""),
                    collection_lane=str(summary.get("tracking_lane") or ""),
                    amount=loan.amount,
                    currency=loan.currency,
                )
            )

        repayment_rows: List[BorrowerRepaymentHistoryItem] = []
        for loan in loans:
            summary = LoanTrackingService.summarize(loan, borrower=borrower)
            for event in sorted(loan.collection_history or [], key=lambda item: item.occurred_at, reverse=True):
                repayment_rows.append(
                    BorrowerRepaymentHistoryItem(
                        event_id=event.event_id,
                        loan_id=loan.loan_id,
                        payment_date=event.occurred_at,
                        amount=event.amount,
                        method=str(cls._enum_value(event.channel)) if event.channel else None,
                        status=str(summary.get("tracker_state") or ""),
                        event_type=str(cls._enum_value(event.event_type)),
                        note=event.note,
                        promise_to_pay_date=event.promise_date,
                    )
                )
        repayment_rows.sort(key=lambda item: item.payment_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        risk_flags = cls._risk_flags(borrower, loans, assessments)
        notes = cls._note_timeline(borrower.id or "", organization_id, loans)
        communication_timeline = cls._communication_timeline(
            borrower_id=borrower.id or "",
            organization_id=organization_id,
            communications=communications,
            sms_logs=sms_logs,
        )
        reminder_schedule = ReminderService.build_schedule(
            borrower=borrower,
            organization_id=organization_id,
            loans=active_loans or loans,
            assessments=assessments,
            preference=contact_preferences,
        )

        return BorrowerProfileOverview(
            identity=identity,
            biodata=biodata,
            loan_summary=BorrowerLoanSummary(
                active_loans=len(active_loans),
                closed_loans=len(closed_loans),
                past_applications=len(applications),
                total_outstanding_balance=outstanding_balance,
                total_repaid_historically=total_repaid,
                most_recent_loan_status=loan_rows[0].status if loan_rows else None,
                current_arrears_amount=current_arrears_amount,
                current_risk_state=(risk_flags[0].label if risk_flags else str(cls._enum_value(getattr(latest_assessment, "risk_level", None))) if latest_assessment else None),
            ),
            applications=applications,
            loans=loan_rows,
            repayments=repayment_rows[:120],
            documents=cls._document_rows(assessments),
            bank_statement_summary=bank_summary or mobile_money_summary,
            payslip_summary=payslip_summary,
            risk_flags=risk_flags,
            notes=notes,
            communications=communication_timeline,
            reminder_schedule=reminder_schedule,
        )
