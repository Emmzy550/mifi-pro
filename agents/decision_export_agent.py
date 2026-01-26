import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

import config
from models.assessment import Assessment
from models.borrower import Borrower
from models.decision_export import DecisionExport, ExportType, ExportStatus
from utils.db import Database


class DecisionExportAgent:
    DISCLAIMER = "This decision was generated automatically by the system based on predefined policies."

    @staticmethod
    def _sanitize_filename(value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9]+", "_", value.strip())
        return safe.strip("_") or "Applicant"

    @staticmethod
    def _string_value(value) -> str:
        if value is None:
            return ""
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)

    @staticmethod
    def _build_export_payload(assessment: Assessment, borrower: Borrower) -> Dict:
        final_meta = assessment.final_decision_metadata or {}
        outcome = final_meta.get("officer_decision") or DecisionExportAgent._string_value(assessment.decision)

        payload = {
            "assessment_id": assessment.assessment_id,
            "applicant_name": borrower.name,
            "decision_outcome": outcome,
            "risk_score": assessment.risk_score,
            "risk_level": DecisionExportAgent._string_value(assessment.risk_level),
            "recommended_amount": final_meta.get("final_amount", assessment.recommended_amount),
            "recommended_interest_rate": final_meta.get("final_interest_rate", assessment.recommended_interest_rate),
            "decision_summary": assessment.decision_summary,
            "generated_at": datetime.now(timezone.utc),
            "model_version": config.ML_MODEL_VERSION,
            "policy_version": assessment.policy_version,
        }
        return payload

    @staticmethod
    def _build_risk_factors(assessment: Assessment) -> List[Dict]:
        metrics = assessment.metrics or {}
        rows: List[Dict] = []

        for key in ["dti_ratio", "expense_ratio", "behavioral_stability", "saving_trend", "utility_compliance"]:
            if key in metrics:
                rows.append({"factor": key, "value": metrics.get(key), "category": "metric"})

        ml_features = metrics.get("ml_feature_importance", {})
        if isinstance(ml_features, dict):
            for feature, value in ml_features.items():
                rows.append({"factor": feature, "value": value, "category": "ml_feature_importance"})

        for flag in assessment.flags or []:
            rows.append({"factor": flag, "value": "FLAG", "category": "flag"})

        for factor in assessment.blocking_factors or []:
            rows.append({"factor": factor, "value": "BLOCK", "category": "blocking_factor"})

        for code in assessment.decision_reason_codes or []:
            rows.append({"factor": code, "value": "REASON_CODE", "category": "reason_code"})

        return rows

    @staticmethod
    def _build_policy_checks(assessment: Assessment) -> List[Dict]:
        metadata = assessment.decision_metadata or {}
        checks: List[Dict] = []

        duration_reason = metadata.get("duration_rejection_reason")
        checks.append({
            "check": "Duration policy",
            "status": "FAIL" if duration_reason else "PASS",
            "details": duration_reason or "Within policy bounds",
        })

        policy_cap_reason = assessment.policy_cap_reason or metadata.get("policy_cap_reason")
        checks.append({
            "check": "Policy cap",
            "status": "FAIL" if policy_cap_reason else "PASS",
            "details": policy_cap_reason or "No policy cap applied",
        })

        starter_applied = bool(metadata.get("starter_loan_applied", assessment.starter_loan_applied))
        checks.append({
            "check": "Starter loan policy",
            "status": "FAIL" if starter_applied else "PASS",
            "details": "Starter policy applied" if starter_applied else "Not applied",
        })

        blocking_factors = assessment.blocking_factors or []
        checks.append({
            "check": "Blocking factors",
            "status": "FAIL" if blocking_factors else "PASS",
            "details": ", ".join(blocking_factors) if blocking_factors else "None",
        })

        return checks

    @staticmethod
    def _build_assessment_inputs(assessment: Assessment, borrower: Borrower) -> List[Dict]:
        rows = [
            {"field": "applicant_name", "value": borrower.name},
            {"field": "employment_type", "value": DecisionExportAgent._string_value(borrower.employment_type)},
            {"field": "monthly_income", "value": borrower.monthly_income},
            {"field": "monthly_expenses", "value": borrower.monthly_expenses},
            {"field": "existing_debt", "value": borrower.existing_debt},
            {"field": "loan_amount_requested", "value": borrower.loan_amount_requested},
            {"field": "loan_purpose", "value": borrower.loan_purpose},
            {"field": "requested_duration_days", "value": assessment.requested_duration_days},
            {"field": "assessment_source", "value": assessment.assessment_source},
        ]

        data_used = assessment.data_used or {}
        for key, value in data_used.items():
            rows.append({"field": f"data_used.{key}", "value": value})

        return rows

    @staticmethod
    def _hash_file(file_path: str) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _write_pdf(file_path: str, payload: Dict):
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(file_path, pagesize=letter)

        content = [
            Paragraph("Decision Summary Export", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Applicant Name: {payload['applicant_name']}", styles["Normal"]),
            Paragraph(f"Assessment ID: {payload['assessment_id']}", styles["Normal"]),
            Paragraph(f"Decision Outcome: {payload['decision_outcome']}", styles["Normal"]),
            Paragraph(f"Risk Score: {payload['risk_score']}", styles["Normal"]),
            Paragraph(f"Risk Level: {payload['risk_level']}", styles["Normal"]),
            Paragraph(f"Recommended Amount: {payload['recommended_amount']}", styles["Normal"]),
            Paragraph(f"Recommended Interest Rate: {payload['recommended_interest_rate']}", styles["Normal"]),
            Spacer(1, 12),
            Paragraph("Decision Summary", styles["Heading2"]),
            Paragraph(payload["decision_summary"], styles["Normal"]),
            Spacer(1, 12),
            Paragraph(f"Generated At: {payload['generated_at'].isoformat()}", styles["Normal"]),
            Paragraph(f"Model Version: {payload['model_version']}", styles["Normal"]),
            Paragraph(f"Policy Version: {payload['policy_version']}", styles["Normal"]),
            Spacer(1, 18),
            Paragraph(DecisionExportAgent.DISCLAIMER, styles["Italic"]),
        ]

        doc.build(content)

    @staticmethod
    def _write_xlsx(file_path: str, payload: Dict, assessment: Assessment, borrower: Borrower):
        decision_summary = pd.DataFrame([{
            "assessment_id": payload["assessment_id"],
            "applicant_name": payload["applicant_name"],
            "decision_outcome": payload["decision_outcome"],
            "risk_score": payload["risk_score"],
            "risk_level": payload["risk_level"],
            "recommended_amount": payload["recommended_amount"],
            "recommended_interest_rate": payload["recommended_interest_rate"],
            "decision_summary": payload["decision_summary"],
            "generated_at": payload["generated_at"].isoformat(),
            "model_version": payload["model_version"],
            "policy_version": payload["policy_version"],
        }])

        risk_factors = pd.DataFrame(DecisionExportAgent._build_risk_factors(assessment))
        assessment_inputs = pd.DataFrame(DecisionExportAgent._build_assessment_inputs(assessment, borrower))
        policy_checks = pd.DataFrame(DecisionExportAgent._build_policy_checks(assessment))

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            decision_summary.to_excel(writer, sheet_name="Decision Summary", index=False)
            risk_factors.to_excel(writer, sheet_name="Risk Factors", index=False)
            assessment_inputs.to_excel(writer, sheet_name="Assessment Inputs", index=False)
            policy_checks.to_excel(writer, sheet_name="Policy Checks", index=False)

    @staticmethod
    def generate_exports(
        assessment: Assessment,
        borrower: Borrower,
        generated_by: str,
        force: bool = False
    ) -> List[DecisionExport]:
        if not assessment.final_decision_metadata:
            raise ValueError("Decision is not finalized. Cannot generate exports.")

        payload = DecisionExportAgent._build_export_payload(assessment, borrower)
        export_date = payload["generated_at"].strftime("%Y%m%d")
        safe_name = DecisionExportAgent._sanitize_filename(payload["applicant_name"])

        export_dir = os.getenv("EXPORT_BASE_DIR", os.path.join("exports", "decisions", assessment.assessment_id))
        os.makedirs(export_dir, exist_ok=True)

        existing = Database.list_decision_exports(assessment.assessment_id)
        if existing and not force:
            return existing

        next_version = 1
        if existing:
            next_version = max(exp.export_version for exp in existing) + 1
        exports: List[DecisionExport] = []

        for export_type in [ExportType.PDF, ExportType.XLSX]:
            extension = "pdf" if export_type == ExportType.PDF else "xlsx"
            filename = f"{safe_name}_{assessment.assessment_id}_{export_date}_{export_type.value}.v{next_version}.{extension}"
            file_path = os.path.join(export_dir, filename)

            try:
                if export_type == ExportType.PDF:
                    DecisionExportAgent._write_pdf(file_path, payload)
                else:
                    DecisionExportAgent._write_xlsx(file_path, payload, assessment, borrower)

                file_hash = DecisionExportAgent._hash_file(file_path)
                export_record = DecisionExport(
                    id=f"EXP-{uuid.uuid4().hex[:10].upper()}",
                    decision_id=assessment.assessment_id,
                    assessment_id=assessment.assessment_id,
                    organization_id=assessment.organization_id,
                    applicant_name=payload["applicant_name"],
                    export_type=export_type,
                    file_path=file_path,
                    file_hash=file_hash,
                    generated_by=generated_by,
                    model_version=payload["model_version"],
                    policy_version=payload["policy_version"],
                    export_version=next_version,
                    status=ExportStatus.READY,
                )
                Database.save_decision_export(export_record)
                exports.append(export_record)
            except Exception as exc:
                export_record = DecisionExport(
                    id=f"EXP-{uuid.uuid4().hex[:10].upper()}",
                    decision_id=assessment.assessment_id,
                    assessment_id=assessment.assessment_id,
                    organization_id=assessment.organization_id,
                    applicant_name=payload["applicant_name"],
                    export_type=export_type,
                    file_path=file_path,
                    file_hash="",
                    generated_by=generated_by,
                    model_version=payload["model_version"],
                    policy_version=payload["policy_version"],
                    export_version=next_version,
                    status=ExportStatus.FAILED,
                    error=str(exc),
                )
                Database.save_decision_export(export_record)
                exports.append(export_record)

        return exports
