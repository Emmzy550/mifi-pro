import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

import config
from models.assessment import Assessment
from models.borrower import Borrower, IDType
from models.decision_export import DecisionExport, ExportType, ExportStatus
from utils.db import Database


class DecisionExportAgent:
    DISCLAIMER = "This decision was generated automatically by the system based on predefined policies. It serves as decision support, and the final lending decision remains with the institution."

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
    def _format_currency(value) -> str:
        if value is None: return "ZMW 0.00"
        try:
            return f"ZMW {float(value):,.2f}"
        except:
            return f"ZMW {value}"

    @staticmethod
    def _build_export_payload(assessment: Assessment, borrower: Borrower) -> Dict:
        final_meta = assessment.final_decision_metadata or {}
        outcome = final_meta.get("officer_decision") or DecisionExportAgent._string_value(assessment.decision)

        # Identification status
        id_provided = "Yes" if getattr(borrower, "id_provided", False) else "No"
        id_type = DecisionExportAgent._string_value(getattr(borrower, "id_type", IDType.UNKNOWN))
        
        payload = {
            "assessment_id": assessment.assessment_id,
            "applicant_name": borrower.name,
            "decision_outcome": outcome,
            "risk_score": assessment.risk_score,
            "risk_score_pct": f"{assessment.risk_score*100:.0f}%" if assessment.risk_score <= 1 else f"{assessment.risk_score:.0f}%",
            "risk_level": DecisionExportAgent._string_value(assessment.risk_level),
            "recommended_amount": DecisionExportAgent._format_currency(final_meta.get("final_amount", assessment.recommended_amount)),
            "recommended_duration": f"{final_meta.get('final_duration', assessment.recommended_duration_days or assessment.requested_duration_days)} Days",
            "recommended_interest_rate": f"{final_meta.get('final_interest_rate', assessment.recommended_interest_rate)}%",
            "decision_summary": assessment.decision_summary,
            "generated_at": datetime.now(timezone.utc),
            "model_version": config.ML_MODEL_VERSION,
            "policy_version": assessment.policy_version,
            "identification_provided": id_provided,
            "id_type": id_type,
            "key_factors": DecisionExportAgent._generate_key_factors(assessment, borrower)
        }
        return payload

    @staticmethod
    def _generate_key_factors(assessment: Assessment, borrower: Borrower) -> List[str]:
        factors = []
        metrics = assessment.metrics or {}
        
        # 1. Income vs Expenses (Affordability)
        dti = metrics.get("dti_ratio")
        if dti is not None:
            if dti < 0.4: factors.append("Strong affordability: Debt-to-income ratio is within safe limits.")
            else: factors.append("Affordability constraint: High debt-to-income ratio detected.")
        
        # 2. Transaction Stability
        stability = metrics.get("behavioral_stability")
        if stability is not None:
            if stability > 0.7: factors.append("Stable transaction history: Suggests consistent financial behavior.")
            else: factors.append("Transaction patterns show some variability, consistent with informal income and within acceptable risk limits.")

        # 3. Request vs Policy
        if assessment.requested_duration_days > 90:
            factors.append("Term risk: Requested duration exceeds standard short-term policy.")
        elif assessment.requested_duration_days <= 30:
            factors.append("Term compliance: Short-term request aligns with liquidity pools.")

        # 4. Flags & Risks
        if not assessment.flags:
            factors.append("Clean risk profile: No critical high-risk flags detected.")
        else:
            high_risk = [f for f in assessment.flags if "HIGH" in f or "CRITICAL" in f]
            if high_risk: factors.append(f"Risk alerts: {len(high_risk)} critical flags requiring attention.")
            else: factors.append("Supporting merits: Minor risk adjustments applied.")

        # Ensure we have 3-5 factors
        if len(factors) < 3:
            factors.append("Policy alignment: Evaluation based on standard MFI underwriting rules.")
            
        return factors[:5]

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
            {"field": "monthly_income", "value": DecisionExportAgent._format_currency(borrower.monthly_income)},
            {"field": "monthly_expenses", "value": DecisionExportAgent._format_currency(borrower.monthly_expenses)},
            {"field": "existing_debt", "value": DecisionExportAgent._format_currency(borrower.existing_debt)},
            {"field": "loan_amount_requested", "value": DecisionExportAgent._format_currency(borrower.loan_amount_requested)},
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
        from reportlab.platypus import HRFlowable
        
        styles = getSampleStyleSheet()
        accent_color = colors.Color(0.12, 0.16, 0.23) # Dark Slate #1E293B equivalent
        
        # Custom styles for MFI-friendly, institution-grade look
        title_style = ParagraphStyle(
            'MFITitle',
            parent=styles['Title'],
            fontSize=22,
            fontName='Helvetica-Bold',
            spaceAfter=5,
            alignment=0,
            textColor=accent_color
        )
        
        section_header_style = ParagraphStyle(
            'MFISectionHeader',
            parent=styles['Heading2'],
            fontSize=11,
            fontName='Helvetica-Bold',
            spaceBefore=12,
            spaceAfter=6,
            textColor=accent_color,
            textTransform='UPPERCASE',
            letterSpacing=1
        )

        label_style = ParagraphStyle(
            'MFILabel',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            fontName='Helvetica'
        )

        value_style = ParagraphStyle(
            'MFIValue',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        
        doc = SimpleDocTemplate(
            file_path, 
            pagesize=letter, 
            leftMargin=0.75*inch, 
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        content = []

        # 1. Header: Title and Divider
        content.append(Paragraph("Credit Decision Summary", title_style))
        content.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=15))
        
        # 2. Applicant and Assessment Details (Two-column Grid)
        details_data = [
            [
                [Paragraph("APPLICANT NAME", label_style), Paragraph(payload['applicant_name'], value_style)],
                [Paragraph("ASSESSMENT DATE", label_style), Paragraph(payload['generated_at'].strftime("%Y-%m-%d %H:%M"), value_style)]
            ],
            [
                [Paragraph("ASSESSMENT ID", label_style), Paragraph(payload['assessment_id'], value_style)],
                [Paragraph("POLICY VERSION", label_style), Paragraph(payload['policy_version'], value_style)]
            ]
        ]
        
        details_table = Table(details_data, colWidths=[3.5*inch, 3.5*inch])
        details_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        content.append(details_table)
        content.append(Spacer(1, 10))

        # 3. Decision Summary Box (Key Outcome)
        # We use a nested table for the background fill and border
        summary_inner_data = [
            [Paragraph("DECISION OUTCOME", label_style), Paragraph("RISK LEVEL", label_style), Paragraph("RISK SCORE", label_style)],
            [
                Paragraph(f"<font size=16 color='{accent_color}'><b>{payload['decision_outcome']}</b></font>", styles['Normal']),
                Paragraph(f"<font size=16 color='{accent_color}'><b>{payload['risk_level']}</b></font>", styles['Normal']),
                Paragraph(f"<font size=16 color='{accent_color}'><b>{payload['risk_score_pct']}</b></font>", styles['Normal'])
            ]
        ]
        summary_inner_table = Table(summary_inner_data, colWidths=[2.3*inch, 2.3*inch, 2.3*inch])
        summary_inner_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,1), (-1,1), 12),
            ('TOPPADDING', (0,0), (-1,0), 12),
        ]))

        summary_box_table = Table([[summary_inner_table]], colWidths=[7.0*inch])
        summary_box_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,-1), colors.Color(0.97, 0.98, 1.0)), # Very light blue/grey #F8FAFC
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        content.append(summary_box_table)
        content.append(Spacer(1, 25))

        # 4. Loan Recommendation Section
        content.append(Paragraph("Financial Recommendation", section_header_style))
        content.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=10))
        
        reco_data = [
            [
                [Paragraph("RECOMMENDED AMOUNT", label_style), Paragraph(payload['recommended_amount'], value_style)],
                [Paragraph("TENOR / DURATION", label_style), Paragraph(payload['recommended_duration'], value_style)]
            ],
            [
                [Paragraph("INTEREST RATE", label_style), Paragraph(payload['recommended_interest_rate'], value_style)],
                [Paragraph("IDENTIFICATION STATUS", label_style), Paragraph(f"Provided ({payload['id_type']})" if payload['identification_provided'] == "Yes" else "Not Provided", value_style)]
            ]
        ]
        
        reco_table = Table(reco_data, colWidths=[3.5*inch, 3.5*inch])
        reco_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ]))
        content.append(reco_table)
        content.append(Spacer(1, 15))

        # 5. Policy & Risk Analysis
        content.append(Paragraph("Risk Assessment Factors", section_header_style))
        content.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=10))
        
        for factor in payload['key_factors']:
            content.append(Paragraph(f"<font color='#475569'>•</font> {factor}", styles['Normal']))
            content.append(Spacer(1, 5))
        
        content.append(Spacer(1, 15))
        content.append(Paragraph("Policy Justification", section_header_style))
        content.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=10))
        content.append(Paragraph(payload["decision_summary"], styles["Normal"]))
        
        # 6. Footer & Disclaimer
        content.append(Spacer(1, 40))
        content.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=10))
        
        footer_data = [
            [Paragraph(f"<font color='grey'>{DecisionExportAgent.DISCLAIMER}</font>", styles["Italic"]), 
             Paragraph(f"<font color='grey' size=8>System Version: v1.0.0 | Model: {payload['model_version']}</font>", styles["Normal"])]
        ]
        footer_table = Table(footer_data, colWidths=[5.0*inch, 2.0*inch])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ]))
        content.append(footer_table)

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
