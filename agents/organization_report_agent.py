import io
import math
import os
import unicodedata
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from agents.billing_agent import BillingAgent
from models.organization import Organization
from pricing_config import PLAN_CONFIG
from utils.db import Database


class OrganizationReportAgent:
    REPORT_DIR = os.path.join("exports", "organization_reports")
    DOCUMENT_LABELS = {
        "bank_statement": "Bank Statement",
        "payslip": "Payslip",
        "mobile_money": "Mobile Money",
        "generic_csv": "CSV",
        "nrc_id": "National ID",
        "combined_snapshot": "Combined Snapshot",
        "unknown": "Other",
    }
    CHART_COLORS = [
        "#4f46e5",
        "#22c55e",
        "#f59e0b",
        "#ef4444",
        "#0ea5e9",
        "#8b5cf6",
        "#14b8a6",
    ]

    @staticmethod
    def _to_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                return None
        return None

    @staticmethod
    def _format_iso(value: Any) -> Optional[str]:
        dt = OrganizationReportAgent._to_datetime(value)
        return dt.isoformat() if dt else None

    @staticmethod
    def _format_money(value: float, currency: str = "ZMW") -> str:
        return f"{currency} {float(value or 0):,.0f}"

    @staticmethod
    def _resolve_user_limit(org: Organization) -> Optional[int]:
        if org.user_limit is not None:
            return org.user_limit
        plan_name = org.plan.value if hasattr(org.plan, "value") else str(org.plan)
        plan_config = PLAN_CONFIG.get(plan_name.upper(), PLAN_CONFIG["SANDBOX"])
        return plan_config.get("user_limit")

    @staticmethod
    def _pdf_safe_text(value: Any) -> str:
        if value is None:
            return ""

        text = str(value)
        replacements = {
            "\u00a0": " ",
            "\u00b7": " - ",
            "\u2012": "-",
            "\u2013": "-",
            "\u2014": "-",
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2022": "-",
            "&": " and ",
            "<": "(",
            ">": ")",
            "Â·": " - ",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)

        normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        return " ".join(normalized.split())

    @classmethod
    def _sanitize_for_pdf(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._sanitize_for_pdf(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._sanitize_for_pdf(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._sanitize_for_pdf(item) for item in value)
        if isinstance(value, str):
            return cls._pdf_safe_text(value)
        return value

    @classmethod
    def _paragraph_text(cls, value: Any) -> str:
        return escape(cls._pdf_safe_text(value))

    @classmethod
    def build_report_data(cls, org: Organization, days: int = 30) -> Dict[str, Any]:
        days = max(7, min(int(days or 30), 365))
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=days - 1)
        db = Database.get_db()

        assessment_docs = list(db.collection("assessments").where("organization_id", "==", org.id).stream())
        loans = Database.list_loans(organization_id=org.id)
        users = Database.list_users_by_org(org.id)
        api_keys = Database.list_api_keys(org.id)
        payments = sorted(Database.list_payments(org.id), key=lambda item: item.timestamp, reverse=True)
        usage_logs = Database.get_usage_logs(org.id, limit=1000, start_date=cutoff_date)
        billing_summary = BillingAgent.get_full_usage_summary(org)

        risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "REJECTED": 0}
        decision_totals = {"Approved": 0, "Conditional": 0, "Rejected": 0, "Referred": 0}
        upload_counts: Counter[str] = Counter()
        role_counts: Counter[str] = Counter()
        endpoint_counts: Counter[str] = Counter()
        alerts: List[Dict[str, str]] = []
        recent_assessments: List[Dict[str, Any]] = []

        today = now.date()
        decision_trend_map: Dict[Any, Dict[str, Any]] = {}
        usage_trend_map: Dict[Any, int] = {}
        for index in range(days):
            day = today - timedelta(days=index)
            decision_trend_map[day] = {
                "name": day.strftime("%b %d"),
                "approved": 0,
                "conditional": 0,
                "rejected": 0,
            }
            usage_trend_map[day] = 0

        total_assessments = 0
        assessments_in_range = 0
        assessments_with_documents = 0
        uploaded_documents = 0
        missing_documents = 0

        for doc in assessment_docs:
            data = doc.to_dict() or {}
            created_dt = cls._to_datetime(data.get("created_at") or data.get("decision_timestamp"))
            if not created_dt:
                created_dt = now

            total_assessments += 1
            if created_dt < cutoff_date:
                continue

            assessments_in_range += 1
            decision = str(data.get("decision") or "").upper()
            risk_level = str(data.get("risk_level") or "").upper()
            metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
            document_summaries = metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []
            missing_document_list = metrics.get("missing_documents") if isinstance(metrics.get("missing_documents"), list) else []

            if decision == "APPROVE":
                decision_totals["Approved"] += 1
                trend_bucket = decision_trend_map.get(created_dt.date())
                if trend_bucket:
                    trend_bucket["approved"] += 1
            elif decision == "CONDITIONAL":
                decision_totals["Conditional"] += 1
                trend_bucket = decision_trend_map.get(created_dt.date())
                if trend_bucket:
                    trend_bucket["conditional"] += 1
            elif decision == "REFER":
                decision_totals["Referred"] += 1
            elif decision == "REJECT":
                decision_totals["Rejected"] += 1
                trend_bucket = decision_trend_map.get(created_dt.date())
                if trend_bucket:
                    trend_bucket["rejected"] += 1

            if decision == "REJECT":
                risk_counts["REJECTED"] += 1
            elif risk_level in risk_counts:
                risk_counts[risk_level] += 1

            if document_summaries:
                assessments_with_documents += 1
            uploaded_documents += len(document_summaries)
            missing_documents += len(missing_document_list)

            for summary in document_summaries:
                doc_type = str(summary.get("document_type") or "unknown").lower()
                upload_counts[doc_type] += 1

            recent_assessments.append({
                "assessment_id": data.get("assessment_id") or doc.id,
                "borrower_id": data.get("borrower_id"),
                "decision": decision or "UNKNOWN",
                "risk_level": risk_level or "UNKNOWN",
                "document_count": len(document_summaries),
                "created_at": created_dt.isoformat(),
            })

        active_loans = 0
        defaulted_loans = 0
        disbursed_volume = 0.0
        loans_in_range = 0
        par_30 = 0
        par_60 = 0
        par_90 = 0
        recent_payments = []
        for loan in loans:
            status = str(getattr(loan, "status", "")).upper()
            amount = float(getattr(loan, "amount", 0.0) or 0.0)
            disbursed_volume += amount

            disbursed_dt = cls._to_datetime(getattr(loan, "disbursed_at", None))
            if status in {"DISBURSED", "ACTIVE"}:
                active_loans += 1
                if disbursed_dt:
                    age_days = (today - disbursed_dt.date()).days
                    if age_days > 30:
                        par_30 += 1
                    if age_days > 60:
                        par_60 += 1
                    if age_days > 90:
                        par_90 += 1

            if disbursed_dt and disbursed_dt >= cutoff_date:
                loans_in_range += 1
                if "DEFAULT" in status:
                    defaulted_loans += 1

        default_rate = (defaulted_loans / loans_in_range * 100) if loans_in_range else 0.0

        for user in users:
            role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
            role_counts[str(role_value).upper()] += 1

        for usage_log in usage_logs:
            endpoint_counts[usage_log.endpoint] += 1
            log_dt = cls._to_datetime(usage_log.timestamp)
            if log_dt and log_dt.date() in usage_trend_map:
                usage_trend_map[log_dt.date()] += 1

        negative_outcome_rate = (
            (risk_counts["REJECTED"] + risk_counts["HIGH"]) / assessments_in_range
            if assessments_in_range else 0.0
        )
        if negative_outcome_rate >= 0.4:
            alerts.append({
                "title": "Risk outcomes elevated",
                "message": f"{negative_outcome_rate * 100:.1f}% of assessments were rejected or high risk in the selected period."
            })

        production_limit = billing_summary["production"]["limit"]
        production_usage = billing_summary["production"]["usage"]
        if production_limit and production_limit < 1000000000:
            production_ratio = production_usage / max(production_limit, 1)
            if production_ratio >= 0.8:
                alerts.append({
                    "title": "Production usage nearing limit",
                    "message": f"{production_usage} of {production_limit} production assessments used this billing period."
                })

        if missing_documents > 0:
            alerts.append({
                "title": "Document gaps detected",
                "message": f"{missing_documents} required documents were still missing across recent assessments."
            })

        paid_amount_total = sum(
            float(payment.amount or 0.0)
            for payment in payments
            if str(getattr(payment.status, "value", payment.status)) == "PAID"
        )
        paid_invoices = sum(1 for payment in payments if str(getattr(payment.status, "value", payment.status)) == "PAID")
        pending_invoices = sum(1 for payment in payments if str(getattr(payment.status, "value", payment.status)) == "PENDING")

        for payment in payments[:5]:
            payment_status = payment.status.value if hasattr(payment.status, "value") else str(payment.status)
            gateway = payment.gateway.value if hasattr(payment.gateway, "value") else str(payment.gateway)
            recent_payments.append({
                "payment_id": payment.payment_id,
                "plan": payment.plan,
                "amount": float(payment.amount or 0.0),
                "currency": payment.currency,
                "status": payment_status,
                "gateway": gateway,
                "timestamp": cls._format_iso(payment.timestamp),
            })

        recent_usage = [
            {
                "timestamp": cls._format_iso(log.timestamp),
                "endpoint": log.endpoint,
                "api_key_id": log.api_key_id,
                "assessment_id": log.assessment_id,
            }
            for log in usage_logs[:8]
        ]

        recent_assessments.sort(key=lambda item: item["created_at"] or "", reverse=True)
        top_endpoints = [
            {"name": endpoint, "count": count}
            for endpoint, count in endpoint_counts.most_common(6)
        ]
        upload_distribution = []
        for index, (doc_type, count) in enumerate(upload_counts.most_common()):
            upload_distribution.append({
                "name": cls.DOCUMENT_LABELS.get(doc_type, doc_type.replace("_", " ").title()),
                "value": count,
                "color": cls.CHART_COLORS[index % len(cls.CHART_COLORS)]
            })

        risk_distribution = [
            {"name": "Low Risk", "value": risk_counts["LOW"], "color": "#22c55e"},
            {"name": "Medium Risk", "value": risk_counts["MEDIUM"], "color": "#f59e0b"},
            {"name": "High Risk", "value": risk_counts["HIGH"], "color": "#ef4444"},
            {"name": "Rejected", "value": risk_counts["REJECTED"], "color": "#94a3b8"},
        ]

        decision_summary = [
            {"name": name, "value": value, "color": color}
            for (name, value), color in zip(
                decision_totals.items(),
                ["#22c55e", "#f59e0b", "#ef4444", "#4f46e5"]
            )
        ]

        usage_trends = [
            {"name": day.strftime("%b %d"), "count": usage_trend_map[day]}
            for day in sorted(usage_trend_map.keys())
        ]
        decision_trends = [decision_trend_map[day] for day in sorted(decision_trend_map.keys())]
        role_breakdown = [
            {"name": role.replace("_", " ").title(), "value": count}
            for role, count in sorted(role_counts.items(), key=lambda item: (-item[1], item[0]))
        ]

        seat_limit = cls._resolve_user_limit(org)
        plan_name = org.plan.value if hasattr(org.plan, "value") else str(org.plan)

        return {
            "generated_at": now.isoformat(),
            "range": {
                "days": days,
                "start": cutoff_date.date().isoformat(),
                "end": today.isoformat(),
            },
            "organization": {
                "id": org.id,
                "name": org.name,
                "plan": plan_name,
                "billing_status": org.billing_status.value if hasattr(org.billing_status, "value") else str(org.billing_status),
                "payment_status": org.payment_status.value if hasattr(org.payment_status, "value") else str(org.payment_status),
                "environment": org.environment.value if hasattr(org.environment, "value") else str(org.environment),
                "created_at": cls._format_iso(org.created_at),
                "period_end": cls._format_iso(org.current_period_end),
            },
            "summary": {
                "assessments_in_range": assessments_in_range,
                "lifetime_assessments": total_assessments,
                "uploaded_documents": uploaded_documents,
                "assessments_with_documents": assessments_with_documents,
                "api_calls_in_range": len(usage_logs),
                "active_loans": active_loans,
                "disbursed_volume": round(disbursed_volume, 2),
                "default_rate": round(default_rate, 1),
                "team_members": len(users),
                "api_keys": len(api_keys),
            },
            "billing": {
                "current_plan": billing_summary["current_plan"],
                "billing_status": billing_summary["billing_status"],
                "payment_status": billing_summary["payment_status"],
                "period_end": billing_summary["period_end"],
                "sandbox": billing_summary["sandbox"],
                "production": billing_summary["production"],
                "payments_count": len(payments),
                "paid_invoices": paid_invoices,
                "pending_invoices": pending_invoices,
                "paid_amount_total": round(paid_amount_total, 2),
            },
            "team": {
                "seat_limit": seat_limit,
                "seat_used": len(users),
                "role_breakdown": role_breakdown,
            },
            "portfolio": {
                "par_snapshot": {
                    "par_30": par_30,
                    "par_60": par_60,
                    "par_90": par_90,
                    "par_30_rate": round((par_30 / max(active_loans, 1)) * 100, 1) if active_loans else 0.0,
                    "par_60_rate": round((par_60 / max(active_loans, 1)) * 100, 1) if active_loans else 0.0,
                    "par_90_rate": round((par_90 / max(active_loans, 1)) * 100, 1) if active_loans else 0.0,
                },
                "alerts": alerts,
            },
            "charts": {
                "decision_trends": decision_trends,
                "decision_summary": decision_summary,
                "risk_distribution": risk_distribution,
                "upload_distribution": upload_distribution,
                "usage_trends": usage_trends,
            },
            "activity": {
                "top_endpoints": top_endpoints,
                "recent_usage": recent_usage,
                "recent_assessments": recent_assessments[:8],
                "recent_payments": recent_payments,
            },
        }

    @classmethod
    def _build_pie_chart(cls, title: str, items: List[Dict[str, Any]]) -> Optional[Drawing]:
        valid_items = [item for item in items if float(item.get("value", 0) or 0) > 0]
        if not valid_items:
            return None

        drawing = Drawing(260, 180)
        drawing.add(String(10, 164, cls._pdf_safe_text(title), fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0f172a")))

        chart = Pie()
        chart.x = 40
        chart.y = 18
        chart.width = 110
        chart.height = 110
        chart.sideLabels = True
        chart.simpleLabels = False
        chart.data = [float(item["value"]) for item in valid_items[:5]]
        chart.labels = [cls._pdf_safe_text(item["name"])[:22] for item in valid_items[:5]]
        chart.slices.strokeColor = colors.white
        chart.slices.strokeWidth = 0.5

        for index, item in enumerate(valid_items[:5]):
            chart.slices[index].fillColor = colors.HexColor(item.get("color", cls.CHART_COLORS[index % len(cls.CHART_COLORS)]))

        drawing.add(chart)
        return drawing

    @classmethod
    def _build_bar_chart(cls, title: str, items: List[Dict[str, Any]], color: str = "#4f46e5") -> Optional[Drawing]:
        valid_items = items[:6]
        if not valid_items:
            return None

        values = [float(item.get("value", item.get("count", 0)) or 0) for item in valid_items]
        max_value = max(values) if values else 0

        drawing = Drawing(300, 190)
        drawing.add(String(10, 174, cls._pdf_safe_text(title), fontName="Helvetica-Bold", fontSize=11, fillColor=colors.HexColor("#0f172a")))

        chart = VerticalBarChart()
        chart.x = 42
        chart.y = 30
        chart.height = 110
        chart.width = 230
        chart.data = [values]
        chart.categoryAxis.categoryNames = [cls._pdf_safe_text(item.get("name", ""))[:14] for item in valid_items]
        chart.categoryAxis.labels.boxAnchor = "ne"
        chart.categoryAxis.labels.angle = 20
        chart.categoryAxis.labels.fontSize = 7
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(1, math.ceil(max_value * 1.25))
        chart.valueAxis.valueStep = max(1, math.ceil(chart.valueAxis.valueMax / 4))
        chart.valueAxis.labels.fontSize = 7
        chart.bars[0].fillColor = colors.HexColor(color)
        chart.bars[0].strokeColor = colors.HexColor(color)
        chart.barWidth = 20
        chart.groupSpacing = 10
        drawing.add(chart)
        return drawing

    @classmethod
    def generate_report_pdf(cls, report: Dict[str, Any]) -> str:
        os.makedirs(cls.REPORT_DIR, exist_ok=True)

        organization = report["organization"]
        filename = (
            f"Organization_Report_{organization['id']}_{report['range']['days']}d_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        file_path = os.path.join(cls.REPORT_DIR, filename)

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=0.65 * inch,
            rightMargin=0.65 * inch,
            topMargin=0.65 * inch,
            bottomMargin=0.65 * inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        )
        subtitle_style = ParagraphStyle(
            "ReportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=18,
        )
        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=10,
            spaceAfter=8,
        )
        label_style = ParagraphStyle(
            "Label",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_LEFT,
        )
        value_style = ParagraphStyle(
            "Value",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        table_header_style = ParagraphStyle(
            "TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#334155"),
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        table_header_right_style = ParagraphStyle(
            "TableHeaderRight",
            parent=table_header_style,
            alignment=TA_RIGHT,
        )
        table_cell_style = ParagraphStyle(
            "TableCell",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=11.5,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_LEFT,
            wordWrap="CJK",
        )
        table_cell_right_style = ParagraphStyle(
            "TableCellRight",
            parent=table_cell_style,
            alignment=TA_RIGHT,
        )
        metric_label_style = ParagraphStyle(
            "MetricLabel",
            parent=table_cell_style,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor("#475569"),
        )
        metric_value_style = ParagraphStyle(
            "MetricValue",
            parent=table_cell_style,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
        )

        summary = report["summary"]
        billing = report["billing"]
        team = report["team"]
        portfolio = report["portfolio"]
        activity = report["activity"]
        usable_width = doc.width

        def width_ratio(*parts: float) -> List[float]:
            total = sum(parts) or 1
            return [usable_width * (part / total) for part in parts]

        def table_paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
            text = "-" if value is None else str(value).strip() or "-"
            safe_text = escape(cls._pdf_safe_text(text)).replace("\n", "<br/>")
            return Paragraph(safe_text, style)

        def build_table(
            rows: List[List[Any]],
            col_widths: List[float],
            *,
            header: bool = True,
            alignments: Optional[List[str]] = None,
            header_fill: str = "#e2e8f0",
            header_text_color: str = "#334155",
            grid_color: str = "#e2e8f0",
            stripe_fill: str = "#f8fafc",
            plain_fill: str = "#ffffff",
            repeat_header: bool = True,
        ) -> Table:
            formatted_rows: List[List[Paragraph]] = []
            for row_index, row in enumerate(rows):
                formatted_row: List[Paragraph] = []
                for col_index, value in enumerate(row):
                    align_right = bool(alignments and col_index < len(alignments) and alignments[col_index] == "right")
                    if header and row_index == 0:
                        style = table_header_right_style if align_right else table_header_style
                    else:
                        style = table_cell_right_style if align_right else table_cell_style
                    formatted_row.append(table_paragraph(value, style))
                formatted_rows.append(formatted_row)

            table = Table(
                formatted_rows,
                colWidths=col_widths,
                hAlign="LEFT",
                repeatRows=1 if header and repeat_header else 0,
            )
            table_styles = [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(grid_color)),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor(grid_color)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(plain_fill)),
            ]
            if header:
                table_styles.extend(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_fill)),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(header_text_color)),
                    ]
                )
            data_start = 1 if header else 0
            for row_index in range(data_start, len(rows)):
                if (row_index - data_start) % 2 == 0:
                    table_styles.append(
                        ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor(stripe_fill))
                    )
            table.setStyle(TableStyle(table_styles))
            return table

        story: List[Any] = []
        story.append(Paragraph("Organization Report", title_style))
        story.append(
            Paragraph(
                f"{organization['name']} - {report['range']['days']}-day summary - Generated {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}",
                subtitle_style,
            )
        )
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=14))

        overview_table = Table(
            [
                [Paragraph("Organization", label_style), Paragraph(organization["name"], value_style), Paragraph("Plan", label_style), Paragraph(organization["plan"], value_style)],
                [Paragraph("Billing Status", label_style), Paragraph(organization["billing_status"], value_style), Paragraph("Payment Status", label_style), Paragraph(organization["payment_status"], value_style)],
                [Paragraph("Environment", label_style), Paragraph(organization["environment"], value_style), Paragraph("Period End", label_style), Paragraph(str(organization["period_end"] or "N/A"), value_style)],
            ],
            colWidths=width_ratio(1.1, 2.5, 1.1, 2.5),
            hAlign="LEFT",
        )
        overview_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2ff")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#eef2ff")),
        ]))
        story.append(overview_table)
        story.append(Spacer(1, 12))

        story.append(Paragraph("Summary Metrics", section_style))
        summary_table = Table(
            [
                [
                    Paragraph("Assessments", metric_label_style),
                    Paragraph(f"{summary['assessments_in_range']}", metric_value_style),
                    Paragraph("Uploaded Docs", metric_label_style),
                    Paragraph(f"{summary['uploaded_documents']}", metric_value_style),
                ],
                [
                    Paragraph("API Calls", metric_label_style),
                    Paragraph(f"{summary['api_calls_in_range']}", metric_value_style),
                    Paragraph("Team Members", metric_label_style),
                    Paragraph(f"{summary['team_members']}", metric_value_style),
                ],
                [
                    Paragraph("Active Loans", metric_label_style),
                    Paragraph(f"{summary['active_loans']}", metric_value_style),
                    Paragraph("Default Rate", metric_label_style),
                    Paragraph(f"{summary['default_rate']:.1f}%", metric_value_style),
                ],
                [
                    Paragraph("Disbursed Volume", metric_label_style),
                    Paragraph(cls._format_money(summary["disbursed_volume"]), metric_value_style),
                    Paragraph("API Keys", metric_label_style),
                    Paragraph(f"{summary['api_keys']}", metric_value_style),
                ],
            ],
            colWidths=width_ratio(1.35, 1.75, 1.45, 2.65),
            hAlign="LEFT",
        )
        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#eef2ff")),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 12))

        chart_flowables = []
        risk_chart = cls._build_pie_chart("Risk Distribution", report["charts"]["risk_distribution"])
        upload_chart = cls._build_bar_chart("Uploaded Documents", report["charts"]["upload_distribution"], color="#0ea5e9")
        if risk_chart:
            chart_flowables.append(risk_chart)
        if upload_chart:
            chart_flowables.append(upload_chart)
        if len(chart_flowables) == 2:
            chart_table = Table([[chart_flowables[0], chart_flowables[1]]], colWidths=width_ratio(1, 1), hAlign="LEFT")
            chart_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(chart_table)
            story.append(Spacer(1, 8))
        elif chart_flowables:
            story.append(chart_flowables[0])
            story.append(Spacer(1, 8))

        story.append(Paragraph("Billing & Team", section_style))
        billing_team_table = Table(
            [
                [
                    Paragraph("Sandbox Usage", metric_label_style),
                    Paragraph(f"{billing['sandbox']['usage']} / {billing['sandbox']['limit']}", metric_value_style),
                    Paragraph("Seat Usage", metric_label_style),
                    Paragraph(f"{team['seat_used']} / {team['seat_limit'] or 'Unlimited'}", metric_value_style),
                ],
                [
                    Paragraph("Production Usage", metric_label_style),
                    Paragraph(f"{billing['production']['usage']} / {billing['production']['limit']}", metric_value_style),
                    Paragraph("Paid Invoices", metric_label_style),
                    Paragraph(f"{billing['paid_invoices']}", metric_value_style),
                ],
                [
                    Paragraph("Pending Invoices", metric_label_style),
                    Paragraph(f"{billing['pending_invoices']}", metric_value_style),
                    Paragraph("Paid Amount", metric_label_style),
                    Paragraph(cls._format_money(billing['paid_amount_total'], "ZMW"), metric_value_style),
                ],
            ],
            colWidths=width_ratio(1.5, 1.85, 1.45, 2.4),
            hAlign="LEFT",
        )
        billing_team_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
            ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#eef2ff")),
        ]))
        story.append(billing_team_table)
        story.append(Spacer(1, 10))

        if team["role_breakdown"]:
            story.append(Paragraph("Role Breakdown", section_style))
            role_rows = [["Role", "Count"]] + [[item["name"], str(item["value"])] for item in team["role_breakdown"]]
            role_table = build_table(role_rows, width_ratio(5.8, 1.4), alignments=["left", "right"])
            story.append(role_table)
            story.append(Spacer(1, 10))

        if activity["top_endpoints"]:
            story.append(Paragraph("Top Endpoints", section_style))
            endpoint_rows = [["Endpoint", "Calls"]] + [[item["name"], str(item["count"])] for item in activity["top_endpoints"]]
            endpoint_table = build_table(endpoint_rows, width_ratio(6.0, 0.9), alignments=["left", "right"])
            story.append(endpoint_table)
            story.append(Spacer(1, 10))

        story.append(Paragraph("Portfolio Snapshot", section_style))
        par = portfolio["par_snapshot"]
        par_table = build_table(
            [
                ["Metric", "Current Position"],
                ["PAR 30", f"{par['par_30']} ({par['par_30_rate']:.1f}%)"],
                ["PAR 60", f"{par['par_60']} ({par['par_60_rate']:.1f}%)"],
                ["PAR 90", f"{par['par_90']} ({par['par_90_rate']:.1f}%)"],
            ],
            width_ratio(2.0, 5.2),
        )
        story.append(par_table)
        story.append(Spacer(1, 10))

        if portfolio["alerts"]:
            story.append(Paragraph("Alerts", section_style))
            alert_rows = [["Title", "Message"]] + [[item["title"], item["message"]] for item in portfolio["alerts"]]
            alert_table = build_table(
                alert_rows,
                width_ratio(2.0, 5.2),
                header_fill="#fef3c7",
                header_text_color="#92400e",
                grid_color="#fcd34d",
                stripe_fill="#fffbeb",
            )
            story.append(alert_table)
            story.append(Spacer(1, 10))

        if activity["recent_assessments"]:
            story.append(Paragraph("Recent Assessments", section_style))
            assessment_rows = [["Assessment", "Decision", "Risk", "Docs", "Created"]]
            for item in activity["recent_assessments"][:6]:
                created_label = item["created_at"][:10] if item.get("created_at") else "-"
                assessment_rows.append([
                    item["assessment_id"],
                    item["decision"],
                    item["risk_level"],
                    str(item["document_count"]),
                    created_label,
                ])
            assessment_table = build_table(
                assessment_rows,
                width_ratio(2.5, 1.4, 1.1, 0.7, 1.5),
                alignments=["left", "left", "left", "right", "left"],
            )
            story.append(assessment_table)
            story.append(Spacer(1, 10))

        if activity["recent_payments"]:
            story.append(Paragraph("Recent Payments", section_style))
            payment_rows = [["Plan", "Amount", "Status", "Gateway", "Date"]]
            for item in activity["recent_payments"]:
                payment_rows.append([
                    item["plan"],
                    f"{item['currency']} {item['amount']:,.2f}",
                    item["status"],
                    item["gateway"],
                    (item["timestamp"] or "")[:10],
                ])
            payment_table = build_table(
                payment_rows,
                width_ratio(1.5, 1.55, 1.15, 1.35, 1.65),
                alignments=["left", "right", "left", "left", "left"],
            )
            story.append(payment_table)

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#cbd5e1"), spaceAfter=6))
        story.append(Paragraph("Generated by Loan Officer AI Organization Reports", label_style))

        doc.build(story)
        return file_path

    @classmethod
    def generate_report_pdf_bytes(cls, report: Dict[str, Any]) -> bytes:
        safe_report = cls._sanitize_for_pdf(report)
        file_path = cls.generate_report_pdf(safe_report)
        with open(file_path, "rb") as pdf_file:
            return pdf_file.read()
