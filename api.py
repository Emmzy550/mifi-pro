import uuid
from fastapi import FastAPI, HTTPException, Body, Depends, Security, UploadFile, File, Form, Request, Header, BackgroundTasks
from pydantic import ValidationError, BaseModel, Field
from fastapi.responses import FileResponse
from typing import Dict, List, Optional, Any, Literal, Tuple, Union
import io
import json
import hashlib
import secrets
import time
import re
from datetime import datetime, timedelta, timezone
import logging
logger = logging.getLogger(__name__)

from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from models.borrower import Borrower, IDType, IDReviewStatus
from models.assessment import Assessment
from models.loan import Loan, LoanStatus
from models.alternative_data import AlternativeData
from models.organization import Organization, BillingPlan, BillingStatus, OrgEnvironment
from models.api_key import APIKey, KeyStatus
from models.decision_export import DecisionExport
from models.decision_counterfactual import DecisionCounterfactual
from models.user import User, UserRole
from models.officer_action import OfficerAction, OfficerDecision, CommChannel
from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from agents.query_agent import QueryAgent
from agents.auth_agent import AuthAgent, AuthUser, ACCESS_TOKEN_EXPIRE_MINUTES, get_super_admin
from pricing_config import PLAN_CONFIG
from agents.audit_agent import AuditAgent
from agents.decision_export_agent import DecisionExportAgent
from agents.decision_counterfactual_agent import DecisionCounterfactualAgent
from agents.self_healing_agent import SelfHealingAgent
from utils.db import Database
from utils.transaction_parser import TransactionParser
from utils.document_readiness import DocumentReadinessEvaluator
from utils.profile_builder import ProfileBuilder
from models.document import DocumentType, Transaction as DocTransaction, SummaryProfile
from models.document_insight import (
    DecisionDocumentSummary,
    DocumentInsight,
    DocumentInsightFlag,
    DocumentInsightRecord,
    DocumentStatus,
    DocumentFlagSeverity,
)
from models.unified_profile import UnifiedFinancialProfile, AssessmentReadiness
from models.sms_log import SMSLog
from models.follow_up_task import FollowUpTask, FollowUpStatus, FollowUpType, FollowUpPriority
from models.notification import Notification
from models.demo_request import DemoRequest, DemoRequestCreate
from models.loan_tracking import LoanTrackingEventCreate, LoanTrackingSetupRequest
from models.borrower_communication import (
    BorrowerCommunicationRecord,
    BorrowerContactPreference,
    ReminderPreviewRequest,
    ReminderPreviewResponse,
    ReminderScheduleItem,
    ReminderSendRequest,
)
from models.borrower_note import BorrowerNote, BorrowerNoteCreate
from models.borrower_profile import BorrowerDirectoryItem, BorrowerProfileOverview
from services.sms_service import SMSService
from services.email_service import EmailService
from services.webhook_service import WebhookService
from services.loan_tracking_service import LoanTrackingService
from services.reminder_service import ReminderService
from services.borrower_profile_service import BorrowerProfileService
from utils.validators import normalize_phone, clean_name

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, PlainTextResponse, Response
import os
import logging

# PDF parsing is handled within TransactionParser


app = FastAPI(
    title="Loan Officer AI Agent",
    description="""
# Loan Officer AI Agent - API Documentation

The **Loan Officer AI Agent** is an intelligent credit decision system for microfinance institutions, 
SACCOs, and digital lenders. This API helps you:

## Key Features

* Instant Risk Assessment - Get AI-powered loan recommendations in seconds
* Alternative Data Analysis - Upload bank statements for enhanced accuracy
* **🔐 Multi-Tenant Security** - Your data is isolated and secure
* **📈 ML + Rules** - Combines machine learning with business rules
* **📝 Full Audit Trail** - Every decision is logged and explainable

## 🎯 Quick Start

1. **Create a borrower profile** using `/intake/start`
2. **Run risk assessment** using `/assessment/run`
3. **Review the AI recommendation** and make your decision
4. **Disburse the loan** using `/loan/disburse` (if approved)

## 🔑 Authentication

Most endpoints require authentication:
- **API Keys**: For machine-to-machine integration (use `X-API-Key` header)
- **JWT Tokens**: For dashboard users (use `Authorization: Bearer` header)

Get your API keys from the dashboard: Settings → API Keys

## 📚 Full Documentation

* **User Guides**: [http://localhost:8000/documentation](http://localhost:8000/documentation)
* **Developer Docs**: [http://localhost:8000/documentation/getting-started](http://localhost:8000/documentation/getting-started)
* **Integration Guide**: [http://localhost:8000/documentation/customer-api-setup](http://localhost:8000/documentation/customer-api-setup)

## 🆘 Support

Need help? Contact support@your-lender.com or visit our [FAQ](http://localhost:8000/documentation/faq)

---

**Version:** 2.0.0 | **Status:** Production Ready
    """,
    version="2.0.0",
    terms_of_service="https://your-lender.com/terms",
    contact={
        "name": "Support Team",
        "email": "support@your-lender.com",
        "url": "https://your-lender.com/support",
    },
    license_info={
        "name": "Proprietary",
        "url": "https://your-lender.com/license",
    },
    openapi_tags=[
        {
            "name": "System",
            "description": "Health checks and system information",
        },
        {
            "name": "Borrower Management",
            "description": "Create and manage borrower profiles",
        },
        {
            "name": "Risk Assessment",
            "description": "Run AI-powered risk assessments and get loan recommendations",
        },
        {
            "name": "Alternative Data",
            "description": "Upload bank statements and transaction history for enhanced accuracy",
        },
        {
            "name": "Loan Management",
            "description": "Disburse loans and manage loan lifecycle",
        },
        {
            "name": "Authentication",
            "description": "Login, user management, and API key operations",
        },
        {
            "name": "Organization",
            "description": "Organization settings, metrics, and audit logs",
        },
        {
            "name": "Configuration",
            "description": "Feature flags, model version, and system configuration",
        },
    ]
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/debug/health")
async def debug_health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}

@app.get("/debug/db")
async def debug_db_status():
    """Diagnostic endpoint to check database connection status."""
    db = Database.get_db()
    is_mock = isinstance(db, MockFirestore)
    service_name = os.getenv("K_SERVICE", "local")
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "mfi--pro")
    
    return {
        "status": "connected",
        "database_type": "MockFirestore" if is_mock else "Real Firestore",
        "is_mock": is_mock,
        "environment": {
            "service": service_name,
            "project_id": project_id,
            "service_account_path_exists": os.path.exists("serviceAccountKey.json")
        }
    }

@app.get("/debug/assessments")
async def debug_all_assessments():
    """Diagnostic endpoint to list ALL assessments in the database without filtering."""
    assessments = Database.list_assessments()
    org_counts = {}
    for a in assessments:
        org_counts[a.organization_id] = org_counts.get(a.organization_id, 0) + 1
    
    return {
        "total_count": len(assessments),
        "organization_counts": org_counts,
        "recent_assessments": [
            {
                "id": a.assessment_id,
                "org": a.organization_id,
                "created": a.created_at.isoformat() if hasattr(a.created_at, 'isoformat') else str(a.created_at)
            } for a in assessments[:20]
        ]
    }

@app.middleware("http")
async def strip_api_prefix(request: Request, call_next):
    """
    Middleware to strip /api prefix if present.
    This allows local dev (sending /api/...) to work with the app (expecting /...)
    """
    if request.url.path.startswith("/api"):
        request.scope.setdefault("state", {})["api_prefixed"] = True
        request.scope["path"] = request.url.path.replace("/api", "", 1)
    response = await call_next(request)
    return response

# --------------------------------------------------------------------
# STATIC FILES & SPA SERVING
# --------------------------------------------------------------------
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
static_path = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(frontend_dist):
    logger.info(f"STARTUP: FRONTEND: Serving from {frontend_dist}")
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    logger.warning(f"WARNING: FRONTEND: {frontend_dist} not found. Using root legacy mode.")
    # Fallback for root assets if they exist
    root_assets = os.path.join(static_path, "assets")
    if os.path.exists(root_assets):
        app.mount("/assets", StaticFiles(directory=root_assets), name="assets")




# Include Admin Router
from admin_router import admin_router
app.include_router(admin_router)



@app.get("/tester")
async def get_tester():
    return FileResponse(os.path.join(static_path, "index.html"))

@app.get("/apply")
async def get_apply_portal():
    return FileResponse(os.path.join(static_path, "borrower_portal.html"))

@app.get("/admin-ui")
async def get_super_admin_dashboard_ui():
    """
    Public access to the Super Admin Dashboard HTML.
    Note: Data still requires API key.
    """
    return FileResponse(os.path.join(static_path, "super_dashboard.html"))

@app.get("/admin/platform/stats", tags=["Super Admin"])
async def get_platform_stats(current_user: User = Depends(get_super_admin)):
    """
    Get global platform statistics for the Super Admin dashboard.
    """
    import config
    orgs = Database.list_organizations()
    loans = Database.list_loans()
    assessments = Database.list_assessments()
    logger.debug(f"DEBUG: Found {len(orgs)} orgs, {len(loans)} loans, {len(assessments)} assessments")
    
    total_mfis = len(orgs)
    total_disbursed_volume = sum(loan.amount for loan in loans)
    total_assessments = len(assessments)
    
    # Calculate global default rate
    defaulted_loans = [loan for loan in loans if loan.status == "DEFAULTED"]
    global_default_rate = (len(defaulted_loans) / len(loans) * 100) if loans else 0.0
    
    return {
        "total_mfis": total_mfis,
        "total_disbursed_volume": total_disbursed_volume,
        "total_assessments": total_assessments,
        "global_default_rate": global_default_rate,
        "llm_enabled": config.ENABLE_LLM_EXPLANATIONS
    }

@app.patch("/admin/platform/settings", tags=["Super Admin"])
async def update_platform_settings(
    settings: Dict = Body(...),
    current_user: User = Depends(get_super_admin)
):
    """
    Update global platform settings (e.g., toggle LLM).
    """
    import config
    global_updates = []
    
    if "llm_enabled" in settings:
        config.ENABLE_LLM_EXPLANATIONS = settings["llm_enabled"]
        global_updates.append(f"LLM_ENABLED={config.ENABLE_LLM_EXPLANATIONS}")
    
    AuditAgent.log_event("PLATFORM_SETTINGS_UPDATED", current_user.email, {"updates": global_updates})
    return {"status": "success", "updates": global_updates}


def _normalize_public_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value)).strip()
    return normalized or None


def _list_super_admin_users() -> List[User]:
    super_admins = []
    for candidate in Database.list_all_users():
        role_value = getattr(candidate.role, "value", candidate.role)
        if str(role_value).upper() == "SUPER_ADMIN":
            super_admins.append(candidate)
    return super_admins


def _notify_super_admins_of_demo_request(demo_request: DemoRequest) -> int:
    dashboard_url = os.getenv("DASHBOARD_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    if dashboard_url.endswith("/login"):
        dashboard_url = dashboard_url[:-len("/login")]
    admin_url = dashboard_url + "/admin"
    notified_count = 0

    for super_admin in _list_super_admin_users():
        notification = Notification(
            notification_id=f"NTF-{uuid.uuid4().hex[:12].upper()}",
            organization_id=super_admin.organization_id or "PLATFORM_OWNER",
            recipient_user_id=super_admin.id,
            recipient_email=super_admin.email,
            created_by_user_id="PUBLIC_LEAD_FORM",
            type="DEMO_REQUEST_SUBMITTED",
            title="New landing page request",
            message=(
                f"{demo_request.name} from {demo_request.institution} requested a "
                f"{demo_request.intent.value}."
            ),
            metadata={
                "request_id": demo_request.request_id,
                "intent": demo_request.intent.value,
                "name": demo_request.name,
                "institution": demo_request.institution,
                "phone": demo_request.phone,
                "institution_type": demo_request.institution_type,
                "volume": demo_request.volume,
                "admin_url": admin_url
            }
        )
        Database.save_notification(notification)

        if super_admin.email:
            EmailService.send_email(
                to_email=super_admin.email,
                subject=f"New {demo_request.intent.value} request from {demo_request.institution}",
                body_text=(
                    f"A new landing page request was submitted.\n\n"
                    f"Request ID: {demo_request.request_id}\n"
                    f"Intent: {demo_request.intent.value}\n"
                    f"Name: {demo_request.name}\n"
                    f"Institution: {demo_request.institution}\n"
                    f"Phone: {demo_request.phone}\n"
                    f"Institution type: {demo_request.institution_type or 'Not provided'}\n"
                    f"Monthly volume: {demo_request.volume or 'Not provided'}\n\n"
                    f"Open the Super Admin dashboard to review: {admin_url}"
                )
            )

        notified_count += 1

    return notified_count


@app.post("/lead-requests", response_model=Dict[str, Any], tags=["System"])
async def submit_demo_request(payload: DemoRequestCreate):
    """
    Public landing page endpoint for demo, trial, pilot, and contact requests.
    """
    normalized_name = clean_name(payload.name)
    normalized_institution = _normalize_public_text(payload.institution)
    normalized_phone = normalize_phone(payload.phone)
    normalized_institution_type = _normalize_public_text(payload.institution_type)
    normalized_volume = _normalize_public_text(payload.volume)

    if not normalized_name or not normalized_institution or not normalized_phone:
        raise HTTPException(status_code=400, detail="Name, institution, and phone are required.")

    if len(normalized_phone) < 7:
        raise HTTPException(status_code=400, detail="Please enter a valid phone number.")

    demo_request = DemoRequest(
        request_id=f"DRQ-{uuid.uuid4().hex[:10].upper()}",
        intent=payload.intent,
        name=normalized_name,
        institution=normalized_institution,
        phone=normalized_phone,
        institution_type=normalized_institution_type,
        volume=normalized_volume
    )
    Database.save_demo_request(demo_request)

    notified_count = _notify_super_admins_of_demo_request(demo_request)
    AuditAgent.log_event(
        "DEMO_REQUEST_RECEIVED",
        "PUBLIC_LEAD",
        {
            "request_id": demo_request.request_id,
            "intent": demo_request.intent.value,
            "institution": demo_request.institution,
            "notification_count": notified_count,
            "source": demo_request.source,
            "org": "PLATFORM_OWNER"
        }
    )

    return {
        "status": "received",
        "request_id": demo_request.request_id,
        "notified_super_admins": notified_count
    }

# ============================================================================
# AUDIT GUARD: RESPONSE INTEGRITY GATE (NO MERCY)
# ============================================================================
class SemanticContractViolationError(Exception):
    pass

def verify_response_integrity(data: Any):
    """
    Recursively scans the final response object for forbidden legacy artifacts.
    This is the final line of defense.
    """
    FORBIDDEN_KEYS = ["capacity_anchor", "ml_prob_default", "capacity_anchor_amount", "capacity_anchor_reason"]
    FORBIDDEN_PHRASES = ["capacity anchor", "safety limits"]
    
    if isinstance(data, dict):
        for k, v in data.items():
            # Check Keys
            for banned in FORBIDDEN_KEYS:
                if banned in k:
                    raise SemanticContractViolationError(f"Forbidden Key Detected: {k}")
            
            # Check Values (if string)
            if isinstance(v, str):
                for phrase in FORBIDDEN_PHRASES:
                    if phrase in v.lower():
                        raise SemanticContractViolationError(f"Forbidden Phrase Detected in '{k}': {phrase}")
            
            # Recurse
            verify_response_integrity(v)
            
    elif isinstance(data, list):
        for item in data:
            verify_response_integrity(item)

# ============================================================================
# AUDIT GUARD: ROLE-BASED RESPONSE FILTERING
# ============================================================================

def filter_assessment_for_role(assessment: Assessment, role: str) -> Dict[str, Any]:
    """
    Senior Audit Guard: Strips sensitive fields based on requester role.
    Ensures PII and internal risk-logic privacy.
    """
    # Pydantic V2: Use model_dump instead of dict()
    total_data = assessment.model_dump()
    
    # 1. PUBLIC/BORROWER VIEW (Most Restricted)
    # Only what the customer needs to see.
    # GOVERNANCE FIELDS (MANDATORY FOR ALL VIEWS)
    governance_fields = {
        "requested_amount", "decision_timestamp", "decision_reason_codes", "data_used"
    }
    
    public_fields = governance_fields | {
        "assessment_id", "borrower_id", "decision", "recommended_amount", 
        "recommended_interest_rate", "decision_summary", "customer_view", 
        "customer_message", "created_at", "assessment_source"
    }
    
    # 2. OFFICER VIEW
    # Add metrics and professional rationale.
    officer_fields = public_fields | {
        "risk_level", "risk_score", "officer_view", "internal_notes", 
        "flags", "metrics", "blocking_factors",
        "data_quality_score", "adverse_action"
    }
    
    # 3. AUDIT/ADMIN VIEW (Full Transparency)
    # Policy lineage, capacity anchors, and decision metadata.
    audit_fields = officer_fields | {
        "audit_view", "explanation", "explanation_source", "decision_source",
        "policy_version", "observed_deposit_volume", "transaction_count",
        "history_days", "policy_cap_amount", "policy_cap_reason",
        "capacity_based_max", "capacity_multiplier_used", "starter_loan_applied",
        "ml_advisory_only", "ml_attempted_override", "decision_metadata",
        "decision_trace", "data_provenance"
    }
    
    target_fields = public_fields
    if role in ["OFFICER", "API_USER", "BORROWER_PORTAL_ADMIN"]:
        target_fields = officer_fields
    if role in ["SUPER_ADMIN", "ADMIN", "COMPLIANCE"]:
        target_fields = audit_fields
        
    payload = {k: v for k, v in total_data.items() if k in target_fields}
    return augment_assessment_payload(payload)


def decision_to_legacy(decision_value: Any) -> str:
    """
    Backward-compatible decision mapping for legacy clients.
    """
    if decision_value is None:
        return "UNKNOWN"
    decision_str = str(decision_value)
    mapping = {
        "APPROVE": "APPROVED",
        "CONDITIONAL": "CONDITIONAL_APPROVAL",
        "REJECT": "REJECT",
        "REFER": "REFER",
        "WAIT": "WAIT",
    }
    return mapping.get(decision_str, decision_str)


def augment_assessment_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds stable, backward-compatible fields without altering core contracts.
    """
    if "decision" in payload:
        payload["decision_legacy"] = decision_to_legacy(payload.get("decision"))
    if "risk_score" in payload and payload["risk_score"] is not None:
        try:
            payload["risk_score_percent"] = round(float(payload["risk_score"]) * 100.0, 1)
            payload["risk_score_scale"] = "0-1"
        except Exception:
            pass
    return payload


def stable_hash(payload: Dict[str, Any]) -> str:
    """
    Deterministic hash for audit traceability.
    """
    try:
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        return ""


def build_decision_trace(
    borrower: Borrower,
    requested_duration_days: int,
    assessment_source: str,
    risk_results: Dict[str, Any],
    decision_results: Dict[str, Any],
    reason_codes: List[str],
    data_quality_score: Optional[float]
) -> Dict[str, Any]:
    input_snapshot = {
        "borrower_id": borrower.id,
        "organization_id": borrower.organization_id,
        "requested_amount": borrower.loan_amount_requested,
        "requested_duration_days": requested_duration_days,
        "monthly_income": borrower.monthly_income,
        "monthly_expenses": borrower.monthly_expenses,
        "existing_debt": borrower.existing_debt,
        "employment_type": borrower.employment_type,
        "assessment_source": assessment_source
    }
    derived_features = risk_results.get("metrics", {})
    decision_metadata = decision_results.get("decision_metadata", {})

    trace = {
        "input_snapshot": input_snapshot,
        "derived_features": derived_features,
        "risk_score": risk_results.get("risk_score"),
        "risk_level": risk_results.get("risk_level"),
        "decision": decision_results.get("decision"),
        "reason_codes": reason_codes,
        "policy_version": decision_metadata.get("policy_version", "unknown"),
        "decision_engine": "rules_engine",
        "data_quality_score": data_quality_score
    }
    trace["input_hash"] = stable_hash(input_snapshot)
    trace["features_hash"] = stable_hash(derived_features)
    trace["decision_hash"] = stable_hash({
        "decision": trace["decision"],
        "risk_score": trace["risk_score"],
        "risk_level": trace["risk_level"],
        "reason_codes": trace["reason_codes"],
        "policy_version": trace["policy_version"]
    })
    return trace


def apply_data_quality_policy(decision_results: Dict[str, Any], data_quality_score: Optional[float]) -> Dict[str, Any]:
    """
    If data quality is below threshold, force a manual review (REFER) and annotate metadata.
    """
    if data_quality_score is None:
        return decision_results

    import config
    from utils.policy_context import policy_value
    threshold = float(policy_value("data_quality_refer_threshold", config.DATA_QUALITY_REFER_THRESHOLD))
    decision_metadata = decision_results.get("decision_metadata", {})
    decision_metadata["data_quality_score"] = data_quality_score

    if data_quality_score < threshold:
        decision_metadata.setdefault("blocking_factors", [])
        decision_metadata["blocking_factors"].append("DATA_QUALITY_LIMITED")
        decision_metadata["data_quality_impact"] = (
            f"Data quality {data_quality_score:.2f} below threshold {threshold:.2f}; manual review required."
        )
        return {
            "decision": "REFER",
            "recommended_amount": None,
            "recommended_duration_days": None,
            "recommended_interest_rate": 0.0,
            "interest_rate_basis": None,
            "decision_metadata": decision_metadata
        }

    decision_metadata["data_quality_impact"] = "Data quality sufficient for automated assessment."
    decision_results["decision_metadata"] = decision_metadata
    return decision_results


def build_data_provenance(
    data_used: Dict[str, Any],
    data_quality_score: Optional[float],
    consent_event_id: Optional[str],
    consent_channel: Optional[str],
    consent_timestamp: Optional[str],
    document_info: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    provenance = {
        "data_sources": data_used.get("data_sources", []),
        "transaction_days": data_used.get("transaction_days"),
        "transaction_count": data_used.get("transaction_count"),
        "data_recency_days": data_used.get("data_recency_days"),
    }
    if data_quality_score is not None:
        provenance["data_quality_score"] = data_quality_score
    if consent_event_id:
        provenance["consent_event_id"] = consent_event_id
    if consent_channel:
        provenance["consent_channel"] = consent_channel
    if consent_timestamp:
        provenance["consent_timestamp"] = consent_timestamp
    if document_info:
        provenance["document"] = document_info
    return provenance


def transactions_to_history_dicts(transactions: List[Any]) -> List[Dict[str, Any]]:
    history_dicts = []
    for tx in transactions or []:
        t_amount = getattr(tx, "amount", None)
        t_direction = getattr(tx, "direction", None)
        t_date = getattr(tx, "date", None)
        t_id = getattr(tx, "transaction_id", None)

        if isinstance(tx, tuple):
            t_id = tx[0]
            t_date = tx[1]
            t_amount = tx[2]
            t_direction = tx[4]

        if not t_id:
            t_id = f"TX-{hash(str(t_date) + str(getattr(tx, 'description', '')) + str(t_amount))}"

        history_dicts.append({
            "transaction_id": t_id,
            "amount": t_amount,
            "type": "OTHER",
            "timestamp": t_date if isinstance(t_date, str) else t_date.isoformat(),
            "direction": t_direction,
            "description": getattr(tx, "description", ""),
            "confidence_score": getattr(tx, "confidence_score", getattr(tx, "confidence", 0.0)),
            "flags": getattr(tx, "flags", [])
        })

    return history_dicts


def parse_float_or_none(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        text = str(value).replace(",", "").strip()
        return float(text)
    except Exception:
        return None


def sms_next_prompt(step: str) -> str:
    prompts = {
        "CONSENT": "Welcome to Loan Officer AI. Reply YES to consent to data processing.",
        "NAME": "Please reply with your full name.",
        "INCOME": "Monthly income? (numbers only)",
        "EXPENSES": "Monthly expenses? (numbers only)",
        "DEBT": "Existing debt amount? (numbers only, or 0)",
        "AMOUNT": "Requested loan amount? (numbers only)",
        "PURPOSE": "Loan purpose? (e.g., inventory, school fees)",
        "DONE": "Thank you. Processing your assessment now."
    }
    return prompts.get(step, "Reply START to begin a loan assessment.")


def build_document_summaries(extraction_results: List[Any]) -> List[Dict[str, Any]]:
    summaries = []
    for result in extraction_results:
        if result.bank_statement_summary:
            is_mobile_money = str(getattr(result, "document_type", "")).upper().endswith("MOBILE_MONEY")
            summaries.append({
                "document_type": "mobile_money" if is_mobile_money else "bank_statement",
                "summary_profile": result.bank_statement_summary.summary_profile,
                "opening_balance": result.bank_statement_summary.opening_balance,
                "closing_balance": result.bank_statement_summary.closing_balance,
                "total_money_in": result.bank_statement_summary.total_money_in,
                "total_money_out": result.bank_statement_summary.total_money_out,
                "deposit_count": result.bank_statement_summary.deposit_count,
                "transaction_count": len(getattr(result, "transactions", []) or []),
                "statement_period": result.bank_statement_summary.statement_period.model_dump()
                if result.bank_statement_summary.statement_period else None,
                "bank_name": result.bank_statement_summary.bank_name,
                "account_holder_name": result.bank_statement_summary.account_holder_name,
                "provider": result.bank_statement_summary.bank_name if is_mobile_money else None,
                "currency": result.bank_statement_summary.currency,
                "risk_flags": result.bank_statement_summary.risk_flags,
                "confidence": result.confidence,
                "quality_score": result.quality_score,
                "extraction_warnings": result.warnings,
                "source_filename": result.source_filename,
                "source_mime_type": result.source_mime_type,
                "raw_text_preview": result.raw_text_preview
            })
        if result.payslip_summary:
            summaries.append({
                "document_type": "payslip",
                "summary_profile": result.payslip_summary.summary_profile,
                "net_pay": result.payslip_summary.net_pay,
                "gross_pay": result.payslip_summary.gross_pay,
                "deductions": result.payslip_summary.deductions,
                "employer_name": result.payslip_summary.employer_name,
                "employee_name": result.payslip_summary.employee_name,
                "pay_period_start": result.payslip_summary.pay_period_start,
                "pay_period_end": result.payslip_summary.pay_period_end,
                "pay_date": result.payslip_summary.pay_date,
                "pay_frequency": result.payslip_summary.pay_frequency,
                "currency": result.payslip_summary.currency,
                "risk_flags": result.payslip_summary.risk_flags,
                "confidence": result.confidence,
                "quality_score": result.quality_score,
                "extraction_warnings": result.warnings,
                "source_filename": result.source_filename,
                "source_mime_type": result.source_mime_type,
                "raw_text_preview": result.raw_text_preview
            })
        if result.nrc_summary:
            summaries.append({
                "document_type": "nrc_id",
                "summary_profile": result.nrc_summary.summary_profile,
                "full_name": result.nrc_summary.full_name,
                "id_number": result.nrc_summary.id_number,
                "date_of_birth": result.nrc_summary.date_of_birth,
                "gender": result.nrc_summary.gender,
                "risk_flags": result.nrc_summary.risk_flags,
                "confidence": result.confidence,
                "quality_score": result.quality_score,
                "extraction_warnings": result.warnings,
                "source_filename": result.source_filename,
                "source_mime_type": result.source_mime_type,
                "raw_text_preview": result.raw_text_preview
            })
    return summaries


DOCUMENT_TYPE_FROM_PROFILE = {
    "BANK_STATEMENT_SUMMARY": "bank_statement",
    "PAYSLIP_SUMMARY": "payslip",
    "NRC_IDENTITY_SUMMARY": "nrc_id",
    "COMBINED_FINANCIAL_SNAPSHOT": "combined_snapshot",
    "UNKNOWN": "unknown",
}

DOCUMENT_LABELS = {
    "bank_statement": "Bank Statement",
    "payslip": "Payslip",
    "mobile_money": "Mobile Money Statement",
    "generic_csv": "CSV Document",
    "nrc_id": "National ID",
    "combined_snapshot": "Combined Financial Snapshot",
    "unknown": "Document",
}

DOC_ID_UPLOADED_PATTERN = re.compile(r"^(ASMT-[A-Z0-9]+)-DOC-(\d+)$")
DOC_ID_MISSING_PATTERN = re.compile(r"^(ASMT-[A-Z0-9]+)-MISSING-([a-z0-9_]+)$")


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _safe_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return str(value)


def _slugify_token(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _normalize_doc_type(doc_type_hint: Any, summary_profile: Any) -> str:
    if isinstance(doc_type_hint, str) and doc_type_hint.strip():
        normalized = doc_type_hint.strip().lower()
        aliases = {
            "bankstatement": "bank_statement",
            "bank_statement": "bank_statement",
            "payslip": "payslip",
            "mobile_money": "mobile_money",
            "generic_csv": "generic_csv",
            "nrc_id": "nrc_id",
        }
        if normalized in aliases:
            return aliases[normalized]
    profile = str(summary_profile or "").upper()
    return DOCUMENT_TYPE_FROM_PROFILE.get(profile, "unknown")


def _doc_period(summary: Dict[str, Any]) -> Optional[Any]:
    statement_period = summary.get("statement_period")
    if isinstance(statement_period, dict):
        start = statement_period.get("start")
        end = statement_period.get("end")
        if start or end:
            return {"from": start, "to": end}
    pay_start = summary.get("pay_period_start")
    pay_end = summary.get("pay_period_end")
    if pay_start or pay_end:
        return {"from": pay_start, "to": pay_end}
    pay_date = summary.get("pay_date")
    if pay_date:
        return str(pay_date)
    return None


def _doc_provider(summary: Dict[str, Any], doc_type: str) -> Optional[str]:
    if doc_type == "bank_statement":
        return summary.get("bank_name") or summary.get("account_holder_name")
    if doc_type == "mobile_money":
        return summary.get("provider") or summary.get("bank_name") or summary.get("account_holder_name")
    if doc_type == "payslip":
        return summary.get("employer_name") or summary.get("employee_name")
    if doc_type == "nrc_id":
        return summary.get("full_name")
    return summary.get("provider") or summary.get("source_filename")


def _has_primary_content(summary: Dict[str, Any], doc_type: str) -> bool:
    if doc_type == "bank_statement":
        return summary.get("closing_balance") is not None or bool(summary.get("statement_period"))
    if doc_type == "payslip":
        return summary.get("net_pay") is not None or summary.get("gross_pay") is not None
    if doc_type == "nrc_id":
        return bool(summary.get("full_name") or summary.get("id_number"))
    if doc_type in {"mobile_money", "generic_csv"}:
        return bool(summary.get("transaction_count") or summary.get("total_money_in") or summary.get("total_money_out"))
    return bool(summary.get("raw_text_preview"))


def _doc_status(summary: Dict[str, Any], doc_type: str) -> DocumentStatus:
    warnings = summary.get("extraction_warnings") or summary.get("warnings") or []
    has_warning = isinstance(warnings, list) and len(warnings) > 0
    has_content = _has_primary_content(summary, doc_type)
    if not has_content and has_warning:
        return DocumentStatus.ERROR
    if not has_content:
        return DocumentStatus.PARTIAL
    if has_warning:
        return DocumentStatus.PARTIAL
    return DocumentStatus.PARSED


def _doc_one_liner(summary: Dict[str, Any], doc_type: str, status: DocumentStatus) -> str:
    if status == DocumentStatus.MISSING:
        return "Required document has not been uploaded."
    if status == DocumentStatus.ERROR:
        return "Extraction failed. Review source quality and retry."
    if doc_type == "bank_statement":
        balance = summary.get("closing_balance")
        currency = summary.get("currency") or ""
        if balance is not None:
            return f"Closing balance parsed at {currency} {balance}."
        return "Bank statement parsed with partial coverage."
    if doc_type == "payslip":
        net_pay = summary.get("net_pay")
        currency = summary.get("currency") or ""
        if net_pay is not None:
            return f"Net pay extracted at {currency} {net_pay}."
        return "Payslip parsed with partial income extraction."
    if doc_type == "mobile_money":
        total_out = summary.get("total_money_out")
        tx_count = summary.get("transaction_count")
        currency = summary.get("currency") or ""
        if total_out is not None and tx_count:
            return f"{tx_count} mobile money transactions parsed with total outflows of {currency} {total_out}."
        return "Mobile money statement parsed with partial transaction coverage."
    if doc_type == "nrc_id":
        if summary.get("full_name") or summary.get("id_number"):
            return "Identity attributes extracted for verification."
        return "Identity document parsed with partial fields."
    return "Document parsed and indexed for officer review."


def build_decision_document_rows(assessment: Assessment) -> List[DecisionDocumentSummary]:
    metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
    raw_docs = metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []
    rows: List[DecisionDocumentSummary] = []
    created_at = _safe_iso(getattr(assessment, "created_at", None)) or datetime.now(timezone.utc).isoformat()

    for idx, raw_item in enumerate(raw_docs):
        if not isinstance(raw_item, dict):
            continue
        doc_type = _normalize_doc_type(raw_item.get("document_type"), raw_item.get("summary_profile"))
        status = _doc_status(raw_item, doc_type)
        confidence = _coerce_float(raw_item.get("confidence"))
        if confidence is None:
            confidence = _coerce_float(raw_item.get("quality_score"))
        rows.append(
            DecisionDocumentSummary(
                docId=f"{assessment.assessment_id}-DOC-{idx + 1}",
                type=doc_type,
                provider=_doc_provider(raw_item, doc_type),
                period=_doc_period(raw_item),
                status=status,
                oneLiner=_doc_one_liner(raw_item, doc_type, status),
                confidence=confidence,
                createdAt=created_at,
            )
        )

    missing_docs = metrics.get("missing_documents") if isinstance(metrics.get("missing_documents"), list) else []
    for missing in missing_docs:
        if not isinstance(missing, str):
            continue
        missing_type = _normalize_doc_type(missing, None)
        if missing_type == "unknown":
            missing_type = _slugify_token(missing)
        rows.append(
            DecisionDocumentSummary(
                docId=f"{assessment.assessment_id}-MISSING-{_slugify_token(missing)}",
                type=missing_type,
                provider=None,
                period=None,
                status=DocumentStatus.MISSING,
                oneLiner="Required document has not been uploaded.",
                confidence=None,
                createdAt=created_at,
            )
        )

    return rows


def _parse_doc_id(doc_id: str) -> Optional[Tuple[str, Optional[int], Optional[str]]]:
    uploaded_match = DOC_ID_UPLOADED_PATTERN.match(doc_id)
    if uploaded_match:
        assessment_id = uploaded_match.group(1)
        doc_index = int(uploaded_match.group(2)) - 1
        return assessment_id, doc_index, None
    missing_match = DOC_ID_MISSING_PATTERN.match(doc_id)
    if missing_match:
        assessment_id = missing_match.group(1)
        missing_key = missing_match.group(2)
        return assessment_id, None, missing_key
    return None


def _risk_severity_from_label(text: str) -> DocumentFlagSeverity:
    lowered = text.lower()
    if any(token in lowered for token in ["critical", "high", "error", "missing", "failed"]):
        return DocumentFlagSeverity.HIGH
    if any(token in lowered for token in ["warn", "partial", "review", "low confidence"]):
        return DocumentFlagSeverity.MED
    return DocumentFlagSeverity.LOW


def _build_extracted_metrics(summary: Dict[str, Any], doc_type: str) -> Dict[str, Union[str, float, int, bool]]:
    metrics: Dict[str, Union[str, float, int, bool]] = {}

    def _put(label: str, value: Any):
        if value is None:
            return
        metrics[label] = value

    if doc_type == "bank_statement":
        _put("Bank Name", summary.get("bank_name"))
        _put("Account Holder", summary.get("account_holder_name"))
        _put("Currency", summary.get("currency"))
        _put("Closing Balance", summary.get("closing_balance"))
        _put("Opening Balance", summary.get("opening_balance"))
        _put("Total Money In", summary.get("total_money_in"))
        _put("Total Money Out", summary.get("total_money_out"))
        _put("Deposit Count", summary.get("deposit_count"))
    elif doc_type == "mobile_money":
        _put("Provider", summary.get("provider") or summary.get("bank_name"))
        _put("Account Holder", summary.get("account_holder_name"))
        _put("Currency", summary.get("currency"))
        _put("Closing Balance", summary.get("closing_balance"))
        _put("Opening Balance", summary.get("opening_balance"))
        _put("Total Money In", summary.get("total_money_in"))
        _put("Total Money Out", summary.get("total_money_out"))
        _put("Transaction Count", summary.get("transaction_count"))
    elif doc_type == "payslip":
        _put("Employer", summary.get("employer_name"))
        _put("Employee", summary.get("employee_name"))
        _put("Currency", summary.get("currency"))
        _put("Gross Pay", summary.get("gross_pay"))
        _put("Net Pay", summary.get("net_pay"))
        _put("Deductions", summary.get("deductions"))
        _put("Pay Frequency", summary.get("pay_frequency"))
    elif doc_type == "nrc_id":
        _put("Full Name", summary.get("full_name"))
        _put("ID Number", summary.get("id_number"))
        _put("Date of Birth", summary.get("date_of_birth"))
        _put("Gender", summary.get("gender"))
    else:
        _put("Document Type", DOCUMENT_LABELS.get(doc_type, doc_type.replace("_", " ").title()))
        _put("Filename", summary.get("source_filename"))

    return metrics


def _build_document_insight_payload(
    assessment: Assessment,
    row: DecisionDocumentSummary,
    summary: Dict[str, Any],
    source_index: Optional[int] = None
) -> DocumentInsightRecord:
    summary_bullets: List[str] = []
    flags: List[DocumentInsightFlag] = []

    period = row.period
    if isinstance(period, dict) and (period.get("from") or period.get("to")):
        summary_bullets.append(f"Coverage period: {period.get('from') or 'N/A'} to {period.get('to') or 'N/A'}.")
    elif isinstance(period, str):
        summary_bullets.append(f"Document date: {period}.")

    if row.provider:
        summary_bullets.append(f"Provider/source: {row.provider}.")

    if row.status == DocumentStatus.PARSED:
        summary_bullets.append("Primary structured fields were extracted successfully.")
    elif row.status == DocumentStatus.PARTIAL:
        summary_bullets.append("Document parsed with partial extraction coverage; verify missing fields manually.")
    elif row.status == DocumentStatus.ERROR:
        summary_bullets.append("Extraction failed for core fields; re-upload or request a clearer copy.")
    elif row.status == DocumentStatus.MISSING:
        summary_bullets.append("Required document was not present at assessment time.")

    risk_flags = summary.get("risk_flags") if isinstance(summary.get("risk_flags"), list) else []
    for flag_label in risk_flags:
        if not isinstance(flag_label, str):
            continue
        flags.append(
            DocumentInsightFlag(
                label=flag_label,
                severity=_risk_severity_from_label(flag_label),
                detail=None,
            )
        )

    extraction_warnings = summary.get("extraction_warnings") if isinstance(summary.get("extraction_warnings"), list) else []
    for warning_label in extraction_warnings:
        if not isinstance(warning_label, str):
            continue
        flags.append(
            DocumentInsightFlag(
                label=warning_label,
                severity=_risk_severity_from_label(warning_label),
                detail="Extractor warning",
            )
        )

    if row.status in {DocumentStatus.MISSING, DocumentStatus.ERROR, DocumentStatus.PARTIAL} and not flags:
        flags.append(
            DocumentInsightFlag(
                label=row.status.value.upper(),
                severity=DocumentFlagSeverity.HIGH if row.status in {DocumentStatus.MISSING, DocumentStatus.ERROR} else DocumentFlagSeverity.MED,
                detail="Operational data-quality status",
            )
        )

    provenance: Dict[str, Any] = {
        "source": "assessment.metrics.document_summaries",
        "assessmentId": assessment.assessment_id,
    }
    if source_index is not None:
        provenance["documentIndex"] = source_index + 1
    if summary.get("source_filename"):
        provenance["sourceFilename"] = summary.get("source_filename")
    if summary.get("raw_text_preview"):
        provenance["rawTextPreview"] = str(summary.get("raw_text_preview"))[:300]

    secure_file_url = summary.get("secure_file_url")
    if not isinstance(secure_file_url, str):
        secure_file_url = None
    elif secure_file_url.startswith("http") and "signature=" not in secure_file_url.lower():
        # Do not expose raw storage URLs.
        secure_file_url = None

    now = datetime.now(timezone.utc)
    return DocumentInsightRecord(
        docId=row.docId,
        decisionId=assessment.assessment_id,
        organizationId=assessment.organization_id,
        sourceIndex=source_index,
        type=row.type,
        provider=row.provider,
        period=row.period,
        status=row.status,
        confidence=row.confidence,
        keyTakeaway=row.oneLiner,
        summaryBullets=summary_bullets,
        extractedMetrics=_build_extracted_metrics(summary, row.type),
        flags=flags,
        provenance=provenance,
        secureFileUrl=secure_file_url,
        createdAt=now,
        updatedAt=now,
    )


def enforce_summary_profile_metrics(assessment: Assessment) -> Assessment:
    """
    Contract hardening: ensure summary_profile is always present in metrics.
    """
    if assessment.metrics is None:
        assessment.metrics = {}
    if not assessment.metrics.get("summary_profile"):
        doc_summaries = assessment.metrics.get("document_summaries") or []
        if isinstance(doc_summaries, list) and doc_summaries:
            assessment.metrics["summary_profile"] = doc_summaries[0].get("summary_profile", SummaryProfile.UNKNOWN.value)
        else:
            assessment.metrics["summary_profile"] = SummaryProfile.UNKNOWN.value
    return augment_assessment_payload(assessment.model_dump())


# ============================================================================
# DECISION COPILOT ASSISTANT
# ============================================================================

ASSISTANT_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("ASSISTANT_RATE_LIMIT_WINDOW_SECONDS", "60"))
ASSISTANT_RATE_LIMIT_MAX_REQUESTS = int(os.getenv("ASSISTANT_RATE_LIMIT_MAX_REQUESTS", "20"))
ASSISTANT_MAX_MESSAGES = int(os.getenv("ASSISTANT_MAX_MESSAGES", "40"))
ASSISTANT_MAX_TURNS = int(os.getenv("ASSISTANT_MAX_TURNS", "20"))
ASSISTANT_RATE_BUCKETS: Dict[str, List[float]] = {}
ASSISTANT_RULE_REFERENCE: Dict[str, Dict[str, str]] = {
    "HIGH_DTI": {
        "name": "Debt Burden Too High",
        "human_description": "Debt obligations are high relative to verified income, which can weaken repayment capacity.",
        "officer_verify": "Confirm all outstanding debt obligations and recalculate debt-to-income with latest verified income."
    },
    "AFFORDABILITY_CAP": {
        "name": "Affordability Cap Applied",
        "human_description": "The requested amount exceeds what can be serviced under affordability policy.",
        "officer_verify": "Review net disposable income, repayment schedule assumptions, and expense quality."
    },
    "DATA_QUALITY_LIMITED": {
        "name": "Data Quality Limitation",
        "human_description": "The record has incomplete or low-confidence data that reduced automation confidence.",
        "officer_verify": "Request missing documents or clarify extracted values before sealing a final decision."
    },
    "INSUFFICIENT_OBSERVATION_WINDOW": {
        "name": "Insufficient Observation Window",
        "human_description": "Transaction history duration is below the policy minimum for confident assessment.",
        "officer_verify": "Confirm account history period and request longer statement coverage."
    },
    "OBSERVATION_WINDOW": {
        "name": "Observation Window Constraint",
        "human_description": "Observed account history does not meet the minimum policy window.",
        "officer_verify": "Verify statement period start/end dates and require additional history."
    },
    "POLICY_CAP": {
        "name": "Policy Cap Applied",
        "human_description": "A policy limit constrained the final recommendation below the requested amount.",
        "officer_verify": "Confirm cap reason and whether policy exception process applies."
    },
    "STARTER_LOAN_APPROVED_LIMITED_HISTORY": {
        "name": "Starter Loan Policy",
        "human_description": "Borrower approved under starter policy due to limited historical evidence.",
        "officer_verify": "Validate identity consistency and borrower onboarding evidence before disbursement."
    },
    "MISSING_DOCUMENTS": {
        "name": "Missing Supporting Documents",
        "human_description": "Required supporting evidence is missing, limiting verification quality.",
        "officer_verify": "Request missing bank statement or payslip and rerun validation."
    },
    "HIGH_RISK": {
        "name": "High Risk Classification",
        "human_description": "Aggregated risk signals placed this borrower in a high-risk category.",
        "officer_verify": "Review adverse signals and confirm whether further evidence can reduce uncertainty."
    }
}


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(..., min_length=1, max_length=6000)


class AssistantChatContext(BaseModel):
    route: str = Field(..., min_length=1, max_length=300)
    decisionId: Optional[str] = Field(default=None, max_length=120)
    policyVersion: Optional[str] = Field(default=None, max_length=120)
    status: Optional[str] = Field(default=None, max_length=120)
    orgId: Optional[str] = Field(default=None, max_length=120)
    userRole: Optional[str] = Field(default=None, max_length=120)


class AssistantChatRequest(BaseModel):
    messages: List[AssistantChatMessage] = Field(..., min_length=1, max_length=40)
    context: AssistantChatContext


class AssistantChatMeta(BaseModel):
    provider: Literal["vertex", "openai", "stub", "error"]
    model: str
    requestId: str
    # Backward-compatible default so response validation does not fail
    # if any legacy return path omits mode.
    mode: str = "console_mode"


class AssistantChatResponse(BaseModel):
    reply: str
    meta: AssistantChatMeta


def _assistant_user_role(user: User) -> str:
    role_value = getattr(user, "role", "")
    if hasattr(role_value, "value"):
        return str(role_value.value).upper()
    return str(role_value).upper()


def _enforce_assistant_rate_limit(user: User) -> None:
    now = time.time()
    key = f"{user.organization_id}:{user.id}"
    bucket = ASSISTANT_RATE_BUCKETS.get(key, [])
    recent = [ts for ts in bucket if now - ts <= ASSISTANT_RATE_LIMIT_WINDOW_SECONDS]
    if len(recent) >= ASSISTANT_RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {ASSISTANT_RATE_LIMIT_WINDOW_SECONDS} seconds."
        )
    recent.append(now)
    ASSISTANT_RATE_BUCKETS[key] = recent


def _latest_user_message(messages: List[AssistantChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user" and msg.content.strip():
            return msg.content.strip()
    return ""


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "Unavailable"
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "Unavailable"


def _build_assistant_decision_bundle(assessment: Assessment) -> Dict[str, Any]:
    metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
    data_used = assessment.data_used if isinstance(assessment.data_used, dict) else {}
    raw_doc_summaries = metrics.get("document_summaries") if isinstance(metrics, dict) else []
    compact_docs: List[Dict[str, Any]] = []

    if isinstance(raw_doc_summaries, list):
        for item in raw_doc_summaries[:5]:
            if not isinstance(item, dict):
                continue
            compact_docs.append({
                "summary_profile": item.get("summary_profile"),
                "bank_name": item.get("bank_name"),
                "employer_name": item.get("employer_name"),
                "full_name": item.get("full_name"),
                "quality_score": item.get("quality_score"),
            })

    policy_triggers: List[str] = []
    for code in assessment.decision_reason_codes or []:
        value = str(code).strip()
        if value and value not in policy_triggers:
            policy_triggers.append(value)
    for factor in assessment.blocking_factors or []:
        value = str(factor).strip()
        if value and value not in policy_triggers:
            policy_triggers.append(value)
    if assessment.policy_cap_reason:
        trigger = f"POLICY_CAP:{assessment.policy_cap_reason}"
        if trigger not in policy_triggers:
            policy_triggers.append(trigger)

    delta: Optional[float] = None
    try:
        if assessment.recommended_amount is not None:
            delta = float(assessment.recommended_amount) - float(assessment.requested_amount)
    except Exception:
        delta = None

    decision_value = assessment.decision.value if hasattr(assessment.decision, "value") else assessment.decision
    risk_level_value = assessment.risk_level.value if hasattr(assessment.risk_level, "value") else assessment.risk_level
    final_decision = None
    if isinstance(assessment.final_decision_metadata, dict):
        final_decision = assessment.final_decision_metadata.get("officer_decision") or assessment.final_decision_metadata.get("decision")

    return {
        "decision_id": assessment.assessment_id,
        "system_recommendation": str(decision_value) if decision_value is not None else None,
        "risk_score": assessment.risk_score,
        "risk_level": str(risk_level_value) if risk_level_value is not None else None,
        "policy_version": assessment.policy_version,
        "policy_triggers": policy_triggers,
        "requested_amount": assessment.requested_amount,
        "recommended_amount": assessment.recommended_amount,
        "recommended_duration_days": assessment.recommended_duration_days,
        "recommended_interest_rate": assessment.recommended_interest_rate,
        "loan_adjustment_delta": delta,
        "document_summaries": compact_docs,
        "data_sources": data_used.get("data_sources") if isinstance(data_used.get("data_sources"), list) else [],
        "status": "SEALED" if assessment.final_decision_metadata else "PENDING_OFFICER",
        "final_decision": final_decision,
    }


def _assistant_mode_from_route(route: str) -> str:
    path = (route or "/").split("?")[0].strip().lower()
    if path.startswith("/decisions"):
        return "decision_mode"
    if path.startswith("/manual-assessments"):
        return "intake_mode"
    if path.startswith("/policy-studio"):
        return "policy_mode"
    if path.startswith("/audit-logs"):
        return "audit_mode"
    if path.startswith("/settings"):
        return "settings_mode"
    return "console_mode"


def _classify_assistant_intent(question: str) -> str:
    q = (question or "").strip().lower()
    if not q:
        return "capability"

    greeting_word_tokens = ["hi", "hello", "hey", "thanks"]
    greeting_phrase_tokens = ["good morning", "good afternoon", "good evening", "how are you", "thank you"]
    has_greeting_word = any(re.search(rf"\b{re.escape(token)}\b", q) for token in greeting_word_tokens)
    has_greeting_phrase = any(token in q for token in greeting_phrase_tokens)
    if has_greeting_word or has_greeting_phrase:
        if len(q.split()) <= 8 or "how are you" in q or "thank" in q:
            return "greeting"

    capability_tokens = ["what can you do", "what can you help", "help me", "capabilities", "what do you help with", "what can i ask"]
    if any(token in q for token in capability_tokens):
        return "capability"

    decision_tokens = ["explain recommendation", "why approve", "why reject", "why was", "decision", "approved", "rejected", "borderline", "risk score"]
    if any(token in q for token in decision_tokens):
        return "decision_explain"

    workflow_tokens = ["upload", "batch", "spreadsheet", "file format", "validation", "template", "row", "csv", "xlsx", "error"]
    if any(token in q for token in workflow_tokens):
        return "workflow_help"

    policy_tokens = ["policy", "rule", "trigger", "threshold", "version", "override"]
    if any(token in q for token in policy_tokens):
        return "policy_help"

    return "general"


def _extract_decision_id_from_route(route: str) -> Optional[str]:
    path = (route or "/").split("?")[0].strip()
    prefix = "/decisions/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix):]
    candidate = remainder.split("/")[0].strip()
    return candidate or None


def _is_capability_request(question: str) -> bool:
    q = question.lower()
    capability_phrases = [
        "what can you help me with",
        "what can you do",
        "how can you help",
        "capabilities",
        "help me with"
    ]
    return any(phrase in q for phrase in capability_phrases)


def _assistant_mode_summary(mode: str, has_decision_context: bool) -> str:
    if mode == "decision_mode":
        if has_decision_context:
            return "I can explain this decision record, the policy reasoning, and risk interpretation."
        return (
            "You are in the Decision workflow. I can guide decision interpretation now, and provide "
            "record-level explanations when a specific decision is open."
        )
    if mode == "intake_mode":
        return "You are in Manual Assessments. I can guide spreadsheet intake, validation, and batch readiness."
    if mode == "policy_mode":
        return "You are in Policy Studio. I can explain rule design, threshold impacts, and governance checks."
    return "You are in Partner Console. I can guide workflows, risk interpretation, and operational navigation."


def _assistant_mode_capabilities(mode: str) -> List[str]:
    if mode == "decision_mode":
        return [
            "Explain system recommendation, risk score interpretation, and loan adjustment delta.",
            "Summarize key policy triggers and stored rule references for the active decision.",
            "Suggest officer next actions before sealing the final decision."
        ]
    if mode == "intake_mode":
        return [
            "Guide batch spreadsheet uploads, required file formats, and validation behavior.",
            "Explain row-level processing outcomes and where to review decisions.",
            "Clarify document completeness expectations before final submission."
        ]
    if mode == "policy_mode":
        return [
            "Explain how policy thresholds and rule ordering influence outcomes.",
            "Clarify governance controls, overrides, and operational implications.",
            "Guide where to verify policy versions used by decision records."
        ]
    return [
        "Guide Partner Console workflows across assessments, decisions, and governance.",
        "Explain where to find risk, policy, and audit context in the current product surface.",
        "Provide practical operational next steps based on your page context."
    ]


def _assistant_mode_examples(mode: str) -> List[str]:
    if mode == "decision_mode":
        return [
            "Explain this recommendation",
            "Which policy rules fired?",
            "What would change if amount increases?"
        ]
    if mode == "intake_mode":
        return [
            "How do batch uploads work?",
            "What file format is required?",
            "Which validation checks run first?"
        ]
    if mode == "policy_mode":
        return [
            "Which rules most affect approval rate?",
            "How do I tighten affordability thresholds?",
            "How should overrides be documented?"
        ]
    return [
        "What can you help me with?",
        "How do I review audit history?",
        "Where should I start a manual assessment?"
    ]


def _assistant_mode_next_steps(mode: str, has_decision_context: bool) -> List[str]:
    if mode == "decision_mode":
        if has_decision_context:
            return [
                "Review recommendation drivers, then verify document quality before sealing.",
                "Record officer rationale if you override the system recommendation."
            ]
        return [
            "Open a Decision record to unlock record-level policy trigger and risk details.",
            "Use this page to frame the question, then ask again from the selected record."
        ]

    if mode == "intake_mode":
        return [
            "Upload the spreadsheet template and resolve row-level validation flags.",
            "For decision-specific explanations, open a Decision record."
        ]

    if mode == "policy_mode":
        return [
            "Review threshold and trigger configuration before publishing policy updates.",
            "For decision-specific explanations, open a Decision record."
        ]

    return [
        "Open the relevant workflow area (Manual Assessments, Decisions, or Policy Studio) for targeted guidance.",
        "For decision-specific explanations, open a Decision record."
    ]


def _compose_standard_mode_response(summary: str, help_items: List[str], next_steps: List[str]) -> str:
    lines: List[str] = [
        "Summary",
        f"- {summary}",
        "",
        "What I can help with",
    ]
    lines.extend([f"- {item}" for item in help_items])
    lines.append("")
    lines.append("Next Steps")
    lines.extend([f"- {step}" for step in next_steps])
    lines.append("")
    lines.append("Final credit approval remains the officer's responsibility.")
    return "\n".join(lines)


def _compose_mode_help_reply(mode: str, has_decision_context: bool) -> str:
    capabilities = _assistant_mode_capabilities(mode)
    examples = _assistant_mode_examples(mode)
    help_items = list(capabilities)
    help_items.append(f"Example questions: {'; '.join(examples)}.")
    return _compose_standard_mode_response(
        summary=_assistant_mode_summary(mode, has_decision_context),
        help_items=help_items,
        next_steps=_assistant_mode_next_steps(mode, has_decision_context)
    )


def _assistant_mode_specific_answer(question: str, mode: str, has_decision_context: bool) -> Optional[str]:
    q = question.lower()

    if mode == "intake_mode":
        if "file format" in q or "format" in q or "xlsx" in q or "xls" in q or "csv" in q:
            return _compose_standard_mode_response(
                summary="Spreadsheet intake accepts .xlsx, .xls, and .csv formats for borrower rows.",
                help_items=[
                    "Validate template column names and required fields before upload.",
                    "Use row-level validation feedback to fix missing values or invalid formats.",
                    "Run assessments after validation succeeds."
                ],
                next_steps=[
                    "Download and populate the template, then re-upload.",
                    "For decision-specific explanations, open a Decision record."
                ]
            )
        if "batch" in q or "upload" in q or "validation" in q:
            return _compose_standard_mode_response(
                summary="Batch intake validates each row first, then processes borrower decisions independently.",
                help_items=[
                    "Explain validation errors and how they block row processing.",
                    "Clarify how borrower-level outcomes are generated from one upload.",
                    "Guide where to review results after processing."
                ],
                next_steps=[
                    "Resolve flagged rows and rerun the upload.",
                    "Open Decisions to review borrower-level outcomes."
                ]
            )

    if mode == "policy_mode" and ("policy" in q or "rule" in q or "trigger" in q):
        return _compose_standard_mode_response(
            summary="Policy Studio guidance is available for rule behavior and threshold impacts.",
            help_items=[
                "Explain how affordability and DTI thresholds influence outcomes.",
                "Guide governance controls and override expectations.",
                "Identify where policy versioning is reviewed."
            ],
            next_steps=[
                "Review rule configuration and version metadata in Policy Studio.",
                "For decision-specific trigger IDs, open a Decision record."
            ]
        )

    if mode == "console_mode" and ("risk" in q or "score" in q or "recommendation" in q):
        return _compose_standard_mode_response(
            summary="Risk interpretation guidance is available in Partner Console context.",
            help_items=[
                "Clarify risk levels and where they appear in workflows.",
                "Guide where policy references and audit records are reviewed.",
                "Suggest operational follow-up actions before final approval."
            ],
            next_steps=[
                "Open a Decision record for exact recommendation drivers and policy references.",
                "Use Audit Logs to confirm historical decision activity."
            ]
        )

    if mode == "decision_mode" and not has_decision_context and ("policy" in q or "rule" in q or "risk" in q):
        return _compose_standard_mode_response(
            summary=(
                "A specific Decision record is not attached to this chat yet, so record-level "
                "policy and risk values are not available in this view."
            ),
            help_items=[
                "Guide which decision fields to inspect once the record is open.",
                "Explain how recommendation, risk score, and policy triggers relate.",
                "Prepare officer-oriented follow-up questions for the selected record."
            ],
            next_steps=[
                "Open a Decision record and ask the same question again for exact values.",
                "Use the decision context pills to confirm policy version and status."
            ]
        )

    return None


def _assistant_next_steps(question: str, decision_bundle: Dict[str, Any]) -> List[str]:
    q = question.lower()
    steps: List[str] = []

    if "increase" in q and "amount" in q:
        steps.append("Re-check affordability and DTI limits against current income and expense evidence.")
        steps.append("Request stronger income continuity evidence before approving a higher amount.")
    elif "risk" in q:
        steps.append("Address missing or low-confidence evidence that is increasing uncertainty.")
    else:
        steps.append("Validate document completeness and resolve any blocking policy trigger.")

    if not decision_bundle.get("document_summaries"):
        steps.append("Upload supporting documents to improve confidence and reduce manual uncertainty.")

    steps.append("Record officer rationale before sealing any override decision.")
    return steps


def _compose_assistant_reply(
    question: str,
    route: str,
    mode: str,
    decision_bundle: Optional[Dict[str, Any]]
) -> str:
    has_decision_context = decision_bundle is not None

    if _is_capability_request(question):
        return _compose_mode_help_reply(mode, has_decision_context)

    specific_reply = _assistant_mode_specific_answer(question, mode, has_decision_context)
    if specific_reply:
        return specific_reply

    if mode != "decision_mode" and not decision_bundle:
        return _compose_mode_help_reply(mode, has_decision_context)

    if not decision_bundle:
        return _compose_mode_help_reply("decision_mode", has_decision_context=False)

    summary_lines: List[str] = []
    recommendation = decision_bundle.get("system_recommendation") or "Unavailable"
    risk_level = decision_bundle.get("risk_level") or "Unavailable"
    risk_score = decision_bundle.get("risk_score")
    status = decision_bundle.get("status") or "PENDING_OFFICER"
    policy_version = decision_bundle.get("policy_version") or "Unavailable"
    final_decision = decision_bundle.get("final_decision")

    if risk_score is None:
        summary_lines.append(f"System recommendation: {recommendation}. Risk level: {risk_level}.")
    else:
        try:
            summary_lines.append(
                f"System recommendation: {recommendation}. Risk score: {float(risk_score):.2f} ({risk_level})."
            )
        except Exception:
            summary_lines.append(f"System recommendation: {recommendation}. Risk level: {risk_level}.")

    summary_lines.append(f"Decision record status: {status}.")
    if final_decision:
        summary_lines.append(f"Sealed officer decision: {final_decision}.")

    drivers: List[str] = []
    triggers = decision_bundle.get("policy_triggers") or []
    if triggers:
        drivers.extend([f"Policy trigger: {t}" for t in triggers[:5]])
    else:
        drivers.append("Policy trigger data is not available in this view.")

    delta = decision_bundle.get("loan_adjustment_delta")
    if delta is None:
        drivers.append("Loan adjustment delta is not available in this view.")
    else:
        try:
            drivers.append(f"Loan adjustment delta vs requested amount: {float(delta):+.2f}.")
        except Exception:
            drivers.append("Loan adjustment delta is not available in this view.")

    docs = decision_bundle.get("document_summaries") or []
    if docs:
        profiles = [str(doc.get("summary_profile")) for doc in docs if doc.get("summary_profile")]
        if profiles:
            drivers.append(f"Document summaries available: {', '.join(profiles[:4])}.")
        else:
            drivers.append("Documents are present but summary profiles are not fully populated.")
    else:
        drivers.append("Document summary metadata is not available in this view.")

    policy_version_line = "not available in this view" if policy_version == "Unavailable" else policy_version
    policy_refs = [f"Policy version: {policy_version_line}."]
    reason_codes = [t for t in triggers if isinstance(t, str) and t]
    if reason_codes:
        policy_refs.append(f"Rule IDs / reason codes: {', '.join(reason_codes[:6])}.")
    else:
        policy_refs.append("Rule IDs / reason codes are not available in this view.")

    next_steps = _assistant_next_steps(question, decision_bundle)

    sections: List[str] = ["Summary"]
    sections.extend([f"- {line}" for line in summary_lines])
    sections.append("")
    sections.append("Key Drivers")
    sections.extend([f"- {line}" for line in drivers])
    sections.append("")
    sections.append("Policy References")
    sections.extend([f"- {line}" for line in policy_refs])
    sections.append("")
    sections.append("Next Steps")
    sections.extend([f"- {line}" for line in next_steps])
    sections.append("")
    sections.append("Final credit approval remains the officer's responsibility.")
    return "\n".join(sections)


def _truncate_messages(messages: List[AssistantChatMessage]) -> List[AssistantChatMessage]:
    max_messages = max(1, min(ASSISTANT_MAX_MESSAGES, ASSISTANT_MAX_TURNS * 2))
    return messages[-max_messages:]


def _assistant_capabilities_for_mode(mode: str) -> List[str]:
    if mode == "decision_mode":
        return [
            "Explain recommendation rationale in plain language.",
            "Break down risk score, risk level, and adjustment delta.",
            "Translate fired policy rules into officer-friendly meaning.",
            "Highlight evidence gaps and what to verify before sealing.",
            "Suggest controlled ways to improve the likely outcome.",
            "Summarize decision context for audit-ready officer notes."
        ]
    if mode == "intake_mode":
        return [
            "Guide spreadsheet intake for batch assessments.",
            "Explain accepted file formats and validation expectations.",
            "Help interpret flagged rows and upload-readiness checks.",
            "Clarify where to review generated outcomes.",
            "Advise what evidence improves downstream decision quality."
        ]
    if mode == "policy_mode":
        return [
            "Explain policy threshold intent and operational impact.",
            "Clarify rule interactions and likely downstream effects.",
            "Recommend governance checks before policy activation.",
            "Identify what evidence officers should verify for exceptions.",
            "Map policy controls to audit and review workflows."
        ]
    if mode == "audit_mode":
        return [
            "Explain what each audit event means in operational terms.",
            "Map events to user actions and workflow stages.",
            "Help trace who did what and when across assessment lifecycle.",
            "Highlight what to investigate when an audit trail looks unusual.",
            "Suggest compliant follow-up documentation for investigations."
        ]
    if mode == "settings_mode":
        return [
            "Explain environment and configuration options in practical terms.",
            "Guide safe changes to roles, preferences, and platform settings.",
            "Clarify downstream impact of configuration updates.",
            "Recommend governance checks before applying production changes.",
            "Help identify where to verify a change was applied."
        ]
    return [
        "Guide navigation and workflows across Partner Console.",
        "Explain where risk, policy, and audit evidence is surfaced.",
        "Suggest next operational steps by current page context.",
        "Clarify when to use manual assessments vs decision chamber.",
        "Help frame better questions for decision-level analysis."
    ]


def _assistant_examples_for_mode(mode: str) -> List[str]:
    if mode == "decision_mode":
        return [
            "Explain recommendation",
            "Which policy rules fired?",
            "What would change if amount increases?"
        ]
    if mode == "intake_mode":
        return [
            "How do batch uploads work?",
            "What file format is required?",
            "What validation checks run first?"
        ]
    if mode == "policy_mode":
        return [
            "How do affordability thresholds affect approvals?",
            "Which controls should we review before activation?",
            "How should exceptions be documented?"
        ]
    if mode == "audit_mode":
        return [
            "What does FINAL_HUMAN_DECISION_SEALED mean?",
            "Which user initiated this action?",
            "How should I investigate this audit sequence?"
        ]
    if mode == "settings_mode":
        return [
            "Which settings are safe to change in production?",
            "How do role updates affect approval workflow?",
            "Where can I verify a setting change was applied?"
        ]
    return [
        "What can you help me with?",
        "Where do I review audit history?",
        "How do I start a manual assessment?"
    ]


def _build_capability_response(mode: str) -> str:
    opening = (
        "I can support you as a decision and workflow copilot in this page context. "
        "If you share what you are trying to decide, I will keep the guidance practical and policy-aware."
    )
    lines: List[str] = [opening, "", "What I can help with:"]
    lines.extend([f"- {item}" for item in _assistant_capabilities_for_mode(mode)])
    examples = _assistant_examples_for_mode(mode)
    lines.append("")
    lines.append("What to do next:")
    lines.append(f"- Ask one of these to get started: {examples[0]}; {examples[1]}; {examples[2]}.")
    lines.append("- Final credit approval remains the officer's responsibility.")
    return "\n".join(lines)


def _build_greeting_response(mode: str) -> str:
    mode_prompts = {
        "decision_mode": "I can explain this decision in analyst terms, including triggers, risk posture, and next checks.",
        "intake_mode": "I can guide uploads, validation issues, and batch processing readiness.",
        "policy_mode": "I can walk through rules, thresholds, and safe policy changes.",
        "audit_mode": "I can help interpret audit events and trace workflow actions.",
        "settings_mode": "I can clarify configuration impact and safe rollout checks.",
        "console_mode": "I can help with navigation, workflows, and where to find key risk or policy context."
    }
    redirect = mode_prompts.get(mode, mode_prompts["console_mode"])
    return (
        "I’m doing well, thanks. "
        f"{redirect} "
        "What are you working on right now?"
    )


def _build_decision_without_record_response(mode: str) -> str:
    if mode == "decision_mode":
        return (
            "I can still help frame the recommendation logic from this page, even before record-level values are loaded. "
            "What I’m seeing: you’re asking for a decision explanation, which is strongest when a specific decision record is attached.\n\n"
            "What to do next:\n"
            "- Open the target decision record and ask the same question.\n"
            "- If helpful, I can also explain what each trigger means before you open it."
        )
    return (
        "I can help with the current workflow, and I can also explain decision outcomes in detail once a specific decision record is open. "
        "What I’m seeing: this question is decision-specific, so record-level analysis is limited in this view.\n\n"
        "What to do next:\n"
        "- Open a decision record under Decisions and ask this again.\n"
        "- If you want, I can first outline the key checks officers usually apply."
    )


def _compose_intent_fallback_response(intent: str, mode: str, decision_context: Optional[Dict[str, Any]]) -> Optional[str]:
    if intent == "greeting":
        return _build_greeting_response(mode)
    if intent == "capability":
        return _build_capability_response(mode)
    if intent == "decision_explain" and decision_context is None:
        return _build_decision_without_record_response(mode)
    return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _normalize_rule_id(raw_rule: str) -> str:
    value = str(raw_rule or "").strip().upper().replace("-", "_")
    if value.startswith("POLICY_CAP:"):
        return "POLICY_CAP"
    return value


def _threshold_values_for_rule(rule_id: str, assessment: Assessment, metrics: Dict[str, Any]) -> Dict[str, Any]:
    import config

    dti = metrics.get("dti_ratio")
    affordability = metrics.get("affordability_ratio")
    policy_cap = assessment.policy_cap_amount
    values: Dict[str, Any] = {}

    if rule_id == "HIGH_DTI":
        values = {"observed_dti": dti, "max_dti": config.MAX_DEBT_TO_INCOME_RATIO}
    elif rule_id == "AFFORDABILITY_CAP":
        values = {"observed_affordability_ratio": affordability, "target_affordability_ratio": config.AFFORDABILITY_RATIO_TARGET}
    elif rule_id in {"OBSERVATION_WINDOW", "INSUFFICIENT_OBSERVATION_WINDOW"}:
        values = {"history_days": assessment.history_days, "minimum_days": 30}
    elif rule_id == "POLICY_CAP":
        values = {"policy_cap_amount": policy_cap, "requested_amount": assessment.requested_amount}
    elif rule_id == "DATA_QUALITY_LIMITED":
        values = {"data_quality_score": assessment.data_quality_score, "minimum_quality_score": config.DATA_QUALITY_REFER_THRESHOLD}

    return values


def _why_rule_fired(rule_id: str, assessment: Assessment, metrics: Dict[str, Any]) -> str:
    if rule_id == "HIGH_DTI":
        dti = _safe_float(metrics.get("dti_ratio"))
        if dti is not None:
            return f"DTI was measured at {dti:.2f}, above permitted policy tolerance."
        return "Debt-to-income exceeded policy tolerance based on available debt and income evidence."
    if rule_id == "AFFORDABILITY_CAP":
        return "Requested repayment burden exceeded affordability target for the verified income profile."
    if rule_id in {"OBSERVATION_WINDOW", "INSUFFICIENT_OBSERVATION_WINDOW"}:
        return f"Only {assessment.history_days or 0} days of usable history were available, below policy minimum."
    if rule_id == "POLICY_CAP":
        if assessment.policy_cap_reason:
            return f"Policy cap was applied due to: {assessment.policy_cap_reason}."
        return "A configured policy ceiling restricted recommendation size."
    if rule_id == "DATA_QUALITY_LIMITED":
        if assessment.data_quality_score is not None:
            return f"Data quality score {assessment.data_quality_score:.2f} triggered manual caution thresholds."
        return "Data quality checks found missing or low-confidence inputs."
    if rule_id == "STARTER_LOAN_APPROVED_LIMITED_HISTORY":
        return "Limited profile history triggered starter-loan controls."
    if rule_id == "MISSING_DOCUMENTS":
        missing_docs = metrics.get("missing_documents") or []
        if isinstance(missing_docs, list) and missing_docs:
            return f"Missing required evidence: {', '.join(str(item) for item in missing_docs[:3])}."
        return "Required supporting evidence was not complete."
    return "Rule was recorded on the decision trace and influenced the recommendation."


def _lookup_rule_reference(rule_id: str) -> Dict[str, str]:
    if rule_id in ASSISTANT_RULE_REFERENCE:
        return ASSISTANT_RULE_REFERENCE[rule_id]
    return {
        "name": rule_id.replace("_", " ").title() or "Policy Rule",
        "human_description": "This rule appears in the decision trace but does not have expanded metadata in this view.",
        "officer_verify": "Review policy configuration and decision trace before sealing."
    }


def _build_fired_rules(assessment: Assessment, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_rules: List[str] = []
    for code in assessment.decision_reason_codes or []:
        value = str(code).strip()
        if value:
            raw_rules.append(value)
    for factor in assessment.blocking_factors or []:
        value = str(factor).strip()
        if value:
            raw_rules.append(value)
    if assessment.policy_cap_reason:
        raw_rules.append(f"POLICY_CAP:{assessment.policy_cap_reason}")
    missing_docs = metrics.get("missing_documents")
    if isinstance(missing_docs, list) and missing_docs:
        raw_rules.append("MISSING_DOCUMENTS")

    deduped: List[str] = []
    for raw_rule in raw_rules:
        if raw_rule not in deduped:
            deduped.append(raw_rule)

    fired_rules: List[Dict[str, Any]] = []
    for raw_rule in deduped[:10]:
        rule_id = _normalize_rule_id(raw_rule)
        reference = _lookup_rule_reference(rule_id)
        fired_rules.append({
            "id": rule_id,
            "name": reference["name"],
            "human_description": reference["human_description"],
            "threshold_values": _threshold_values_for_rule(rule_id, assessment, metrics),
            "why_it_fired": _why_rule_fired(rule_id, assessment, metrics),
            "officer_verify": reference["officer_verify"]
        })
    return fired_rules


def _build_top_reasons_plain(assessment: Assessment, fired_rules: List[Dict[str, Any]]) -> List[str]:
    reasons: List[str] = []

    for rule in fired_rules:
        why = str(rule.get("why_it_fired") or "").strip()
        if why:
            reasons.append(why)
        if len(reasons) >= 3:
            break

    if len(reasons) < 3:
        recommendation = assessment.decision.value if hasattr(assessment.decision, "value") else str(assessment.decision)
        reasons.append(f"System recommendation is {recommendation} under policy version {assessment.policy_version}.")
    if len(reasons) < 3 and assessment.recommended_amount is not None:
        delta = _safe_float(assessment.recommended_amount) - _safe_float(assessment.requested_amount)  # type: ignore
        if delta is not None:
            reasons.append(f"Recommended amount differs from request by {delta:+.2f}.")
    if len(reasons) < 3:
        reasons.append("Available evidence quality and policy controls together determined recommendation confidence.")

    return reasons[:3]


def _build_assistant_decision_context_v2(assessment: Assessment) -> Dict[str, Any]:
    import config

    metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
    data_used = assessment.data_used if isinstance(assessment.data_used, dict) else {}
    data_provenance = assessment.data_provenance if isinstance(assessment.data_provenance, dict) else {}
    raw_doc_summaries = metrics.get("document_summaries") if isinstance(metrics, dict) else []
    compact_docs: List[Dict[str, Any]] = []
    available_doc_types: List[str] = []

    if isinstance(raw_doc_summaries, list):
        for item in raw_doc_summaries[:6]:
            if not isinstance(item, dict):
                continue
            profile = item.get("summary_profile")
            compact_docs.append({
                "summary_profile": profile,
                "bank_name": item.get("bank_name"),
                "employer_name": item.get("employer_name"),
                "full_name": item.get("full_name"),
                "quality_score": item.get("quality_score"),
            })
            if profile:
                profile_str = str(profile)
                if profile_str not in available_doc_types:
                    available_doc_types.append(profile_str)

    delta: Optional[float] = None
    try:
        if assessment.recommended_amount is not None:
            delta = float(assessment.recommended_amount) - float(assessment.requested_amount)
    except Exception:
        delta = None

    decision_value = assessment.decision.value if hasattr(assessment.decision, "value") else assessment.decision
    risk_level_value = assessment.risk_level.value if hasattr(assessment.risk_level, "value") else assessment.risk_level
    final_decision = None
    if isinstance(assessment.final_decision_metadata, dict):
        final_decision = assessment.final_decision_metadata.get("officer_decision") or assessment.final_decision_metadata.get("decision")

    fired_rules = _build_fired_rules(assessment, metrics)
    missing_documents = metrics.get("missing_documents") if isinstance(metrics.get("missing_documents"), list) else []
    top_reasons = _build_top_reasons_plain(assessment, fired_rules)
    dti_ratio = _safe_float(metrics.get("dti_ratio"))
    affordability_ratio = _safe_float(metrics.get("affordability_ratio"))
    haircut_percent: Optional[float] = None
    affordability_margin: Optional[float] = None

    if assessment.requested_amount and assessment.requested_amount > 0 and assessment.recommended_amount is not None:
        try:
            haircut_percent = ((float(assessment.requested_amount) - float(assessment.recommended_amount)) / float(assessment.requested_amount)) * 100.0
        except Exception:
            haircut_percent = None

    if affordability_ratio is not None:
        try:
            affordability_margin = float(config.AFFORDABILITY_RATIO_TARGET) - affordability_ratio
        except Exception:
            affordability_margin = None

    risk_level_str = str(risk_level_value) if risk_level_value is not None else "UNKNOWN"
    confidence_band = "strong"
    if risk_level_str == "MEDIUM" or (assessment.data_quality_score is not None and assessment.data_quality_score < 0.7):
        confidence_band = "borderline"
    if risk_level_str == "HIGH":
        confidence_band = "elevated-risk"

    return {
        "decision_id": assessment.assessment_id,
        "system_recommendation": str(decision_value) if decision_value is not None else None,
        "risk_score": assessment.risk_score,
        "risk_level": str(risk_level_value) if risk_level_value is not None else None,
        "policy_version": assessment.policy_version,
        "requested_amount": assessment.requested_amount,
        "recommended_amount": assessment.recommended_amount,
        "delta": delta,
        "recommended_duration_days": assessment.recommended_duration_days,
        "recommended_interest_rate": assessment.recommended_interest_rate,
        "fired_rules": fired_rules,
        "affordability_summary": {
            "dti_ratio": dti_ratio,
            "dti_threshold": config.MAX_DEBT_TO_INCOME_RATIO,
            "affordability_ratio": affordability_ratio,
            "affordability_target": config.AFFORDABILITY_RATIO_TARGET,
            "affordability_margin": affordability_margin,
            "capacity_based_max": assessment.capacity_based_max,
            "policy_cap_amount": assessment.policy_cap_amount,
            "policy_cap_reason": assessment.policy_cap_reason,
            "haircut_percent": haircut_percent,
        },
        "data_provenance": {
            "data_sources": data_used.get("data_sources") if isinstance(data_used.get("data_sources"), list) else [],
            "transaction_count": assessment.transaction_count,
            "history_days": assessment.history_days,
            "data_quality_score": assessment.data_quality_score,
            "data_recency_days": data_used.get("data_recency_days"),
            "consent_scope": data_provenance.get("consent_scope"),
        },
        "document_summary": {
            "documents": compact_docs,
            "available_document_types": available_doc_types,
            "missing_documents": missing_documents,
        },
        "top_reasons": top_reasons,
        "analyst_signal": {
            "confidence_band": confidence_band,
            "notes": "Use confidence band as directional context, not a replacement for officer judgment."
        },
        "status": "SEALED" if assessment.final_decision_metadata else "PENDING_OFFICER",
        "final_decision": final_decision,
    }


def _derive_last_topic(messages: List[AssistantChatMessage], question: str) -> str:
    user_messages = [m.content.strip() for m in messages if m.role == "user" and m.content.strip()]
    if len(user_messages) >= 2:
        raw_topic = user_messages[-2]
    elif user_messages:
        raw_topic = user_messages[-1]
    else:
        raw_topic = question

    topic = " ".join(raw_topic.split())
    if len(topic) > 160:
        topic = f"{topic[:157]}..."
    return topic


def _format_history_for_prompt(messages: List[AssistantChatMessage]) -> str:
    transcript_lines: List[str] = []
    for msg in messages:
        role = "User" if msg.role == "user" else ("Assistant" if msg.role == "assistant" else "System")
        content = " ".join(msg.content.strip().split())
        if len(content) > 800:
            content = f"{content[:797]}..."
        transcript_lines.append(f"{role}: {content}")
    return "\n".join(transcript_lines)


def _build_system_prompt(mode: str, question: str, has_decision_context: bool) -> str:
    mode_map = {
        "decision_mode": "Decision Chamber",
        "intake_mode": "Manual Assessments",
        "policy_mode": "Policy Studio",
        "audit_mode": "Audit Logs",
        "settings_mode": "Settings",
        "console_mode": "Partner Console"
    }
    mode_label = mode_map.get(mode, "Partner Console")
    mode_behavior = {
        "decision_mode": "Give analyst-grade reasoning: explain why approve/reject, whether signal strength is strong or borderline, and what officers should verify.",
        "intake_mode": "Provide step-by-step guidance for spreadsheet uploads, formats, validation behavior, and batch outcomes.",
        "policy_mode": "Explain rules, thresholds, versioning, and safe policy adjustments.",
        "audit_mode": "Interpret audit events clearly, map them to actions, and suggest investigation flow.",
        "settings_mode": "Explain configuration impact and safe operational checks before applying changes.",
        "console_mode": "Provide practical navigation and workflow help across Partner Console."
    }.get(mode, "Provide practical workflow help.")
    return (
        "You are Decision Copilot for an enterprise lending platform. "
        "Tone: warm, professional, and concise. Sound like a risk analyst, not a generic chatbot.\n"
        f"Current mode: {mode} ({mode_label}).\n"
        f"Mode behavior: {mode_behavior}\n"
        f"Current question: {question}\n"
        f"Decision context attached: {'yes' if has_decision_context else 'no'}.\n"
        "Hard requirements:\n"
        "- Use only provided context and conversation history.\n"
        "- If data is missing, say 'not available in this view' and suggest where to find it.\n"
        "- Do not fabricate policy IDs, thresholds, or scores.\n"
        "- Never start with 'I do not have a decision record in context'.\n"
        "- Never use 'I’m functioning as expected'.\n"
        "- Avoid markdown-heavy formatting, no numbered section scaffolding unless user asks for it.\n"
        "- Default format: short direct answer (2-4 sentences), optional 'What I’m seeing:' line, compact bullets only if useful, then 'What to do next:' with 1-3 steps.\n"
        "- Capability question response must include 5-7 bullets and 3 example questions tailored to mode.\n"
        "- Greeting/smalltalk should be friendly and then redirect to helpful work guidance.\n"
        "- In decision explanations, translate trigger IDs to plain language and include practical improvement suggestions.\n"
        "- Final credit approval remains the officer's responsibility.\n"
        "Conversation memory: respect the user's recent topic and continue naturally."
    )


def _build_user_prompt(
    route: str,
    mode: str,
    intent: str,
    question: str,
    history: List[AssistantChatMessage],
    last_topic: str,
    decision_context: Optional[Dict[str, Any]]
) -> str:
    context_blob = json.dumps(decision_context or {"note": "Decision context not available in this view."}, default=str, indent=2)
    history_blob = _format_history_for_prompt(history)
    return (
        f"Route: {route}\n"
        f"Mode: {mode}\n"
        f"Intent: {intent}\n"
        f"Remembered last topic: {last_topic}\n\n"
        "DecisionContext:\n"
        f"{context_blob}\n\n"
        "ConversationHistory:\n"
        f"{history_blob}\n\n"
        "UserQuestion:\n"
        f"{question}\n"
    )


def _resolve_assistant_provider() -> Tuple[str, str]:
    import config

    raw_provider = (os.getenv("ASSISTANT_PROVIDER") or config.LLM_PROVIDER or "vertex_ai").strip().lower()
    if raw_provider in {"vertex", "vertex_ai", "google_vertex"}:
        model = (os.getenv("ASSISTANT_MODEL") or os.getenv("VERTEX_MODEL_NAME") or config.VERTEX_MODEL_NAME or "gemini-2.0-flash-001").strip()
        return "vertex", model
    if raw_provider == "openai":
        model = (os.getenv("ASSISTANT_MODEL") or os.getenv("OPENAI_MODEL") or config.LLM_MODEL or "gpt-4o-mini").strip()
        return "openai", model
    if raw_provider == "stub":
        model = (os.getenv("ASSISTANT_MODEL") or "deterministic-stub-v1").strip()
        return "stub", model
    raise ValueError(f"Unsupported ASSISTANT_PROVIDER/LLM_PROVIDER value: {raw_provider}")


def _provider_error_hint(provider: str, error: Exception) -> str:
    msg = str(error)
    msg_lower = msg.lower()
    if provider == "vertex":
        if "publisher model" in msg_lower and "not found" in msg_lower:
            return "Configured Vertex model is unavailable in this project/region. Set VERTEX_MODEL_NAME=gemini-2.0-flash-001 and retry."
        if "service_disabled" in msg_lower or "aiplatform.googleapis.com" in msg_lower:
            return "Vertex AI API is disabled for this project. Run: gcloud services enable aiplatform.googleapis.com --project mfi--pro"
        if "reauthentication is needed" in msg_lower or "application-default login" in msg_lower:
            return "Google ADC token expired. Run: gcloud auth application-default login"
        if "credential" in msg_lower or "google_application_credentials" in msg_lower:
            return "Vertex credentials are not available. Set GOOGLE_APPLICATION_CREDENTIALS or run gcloud ADC login."
        if "permission" in msg_lower or "403" in msg_lower:
            return "Vertex access was denied. Verify IAM roles and project permissions."
        return "Vertex request failed. Verify VERTEX_PROJECT_ID, VERTEX_REGION, and model access."
    if provider == "openai":
        if "api key" in msg_lower or "authentication" in msg_lower or "unauthorized" in msg_lower:
            return "OpenAI credentials are missing or invalid. Set OPENAI_API_KEY."
        return "OpenAI request failed. Verify OPENAI_API_KEY and model availability."
    if provider == "stub":
        return "Stub provider failed unexpectedly. Check assistant prompt/context assembly."
    return "Unknown assistant provider error."


def _call_vertex_assistant(system_prompt: str, user_prompt: str, model: str) -> str:
    import config
    import vertexai
    try:
        from vertexai.generative_models import GenerativeModel, GenerationConfig
    except Exception:
        # Compatibility path for older vertex-ai SDKs where GenerativeModel is in preview.
        from vertexai.preview.generative_models import GenerativeModel, GenerationConfig

    project_id = os.getenv("VERTEX_PROJECT_ID") or config.VERTEX_PROJECT_ID
    region = os.getenv("VERTEX_REGION") or config.VERTEX_REGION
    if not project_id:
        raise RuntimeError("VERTEX_PROJECT_ID is not configured.")
    if not region:
        raise RuntimeError("VERTEX_REGION is not configured.")

    vertexai.init(project=project_id, location=region)
    model_client = GenerativeModel(model)
    prompt = f"{system_prompt}\n\n{user_prompt}"
    generation_config = GenerationConfig(
        temperature=float(os.getenv("ASSISTANT_LLM_TEMPERATURE", "0.2")),
        max_output_tokens=int(os.getenv("ASSISTANT_LLM_MAX_TOKENS", "900"))
    )
    response = model_client.generate_content(prompt, generation_config=generation_config)
    text = getattr(response, "text", None)
    if text and text.strip():
        return text.strip()

    candidates = getattr(response, "candidates", None)
    if candidates:
        parts: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    parts.append(part_text)
        merged = "\n".join(parts).strip()
        if merged:
            return merged

    raise RuntimeError("Vertex returned an empty response.")


def _call_openai_assistant(system_prompt: str, user_prompt: str, model: str) -> str:
    import config
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY") or config.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)
    completion = client.chat.completions.create(
        model=model,
        temperature=float(os.getenv("ASSISTANT_LLM_TEMPERATURE", "0.2")),
        max_tokens=int(os.getenv("ASSISTANT_LLM_MAX_TOKENS", "900")),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    if not completion.choices:
        raise RuntimeError("OpenAI returned no choices.")
    content = completion.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty response.")
    return content.strip()


def _call_stub_assistant(mode: str, question: str, decision_context: Optional[Dict[str, Any]]) -> str:
    if _is_capability_request(question):
        return _build_capability_response(mode)

    if mode == "decision_mode" and decision_context:
        requested = decision_context.get("requested_amount")
        recommended = decision_context.get("recommended_amount")
        delta = decision_context.get("delta")
        top_reasons = decision_context.get("top_reasons") or []
        fired_rules = decision_context.get("fired_rules") or []
        lines = [
            "Summary",
            "- The recommendation reflects policy checks, risk classification, and available document quality.",
            "",
            "Key Drivers",
            f"- Requested amount: {requested}. Recommended amount: {recommended}. Delta: {delta}.",
        ]
        for reason in top_reasons[:3]:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append("Policy References")
        if fired_rules:
            for rule in fired_rules[:4]:
                lines.append(f"- {rule.get('name')}: {rule.get('human_description')}")
        else:
            lines.append("- Rule details are not available in this view.")
        lines.append("")
        lines.append("Next Steps")
        lines.append("- Verify missing evidence and policy threshold assumptions before sealing.")
        lines.append("- If you want to improve outcome, reduce amount or add stronger income evidence.")
        lines.append("")
        lines.append("Final credit approval remains the officer's responsibility.")
        return "\n".join(lines)

    return _build_capability_response(mode)


def _run_assistant_provider(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    mode: str,
    question: str,
    decision_context: Optional[Dict[str, Any]]
) -> str:
    if provider == "vertex":
        return _call_vertex_assistant(system_prompt, user_prompt, model)
    if provider == "openai":
        return _call_openai_assistant(system_prompt, user_prompt, model)
    if provider == "stub":
        return _call_stub_assistant(mode, question, decision_context)
    raise RuntimeError(f"Unsupported provider: {provider}")


def _clean_assistant_reply(reply: str) -> str:
    text = (reply or "").replace("**", "").replace("__", "").replace("```", "").strip()
    replacements = {
        "I’m functioning as expected.": "I’m doing well, thanks.",
        "I'm functioning as expected.": "I’m doing well, thanks.",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    lines = [line.rstrip() for line in text.splitlines()]
    cleaned_lines: List[str] = []
    heading_lines = {"summary", "key drivers", "policy references", "next steps", "what i can help with"}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            cleaned_lines.append("")
            continue
        normalized = line.lower().strip(":")
        if normalized in heading_lines:
            continue
        if line.startswith(("* ", "• ")):
            line = f"- {line[2:].strip()}"
        if line.startswith(("#", "##", "###")):
            line = line.lstrip("# ").strip()
        cleaned_lines.append(line)

    while cleaned_lines and not cleaned_lines[-1]:
        cleaned_lines.pop()
    cleaned = "\n".join(cleaned_lines).strip()

    if cleaned.lower().startswith("i do not have a decision record in context"):
        cleaned = (
            "I can still help with this workflow now, and I can provide deeper decision-level analysis once a specific record is open.\n\n"
            "What to do next:\n- Open the relevant decision and ask again for a full recommendation breakdown."
        )
    return cleaned

# ============================================================================
# PARTNER DASHBOARD METRICS (Portfolio Analytics)
# ============================================================================

from fastapi.security import APIKeyHeader

async def get_dashboard_user(
    received_key: Optional[str] = Security(AuthAgent.api_key_header),
    token: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False))
) -> User:
    """
    Flexible auth dependency that works with both JWT (dashboard) and API Key.
    """
    user = None
    
    # 1. Try JWT first (common for dashboard)
    if token:
        try:
            user = await AuthAgent.get_current_user(token)
        except Exception as e:
            logger.error(f"DEBUG: JWT auth failed: {e}")
            pass
            
    # 2. Try API Key if no user found yet
    if not user and received_key:
        try:
            auth_user = await AuthAgent.get_api_key(received_key)
            # Convert AuthUser to User-like object
            user = Database.get_user_by_email(auth_user.email)
            if not user:
                # Create a minimal User object from AuthUser
                user = User(
                    id=f"API-{auth_user.organization_id}",
                    email=auth_user.email,
                    organization_id=auth_user.organization_id,
                    role="API_USER"
                )
        except Exception as e:
            logger.error(f"DEBUG: API Key auth failed: {e}")
            pass
            
    if not user:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED, 
            detail="Authentication required. Please login or provide a valid API Key."
        )

    return user

@app.get("/org/metrics", tags=["Dashboard"])
async def get_org_metrics(
    days: int = 30,
    current_user: User = Depends(get_dashboard_user)
):
    """
    Portfolio-level metrics for the Partner Console dashboard.
    Robustly aggregates data by using raw docs to avoid strict Pydantic validation errors on legacy records.
    Supports time range filtering via 'days' parameter.
    """
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    org_id = current_user.organization_id
    db = Database.get_db()
    
    # Calculate cutoff date
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Fetch raw documents
    asmt_query = db.collection("assessments").where("organization_id", "==", org_id)
    asmt_docs = list(asmt_query.stream())
    
    loan_query = db.collection("loans").where("organization_id", "==", org_id)
    loan_docs = list(loan_query.stream())
    
    # --- Statistics Preparation ---
    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "REJECTED": 0}
    
    # Trends Prep
    today = datetime.utcnow().date()
    trends_map = {}
    for i in range(days):
        day = today - timedelta(days=i)
        trends_map[day] = {"approved": 0, "conditional": 0, "rejected": 0, "label": day.strftime("%b %d")}
    
    filtered_asmt_count = 0
    total_asmt_count = 0
    
    for doc in asmt_docs:
        try:
            data = doc.to_dict()
            decision = data.get("decision")
            risk_level = data.get("risk_level")
            created_at_val = data.get("created_at")
            
            # Parse created_at
            created_dt = None
            if created_at_val:
                if isinstance(created_at_val, datetime):
                    created_dt = created_at_val
                elif isinstance(created_at_val, str):
                    try:
                        created_dt = datetime.fromisoformat(created_at_val.replace('Z', '+00:00'))
                    except: pass
            
            # Global count (within organization)
            total_asmt_count += 1
            
            # Time filter check
            is_in_range = False
            if created_dt:
                # Ensure it has timezone for comparison if needed, or stripping for naive
                ref_dt = created_dt.replace(tzinfo=None) if created_dt.tzinfo else created_dt
                if ref_dt >= cutoff_date:
                    is_in_range = True
                    filtered_asmt_count += 1
            
            if is_in_range:
                # Risk Stats
                if decision == "REJECT":
                    risk_counts["REJECTED"] += 1
                elif risk_level:
                    risk_counts[str(risk_level)] = risk_counts.get(str(risk_level), 0) + 1
                
                # Trend Stats
                created_date = created_dt.date() if created_dt else None
                if created_date in trends_map:
                    if decision == "APPROVE":
                        trends_map[created_date]["approved"] += 1
                    elif decision == "CONDITIONAL":
                        trends_map[created_date]["conditional"] += 1
                    elif decision == "REJECT":
                        trends_map[created_date]["rejected"] += 1
                    
        except Exception as e:
            continue

    # Risk Distribution Percentages
    total_in_range = sum(risk_counts.values())
    risk_distribution = [
        {"name": "Low Risk", "value": risk_counts["LOW"], "color": "#22c55e"},
        {"name": "Medium Risk", "value": risk_counts["MEDIUM"], "color": "#f59e0b"},
        {"name": "High Risk", "value": risk_counts["HIGH"], "color": "#ef4444"},
        {"name": "Rejected", "value": risk_counts["REJECTED"], "color": "#94a3b8"},
    ]
    
    # Format trends for frontend (Sorted by date)
    decision_trends = []
    sorted_days = sorted(trends_map.keys())
    for d in sorted_days:
        decision_trends.append({
            "name": trends_map[d]["label"],
            **trends_map[d]
        })
    
    # --- Loan KPIs ---
    active_count = 0
    default_count = 0
    total_loans_in_range = 0
    disbursed_volume = 0.0
    par_30 = 0
    par_60 = 0
    par_90 = 0
    tracked_loan_count = 0
    recovery_count = 0
    
    for doc in loan_docs:
        try:
            loan = Loan(**doc.to_dict())
            status = getattr(loan.status, "value", loan.status)
            amount = float(loan.amount or 0.0)
            disbursed_dt = loan.disbursed_at
            tracking_summary = LoanTrackingService.summarize(loan)
            
            # Exclusion: PENDING_DISBURSEMENT is not considered "disbursed" yet
            if status == "PENDING_DISBURSEMENT":
                continue

            # KPI 1: Lifetime Disbursed Volume (Actual Full Amount)
            # KPI 2: Current Active Snapshot
            disbursed_volume += amount
            if loan.tracking_profile:
                tracked_loan_count += 1
            if status in ["DISBURSED", "ACTIVE"]:
                active_count += 1
                dpd = int(tracking_summary.get("days_past_due") or 0)
                if loan.tracking_profile:
                    if dpd >= 30:
                        par_30 += 1
                    if dpd >= 60:
                        par_60 += 1
                    if dpd >= 90:
                        par_90 += 1
                    if tracking_summary.get("tracker_state") == "RECOVERY":
                        recovery_count += 1
                elif disbursed_dt:
                    age_days = (datetime.utcnow().date() - disbursed_dt.date()).days
                    if age_days > 30:
                        par_30 += 1
                    if age_days > 60:
                        par_60 += 1
                    if age_days > 90:
                        par_90 += 1
            
            # KPI 3: Range-bound metrics (Defaults)
            is_in_range = False
            if disbursed_dt:
                ref_dt = disbursed_dt.replace(tzinfo=None) if disbursed_dt.tzinfo else disbursed_dt
                if ref_dt >= cutoff_date:
                    is_in_range = True
            
            if is_in_range:
                if status == "DEFAULTED":
                    default_count += 1
                total_loans_in_range += 1
                
        except: continue
        
    default_rate = (default_count / total_loans_in_range * 100) if total_loans_in_range > 0 else 0.0
    
    # --- Risk Drift Detection ---
    alerts = []
    if total_in_range > 0:
        negative_rate = (risk_counts["REJECTED"] + risk_counts["HIGH"]) / total_in_range
        if negative_rate > 0.4:
            alerts.append({
                "type": "RISK_DRIFT",
                "severity": "WARNING",
                "message": f"Negative outcome rate ({negative_rate*100:.1f}%) exceeds safety threshold. Review policy strictness."
            })
    if active_count > 0 and tracked_loan_count < active_count:
        alerts.append({
            "type": "TRACKING_GAP",
            "severity": "INFO",
            "message": f"{active_count - tracked_loan_count} active loans still need repayment tracking setup."
        })
    
    par_base = active_count if active_count > 0 else 1
    return {
        "total_assessments": filtered_asmt_count,
        "active_loans": active_count,
        "disbursed_volume": round(disbursed_volume, 2),
        "default_rate": round(default_rate, 1),
        "tracker_coverage": round((tracked_loan_count / active_count) * 100, 1) if active_count > 0 else 0.0,
        "recovery_loans": recovery_count,
        "par_snapshot": {
            "par_30": par_30,
            "par_60": par_60,
            "par_90": par_90,
            "par_30_rate": round((par_30 / par_base) * 100, 1),
            "par_60_rate": round((par_60 / par_base) * 100, 1),
            "par_90_rate": round((par_90 / par_base) * 100, 1)
        },
        "risk_distribution": risk_distribution,
        "decision_trends": decision_trends,
        "alerts": alerts
    }


@app.get("/org/watchlist", tags=["Dashboard"])
async def get_org_watchlist(
    limit: int = 20,
    current_user: User = Depends(get_dashboard_user)
):
    if current_user.role not in ["OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = current_user.organization_id if current_user.organization_id != "PLATFORM_OWNER" else None
    assessments = Database.get_assessments_by_org(org_id, limit=200) if org_id else Database.list_assessments()
    loans = Database.list_loans(organization_id=org_id) if org_id else Database.list_loans()
    loan_by_assessment = {l.assessment_id: l for l in loans if getattr(l, "assessment_id", None)}

    import config
    from utils.policy_config import get_policy_for_org
    from utils.policy_context import set_policy_context, reset_policy_context, policy_value

    policy_values, _ = get_policy_for_org(current_user.organization_id)
    token = set_policy_context(policy_values)
    watchlist = []
    try:
        for assessment in assessments:
            loan = loan_by_assessment.get(assessment.assessment_id)

            def add_alert(alert_type: str, severity: str, message: str):
                watchlist.append({
                    "alert_id": f"{assessment.assessment_id}:{alert_type}",
                    "type": alert_type,
                    "severity": severity,
                    "message": message,
                    "assessment_id": assessment.assessment_id,
                    "borrower_id": assessment.borrower_id,
                    "decision": str(assessment.decision),
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level,
                    "data_quality_score": assessment.data_quality_score,
                    "loan_status": getattr(loan, "status", None),
                    "timestamp": getattr(assessment, "decision_timestamp", None)
                })

            # High risk or high DTI
            if assessment.risk_score is not None and assessment.risk_score >= 0.7:
                add_alert("HIGH_RISK", "HIGH", "Risk score is high; review before disbursement or renewal.")
            dti_ratio = (assessment.metrics or {}).get("dti_ratio")
            if dti_ratio is not None and dti_ratio > policy_value("max_debt_to_income_ratio", config.MAX_DEBT_TO_INCOME_RATIO):
                add_alert("HIGH_DTI", "HIGH", "Debt-to-income ratio exceeds policy threshold.")

            # Low data quality
            if assessment.data_quality_score is not None and assessment.data_quality_score < policy_value("data_quality_refer_threshold", config.DATA_QUALITY_REFER_THRESHOLD):
                add_alert("LOW_DATA_QUALITY", "HIGH", "Data quality is below threshold; manual verification recommended.")

            # Missing documents
            missing_docs = (assessment.metrics or {}).get("missing_documents") or []
            if missing_docs:
                add_alert("MISSING_DOCUMENTS", "MEDIUM", f"Missing required documents: {', '.join(missing_docs)}.")

            # Thin file
            if assessment.blocking_factors and any("INSUFFICIENT_TRANSACTION_HISTORY" in f for f in assessment.blocking_factors):
                add_alert("THIN_FILE", "MEDIUM", "Insufficient transaction history; monitor before approval.")

            # Loan status flags
            if loan:
                tracking_summary = LoanTrackingService.summarize(loan)
                if tracking_summary.get("broken_promise"):
                    add_alert("BROKEN_PROMISE", "HIGH", "Promise-to-pay date has expired without a matching repayment.")
                if tracking_summary.get("cadence_fit") == "LOW":
                    add_alert("CADENCE_MISMATCH", "MEDIUM", "Repayment cadence does not match the borrower's income rhythm.")
                if tracking_summary.get("tracker_state") == "RECOVERY":
                    add_alert("RECOVERY_LANE", "HIGH", str(tracking_summary.get("recommended_action")))
                elif tracking_summary.get("tracker_state") == "AT_RISK":
                    add_alert("COLLECTION_SLIPPAGE", "MEDIUM", str(tracking_summary.get("recommended_action")))

                status = str(getattr(loan, "status", "")).upper()
                if "DEFAULT" in status:
                    add_alert("LOAN_DEFAULTED", "CRITICAL", "Loan marked as defaulted; immediate action required.")
                elif "ACTIVE" in status and assessment.risk_score is not None and assessment.risk_score >= 0.6:
                    add_alert("ACTIVE_HIGH_RISK", "MEDIUM", "Active loan with elevated risk score.")
    finally:
        reset_policy_context(token)

    severity_rank = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1}
    watchlist.sort(key=lambda item: (severity_rank.get(item["severity"], 0), item.get("risk_score") or 0), reverse=True)
    return watchlist[:limit]


@app.get("/org/report", tags=["Dashboard"])
async def get_org_report(
    days: int = 30,
    current_user: User = Depends(get_dashboard_user)
):
    """
    Detailed organization report for the selected time window.
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    from agents.organization_report_agent import OrganizationReportAgent

    return OrganizationReportAgent.build_report_data(org, days)


@app.get("/org/report/pdf", tags=["Dashboard"])
async def download_org_report_pdf(
    days: int = 30,
    current_user: User = Depends(get_dashboard_user)
):
    """
    Generates and downloads a PDF version of the organization report.
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    from agents.organization_report_agent import OrganizationReportAgent

    try:
        report = OrganizationReportAgent.build_report_data(org, days)
        pdf_bytes = OrganizationReportAgent.generate_report_pdf_bytes(report)
        filename = f"organization-report-{days}d.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    except Exception as exc:
        logger.exception("Failed to generate organization report PDF")
        raise HTTPException(status_code=500, detail=f"Failed to generate organization report PDF: {exc}")

# Database initialization happens via the Database class
# No local dictionaries needed for V2

@app.get(
    "/health",
    tags=["System"],
    summary="Health Check",
    description="""
    Check if the API is online and view system configuration.
    
    **No authentication required.**
    
    Returns:
    - System status message
    - API version
    - Feature flags (ML enabled, behavioral analysis, LLM explanations)
    
    Use this endpoint to verify the API is accessible before making other requests.
    """
)
async def health_check():
    """Check API health and system configuration"""
    import config
    return {
        "message": "Loan Officer AI Agent V1→V4 is online.",
        "version": "2.0.0",
        "ml_enabled": config.ENABLE_ML_RISK_SCORING,
        "behavioral_v2_enabled": config.ENABLE_BEHAVIORAL_V2,
        "llm_enabled": config.ENABLE_LLM_EXPLANATIONS
    }

@app.post(
    "/intake/start",
    response_model=Dict[str, str],
    tags=["Borrower Management"],
    summary="Create Borrower Profile",
    description="""
    **Step 1:** Create a new borrower profile and validate their information.
    
    This endpoint:
    - Validates all required borrower information
    - Creates a unique borrower ID
    - Saves the profile to the database
    - Prepares the data for risk assessment
    
    **Required Fields:**
    - name, phone, employment_type
    - monthly_income, monthly_expenses, existing_debt
    - loan_amount_requested, loan_purpose
    
    **Authentication:** None required (public borrower portal)
    
    **Next Step:** Use the returned `borrower_id` with `/assessment/run`
    """
)
async def intake_start(
    raw_data: dict = Body(
        ...,
        example={
            "name": "Jane Doe",
            "phone": "+254700000000",
            "email": "jane@example.com",
            "employment_type": "trader",
            "monthly_income": 50000,
            "monthly_expenses": 20000,
            "existing_debt": 5000,
            "loan_amount_requested": 15000,
            "loan_purpose": "Business stock purchase",
            "organization_id": "ORG-123"
        }
    ),
    user: Optional[AuthUser] = Depends(AuthAgent.get_api_key_optional)
):
    """
    Create a new borrower profile with validated information.
    """
    try:
        # Determine Org ID: API key (if provided) overrides body which overrides default
        org_id = raw_data.get("organization_id")
        if user:
            org_id = user.organization_id
        
        if not org_id:
            # 1. Configured Default
            env_default = os.getenv("DEFAULT_ORG_ID")
            if env_default:
                org_id = env_default
            else:
                # 2. Smart Default: If only one org exists, use it.
                try:
                    all_orgs = Database.list_organizations()
                    if len(all_orgs) == 1:
                        org_id = all_orgs[0].id
                        logger.info(f"INFO: Auto-resolved organization to {org_id}")
                    else:
                        org_id = "DEFAULT_ORG"
                except Exception as e:
                    logger.error(f"WARN: Failed to resolve default org: {e}")
                    org_id = "DEFAULT_ORG"

        borrower_profile = IntakeAgent.process(raw_data)
        borrower_profile.id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        borrower_profile.organization_id = org_id
        
        Database.save_borrower(borrower_profile)
        AuditAgent.log_event("INTAKE_START", user.role if user else "BORROWER_PORTAL", 
                             {"borrower_id": borrower_profile.id, "org": org_id})
        
        return {"borrower_id": borrower_profile.id, "status": "INTAKE_COMPLETE", "organization_id": org_id}
    except Exception as e:
        import traceback
        logger.error(f"ERROR in intake_start: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/assessment/run",
    response_model=Dict[str, Any],
    tags=["Risk Assessment"],
    summary="Run Risk Assessment",
    description="""
    **Step 2:** Run AI-powered risk assessment on a borrower.
    
    This endpoint:
    - Evaluates the borrower's creditworthiness
    - Calculates risk score (0-1, lower is better)
    - Provides AI recommendation (APPROVE/CONDITIONAL/REJECT/REFER)
    - Generates detailed explanation of the decision
    
    **Assessment includes:**
    - Debt-to-income ratio analysis
    - Affordability calculations
    - Income stability evaluation
    - Alternative data analysis (if uploaded)
    - ML probability score (if enabled)
    
    **Returns:**
    - `risk_score`: 0-1 (LOW < 0.3, MEDIUM < 0.7, HIGH >= 0.7)
    - `decision`: APPROVE, CONDITIONAL, REJECT, or REFER
    - `recommended_amount`: Suggested loan amount
    - `recommended_interest_rate`: Suggested interest rate (%)
    - `explanation`: Detailed reasoning for the decision
    
    **Authentication:** API Key Required
    
    **Processing time:** 2-3 seconds
    """
)
async def assessment_run(
    payload: Dict[str, Any] = Body(..., example={"borrower_id": "BOR-A1B2C3D4"}),
    background_tasks: BackgroundTasks = None,
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """
    Runs the full analysis pipeline for a borrower with billing metering.
    """
    # 1. Resolve borrower (either by borrower_id or full borrower payload)
    borrower_id = payload.get("borrower_id")
    requested_duration_days = payload.get("requested_duration_days", 30)
    mobile_money_history = payload.get("mobile_money_history")
    utility_history = payload.get("utility_history")
    airtime_usage_avg = payload.get("airtime_usage_avg")

    borrower = None
    if borrower_id:
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found. Please run /intake/start first.")
    else:
        # Create borrower directly from payload (API convenience)
        borrower_fields = set(Borrower.model_fields.keys())
        borrower_payload = {k: v for k, v in payload.items() if k in borrower_fields}
        borrower_profile = IntakeAgent.process(borrower_payload)
        borrower_profile.id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        borrower_profile.organization_id = user.organization_id
        Database.save_borrower(borrower_profile)
        borrower = borrower_profile
        AuditAgent.log_event("INTAKE_START", user.role, {
            "borrower_id": borrower_profile.id,
            "org": borrower_profile.organization_id
        })
    
    if borrower.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Borrower not found.")
        
    org = Database.get_organization(user.organization_id)
    if not org:
        raise HTTPException(status_code=500, detail="Organization context missing")

    # 2. Check billing
    from agents.billing_agent import BillingAgent
    is_allowed, billing_error = BillingAgent.check_billing_limit(org, user.environment)
    if not is_allowed:
        raise HTTPException(status_code=billing_error.get("code", 429), detail=billing_error)

    # 3. Call core assessment logic
    assessment = await _run_assessment_core(
        borrower=borrower,
        requested_duration_days=requested_duration_days,
        mobile_money_history=mobile_money_history,
        utility_history=utility_history,
        airtime_usage_avg=airtime_usage_avg,
        assessment_source="API"
    )

    # 4. Save and Meter
    logger.debug(f"[ASSESSMENT SAVE DEBUG] Saving assessment {assessment.assessment_id} for org: {assessment.organization_id}, borrower: {borrower.id}, borrower_org: {borrower.organization_id}")
    Database.save_assessment(assessment)
    BillingAgent.meter_usage(
        org=org, 
        environment=user.environment, 
        api_key_id="API_KEY",
        endpoint="/assessment/run",
        assessment_id=assessment.assessment_id
    )

    if background_tasks is not None:
        background_tasks.add_task(
            WebhookService.send_event,
            org,
            "assessment.completed",
            augment_assessment_payload(assessment.model_dump())
        )

    return augment_assessment_payload(assessment.model_dump())

async def _run_assessment_core(
    borrower: Borrower,
    requested_duration_days: int,
    mobile_money_history: Optional[List[Dict[str, Any]]] = None,
    utility_history: Optional[List[Dict[str, Any]]] = None,
    airtime_usage_avg: Optional[float] = None,
    statement_summary: Optional[Dict[str, Any]] = None,
    assessment_source: str = "API",
    unified_profile: Optional[UnifiedFinancialProfile] = None,  # NEW: Unified profile parameter
    external_behavioral_results: Optional[Dict[str, Any]] = None,
    data_quality_score: Optional[float] = None,
    data_provenance: Optional[Dict[str, Any]] = None,
    consent_event_id: Optional[str] = None,
    consent_channel: Optional[str] = None,
    consent_timestamp: Optional[str] = None,
    document_info: Optional[Dict[str, Any]] = None
) -> Assessment:
    """
    Internal shared logic for running a credit assessment.
    Ensures identical results across all entry points.
    """
    from utils.policy_config import get_policy_for_org
    from utils.policy_context import set_policy_context, reset_policy_context

    policy_values, _ = get_policy_for_org(borrower.organization_id)
    policy_token = set_policy_context(policy_values)
    try:
        # INSTANT DATA preparation
        external_results = external_behavioral_results
        if external_results is None and (mobile_money_history is not None or utility_history is not None):
            external_results = {
                "transactions": mobile_money_history or [],
                "utility_history": utility_history or [],
                "airtime_usage_avg": airtime_usage_avg or 0.0,
                "behavioral_stability": 0.7,
                "saving_trend": 0.7,
                "utility_compliance": 0.7,
                "early_warnings": []
            }
        if external_results is not None and statement_summary:
            external_results["statement_summary"] = statement_summary

        # NEW: Extract verified income from unified_profile (if available)
        verified_monthly_income = None
        verified_income_source = None
        if unified_profile:
            # Use net_pay from payslip as verified income
            if unified_profile.income.net_pay is not None:
                verified_monthly_income = unified_profile.income.net_pay
                verified_income_source = "PAYSLIP"
                logger.info(f"INFO: Extracted verified income from payslip: {verified_monthly_income}")

            # Pass through external_results for RiskAgent
            if verified_monthly_income:
                if external_results is None:
                    external_results = {
                        "transactions": [],
                        "behavioral_stability": 0.7,
                        "saving_trend": 0.7,
                        "utility_compliance": 0.7,
                        "early_warnings": []
                    }
                external_results["verified_monthly_income"] = verified_monthly_income
                external_results["verified_income_source"] = verified_income_source

        # 1. Evaluate Risk
        risk_results = RiskAgent.evaluate(
            borrower,
            external_behavioral_results=external_results,
            requested_duration_days=requested_duration_days,
        )

        # 2. Recommmend Decision
        decision_results = DecisionAgent.recommend(risk_results, borrower, requested_duration_days)
        decision_results = apply_data_quality_policy(decision_results, data_quality_score)

        # 3. Generate Explanation
        explanation_results = ExplanationAgent.generate(risk_results, decision_results, borrower)

        # 4. Construct Assessment Object
        mdata = decision_results.get("decision_metadata", {})
        decision_timestamp = datetime.utcnow()

        # Reason Codes Extraction
        reason_codes = []
        if decision_results["decision"] == "REJECT":
            for factor in explanation_results.get("blocking_factors", []):
                code = factor.upper().replace(" ", "_").replace(".", "").replace(":", "")
                reason_codes.append(code[:30])
            for flag in risk_results["flags"]:
                if "CRITICAL" in flag:
                    reason_codes.append(flag.split(":")[0].strip().upper().replace(" ", "_"))
        elif decision_results["decision"] == "APPROVE" and mdata.get("adjustments_applied"):
            for adj in mdata["adjustments_applied"]:
                reason_codes.append(f"{adj.get('type', 'ADJUSTMENT')}_{adj.get('reason', 'POLICY').upper().replace(' ', '_')}")
        reason_codes = list(set(reason_codes))

        data_used = {
            "transaction_days": risk_results["metrics"].get("history_days", 0),
            "transaction_count": risk_results["metrics"].get("transaction_count", 0),
            "data_sources": [risk_results.get("data_source", "INTERNAL")],
            "data_recency_days": 0
        }
        if mobile_money_history or utility_history:
            data_used["data_sources"].append("USER_UPLOADED")

        doc_info = dict(document_info or {})
        if statement_summary and isinstance(statement_summary, dict):
            if "summary_profile" in statement_summary and "summary_profile" not in doc_info:
                doc_info["summary_profile"] = statement_summary.get("summary_profile")
        data_prov = build_data_provenance(
            data_used=data_used,
            data_quality_score=data_quality_score,
            consent_event_id=consent_event_id,
            consent_channel=consent_channel,
            consent_timestamp=consent_timestamp,
            document_info=doc_info if doc_info else None
        )
        if data_provenance:
            merged_prov = dict(data_provenance)
            merged_prov.update(data_prov)
            data_prov = merged_prov

        decision_trace = build_decision_trace(
            borrower=borrower,
            requested_duration_days=requested_duration_days,
            assessment_source=assessment_source,
            risk_results=risk_results,
            decision_results=decision_results,
            reason_codes=reason_codes,
            data_quality_score=data_quality_score
        )

        assessment = Assessment(
            assessment_id=f"ASMT-{uuid.uuid4().hex[:8].upper()}",
            borrower_id=borrower.id,
            organization_id=borrower.organization_id,
            requested_amount=borrower.loan_amount_requested,
            requested_duration_days=requested_duration_days,
            decision_timestamp=decision_timestamp,
            decision_reason_codes=reason_codes,
            data_used=data_used,
            data_quality_score=data_quality_score,
            data_provenance=data_prov,
            decision_trace=decision_trace,
            risk_score=risk_results["risk_score"],
            risk_level=risk_results["risk_level"],
            decision=decision_results["decision"],
            assessment_source=assessment_source,
            recommended_amount=decision_results["recommended_amount"],
            recommended_duration_days=decision_results.get("recommended_duration_days"),
            recommended_interest_rate=decision_results["recommended_interest_rate"],
            interest_rate_basis=decision_results.get("interest_rate_basis"),
            decision_summary=explanation_results["decision_summary"],
            customer_view=explanation_results["customer_view"],
            officer_view=explanation_results["officer_view"],
            audit_view=explanation_results["audit_view"],
            blocking_factors=explanation_results["blocking_factors"],
            customer_message=explanation_results["customer_message"],
            internal_notes=explanation_results["internal_notes"],
            adverse_action=explanation_results.get("adverse_action", {}),
            explanation=explanation_results["explanation"],
            explanation_source=explanation_results["explanation_source"],
            decision_source="rules_engine",
            policy_version=mdata.get("policy_version", "v1.2.0-human-first"),
            flags=risk_results["flags"],
            observed_deposit_volume=risk_results["metrics"]["observed_deposit_volume"],
            transaction_count=risk_results["metrics"]["transaction_count"],
            history_days=risk_results["metrics"]["history_days"],
            capacity_based_max=mdata.get("capacity_based_max", risk_results["metrics"].get("capacity_based_max", 0.0)),
            capacity_multiplier_used=risk_results["metrics"].get("capacity_multiplier_used", 0.0),
            starter_loan_applied=mdata.get("starter_loan_applied", risk_results["metrics"].get("starter_loan_applied", False)),
            metrics={**risk_results["metrics"]},
            policy_cap_amount=mdata.get("policy_cap_amount"),
            policy_cap_reason=mdata.get("policy_cap_reason"),
            ml_advisory_only=True,
            ml_attempted_override=any(adj.get("type") == "CAPACITY_CAP" for adj in mdata.get("adjustments_applied", []) if isinstance(adj, dict)),
            decision_metadata=mdata
        )
        # Ensure summary_profile is set when a statement summary exists
        if statement_summary and assessment.metrics is not None and not assessment.metrics.get("summary_profile"):
            summary_profile_val = None
            if isinstance(statement_summary, dict):
                summary_profile_val = statement_summary.get("summary_profile")
            else:
                summary_profile_val = getattr(statement_summary, "summary_profile", None)
            if summary_profile_val:
                assessment.metrics["summary_profile"] = summary_profile_val

        # 5. Semantic Validation & Repair
        from utils.explanation_validator import ExplanationValidator
        assessment.explanation = ExplanationValidator.auto_repair_explanation(assessment)
        assessment.flags = ExplanationValidator.deduplicate_flags(assessment.flags)

        integrity_issues = ExplanationValidator.validate_integrity(assessment)
        if integrity_issues:
            for issue in integrity_issues:
                prefix = "AUDIT_ALERT: " if "ERROR" in issue or "CRITICAL" in issue else "AUDIT_INFO: "
                assessment.flags.append(f"{prefix}{issue}")
            assessment.flags = ExplanationValidator.deduplicate_flags(assessment.flags)

        return assessment
    finally:
        reset_policy_context(policy_token)

@app.post("/assessment/query")
async def assessment_query(assessment: Assessment, question_type: str):
    """
    Safe 'Ask Why' capability for humans to interact with the decision facts.
    Returns deterministic, policy-anchored answers.
    """
    try:
        answer = QueryAgent.answer(assessment, question_type)
        return answer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/assessment/{assessment_id}/ask")
async def assessment_ask(
    assessment_id: str,
    payload: Dict[str, Any] = Body(...),
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    """
    Deterministic decision Q&A. Answers only from the stored decision record.
    """
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to this assessment")

    question_type = payload.get("question_type") or payload.get("question") or ""
    try:
        return QueryAgent.answer(assessment, question_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/assistant/chat", response_model=AssistantChatResponse, tags=["Assistant"])
async def assistant_chat(
    payload: AssistantChatRequest = Body(...),
    user: User = Depends(AuthAgent.get_current_user)
):
    """
    Decision Copilot endpoint.
    Answers strictly from known record context. Does not fabricate missing values.
    """
    _enforce_assistant_rate_limit(user)
    request_id = f"cop-{uuid.uuid4().hex[:12]}"
    messages = _truncate_messages(payload.messages)
    question = _latest_user_message(messages)
    if not question:
        raise HTTPException(status_code=400, detail="A user message is required.")

    route = payload.context.route or "/"
    mode = _assistant_mode_from_route(route)
    intent = _classify_assistant_intent(question)
    decision_context: Optional[Dict[str, Any]] = None
    decision_id = payload.context.decisionId or _extract_decision_id_from_route(route)

    if decision_id:
        assessment = Database.get_assessment(decision_id)
        if not assessment:
            raise HTTPException(status_code=404, detail="Decision context not found.")

        role_value = _assistant_user_role(user)
        user_org = (user.organization_id or "").upper()
        assessment_org = (assessment.organization_id or "").upper()
        if assessment_org != user_org and role_value != "SUPER_ADMIN":
            raise HTTPException(status_code=403, detail="Unauthorized decision context access.")

        decision_context = _build_assistant_decision_context_v2(assessment)
        AuditAgent.log_event("ASSISTANT_EXPLANATION_REQUESTED", user.email, {
            "decisionId": assessment.assessment_id,
            "userId": user.id,
            "route": route,
            "org": user.organization_id
        })

    try:
        provider, model = _resolve_assistant_provider()
    except Exception as provider_error:
        logger.error(
            "[ASSISTANT] request_id=%s provider=error model=unknown org=%s user=%s mode=%s route=%s setup_error=%s",
            request_id,
            user.organization_id,
            user.id,
            mode,
            route,
            str(provider_error)
        )
        hint = _provider_error_hint("error", provider_error)
        return {
            "reply": f"I could not initialize the assistant provider. {hint}",
            "meta": {
                "provider": "error",
                "model": "unknown",
                "requestId": request_id,
                "mode": mode
            }
        }

    fallback_reply = _compose_intent_fallback_response(intent=intent, mode=mode, decision_context=decision_context)
    if provider == "stub" and fallback_reply is not None:
        logger.info(
            "[ASSISTANT] request_id=%s provider=stub model=%s route=%s mode=%s intent=%s org=%s user=%s",
            request_id,
            model,
            route,
            mode,
            intent,
            user.organization_id,
            user.id
        )
        return {
            "reply": _clean_assistant_reply(fallback_reply),
            "meta": {
                "provider": "stub",
                "model": model,
                "requestId": request_id,
                "mode": mode
            }
        }

    last_topic = _derive_last_topic(messages, question)
    system_prompt = _build_system_prompt(mode=mode, question=question, has_decision_context=decision_context is not None)
    user_prompt = _build_user_prompt(
        route=route,
        mode=mode,
        intent=intent,
        question=question,
        history=messages,
        last_topic=last_topic,
        decision_context=decision_context
    )

    logger.info(
        "[ASSISTANT] request_id=%s provider=%s model=%s route=%s mode=%s intent=%s org=%s user=%s decision_id=%s message_count=%d",
        request_id,
        provider,
        model,
        route,
        mode,
        intent,
        user.organization_id,
        user.id,
        decision_id or "none",
        len(messages)
    )

    try:
        reply = _run_assistant_provider(
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            mode=mode,
            question=question,
            decision_context=decision_context
        )
    except Exception as provider_error:
        hint = _provider_error_hint(provider, provider_error)
        logger.error(
            "[ASSISTANT] request_id=%s provider=error model=%s route=%s mode=%s org=%s user=%s provider_error=%s",
            request_id,
            model,
            route,
            mode,
            user.organization_id,
            user.id,
            str(provider_error)
        )
        return {
            "reply": f"I could not complete this assistant request because the {provider} provider failed. {hint}",
            "meta": {
                "provider": "error",
                "model": model,
                "requestId": request_id,
                "mode": mode
            }
        }

    logger.info(
        "[ASSISTANT] request_id=%s provider=%s model=%s status=ok",
        request_id,
        provider,
        model
    )
    return {
        "reply": _clean_assistant_reply(reply),
        "meta": {
            "provider": provider,
            "model": model,
            "requestId": request_id,
            "mode": mode
        }
    }

@app.get("/assessment/result/{assessment_id}", response_model=Dict[str, Any])
async def get_assessment(assessment_id: str, user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Retrieves a previously generated assessment.
    """
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found.")
        
    # SCOPING: strict isolation
    if assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Assessment not found.")
        
    return filter_assessment_for_role(assessment, user.role)

@app.get("/assessments", response_model=List[Assessment])
async def list_assessments(user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Returns assessments for the officer's organization.
    """
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    return Database.list_assessments(organization_id=user.organization_id)

@app.post("/assessment/manual", tags=["Manual Assessments"])
async def assessment_manual(
    borrower_id: Optional[str] = Form(None),
    full_name: str = Form(...),
    phone: str = Form(...),
    employment_type: str = Form(...),
    monthly_income: float = Form(...),
    monthly_expenses: float = Form(...),
    requested_amount: float = Form(...),
    requested_duration_days: int = Form(30),
    loan_purpose: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    bank_statement: Optional[UploadFile] = File(None),
    mobile_money_statement: Optional[UploadFile] = File(None),
    nrc_id: Optional[UploadFile] = File(None),
    utility_bill: Optional[UploadFile] = File(None),
    payslip: Optional[UploadFile] = File(None),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Unified endpoint for Manual UI Assessments.
    Handles borrower creation, file parsing, and core assessment logic.
    """
    def normalize_employment_type(raw_value: str) -> str:
        if not raw_value:
            return raw_value
        normalized = raw_value.strip().lower().replace("-", " ").replace("_", " ")
        normalized = " ".join(normalized.split())
        mapping = {
            "employed": "salaried",
            "salaried": "salaried",
            "salary": "salaried",
            "self employed": "self_employed",
            "self employed business": "self_employed",
            "self employed professional": "self_employed",
            "self employed owner": "self_employed",
            "self employed entrepreneur": "self_employed",
            "self employed trader": "self_employed",
            "self-employed": "self_employed",
            "self_employed": "self_employed",
            "trader": "trader",
            "business owner": "trader",
            "merchant": "trader",
            "farmer": "farmer",
            "gig": "gig",
            "gig worker": "gig",
            "contractor": "gig",
            "freelancer": "gig",
        }
        if normalized in mapping:
            return mapping[normalized]
        return raw_value.strip()

    # 1. Security & Billing Check
    org = Database.get_organization(current_user.organization_id)
    if not org: raise HTTPException(status_code=500, detail="Org context missing")
    
    # Check billing (using current user's org and default env for UI)
    from agents.billing_agent import BillingAgent
    is_allowed, billing_error = BillingAgent.check_billing_limit(org, org.environment)
    if not is_allowed:
        raise HTTPException(status_code=billing_error.get("code", 429), detail=billing_error)

    # 2. Create or load Borrower
    if borrower_id:
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found for document continuation")
        
        # MULTI-TENANCY FIX: If borrower was created via public portal (DEFAULT_ORG),
        # migrate them to the current officer's organization.
        if borrower.organization_id != current_user.organization_id:
            # Safety Check: Can only take over if borrower is in DEFAULT_ORG or requester is SUPER_ADMIN
            if borrower.organization_id == "DEFAULT_ORG" or current_user.role == "SUPER_ADMIN":
                logger.info(f"INFO: Migrating borrower {borrower.id} from {borrower.organization_id} to {current_user.organization_id.upper()}")
                borrower.organization_id = current_user.organization_id.upper()
                # Note: We'll save the borrower below in step 2b
            else:
                # Prevent hijacking borrowers from other MFIs
                AuditAgent.log_event("CROSS_ORG_ACCESS_DENIED", current_user.email, {
                    "borrower_id": borrower.id,
                    "target_org": borrower.organization_id,
                    "officer_org": current_user.organization_id
                })
                raise HTTPException(status_code=403, detail="Borrower belongs to a different organization")
    else:
        # 2a. Determine Identification Support (Optional)
        id_provided = False
        id_type = IDType.UNKNOWN
        if national_id:
            id_provided = True
            # Simple pattern detection: NRC usually has slashes (e.g. 123456/11/1)
            if "/" in national_id:
                id_type = IDType.NRC
            else:
                # Alphanumeric often indicates Passport
                id_type = IDType.PASSPORT

        borrower_id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        employment_type = normalize_employment_type(employment_type)
        try:
            borrower = Borrower(
                id=borrower_id,
                organization_id=current_user.organization_id,
                name=full_name,
                phone=phone,
                employment_type=employment_type,
                monthly_income=monthly_income,
                monthly_expenses=monthly_expenses,
                existing_debt=0, # Default for manual UI if not provided
                loan_amount_requested=requested_amount,
                loan_purpose=loan_purpose or "Not Specified",
                national_id=national_id,
                id_provided=id_provided,
                id_type=id_type,
                id_review_status=IDReviewStatus.NOT_REVIEWED
            )
        except ValidationError as exc:
            issues = []
            for err in exc.errors():
                loc = ".".join([str(v) for v in err.get("loc", [])])
                issues.append({
                    "field": loc or "borrower",
                    "issue": err.get("msg", "Invalid value")
                })
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Borrower data is invalid. Review the highlighted fields and retry.",
                    "issues": issues,
                    "suggestion": "Check required fields, numeric formats, and remove invalid characters."
                }
            )
    
    # 2b. Persist (New or Migrated)
    Database.save_borrower(borrower)

    # 3. Parse Transactions (Evidence Handling)
    tx_parser = TransactionParser()
    all_parsed_transactions = []
    
    logger.debug(
        f"Manual assessment files present: "
        f"bank_statement={bool(bank_statement)}, "
        f"mobile_money_statement={bool(mobile_money_statement)}, "
        f"payslip={bool(payslip)}, "
        f"nrc_id={bool(nrc_id)}"
    )
    
    # Helper to parse upload files
    async def parse_upload(file_obj: UploadFile, document_hint: Optional[str] = None):
        if not file_obj: return []
        content = await file_obj.read()
        try:
            result = tx_parser.parse(content, file_obj.filename, document_hint=document_hint)
            result.source_filename = file_obj.filename
            result.source_mime_type = file_obj.content_type
            summary_profile = None
            summary_snapshot = {}
            if result.bank_statement_summary:
                summary_profile = result.bank_statement_summary.summary_profile
                summary_snapshot = {
                    "closing_balance": result.bank_statement_summary.closing_balance,
                    "statement_period": result.bank_statement_summary.statement_period.model_dump()
                    if result.bank_statement_summary.statement_period else None
                }
            elif result.payslip_summary:
                summary_profile = result.payslip_summary.summary_profile
                summary_snapshot = {
                    "net_pay": result.payslip_summary.net_pay,
                    "gross_pay": result.payslip_summary.gross_pay,
                    "employer_name": result.payslip_summary.employer_name
                }
            elif result.nrc_summary:
                summary_profile = result.nrc_summary.summary_profile
                summary_snapshot = {
                    "full_name": result.nrc_summary.full_name,
                    "id_number": result.nrc_summary.id_number
                }
            logger.info(
                f"EXTRACTION: {file_obj.filename} doc_type={result.document_type} "
                f"summary_profile={summary_profile} summary={summary_snapshot} warnings={result.warnings}"
            )
            is_readable = result.confidence > 0.0 or len(result.transactions) > 0
            if not is_readable or result.warnings:
                AuditAgent.log_event("EXTRACTION_WARNING", current_user.email, {
                    "filename": file_obj.filename,
                    "warnings": result.warnings,
                    "is_readable": is_readable,
                    "org": current_user.organization_id
                })
            if not is_readable:
                logger.warning(f"WARN: Document {file_obj.filename} is unreadable: {result.warnings}")
            return result
        except Exception as e:
            AuditAgent.log_event("EXTRACTION_ERROR", current_user.email, {
                "filename": file_obj.filename,
                "error": str(e),
                "org": current_user.organization_id
            })
            logger.error(f"WARN: Failed to parse {file_obj.filename}: {e}")
            return None

    # Parse primary statements
    extraction_results = []
    
    res_bank = await parse_upload(bank_statement, document_hint="bank_statement")
    if res_bank: extraction_results.append(res_bank)
    
    res_momo = await parse_upload(mobile_money_statement, document_hint="mobile_money")
    if res_momo: extraction_results.append(res_momo)

    res_nrc = await parse_upload(nrc_id, document_hint="nrc_id")
    if res_nrc: extraction_results.append(res_nrc)

    res_payslip = await parse_upload(payslip, document_hint="payslip")
    if res_payslip: extraction_results.append(res_payslip)
    
    all_parsed_transactions = []
    for res in extraction_results:
        all_parsed_transactions.extend(res.transactions)

    # Use bank statement summary if available, otherwise fallback to payslip summary
    bank_statement_summary = None
    payslip_summary = None
    for res in extraction_results:
        if res.bank_statement_summary:
            bank_statement_summary = res.bank_statement_summary
            break
    for res in extraction_results:
        if res.payslip_summary:
            payslip_summary = res.payslip_summary
            break
    summary_for_risk = bank_statement_summary or payslip_summary

    # 4. Build Unified Financial Profile (NEW PIPELINE)
    logger.debug("DEBUG: Building UnifiedFinancialProfile from extraction results")
    unified_profile = ProfileBuilder.build(
        extraction_results=extraction_results,
        transactions=all_parsed_transactions
    )
    
    # Build document summaries for UI display
    document_summaries = build_document_summaries(extraction_results)
    
    # SAFETY CHECK: Log what we're sending to the UI
    logger.info(f"\nDEBUG [API]: Document summaries for UI ({len(document_summaries)} docs):")
    for i, summary in enumerate(document_summaries, 1):
        logger.info(f"  Doc {i}: {summary.get('summary_profile')}")
        if 'bank_name' in summary:
            logger.info(f"    - bank_name: '{summary.get('bank_name')}'")
            logger.info(f"    - account_holder_name: '{summary.get('account_holder_name')}'")
        if 'employer_name' in summary:
            logger.info(f"    - employer_name: '{summary.get('employer_name')}'")
    logger.info("")
    
    # 5. Assessment Gating - BLOCK if not ready
    logger.debug(f"DEBUG: Profile assessment readiness: {unified_profile.assessment_readiness}")
    logger.debug(f"DEBUG: Blocking reasons: {unified_profile.blocking_reasons}")
    allow_manual_without_docs = False
    if unified_profile.assessment_readiness == AssessmentReadiness.BLOCKED:
        doc_only_keywords = [
            "Payslip",
            "Bank statement",
            "mobile money",
            "statement",
            "Account holder",
            "income",
            "transactions",
            "transaction history",
            "identity",
        ]
        doc_only_block = all(
            any(keyword.lower() in reason.lower() for keyword in doc_only_keywords)
            for reason in unified_profile.blocking_reasons
        )
        no_docs_uploaded = len(document_summaries) == 0

        if doc_only_block and no_docs_uploaded:
            allow_manual_without_docs = True
            logger.warning(
                "WARNING: Proceeding without documents for manual assessment. "
                f"Blocking reasons: {unified_profile.blocking_reasons}"
            )
        else:
            error_msg = "Assessment Blocked: " + "; ".join(unified_profile.blocking_reasons)
            raise HTTPException(
                status_code=400,
                detail={
                    "message": error_msg,
                    "blocking_reasons": unified_profile.blocking_reasons,
                    "missing_documents": unified_profile.document_coverage.missing_required_documents,
                    "incomplete_documents": unified_profile.document_coverage.incomplete_documents,
                    "borrower_id": borrower_id,
                    "suggestion": "Upload a payslip and a bank or mobile money statement, or correct missing data before retrying."
                }
            )
    
    # PARTIAL readiness - proceed with warnings
    if unified_profile.assessment_readiness == AssessmentReadiness.PARTIAL:
        logger.warning(f"WARNING: Proceeding with PARTIAL data. Reasons: {unified_profile.blocking_reasons}")

    # 6. Run Core Assessment with Unified Profile
    # Convert Transaction objects to Dicts for the core agent
    history_dicts = []
    logger.debug(f"DEBUG: all_parsed_transactions count: {len(all_parsed_transactions)}")
    for tx in all_parsed_transactions:
        # Compatibility with new Bank-Grade Transaction Model
        # New model has: date, description, amount, direction, balance, currency, confidence, flags
        
        # Determine amount and direction
        t_amount = tx.amount
        t_direction = tx.direction # "INFLOW" or "OUTFLOW"
        
        # Fallback for older attributes if mixed types
        if getattr(tx, "credit", None) and tx.credit and t_direction == "OUTFLOW": # If fallback was needed
             pass # But standardised parser guarantees amount/direction now
        
        # Determine ID (hash if missing)
        t_id = getattr(tx, "transaction_id", f"TX-{hash(tx.date + tx.description + str(t_amount))}")
        t_date = tx.date # YYYY-MM-DD

        
        # Tuple fallback (legacy safety)
        if isinstance(tx, tuple):
             # (id, date, amount, type, direction)
             t_id = tx[0]
             t_amount = tx[2]
             t_direction = tx[4]
             t_date = tx[1]

        history_dicts.append({
            "transaction_id": t_id,
            "amount": t_amount,
            "type": "OTHER", # new model doesn't have type enum yet
            "timestamp": t_date if isinstance(t_date, str) else t_date.isoformat(),
            "direction": t_direction,
            "description": getattr(tx, "description", ""),
            "confidence_score": getattr(tx, "confidence_score", getattr(tx, "confidence", 0.0)),
            "flags": getattr(tx, "flags", [])
        })

    # Use summary from unified profile for legacy compatibility
    # TODO: Refactor agents to use UnifiedFinancialProfile directly
    summary_for_risk = bank_statement_summary or payslip_summary
    
    assessment = await _run_assessment_core(
        borrower=borrower,
        requested_duration_days=requested_duration_days,
        mobile_money_history=history_dicts if history_dicts else None,
        statement_summary=summary_for_risk,
        assessment_source="MANUAL_UI",
        unified_profile=unified_profile  # NEW: Pass unified profile
    )

    if bank_statement_summary:
        assessment.metrics = assessment.metrics or {}
        period = bank_statement_summary.statement_period
        assessment.metrics.update({
            "summary_profile": "BANK_STATEMENT_SUMMARY",
            "statement_account_holder_name": bank_statement_summary.account_holder_name,
            "statement_bank_name": bank_statement_summary.bank_name,
            "statement_currency": bank_statement_summary.currency,
            "statement_period_start": period.start if period else None,
            "statement_period_end_summary": period.end if period else None,
            "statement_opening_balance": bank_statement_summary.opening_balance,
            "statement_closing_balance": bank_statement_summary.closing_balance,
            "statement_summary_credit_amount": bank_statement_summary.total_money_in or bank_statement_summary.calculated_total_money_in,
            "statement_summary_debit_amount": bank_statement_summary.total_money_out or bank_statement_summary.calculated_total_money_out,
            "statement_summary_credit_count": bank_statement_summary.deposit_count,
            "statement_salary_detected": bank_statement_summary.salary_detected,
            "statement_salary_frequency": bank_statement_summary.salary_frequency,
            "statement_risk_flags": bank_statement_summary.risk_flags
        })

    if payslip_summary:
        assessment.metrics = assessment.metrics or {}
        assessment.metrics.update({
            "summary_profile": "PAYSLIP_SUMMARY",
            "payslip_net_pay": payslip_summary.net_pay,
            "payslip_gross_pay": payslip_summary.gross_pay,
            "payslip_deductions": payslip_summary.deductions,
            "payslip_employer_name": payslip_summary.employer_name,
            "payslip_employee_name": payslip_summary.employee_name,
            "payslip_currency": payslip_summary.currency,
            "payslip_pay_period_start": payslip_summary.pay_period_start,
            "payslip_pay_period_end": payslip_summary.pay_period_end,
            "payslip_pay_date": payslip_summary.pay_date,
            "payslip_pay_frequency": payslip_summary.pay_frequency
        })

    assessment.metrics = assessment.metrics or {}
    assessment.metrics["document_summaries"] = document_summaries
    if allow_manual_without_docs:
        assessment.metrics["readiness"] = False
        assessment.metrics["missing_documents"] = unified_profile.document_coverage.missing_required_documents
        assessment.metrics["readiness_warnings"] = unified_profile.blocking_reasons
    else:
        assessment.metrics["readiness"] = True
        assessment.metrics["missing_documents"] = []

    # 6. Persist and Meter
    logger.debug(f"[MANUAL ASSESSMENT DEBUG] User: {current_user.email}, User Org: {current_user.organization_id}")
    logger.debug(f"[MANUAL ASSESSMENT DEBUG] Borrower: {borrower.id}, Borrower Org: {borrower.organization_id}")
    logger.debug(f"[MANUAL ASSESSMENT DEBUG] Assessment: {assessment.assessment_id}, Assessment Org: {assessment.organization_id}")
    Database.save_assessment(assessment)
    BillingAgent.meter_usage(
        org=org, 
        environment=org.environment, 
        api_key_id="MANUAL_UI",
        endpoint="/assessment/manual",
        assessment_id=assessment.assessment_id
    )
    WebhookService.send_event(org, "assessment.completed", augment_assessment_payload(assessment.model_dump()))

    return {
        "assessment": augment_assessment_payload(assessment.model_dump()),
        "extraction_details": {
            "document_confidence": min([r.confidence for r in extraction_results]) if extraction_results else 0.0,
            "risk_indicators": [w for r in extraction_results for w in r.warnings],
            "transactions": [t.model_dump() for t in all_parsed_transactions],
            "documents": [
                {
                    "filename": getattr(r, "filename", None),
                    "document_type": r.document_type,
                    "summary_profile": (
                        r.bank_statement_summary.summary_profile if r.bank_statement_summary
                        else r.payslip_summary.summary_profile if r.payslip_summary
                        else r.nrc_summary.summary_profile if r.nrc_summary
                        else None
                    ),
                    "summary": (
                        {
                            "closing_balance": r.bank_statement_summary.closing_balance,
                            "statement_period": r.bank_statement_summary.statement_period.model_dump()
                            if r.bank_statement_summary.statement_period else None
                        } if r.bank_statement_summary else
                        {
                            "net_pay": r.payslip_summary.net_pay,
                            "gross_pay": r.payslip_summary.gross_pay,
                            "employer_name": r.payslip_summary.employer_name
                        } if r.payslip_summary else
                        {
                            "full_name": r.nrc_summary.full_name,
                            "id_number": r.nrc_summary.id_number
                        } if r.nrc_summary else None
                    ),
                    "warnings": r.warnings
                }
                for r in extraction_results
            ]
        }
    }

@app.get("/org/decisions", response_model=List[Assessment])
async def get_org_decisions(
    limit: int = 50,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns recent assessments for the authenticated user's organization.
    """
    # DEBUG: Log organization and assessment count for visibility debugging
    db_type = "MOCK" if "Mock" in str(type(Database.get_db())) else "REAL"
    logger.debug(f"[DECISIONS DEBUG] User: {current_user.email}, Org: {current_user.organization_id}, DB: {db_type}")
    
    # Use the helper we just added to DB
    org_id = current_user.organization_id.upper() if current_user.organization_id else "DEFAULT_ORG"
    assessments = Database.get_assessments_by_org(org_id, limit=limit)
    borrower_lookup: Dict[str, Optional[Borrower]] = {}
    if assessments:
        unique_ids = {a.borrower_id for a in assessments if getattr(a, "borrower_id", None)}
        for borrower_id in unique_ids:
            borrower_lookup[borrower_id] = Database.get_borrower(borrower_id)
        for assessment in assessments:
            borrower = borrower_lookup.get(assessment.borrower_id)
            if borrower and getattr(borrower, "name", None):
                assessment.borrower_name = borrower.name

    logger.debug(f"[DECISIONS DEBUG] Fetching for Org: {org_id} (Original: {current_user.organization_id})")
    
    # CRITICAL Trace for Visibility
    if not assessments:
         all_raw = Database.list_assessments()
         logger.debug(f"[DECISIONS DEBUG] Found 0 results. Total in DB: {len(all_raw)}")
         if all_raw:
             # Sample for diagnosis
             unique_orgs = set(a.organization_id for a in all_raw)
             logger.debug(f"[DECISIONS DEBUG] Unique Org IDs in DB: {unique_orgs}")
             logger.debug(f"[DECISIONS DEBUG] Search Target: '{org_id}'")
             # Check for raw matches ignoring case
             close_matches = [a.assessment_id for a in all_raw if a.organization_id.upper() == org_id]
             if close_matches:
                 logger.debug(f"[DECISIONS DEBUG] Found {len(close_matches)} case-insensitive matches! This indicates a casing issue in the DB.")
    logger.debug(f"[DECISIONS DEBUG] Final count for frontend: {len(assessments)}")
    if assessments:
        logger.debug(f"[DECISIONS DEBUG] Sample Assessment ID for frontend: {assessments[0].assessment_id}")
        
    return [enforce_summary_profile_metrics(a) for a in assessments]

@app.get("/org/audit-logs", response_model=List[Dict])
async def get_org_audit_logs(
    limit: int = 50,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns system audit logs for the authenticated user's organization.
    """
    logs = AuditAgent.list_org_logs(current_user.organization_id, limit=limit)
    return logs


@app.get("/org/audit-logs/export")
async def export_org_audit_logs(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Exports organization audit logs as CSV.
    """
    logs = AuditAgent.list_org_logs(current_user.organization_id, limit=1000)
    import csv
    import io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "event_type", "actor", "organization_id", "details"])
    for log in logs:
        writer.writerow([
            log.get("timestamp"),
            log.get("event_type"),
            log.get("actor"),
            log.get("organization_id"),
            json.dumps(log.get("details", {}))
        ])
    response = PlainTextResponse(output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=audit_logs.csv"
    return response


@app.get("/org/notifications", response_model=List[Notification])
async def get_org_notifications(
    limit: int = 50,
    unread_only: bool = False,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns notifications for the current user.
    """
    safe_limit = max(1, min(limit, 200))
    return Database.list_notifications_for_user(
        recipient_user_id=current_user.id,
        recipient_email=current_user.email,
        organization_id=current_user.organization_id,
        unread_only=unread_only,
        limit=safe_limit
    )


@app.get("/org/notifications/unread-count", response_model=Dict[str, int])
async def get_unread_notification_count(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    unread = Database.list_notifications_for_user(
        recipient_user_id=current_user.id,
        recipient_email=current_user.email,
        organization_id=current_user.organization_id,
        unread_only=True,
        limit=1000
    )
    return {"count": len(unread)}


@app.post("/org/notifications/read-all", response_model=Dict[str, int])
async def mark_all_notifications_read(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    updated = Database.mark_all_notifications_read(
        recipient_user_id=current_user.id,
        organization_id=current_user.organization_id
    )
    AuditAgent.log_event(
        "NOTIFICATIONS_READ_ALL",
        current_user.email,
        {"updated": updated, "org": current_user.organization_id}
    )
    return {"updated": updated}


@app.post("/org/notifications/{notification_id}/read", response_model=Dict[str, str])
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    notification = Database.get_notification(notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
    if notification.recipient_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    Database.mark_notification_read(notification_id, current_user.id)
    AuditAgent.log_event(
        "NOTIFICATION_READ",
        current_user.email,
        {"notification_id": notification_id, "org": current_user.organization_id}
    )
    return {"status": "ok"}


def _resolve_user_limit(org: Organization) -> Optional[int]:
    if org.user_limit is not None:
        return org.user_limit
    plan_name = org.plan.value if hasattr(org.plan, 'value') else str(org.plan)
    plan_config = PLAN_CONFIG.get(plan_name.upper(), PLAN_CONFIG["SANDBOX"])
    return plan_config.get("user_limit")


def _serialize_user(user: User) -> Dict[str, Any]:
    data = user.model_dump(mode='json')
    data.pop("password_hash", None)
    return data


def _build_invite_email(
    org: Organization,
    inviter: User,
    invitee_email: str,
    temp_password: str
) -> Dict[str, str]:
    dashboard_url = os.getenv("DASHBOARD_PUBLIC_URL", "http://localhost:5173/login")
    inviter_name = inviter.full_name or inviter.email
    subject = f"You've been invited to {org.name} on Loan Officer AI"
    body_text = (
        f"Hello,\n\n"
        f"{inviter_name} invited you to join {org.name} on Loan Officer AI.\n\n"
        f"Login: {dashboard_url}\n"
        f"Email: {invitee_email}\n"
        f"Temporary password: {temp_password}\n\n"
        f"For security, please change your password after your first login.\n\n"
        f"If you did not expect this invitation, you can ignore this email."
    )
    body_html = f"""
    <p>Hello,</p>
    <p><strong>{inviter_name}</strong> invited you to join <strong>{org.name}</strong> on Loan Officer AI.</p>
    <p>
        <strong>Login:</strong> <a href="{dashboard_url}">{dashboard_url}</a><br/>
        <strong>Email:</strong> {invitee_email}<br/>
        <strong>Temporary password:</strong> {temp_password}
    </p>
    <p>For security, please change your password after your first login.</p>
    <p>If you did not expect this invitation, you can ignore this email.</p>
    """
    return {"subject": subject, "text": body_text, "html": body_html}


@app.get("/org/users", response_model=Dict)
async def list_org_users(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns users for the authenticated user's organization.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Insufficient privileges to view users.")

    org_id = current_user.organization_id
    org = Database.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    users = Database.list_users_by_org(org_id)
    seat_limit = _resolve_user_limit(org)
    seat_used = len(users)
    can_add_users = True if seat_limit is None else seat_used < seat_limit

    return {
        "users": [_serialize_user(u) for u in users],
        "seat_limit": seat_limit,
        "seat_used": seat_used,
        "can_add_users": can_add_users,
        "plan": org.plan.value if hasattr(org.plan, 'value') else str(org.plan)
    }


@app.get("/org/referral-targets", response_model=Dict)
async def list_org_referral_targets(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns minimal organization team-member data for referral assignment.
    """
    org_id = (current_user.organization_id or "").strip()
    org = Database.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Use a full scan + in-memory filter for resilience. Some deployments have
    # intermittent query inconsistencies on org-scoped user lookups.
    normalized_org = org_id.upper()
    users = [
        u for u in Database.list_all_users()
        if (u.organization_id or "").strip().upper() == normalized_org
    ]
    targets = []
    for member in users:
        role_value = member.role.value if hasattr(member.role, "value") else str(member.role)
        role_value = role_value.upper()

        targets.append({
            "id": member.id,
            "full_name": member.full_name,
            "email": member.email,
            "role": role_value,
            "is_self": member.id == current_user.id
        })

    if not targets:
        # Safety fallback: include authenticated user so referral flow remains operable.
        self_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
        targets.append({
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
            "role": str(self_role).upper(),
            "is_self": True
        })

    targets.sort(key=lambda x: (x["full_name"] or x["email"] or "").lower())
    return {"targets": targets}


@app.post("/org/users", response_model=Dict)
async def create_org_user(
    user_data: Dict = Body(...),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Creates a new dashboard user within the current organization.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Insufficient privileges to create users.")

    target_org_id = current_user.organization_id
    if current_user.role == "SUPER_ADMIN" and user_data.get("organization_id"):
        target_org_id = user_data.get("organization_id")

    org = Database.get_organization(target_org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Enforce seat limits for non-super admins
    if current_user.role != "SUPER_ADMIN":
        seat_limit = _resolve_user_limit(org)
        if seat_limit is not None:
            seat_used = len(Database.list_users_by_org(target_org_id))
            if seat_used >= seat_limit:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "USER_LIMIT_REACHED",
                        "message": "User limit reached for this organization.",
                        "limit": seat_limit
                    }
                )

    email = (user_data.get("email") or "").strip().lower()
    full_name = (user_data.get("full_name") or "").strip()
    requested_role = (user_data.get("role") or "OFFICER").strip().upper()

    if not email or not full_name:
        raise HTTPException(status_code=400, detail="Email and full_name are required.")

    if Database.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already registered")

    allowed_roles = {"OFFICER", "AUDITOR", "VIEWER", "ORG_ADMIN", "DEVELOPER"}
    if requested_role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Invalid role.")

    if current_user.role == "ORG_ADMIN" and requested_role not in {"OFFICER", "AUDITOR", "VIEWER"}:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="ORG_ADMIN can only create OFFICER, AUDITOR, or VIEWER roles.")

    if current_user.role == "DEVELOPER" and requested_role not in {"OFFICER", "AUDITOR", "VIEWER", "ORG_ADMIN"}:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="DEVELOPER role cannot assign that role.")

    generated_password = secrets.token_urlsafe(10)
    pwd_hash = AuthAgent.get_password_hash(generated_password)

    # Create in Firebase Auth
    firebase_uid = AuthAgent.create_firebase_user(
        email=email,
        password=generated_password,
        display_name=full_name
    )

    new_user = User(
        id=firebase_uid,
        organization_id=target_org_id,
        email=email,
        password_hash=pwd_hash,
        full_name=full_name,
        role=UserRole(requested_role)
    )

    Database.save_user(new_user)
    AuditAgent.log_event(
        "USER_CREATED_BY_ORG_ADMIN",
        current_user.email,
        {"new_user_id": new_user.id, "org": target_org_id, "role": requested_role}
    )

    invite_payload = _build_invite_email(org, current_user, email, generated_password)
    invite_status = EmailService.send_email(
        to_email=email,
        subject=invite_payload["subject"],
        body_text=invite_payload["text"],
        body_html=invite_payload["html"]
    )
    AuditAgent.log_event(
        "USER_INVITE_SENT",
        current_user.email,
        {"email": email, "org": target_org_id, "status": invite_status.get("status"), "environment": invite_status.get("environment")}
    )

    invite_sent = invite_status.get("status") == "SENT" and invite_status.get("environment") == "production"
    response = {
        "user": _serialize_user(new_user),
        "invite_sent": invite_sent,
        "invite": invite_status
    }
    if not invite_sent:
        response["initial_credentials"] = {
            "email": email,
            "password": generated_password
        }
    return response


@app.post("/org/users/{user_id}/resend-invite", response_model=Dict)
async def resend_org_user_invite(
    user_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Resends an invite by rotating the user's password and emailing a fresh temporary password.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Insufficient privileges to resend invites.")

    target_user = Database.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role != "SUPER_ADMIN" and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Cross-organization access denied.")

    org = Database.get_organization(target_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    generated_password = secrets.token_urlsafe(10)
    AuthAgent.update_firebase_user_password(target_user.id, generated_password)
    target_user.password_hash = AuthAgent.get_password_hash(generated_password)
    Database.save_user(target_user)

    invite_payload = _build_invite_email(org, current_user, target_user.email, generated_password)
    invite_status = EmailService.send_email(
        to_email=target_user.email,
        subject=invite_payload["subject"],
        body_text=invite_payload["text"],
        body_html=invite_payload["html"]
    )
    AuditAgent.log_event(
        "USER_INVITE_RESENT",
        current_user.email,
        {"email": target_user.email, "org": target_user.organization_id, "status": invite_status.get("status"), "environment": invite_status.get("environment")}
    )

    invite_sent = invite_status.get("status") == "SENT" and invite_status.get("environment") == "production"
    response = {
        "user": _serialize_user(target_user),
        "invite_sent": invite_sent,
        "invite": invite_status
    }
    if not invite_sent:
        response["initial_credentials"] = {
            "email": target_user.email,
            "password": generated_password
        }
    return response


@app.get("/org/settings")
async def get_org_settings(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns the organization's settings (webhooks, flags).
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return {
        "webhook_url": org.webhook_url,
        "webhook_secret": org.webhook_secret,
        "feature_flags": org.feature_flags or {}
    }


@app.patch("/org/settings")
async def update_org_settings(
    settings: Dict = Body(...),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Updates the organization's settings (webhooks, flags).
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Update allowed fields
    if "webhook_url" in settings:
        org.webhook_url = settings["webhook_url"]
        
    if "feature_flags" in settings:
        # Shallow merge or replacement? Let's do replacement for simplicity V1
        org.feature_flags = settings["feature_flags"]
        
    # Generate a secret if they request one (simplified logic)
    if settings.get("regenerate_secret"):
         import secrets
         org.webhook_secret = "whsec_" + secrets.token_hex(24)

    Database.save_organization(org)
    
    AuditAgent.log_event("ORG_SETTINGS_UPDATED", current_user.email, {"org": org.id, "changes": list(settings.keys())})
    
    return {
        "webhook_url": org.webhook_url,
        "webhook_secret": org.webhook_secret,
        "feature_flags": org.feature_flags
    }

@app.get("/billing/usage", response_model=Dict)
async def get_billing_usage(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Returns billing usage summary for the authenticated user's organization.
    """
    from agents.billing_agent import BillingAgent
    
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    return BillingAgent.get_full_usage_summary(org)

@app.get("/billing/plans", response_model=Dict)
async def list_billing_plans(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Returns available billing plans and their configuration (prices, limits).
    """
    from pricing_config import PLAN_CONFIG
    return PLAN_CONFIG


@app.post("/billing/upgrade", tags=["Billing"])
async def upgrade_billing_plan(
    plan: str = Body(..., embed=True),
    gateway: str = Body("LIPILA", embed=True),
    phone_number: Optional[str] = Body(None, embed=True),
    replace_active: bool = Body(False, embed=True),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Initiate an upgrade for the organization's billing plan.
    Triggers MoMo STK Push or generates an Invoice.
    """
    if current_user.role != "ORG_ADMIN":
        raise HTTPException(status_code=403, detail="Only Organization Admins can initiate upgrades.")
    
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    from pricing_config import PLAN_CONFIG
    if plan.upper() not in PLAN_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan}")

    from agents.payment_agent import PaymentAgent
    try:
        payment_init = PaymentAgent.initiate_payment(
            org=org,
            plan_name=plan,
            gateway=gateway,
            extra_data={"phone_number": phone_number, "replace_active": replace_active}
        )
        return payment_init
    except PaymentAgent.DuplicateActivePaymentError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "ACTIVE_PAYMENT_EXISTS",
                "message": str(e),
                "payment": PaymentAgent._serialize_payment(e.payment),
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentAgent.GatewayError as e:
        raise HTTPException(status_code=502, detail=f"Payment Gateway Error: {str(e)}")
    except Exception as e:
        import traceback
        logger.info(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to initiate payment")

@app.post("/billing/webhook/lipila", tags=["Billing"])
async def billing_webhook_lipila(payload: Dict = Body(...)):
    """
    Async webhook from Lipila for Mobile Money transactions.
    """
    from agents.payment_agent import PaymentAgent
    success = PaymentAgent.handle_webhook("LIPILA", payload)
    if success:
        return {"status": "ACKNOWLEDGED"}
    else:
        # We still return 200 to acknowledge receipt even if logic failed
        # to prevent gateway from retrying indefinitely on bad data
        return {"status": "ERROR_HANDLED"}

@app.post("/billing/admin/confirm-payment", tags=["Billing"])
async def confirm_manual_payment(
    payment_id: str = Body(..., embed=True),
    current_user: User = Depends(get_super_admin)
):
    """
    Global Admin capability to manually confirm Bank Transfers/Invoices.
    """
    from agents.payment_agent import PaymentAgent
    payment = Database.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
    
    # Simulate a successful webhook payload
    payload = {
        "transaction_id": payment.transaction_id or payment.reference_code,
        "status": "Successful",
        "metadata": {"payment_id": payment_id}
    }
    
    success = PaymentAgent.handle_webhook(payment.gateway, payload)
    if success:
        AuditAgent.log_event("MANUAL_PAYMENT_CONFIRMED", current_user.email, {"payment_id": payment_id})
        return {"status": "SUCCESS", "message": f"Payment {payment_id} confirmed and plan activated."}
    
    raise HTTPException(status_code=500, detail="Failed to confirm payment")

@app.get("/billing/payments", tags=["Billing"])
async def list_org_payments(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    List all payment attempts and invoices for the organization.
    """
    from agents.payment_agent import PaymentAgent

    ordered = PaymentAgent.list_payments_for_org(current_user.organization_id)
    return [PaymentAgent._serialize_payment(payment) for payment in ordered]

@app.get("/billing/payment/{payment_id}/status", tags=["Billing"])
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns the latest payment status and refreshes Lipila state when applicable.
    """
    payment = Database.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized to access this payment")

    from agents.payment_agent import PaymentAgent
    try:
        return PaymentAgent.refresh_payment_status(payment)
    except PaymentAgent.GatewayError as exc:
        raise HTTPException(status_code=502, detail=f"Payment Gateway Error: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to refresh payment status: {str(exc)}")

@app.post("/billing/payment/{payment_id}/cancel", tags=["Billing"])
async def cancel_payment_request(
    payment_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Cancels an active payment request and invalidates any queued retry state.
    """
    payment = Database.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized to access this payment")

    from agents.payment_agent import PaymentAgent
    try:
        return PaymentAgent.cancel_payment(payment, requested_by=current_user.email or current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to cancel payment request: {str(exc)}")

@app.get("/billing/invoice/{payment_id}", tags=["Billing"])
async def download_invoice(
    payment_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Downloads the PDF invoice for a specific payment.
    Ensures the user belongs to the payment's organization.
    """
    payment = Database.get_payment(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    if payment.org_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized to access this invoice")
        
    if not payment.invoice_id:
        import secrets
        payment.invoice_id = f"INV-{datetime.now().year}-{secrets.token_hex(3).upper()}"
        payment.invoice_pdf_path = None # Force regeneration
        Database.save_payment(payment)

    if not payment.invoice_pdf_path or not os.path.exists(payment.invoice_pdf_path):
        # Trigger regeneration if missing but record exists
        from agents.invoice_agent import InvoiceAgent
        org = Database.get_organization(payment.org_id)
        if org:
            try:
                payment.invoice_pdf_path = InvoiceAgent.generate_invoice_pdf(org, payment)
                Database.save_payment(payment)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to generate invoice PDF: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="Invoice PDF not found and organization missing")

    return FileResponse(
        path=payment.invoice_pdf_path,
        filename=os.path.basename(payment.invoice_pdf_path),
        media_type='application/pdf'
    )

# --- API KEY MANAGEMENT ---
@app.get("/borrowers", response_model=List[Borrower])
async def list_borrowers(user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Returns borrowers for the officer's organization.
    """
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    return Database.list_borrowers(organization_id=user.organization_id)

@app.post("/borrower/data/upload", response_model=Dict[str, str])
async def upload_alternative_data(data: AlternativeData, user: AuthUser = Depends(AuthAgent.get_api_key)):
    if user.role not in ["OFFICER", "CLIENT"]:
        raise HTTPException(status_code=403, detail="Unauthorized client")
    
    # Verify borrower exists and belongs to the same org
    borrower = Database.get_borrower(data.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    
    if borrower.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to borrower data")
        
    Database.save_alternative_data(data)
    AuditAgent.log_event("DATA_UPLOAD", user.role, {"borrower_id": data.borrower_id, "org": user.organization_id})
    return {"status": "UPLOAD_SUCCESS", "borrower_id": data.borrower_id}

@app.post("/assessment/retrain", response_model=Dict[str, str])
async def assessment_retrain(user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Triggers a retraining cycle for the ML Risk Engine. Requires Officer permissions.
    """
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    
    try:
        from ml_models.training_pipeline import train_bootstrap_model
        train_bootstrap_model()
        from agents.ml_risk_agent import MLRiskAgent
        MLRiskAgent._model = None # Force reload
        AuditAgent.log_event("MODEL_RETRAIN", user.role, {"status": "SUCCESS", "org": user.organization_id})
        return {"status": "RETRAIN_SUCCESS", "message": "Model updated with latest data"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retraining failed: {str(e)}")


def _resolve_loan_context(loan: Loan) -> Tuple[Optional[Assessment], Optional[Borrower]]:
    assessment = Database.get_assessment(loan.assessment_id)
    borrower = Database.get_borrower(loan.borrower_id)
    return assessment, borrower


def _ensure_loan_access(loan: Loan, user: User):
    if loan.organization_id != user.organization_id and user.organization_id != "PLATFORM_OWNER":
        raise HTTPException(status_code=403, detail="Unauthorized")


def _loan_tracker_payload(loan: Loan, assessment: Optional[Assessment], borrower: Optional[Borrower]) -> Dict[str, Any]:
    return {
        "loan": loan.model_dump(mode="json"),
        "assessment": (
            {
                "assessment_id": assessment.assessment_id,
                "borrower_id": assessment.borrower_id,
                "borrower_name": assessment.borrower_name,
                "decision": getattr(assessment.decision, "value", assessment.decision),
                "risk_score": assessment.risk_score,
                "risk_level": getattr(assessment.risk_level, "value", assessment.risk_level),
                "recommended_amount": assessment.recommended_amount,
                "recommended_duration_days": assessment.recommended_duration_days,
            }
            if assessment
            else None
        ),
        "borrower": (
            {
                "id": borrower.id,
                "name": borrower.name,
                "phone": borrower.phone,
                "employment_type": getattr(borrower.employment_type, "value", borrower.employment_type),
                "monthly_income": borrower.monthly_income,
                "monthly_expenses": borrower.monthly_expenses,
                "existing_debt": borrower.existing_debt,
                "loan_amount_requested": borrower.loan_amount_requested,
                "loan_purpose": borrower.loan_purpose,
            }
            if borrower
            else None
        ),
        "tracking_profile": loan.tracking_profile.model_dump(mode="json") if loan.tracking_profile else None,
        "tracking_summary": LoanTrackingService.summarize(loan, borrower=borrower, assessment=assessment),
        "schedule": [item.model_dump(mode="json") for item in loan.repayment_schedule],
        "events": [
            item.model_dump(mode="json")
            for item in sorted(loan.collection_history, key=lambda event: event.occurred_at, reverse=True)
        ],
        "differentiators": LoanTrackingService.differentiators(loan),
    }


def _ensure_borrower_dashboard_access(borrower: Borrower, user: User):
    if user.organization_id != "PLATFORM_OWNER" and borrower.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")


def _ensure_borrower_edit_access(user: User):
    allowed_roles = {"OFFICER", "ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"}
    role_value = str(getattr(user.role, "value", user.role)).upper()
    if role_value not in allowed_roles:
        raise HTTPException(status_code=403, detail="Officer or admin access required")


def _resolve_org_display_name(organization_id: str) -> str:
    organization = Database.get_organization(organization_id)
    if organization and getattr(organization, "name", None):
        return organization.name
    return "MiFi Pro"


def _resolve_borrower_context(
    borrower_id: str,
    user: User,
) -> Tuple[Borrower, List[Assessment], List[Loan], Optional[BorrowerContactPreference]]:
    organization_id = None if user.organization_id == "PLATFORM_OWNER" else user.organization_id
    borrower = BorrowerProfileService.resolve_borrower(borrower_id, organization_id=organization_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")
    _ensure_borrower_dashboard_access(borrower, user)
    assessments = Database.list_assessments_by_borrower(
        borrower_id=borrower_id,
        organization_id=borrower.organization_id,
    )
    loans = Database.list_loans_by_borrower(
        borrower_id=borrower_id,
        organization_id=borrower.organization_id,
    )
    preference = Database.get_borrower_contact_preference(
        borrower_id=borrower_id,
        organization_id=borrower.organization_id,
    )
    return borrower, assessments, loans, preference

@app.post("/loan/disburse", response_model=Loan)
async def loan_disburse(assessment_id: str = Body(..., embed=True), user: User = Depends(get_dashboard_user)):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")
    
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    if assessment.organization_id != user.organization_id and user.organization_id != "PLATFORM_OWNER":
        raise HTTPException(status_code=403, detail="Unauthorized access to assessment")
    
    # Check if a loan already exists for this assessment
    existing_loans = Database.list_loans(organization_id=assessment.organization_id)
    for l in existing_loans:
        if l.assessment_id == assessment_id:
             return l # Idempotent

    loan = Loan(
        loan_id=f"LOAN-{uuid.uuid4().hex[:8].upper()}",
        assessment_id=assessment_id,
        borrower_id=assessment.borrower_id,
        organization_id=assessment.organization_id,
        amount=assessment.recommended_amount,
        interest_rate=assessment.recommended_interest_rate,
        term_days=assessment.recommended_duration_days or assessment.requested_duration_days,
        status=LoanStatus.PENDING_DISBURSEMENT
    )
    
    Database.save_loan(loan)
    AuditAgent.log_event("LOAN_CREATED_PENDING", user.role, {"loan_id": loan.loan_id, "amount": loan.amount, "org": assessment.organization_id})
    return loan

@app.post("/loan/confirm-disbursement")
async def confirm_disbursement(
    loan_id: str = Body(..., embed=True),
    amount: float = Body(..., embed=True),
    method: str = Body(..., embed=True),
    reference: Optional[str] = Body(None, embed=True),
    tracking: Optional[LoanTrackingSetupRequest] = Body(None, embed=True),
    user: User = Depends(get_dashboard_user)
):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")
    
    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    _ensure_loan_access(loan, user)
    
    if loan.status != LoanStatus.PENDING_DISBURSEMENT:
        raise HTTPException(status_code=400, detail=f"Loan is in {loan.status} state, cannot disburse.")

    loan.status = LoanStatus.DISBURSED
    loan.disbursed_at = datetime.now(timezone.utc)
    loan.amount = amount # Allow slight adjustment if needed at point of sale
    loan.disbursement_method = method
    loan.disbursement_reference = reference
    loan.disbursed_by = user.email
    assessment, borrower = _resolve_loan_context(loan)
    LoanTrackingService.ensure_tracking(loan, assessment, borrower, tracking)
    
    Database.save_loan(loan)
    AuditAgent.log_event("LOAN_DISBURSED_MANUAL", user.role, {
        "loan_id": loan.loan_id, 
        "amount": amount, 
        "method": method,
        "ref": reference,
        "tracking_lane": getattr(getattr(getattr(loan, "tracking_profile", None), "tracking_lane", None), "value", None)
    })
    
    return {"status": "SUCCESS", "loan_id": loan_id}

@app.post("/loan/status")
async def update_loan_status(
    loan_id: str = Body(... , embed=True),
    status: LoanStatus = Body(..., embed=True),
    user: User = Depends(get_dashboard_user)
):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")
    
    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    if loan.organization_id != user.organization_id and user.organization_id != "PLATFORM_OWNER":
        raise HTTPException(status_code=403, detail="Unauthorized access to loan")
    
    loan.status = status
    if status in [LoanStatus.PAID, LoanStatus.DEFAULTED]:
        loan.closed_at = datetime.now()
        # Trigger Self-Healing loop
        SelfHealingAgent.register_outcome(loan.loan_id, status)
        
    Database.save_loan(loan)
    AuditAgent.log_event("LOAN_STATUS_CHANGE", user.role, {"loan_id": loan_id, "new_status": status, "org": user.organization_id})
    return {"status": "SUCCESS", "loan_id": loan_id, "new_status": status}

@app.get("/loans", response_model=List[Loan])
async def list_loans(user: User = Depends(get_dashboard_user)):
    if user.role not in ["OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    org_id = user.organization_id if user.organization_id != "PLATFORM_OWNER" else None
    return Database.list_loans(organization_id=org_id)

@app.get("/loans/assessment/{assessment_id}", response_model=Optional[Loan])
async def get_loan_by_assessment(assessment_id: str, user: User = Depends(get_dashboard_user)):
    # Standard security check - platform admins can see everything
    if user.role not in ["OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        return None
        
    # Security: Ensure user has access to this assessment's org
    if user.organization_id != "PLATFORM_OWNER" and assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # 1. Look for existing loan - check BOTH the specific org and ALL loans as fallback
    # (Sometimes org IDs can be inconsistent in legacy data)
    loans = Database.list_loans(organization_id=assessment.organization_id)
    for l in loans:
        if l.assessment_id == assessment_id:
            return l
            
    # Fallback: Search all loans (in case of org mismatch)
    all_loans = Database.list_loans()
    for l in all_loans:
        if l.assessment_id == assessment_id:
            return l
            
    # 2. Self-healing: If assessment is approved but no loan exists, create one
    is_approved = False
    
    # Check assessment decision
    main_decision = str(assessment.decision).split('.')[-1].upper()
    if main_decision == "APPROVE":
        is_approved = True
        
    # Check metadata if exists (more authoritative)
    if assessment.final_decision_metadata:
        meta = assessment.final_decision_metadata
        def get_val(obj, key):
            if isinstance(obj, dict): return obj.get(key)
            return getattr(obj, key, None)
            
        m_decision = get_val(meta, "officer_decision") or get_val(meta, "decision")
        if m_decision:
            m_decision_str = str(m_decision).split('.')[-1].upper()
            is_approved = (m_decision_str == "APPROVE")

    if is_approved:
        try:
            from models.loan import Loan, LoanStatus
            import uuid
            
            # Extract values safely
            meta = assessment.final_decision_metadata or {}
            def get_val(obj, key):
                if isinstance(obj, dict): return obj.get(key)
                return getattr(obj, key, None)
                
            amount = get_val(meta, "final_amount") or assessment.recommended_amount
            rate = get_val(meta, "final_interest_rate") or assessment.recommended_interest_rate
            
            new_loan = Loan(
                loan_id=f"LOAN-{uuid.uuid4().hex[:8].upper()}",
                assessment_id=assessment_id,
                borrower_id=assessment.borrower_id,
                organization_id=assessment.organization_id,
                amount=float(amount) if amount else 0.0,
                interest_rate=float(rate) if rate else 0.0,
                term_days=assessment.recommended_duration_days or assessment.requested_duration_days,
                status=LoanStatus.PENDING_DISBURSEMENT
            )
            Database.save_loan(new_loan)
            # Re-read to confirm persistence
            confirmed = Database.get_loan(new_loan.loan_id)
            if not confirmed:
                 logger.error(f"CRITICAL: Database failed to persist new loan {new_loan.loan_id}")
                 
            return new_loan
        except Exception as e:
                logger.error(f"DEBUG: Self-healing creation failed for {assessment_id}: {e}")
                
    return None


@app.get("/loans/tracker", tags=["Loan Tracking"])
async def get_loan_tracker_workspace(user: User = Depends(get_dashboard_user)):
    if user.role not in ["OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Access denied")

    org_id = user.organization_id if user.organization_id != "PLATFORM_OWNER" else None
    loans = Database.list_loans(organization_id=org_id) if org_id else Database.list_loans()
    borrowers = Database.list_borrowers(organization_id=org_id) if org_id else Database.list_borrowers()
    assessments = Database.list_assessments(organization_id=org_id) if org_id else Database.list_assessments()

    borrower_lookup = {borrower.id: borrower for borrower in borrowers if borrower.id}
    assessment_lookup = {
        assessment.assessment_id: assessment
        for assessment in assessments
        if getattr(assessment, "assessment_id", None)
    }
    return LoanTrackingService.portfolio_snapshot(
        loans,
        borrower_lookup=borrower_lookup,
        assessment_lookup=assessment_lookup,
    )


@app.get("/loans/{loan_id}/tracker", tags=["Loan Tracking"])
async def get_loan_tracker_detail(loan_id: str, user: User = Depends(get_dashboard_user)):
    if user.role not in ["OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Access denied")

    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    _ensure_loan_access(loan, user)
    assessment, borrower = _resolve_loan_context(loan)
    return _loan_tracker_payload(loan, assessment, borrower)


@app.post("/loans/{loan_id}/tracking/setup", tags=["Loan Tracking"])
async def setup_loan_tracking(
    loan_id: str,
    payload: LoanTrackingSetupRequest,
    user: User = Depends(get_dashboard_user)
):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")

    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    _ensure_loan_access(loan, user)

    assessment, borrower = _resolve_loan_context(loan)
    LoanTrackingService.ensure_tracking(loan, assessment, borrower, payload)
    Database.save_loan(loan)
    AuditAgent.log_event(
        "LOAN_TRACKING_CONFIGURED",
        user.email,
        {
            "loan_id": loan.loan_id,
            "tracking_lane": getattr(getattr(loan.tracking_profile, "tracking_lane", None), "value", None),
            "org": loan.organization_id,
        },
    )
    return _loan_tracker_payload(loan, assessment, borrower)


@app.post("/loans/{loan_id}/tracking/events", tags=["Loan Tracking"])
async def record_loan_tracking_event(
    loan_id: str,
    payload: LoanTrackingEventCreate,
    user: User = Depends(get_dashboard_user)
):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")

    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    _ensure_loan_access(loan, user)

    assessment, borrower = _resolve_loan_context(loan)
    if not loan.tracking_profile:
        raise HTTPException(status_code=400, detail="Configure loan tracking before recording events.")

    previous_status = loan.status
    event = LoanTrackingService.record_event(loan, payload, user.email)
    Database.save_loan(loan)
    if previous_status != LoanStatus.PAID and loan.status == LoanStatus.PAID:
        SelfHealingAgent.register_outcome(loan.loan_id, loan.status)
    AuditAgent.log_event(
        "LOAN_TRACKING_EVENT_RECORDED",
        user.email,
        {
            "loan_id": loan.loan_id,
            "event_id": event.event_id,
            "event_type": getattr(event.event_type, "value", event.event_type),
            "amount": event.amount,
            "org": loan.organization_id,
        },
    )
    return _loan_tracker_payload(loan, assessment, borrower)


@app.get("/org/borrowers", response_model=List[BorrowerDirectoryItem], tags=["Borrower 360"])
async def list_borrower_directory(user: User = Depends(get_dashboard_user)):
    if str(getattr(user.role, "value", user.role)).upper() not in {"OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER", "VIEWER"}:
        raise HTTPException(status_code=403, detail="Access denied")

    organization_id = None if user.organization_id == "PLATFORM_OWNER" else user.organization_id
    return BorrowerProfileService.list_directory(organization_id=organization_id)


@app.get("/org/borrowers/{borrower_id}/profile", response_model=BorrowerProfileOverview, tags=["Borrower 360"])
async def get_borrower_profile(borrower_id: str, user: User = Depends(get_dashboard_user)):
    if str(getattr(user.role, "value", user.role)).upper() not in {"OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER", "VIEWER"}:
        raise HTTPException(status_code=403, detail="Access denied")
    borrower, _, _, _ = _resolve_borrower_context(borrower_id, user)
    return BorrowerProfileService.build_profile(borrower=borrower, organization_id=borrower.organization_id)


@app.get("/org/borrowers/{borrower_id}/communications", response_model=List[BorrowerCommunicationRecord], tags=["Borrower 360"])
async def list_borrower_communications(
    borrower_id: str,
    loan_id: Optional[str] = None,
    user: User = Depends(get_dashboard_user),
):
    if str(getattr(user.role, "value", user.role)).upper() not in {"OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER", "VIEWER"}:
        raise HTTPException(status_code=403, detail="Access denied")
    borrower, _, _, _ = _resolve_borrower_context(borrower_id, user)
    profile = BorrowerProfileService.build_profile(borrower=borrower, organization_id=borrower.organization_id)
    if loan_id:
        return [item for item in profile.communications if item.loan_id == loan_id]
    return profile.communications


@app.get("/org/borrowers/{borrower_id}/reminder-schedule", response_model=List[ReminderScheduleItem], tags=["Borrower 360"])
async def get_borrower_reminder_schedule(
    borrower_id: str,
    user: User = Depends(get_dashboard_user),
):
    if str(getattr(user.role, "value", user.role)).upper() not in {"OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER", "VIEWER"}:
        raise HTTPException(status_code=403, detail="Access denied")

    borrower, assessments, loans, preference = _resolve_borrower_context(borrower_id, user)
    return ReminderService.build_schedule(
        borrower=borrower,
        organization_id=borrower.organization_id,
        loans=loans,
        assessments=assessments,
        preference=preference,
    )


@app.post("/org/borrowers/{borrower_id}/communications/preview", response_model=ReminderPreviewResponse, tags=["Borrower 360"])
async def preview_borrower_reminder(
    borrower_id: str,
    payload: ReminderPreviewRequest,
    user: User = Depends(get_dashboard_user),
):
    borrower, assessments, loans, preference = _resolve_borrower_context(borrower_id, user)
    org_name = _resolve_org_display_name(borrower.organization_id)
    return ReminderService.preview_message(
        borrower=borrower,
        institution_name=org_name,
        officer_name=user.full_name or user.email or "Loan Officer",
        contact_number=user.email or borrower.phone,
        request=payload,
        loans=loans,
        assessments=assessments,
        preference=preference,
    )


@app.post("/org/borrowers/{borrower_id}/communications/send", response_model=BorrowerCommunicationRecord, tags=["Borrower 360"])
async def send_borrower_reminder(
    borrower_id: str,
    payload: ReminderSendRequest,
    user: User = Depends(get_dashboard_user),
):
    _ensure_borrower_edit_access(user)
    borrower, assessments, loans, preference = _resolve_borrower_context(borrower_id, user)
    org_name = _resolve_org_display_name(borrower.organization_id)
    record = ReminderService.send_reminder(
        communication_id=f"COM-{uuid.uuid4().hex[:10].upper()}",
        borrower=borrower,
        institution_name=org_name,
        officer_name=user.full_name or user.email or "Loan Officer",
        contact_number=user.email or borrower.phone,
        request=payload,
        loans=loans,
        assessments=assessments,
        preference=preference,
        organization_id=borrower.organization_id,
        triggered_by={
            "user_id": user.id,
            "name": user.full_name,
            "email": user.email,
        },
    )
    Database.save_borrower_communication(record)

    if record.channel.value == "SMS" and record.assessment_id:
        legacy_sms_log = SMSLog(
            id=f"SMS-{uuid.uuid4().hex[:8].upper()}",
            assessment_id=record.assessment_id,
            borrower_id=borrower_id,
            phone_number=record.recipient_number,
            message=record.message_body,
            sent_by=user.id,
            provider=record.provider or "TWILIO",
            provider_id=record.provider_message_id,
            status=record.delivery_status.value,
            environment=os.getenv("MESSAGING_PROVIDER_MODE", "mock"),
        )
        Database.save_sms_log(legacy_sms_log)

    AuditAgent.log_event(
        "BORROWER_REMINDER_SENT",
        user.email,
        {
            "borrower_id": borrower_id,
            "loan_id": record.loan_id,
            "assessment_id": record.assessment_id,
            "channel": record.channel.value,
            "reminder_type": record.reminder_type.value,
            "status": record.delivery_status.value,
            "org": borrower.organization_id,
        },
    )
    return record


@app.put("/org/borrowers/{borrower_id}/contact-preferences", response_model=BorrowerContactPreference, tags=["Borrower 360"])
async def update_borrower_contact_preferences(
    borrower_id: str,
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(get_dashboard_user),
):
    _ensure_borrower_edit_access(user)
    borrower, _, _, _ = _resolve_borrower_context(borrower_id, user)

    preference = BorrowerContactPreference(
        borrower_id=borrower_id,
        organization_id=borrower.organization_id,
        preferred_channel=payload.get("preferred_channel"),
        preferred_number=(payload.get("preferred_number") or borrower.phone or "").strip() or None,
        best_contact_time=(payload.get("best_contact_time") or "").strip() or None,
        communication_language=payload.get("communication_language"),
        consent_opt_in=payload.get("consent_opt_in"),
        updated_by=user.email,
    )
    Database.save_borrower_contact_preference(preference)
    AuditAgent.log_event(
        "BORROWER_CONTACT_PREFERENCES_UPDATED",
        user.email,
        {"borrower_id": borrower_id, "org": borrower.organization_id},
    )
    return preference


@app.get("/org/borrowers/{borrower_id}/notes", response_model=List[BorrowerNote], tags=["Borrower 360"])
async def list_borrower_notes(
    borrower_id: str,
    user: User = Depends(get_dashboard_user),
):
    if str(getattr(user.role, "value", user.role)).upper() not in {"OFFICER", "ORG_ADMIN", "AUDITOR", "SUPER_ADMIN", "DEVELOPER", "VIEWER"}:
        raise HTTPException(status_code=403, detail="Access denied")
    borrower, _, _, _ = _resolve_borrower_context(borrower_id, user)
    return Database.list_borrower_notes(borrower_id=borrower_id, organization_id=borrower.organization_id)


@app.post("/org/borrowers/{borrower_id}/notes", response_model=BorrowerNote, tags=["Borrower 360"])
async def create_borrower_note(
    borrower_id: str,
    payload: BorrowerNoteCreate,
    user: User = Depends(get_dashboard_user),
):
    _ensure_borrower_edit_access(user)
    borrower, _, _, _ = _resolve_borrower_context(borrower_id, user)

    note = BorrowerNote(
        note_id=f"NOTE-{uuid.uuid4().hex[:10].upper()}",
        borrower_id=borrower_id,
        organization_id=borrower.organization_id,
        note_type=payload.note_type,
        text=payload.text.strip(),
        related_loan_id=payload.related_loan_id,
        related_assessment_id=payload.related_assessment_id,
        created_by_user_id=user.id,
        created_by_name=user.full_name,
        created_by_email=user.email,
    )
    Database.save_borrower_note(note)
    AuditAgent.log_event(
        "BORROWER_NOTE_ADDED",
        user.email,
        {
            "borrower_id": borrower_id,
            "note_id": note.note_id,
            "note_type": note.note_type.value,
            "org": borrower.organization_id,
        },
    )
    return note

@app.get("/platform/admin")
async def get_platform_admin():
    """
    Serves the platform admin dashboard. Data is protected via /platform/stats.
    """
    return FileResponse(os.path.join(static_path, "super_dashboard.html"))

@app.get("/platform/stats")
async def get_platform_stats(user: AuthUser = Depends(AuthAgent.get_api_key)):
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Platform Admin access required")
    
    # Aggregated stats across all tenants
    all_loans = Database.list_loans()
    all_assessments = Database.list_assessments()
    
    return {
        "total_mfis": len(set(l.organization_id for l in all_loans) | set(a.organization_id for a in all_assessments)),
        "total_disbursed_volume": sum(l.amount for l in all_loans),
    }

# ============================================================================
# HEALTH CHECK
# ============================================================================
@app.get("/api/health", tags=["System"])
async def health_check():
    """
    Checks connectivity and system status.
    """
    return {
        "message": "Loan Officer AI Agent V1→V4 is online.",
        "version": "2.0.0",
        "ml_enabled": True,
        "behavioral_v2_enabled": True,
        "llm_enabled": False
    }

# ============================================================================
# BORROWER INTAKE (Step 1)
# ============================================================================
@app.post("/intake/start", tags=["Borrower Management"])
async def start_intake(
    intake_data: Dict = Body(..., example={
        "name": "Jane Mwangi",
        "phone": "+254700123456",
        "email": "jane@example.com",
        "employment_type": "trader",
        "monthly_income": 45000,
        "monthly_expenses": 18000,
        "existing_debt": 5000,
        "loan_amount_requested": 25000,
        "loan_purpose": "Stock purchase",
        "organization_id": "ORG-DEFAULT"
    }),
    x_api_key: Optional[str] = Header(None)
):
    """
    Creates a borrower profile from intake data.
    Returns a borrower_id to be used in assessment.
    """
    # Simple validation
    if not intake_data.get("name") or not intake_data.get("monthly_income"):
        raise HTTPException(status_code=400, detail="Missing required fields: name, monthly_income")

    # Generate IDs
    borrower_id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
    intake_id = f"INT-{uuid.uuid4().hex[:8].upper()}"
    
    # In a real app, save to DB here. For now, we simulate success.
    # We can print to console to show 'persistence'
    logger.info(f"📝 INTAKE CREATED: {borrower_id} for {intake_data['name']}")

    return {
        "borrower_id": borrower_id,
        "status": "INTAKE_COMPLETE",
        "intake_id": intake_id,
        "message": "Borrower profile created. Proceed to /assessment/run"
    }


# ============================================================================
# LOAN ASSESSMENT ENDPOINT (CORE)
# ============================================================================

@app.get("/model/version")
async def get_model_version():
    """
    Returns active ML model version and metadata.
    Useful for tracking which model version made which decisions.
    """
    import config
    import os
    
    model_exists = os.path.exists(config.ML_MODEL_PATH)
    
    return {
        "model_version": config.ML_MODEL_VERSION,
        "model_path": config.ML_MODEL_PATH,
        "model_exists": model_exists,
        "ml_enabled": config.ENABLE_ML_RISK_SCORING,
        "ensemble_weights": {
            "rule_weight": config.RULE_WEIGHT,
            "ml_weight": config.ML_WEIGHT
        }
    }

@app.get("/config/flags")
async def get_feature_flags():
    """
    Returns current feature flag configuration.
    Allows operators to verify which AI components are active.
    """
    import config
    
    return config.get_config_snapshot()

@app.get("/policy/config")
async def get_policy_config(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Returns policy studio values for the organization.
    Values are stored per org for auditing. Defaults are provided if none exist.
    """
    from utils.policy_config import get_policy_for_org, get_policy_defaults

    values, meta = get_policy_for_org(current_user.organization_id)
    defaults = get_policy_defaults()

    return {
        "values": values,
        "defaults": defaults,
        "source": meta.get("source"),
        "updated_at": meta.get("updated_at"),
        "updated_by": meta.get("updated_by"),
        "policy_version_id": meta.get("policy_version_id"),
        "status": meta.get("status")
    }

@app.get("/policy/versions")
async def list_policy_versions(
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Lists policy versions for the organization.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")
    from utils.policy_config import list_policy_versions
    return {
        "versions": list_policy_versions(current_user.organization_id)
    }


def _raise_policy_http_error(exc: ValueError) -> None:
    detail = str(exc)
    status_code = 400
    if detail == "Policy version not found":
        status_code = 404
    elif detail == "Cross-organization access denied":
        status_code = 403
    elif detail in {
        "Only draft versions can be updated",
        "Only draft versions can be submitted",
        "Only submitted versions can be approved",
        "Only approved versions can be activated",
    }:
        status_code = 409
    raise HTTPException(status_code=status_code, detail=detail) from exc


@app.post("/policy/versions/draft")
async def create_policy_draft(
    payload: Dict[str, Any] = Body(default=None),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Creates a draft policy version from the active policy.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")

    from utils.policy_config import create_policy_draft, validate_policy_values
    values = (payload or {}).get("values") or {}
    try:
        if values:
            validate_policy_values(values)
        draft = create_policy_draft(current_user.organization_id, current_user.email, values)
    except ValueError as exc:
        _raise_policy_http_error(exc)
    AuditAgent.log_event("POLICY_DRAFT_CREATED", current_user.email, {
        "org": current_user.organization_id,
        "policy_version_id": draft.get("id")
    })
    return {"version": draft}


@app.patch("/policy/versions/{version_id}")
async def update_policy_draft(
    version_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Updates a draft policy version.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")

    from utils.policy_config import update_policy_draft, validate_policy_values
    values = payload.get("values") or {}
    try:
        if values:
            validate_policy_values(values)
        version = update_policy_draft(version_id, current_user.organization_id, current_user.email, values)
    except ValueError as exc:
        _raise_policy_http_error(exc)
    AuditAgent.log_event("POLICY_DRAFT_UPDATED", current_user.email, {
        "org": current_user.organization_id,
        "policy_version_id": version_id,
        "updated_keys": list(values.keys())
    })
    return {"version": version}


@app.post("/policy/versions/{version_id}/submit")
async def submit_policy_version(
    version_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Submits a policy version for approval.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")
    from utils.policy_config import set_policy_status
    try:
        version = set_policy_status(version_id, current_user.organization_id, "SUBMITTED", current_user.email)
    except ValueError as exc:
        _raise_policy_http_error(exc)
    AuditAgent.log_event("POLICY_VERSION_SUBMITTED", current_user.email, {
        "org": current_user.organization_id,
        "policy_version_id": version_id
    })
    return {"version": version}


@app.post("/policy/versions/{version_id}/approve")
async def approve_policy_version(
    version_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Approves a submitted policy version.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")
    from utils.policy_config import set_policy_status
    try:
        version = set_policy_status(version_id, current_user.organization_id, "APPROVED", current_user.email)
    except ValueError as exc:
        _raise_policy_http_error(exc)
    AuditAgent.log_event("POLICY_VERSION_APPROVED", current_user.email, {
        "org": current_user.organization_id,
        "policy_version_id": version_id
    })
    return {"version": version}


@app.post("/policy/versions/{version_id}/activate")
async def activate_policy_version(
    version_id: str,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Activates an approved policy version.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")
    from utils.policy_config import activate_policy_version
    try:
        version = activate_policy_version(version_id, current_user.organization_id, current_user.email)
    except ValueError as exc:
        _raise_policy_http_error(exc)
    AuditAgent.log_event("POLICY_VERSION_ACTIVATED", current_user.email, {
        "org": current_user.organization_id,
        "policy_version_id": version_id
    })
    return {"version": version}

@app.post("/policy/config/update")
async def update_policy_config(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Updates runtime policy configuration (ORG_ADMIN or SUPER_ADMIN).
    Changes are applied in-memory and recorded for audit.
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN", "DEVELOPER"]:
        raise HTTPException(status_code=403, detail="Organization Admin access required.")

    from utils.policy_config import get_policy_defaults, validate_policy_values, create_policy_draft, activate_policy_version

    defaults = get_policy_defaults()
    values = payload.get("values") or {}
    merged = {**defaults, **values}
    try:
        validate_policy_values(merged)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    draft = create_policy_draft(current_user.organization_id, current_user.email, merged)
    version = activate_policy_version(draft.get("id"), current_user.organization_id, current_user.email)

    AuditAgent.log_event("POLICY_CONFIG_UPDATED", current_user.email, {
        "org": current_user.organization_id,
        "updated_keys": list(values.keys()),
        "policy_version_id": version.get("id")
    })

    return {
        "values": version.get("values"),
        "source": "versioned",
        "updated_at": version.get("updated_at"),
        "updated_by": version.get("updated_by"),
        "policy_version_id": version.get("id"),
        "status": version.get("status")
    }

@app.post("/config/flags/update")
async def update_feature_flags(
    flag_name: str = Body(..., embed=True),
    value: bool = Body(..., embed=True),
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """
    Updates a feature flag dynamically (requires SUPER_ADMIN).
    
    WARNING: This modifies runtime configuration. Use with caution.
    For production, feature flags should be set via environment variables.
    """
    if user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Super Admin access required")
    
    import config
    
    allowed_flags = ["ENABLE_ML_RISK_SCORING", "ENABLE_LLM_EXPLANATIONS", "ENABLE_BEHAVIORAL_V2"]
    
    if flag_name not in allowed_flags:
        raise HTTPException(status_code=400, detail=f"Invalid flag. Allowed: {allowed_flags}")
    
    # Update config (runtime only, not persisted)
    setattr(config, flag_name, value)
    
    AuditAgent.log_event("CONFIG_UPDATE", user.role, {
        "flag": flag_name,
        "new_value": value,
        "org": user.organization_id
    })
    
    return {
        "status": "SUCCESS",
        "flag": flag_name,
        "new_value": value,
        "warning": "Runtime change only. Restart server to revert to environment defaults."
    }

# ============================================================================
# OFFICER FINAL DECISION ENDPOINTS
# ============================================================================

@app.post("/assessment/{assessment_id}/officer-action", response_model=OfficerAction)
async def record_officer_action(
    assessment_id: str,
    action_data: Dict = Body(...),
    user: AuthUser = Depends(AuthAgent.get_current_user),
    request: Request = None
):
    """
    Records a human officer action for an assessment.
    - APPROVE seals the final decision.
    - REFER creates a pending referral handoff and keeps the case editable for the assigned officer.
    """
    # 1. Verify Assessment
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    # Check multi-tenant isolation
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to this assessment")

    # 2. Check for existing action (Immutability / Sealing)
    if assessment.final_decision_metadata:
        raise HTTPException(status_code=400, detail="This assessment has already been sealed with a final decision and cannot be modified.")

    pending_referral = (
        assessment.pending_referral_metadata
        if isinstance(assessment.pending_referral_metadata, dict)
        else None
    )
    if pending_referral:
        assigned_user_id = (pending_referral.get("referred_to_user_id") or "").strip()
        if assigned_user_id and assigned_user_id != user.id and user.role != "SUPER_ADMIN":
            raise HTTPException(
                status_code=403,
                detail="This referral is assigned to another team member. Only the assigned user can finalize it."
            )

    # 3. Handle Decision Logic & Override Detection
    officer_decision = action_data.get("officer_decision")
    final_amount = action_data.get("final_amount", assessment.recommended_amount)
    final_duration = action_data.get("final_duration", assessment.recommended_duration_days)
    final_rate = action_data.get("final_interest_rate", assessment.recommended_interest_rate)
    if final_amount is None:
        final_amount = assessment.recommended_amount if assessment.recommended_amount is not None else 0.0
    if final_duration is None:
        final_duration = (
            assessment.recommended_duration_days
            if assessment.recommended_duration_days is not None
            else 0
        )
    if final_rate is None:
        final_rate = assessment.recommended_interest_rate if assessment.recommended_interest_rate is not None else 0.0
    if officer_decision != "APPROVE":
        # Non-approve outcomes do not carry underwriting terms; persist safe numeric values for schema integrity.
        final_amount = float(final_amount or 0.0)
        final_duration = int(final_duration or 0)
        final_rate = float(final_rate or 0.0)
    referred_to_user_id = (action_data.get("referred_to_user_id") or "").strip() or None
    referred_to_user_name = (action_data.get("referred_to_user_name") or "").strip() or None
    referred_to_user_email = (action_data.get("referred_to_user_email") or "").strip() or None
    if pending_referral:
        referred_to_user_id = referred_to_user_id or (pending_referral.get("referred_to_user_id") or None)
        referred_to_user_name = referred_to_user_name or (pending_referral.get("referred_to_user_name") or None)
        referred_to_user_email = referred_to_user_email or (pending_referral.get("referred_to_user_email") or None)

    if officer_decision == "REFER" and not referred_to_user_id:
        raise HTTPException(status_code=400, detail="Referral requires a target team member.")

    if referred_to_user_id and (not referred_to_user_name or not referred_to_user_email):
        recipient_user = Database.get_user_by_id(referred_to_user_id)
        if recipient_user and (recipient_user.organization_id or "").upper() == (user.organization_id or "").upper():
            referred_to_user_name = referred_to_user_name or recipient_user.full_name
            referred_to_user_email = referred_to_user_email or recipient_user.email

    is_override = officer_decision != assessment.decision
    if officer_decision == "APPROVE":
        is_override = is_override or (
            abs((final_amount or 0) - (assessment.recommended_amount or 0)) > 0.01 or
            final_duration != (assessment.recommended_duration_days or 0)
        )
    if is_override:
        if not action_data.get("officer_notes") or not str(action_data.get("officer_notes")).strip():
            raise HTTPException(status_code=400, detail="Override requires officer_notes for audit compliance.")
        if not action_data.get("override_reason_code") or not str(action_data.get("override_reason_code")).strip():
            raise HTTPException(status_code=400, detail="Override requires override_reason_code for audit compliance.")

    # 4. Create Action Metadata
    try:
        current_time = datetime.now(timezone.utc)
        is_referral_handoff = officer_decision == "REFER"
        action = {
            "assessment_id": assessment_id,
            "officer_id": user.id,
            "officer_name": user.full_name or "Unknown Officer",
            "officer_decision": officer_decision,
            "final_amount": final_amount,
            "final_duration_days": final_duration,
            "final_interest_rate": final_rate,
            "officer_notes": action_data.get("officer_notes"),
            "override_reason_code": action_data.get("override_reason_code"),
            "referred_to_user_id": referred_to_user_id,
            "referred_to_user_name": referred_to_user_name,
            "referred_to_user_email": referred_to_user_email,
            "borrower_message": action_data.get("borrower_message"),
            "communication_channel": action_data.get("communication_channel", CommChannel.NONE),
            "created_at": current_time,
            "sealed_at": None if is_referral_handoff else current_time.isoformat(),
            "is_override": is_override,
            "ai_recommendation_snapshot": {
                "decision": assessment.decision,
                "amount": assessment.recommended_amount,
                "duration_days": assessment.recommended_duration_days,
                "interest_rate": assessment.recommended_interest_rate
            }
        }
        # Force validation via OfficerAction model for safety check (forbidden phrases)
        OfficerAction(**action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 5. Safety Logic (Policy check)
    if not action_data.get("confirmed_compliance"):
        raise HTTPException(status_code=400, detail="You must confirm that this decision complies with internal policies.")

    # 6. Referral handoff (non-sealing)
    if officer_decision == "REFER":
        assessment.pending_referral_metadata = {
            **action,
            "status": "PENDING_REVIEW",
            "referred_at": current_time.isoformat(),
            "referred_by_user_id": user.id,
            "referred_by_name": user.full_name or user.email
        }
        Database.save_assessment(assessment)

        try:
            org_users = [
                u for u in Database.list_all_users()
                if (u.organization_id or "").upper() == (user.organization_id or "").upper()
            ]
            recipient_ids = {u.id for u in org_users if u.id != user.id}
            reason_code = action_data.get("override_reason_code")
            instructions = (action_data.get("officer_notes") or "").strip()
            actor_name = user.full_name or user.email or "A team member"
            for member in org_users:
                if member.id not in recipient_ids:
                    continue

                is_primary_assignee = bool(referred_to_user_id and member.id == referred_to_user_id)
                title = "New Referral Assigned" if is_primary_assignee else "Team Referral Alert"
                message = (
                    f"{actor_name} referred assessment {assessment_id} to the team."
                    if not is_primary_assignee
                    else f"{actor_name} referred assessment {assessment_id} to you."
                )
                metadata = {
                    "assessment_id": assessment_id,
                    "referrer_user_id": user.id,
                    "referrer_name": actor_name,
                    "referred_to_user_id": referred_to_user_id,
                    "referred_to_user_email": referred_to_user_email,
                    "reason_code": reason_code,
                    "instructions": instructions
                }
                notification = Notification(
                    notification_id=f"NTF-{uuid.uuid4().hex[:12].upper()}",
                    organization_id=user.organization_id,
                    recipient_user_id=member.id,
                    recipient_email=member.email,
                    created_by_user_id=user.id,
                    type="REFERRAL_ASSIGNED" if is_primary_assignee else "REFERRAL_TEAM_ALERT",
                    title=title,
                    message=message,
                    assessment_id=assessment_id,
                    metadata=metadata
                )
                Database.save_notification(notification)

            AuditAgent.log_event("REFERRAL_ASSIGNED", user.email, {
                "assessment_id": assessment_id,
                "recipient_count": len(recipient_ids),
                "referred_to_user_id": referred_to_user_id,
                "org": user.organization_id
            })
        except Exception as notify_error:
            logger.error(f"Failed to create referral notifications: {notify_error}")

        client_ip = request.client.host if request and request.client else "unknown"
        AuditAgent.log_event("REFERRAL_HANDOFF_CREATED", user.email, {
            "assessment_id": assessment_id,
            "referred_to_user_id": referred_to_user_id,
            "override_reason_code": action_data.get("override_reason_code"),
            "ip": client_ip,
            "org": user.organization_id
        })

        return action

    # 7. Seal Assessment
    assessment.final_decision_metadata = action
    assessment.pending_referral_metadata = None
    Database.save_assessment(assessment)

    # 7.5 Create Loan Record if Approved (Pending Disbursement)
    if officer_decision == "APPROVE":
        try:
            loan = Loan(
                loan_id=f"LOAN-{uuid.uuid4().hex[:8].upper()}",
                assessment_id=assessment_id,
                borrower_id=assessment.borrower_id,
                organization_id=user.organization_id,
                amount=final_amount,
                interest_rate=final_rate,
                status=LoanStatus.PENDING_DISBURSEMENT
            )
            Database.save_loan(loan)
        except Exception as loan_err:
             logger.error(f"WARNING: Failed to auto-create loan record: {loan_err}")

    # 8. Audit
    client_ip = request.client.host if request and request.client else "unknown"
    AuditAgent.log_event("FINAL_HUMAN_DECISION_SEALED", user.email, {
        "assessment_id": assessment_id,
        "decision": officer_decision,
        "is_override": is_override,
        "override_reason_code": action_data.get("override_reason_code"),
        "referred_to_user_id": referred_to_user_id,
        "ip": client_ip,
        "org": user.organization_id
    })

    # 9. Auto-generate decision exports (best-effort)
    try:
        borrower = Database.get_borrower(assessment.borrower_id)
        if borrower:
            DecisionExportAgent.generate_exports(assessment, borrower, user.email, force=False)
            AuditAgent.log_event("DECISION_EXPORT_GENERATED", user.email, {
                "assessment_id": assessment_id,
                "org": user.organization_id
            })
        else:
            AuditAgent.log_event("DECISION_EXPORT_SKIPPED", user.email, {
                "assessment_id": assessment_id,
                "reason": "Borrower not found",
                "org": user.organization_id
            })
    except Exception as export_error:
        AuditAgent.log_event("DECISION_EXPORT_FAILED", user.email, {
            "assessment_id": assessment_id,
            "error": str(export_error),
            "org": user.organization_id
        })

    return action

@app.get("/assessment/{assessment_id}/officer-action", response_model=Optional[OfficerAction])
async def get_officer_action_endpoint(
    assessment_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    """Retrieves the final human decision record for an assessment."""
    action = Database.get_officer_action(assessment_id)
    if not action:
        return None
        
    return action

@app.post("/assessment/{assessment_id}/send-sms")
async def send_borrower_sms(
    assessment_id: str,
    action_data: dict,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    """
    Sends a human-authorized SMS to the borrower.
    Governance: Manual Assessments only, Sealed Decisions only.
    """
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
        
    # Isolation & Auth
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Rule 1: Manual Assessments Only
    if assessment.assessment_source != "MANUAL_UI":
        raise HTTPException(status_code=400, detail="SMS sending is only enabled for Manual UI assessments.")

    # Rule 2: Saved Decision Only (Sealed)
    if not assessment.final_decision_metadata:
        raise HTTPException(status_code=400, detail="A final decision must be sealed before sending communication.")

    # Load Borrower for Phone
    borrower = Database.get_borrower(assessment.borrower_id)
    if not borrower or not borrower.phone:
        raise HTTPException(status_code=400, detail="Borrower contact information (phone) is missing.")

    message_content = action_data.get("message")
    if not message_content:
        raise HTTPException(status_code=400, detail="Message content is required.")

    # Send SMS
    result = SMSService.send_sms(borrower.phone, message_content)

    # Persist SMS Log
    import uuid
    log = SMSLog(
        id=f"SMS-{uuid.uuid4().hex[:8].upper()}",
        assessment_id=assessment_id,
        borrower_id=assessment.borrower_id,
        phone_number=borrower.phone,
        message=message_content,
        sent_by=user.id,
        status=result["status"],
        provider_id=result.get("provider_id"),
        environment=result["environment"]
    )
    Database.save_sms_log(log)

    # Audit
    provider = os.getenv("SMS_PROVIDER", "AFRICASTALKING").upper()
    AuditAgent.log_event("BORROWER_SMS_SENT", user.email, {
        "assessment_id": assessment_id,
        "status": result["status"],
        "environment": result["environment"],
        "provider": provider
    })

    return log

@app.get("/assessment/{assessment_id}", response_model=Assessment)
async def get_assessment_details(
    assessment_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    """Retrieves full details for a single assessment."""
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
        
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to this assessment")
        
    return enforce_summary_profile_metrics(assessment)


@app.get("/decisions/{decision_id}/documents", response_model=List[DecisionDocumentSummary])
async def list_decision_documents(
    decision_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    assessment = Database.get_assessment(decision_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Decision not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to decision")

    return build_decision_document_rows(assessment)


@app.get("/documents/{doc_id}/insight", response_model=DocumentInsight)
async def get_document_insight(
    doc_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    cached = Database.get_document_insight(doc_id)
    if cached:
        if cached.organizationId != user.organization_id and user.role != "SUPER_ADMIN":
            raise HTTPException(status_code=403, detail="Unauthorized access to document insight")
        return cached

    locator = _parse_doc_id(doc_id)
    if not locator:
        raise HTTPException(status_code=404, detail="Document insight not found")

    decision_id, source_index, _missing_key = locator
    assessment = Database.get_assessment(decision_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Decision not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to decision")

    rows = build_decision_document_rows(assessment)
    row = next((candidate for candidate in rows if candidate.docId == doc_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Document insight not found")

    metrics = assessment.metrics if isinstance(assessment.metrics, dict) else {}
    raw_summaries = metrics.get("document_summaries") if isinstance(metrics.get("document_summaries"), list) else []
    raw_summary: Dict[str, Any] = {}
    if source_index is not None and 0 <= source_index < len(raw_summaries):
        candidate_summary = raw_summaries[source_index]
        if isinstance(candidate_summary, dict):
            raw_summary = candidate_summary

    insight = _build_document_insight_payload(
        assessment=assessment,
        row=row,
        summary=raw_summary,
        source_index=source_index,
    )
    Database.save_document_insight(insight)
    return insight


@app.get("/assessment/{assessment_id}/exports", response_model=List[DecisionExport])
async def list_decision_exports(
    assessment_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to this assessment")

    return Database.list_decision_exports(assessment_id)


@app.post("/assessment/{assessment_id}/exports/generate", response_model=List[DecisionExport])
async def generate_decision_exports(
    assessment_id: str,
    force: bool = False,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to this assessment")
    if not assessment.final_decision_metadata:
        raise HTTPException(status_code=400, detail="Decision is not finalized")

    borrower = Database.get_borrower(assessment.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")

    exports = DecisionExportAgent.generate_exports(assessment, borrower, user.email, force=force)
    AuditAgent.log_event("DECISION_EXPORT_REQUESTED", user.email, {
        "assessment_id": assessment_id,
        "force": force,
        "org": user.organization_id
    })
    return exports


@app.get("/assessment/{assessment_id}/exports/{export_id}/download")
async def download_decision_export(
    assessment_id: str,
    export_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    export = Database.get_decision_export(export_id)
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.decision_id != assessment_id:
        raise HTTPException(status_code=404, detail="Export not found for assessment")
    if export.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to export")
    if export.status != "READY":
        raise HTTPException(status_code=400, detail="Export is not ready")
    if not os.path.exists(export.file_path):
        raise HTTPException(status_code=404, detail="Export file missing")

    filename = os.path.basename(export.file_path)
    media_type = "application/pdf" if export.export_type.value == "PDF" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(export.file_path, media_type=media_type, filename=filename)


@app.get("/decisions/{decision_id}/counterfactuals", response_model=List[DecisionCounterfactual])
async def list_decision_counterfactuals(
    decision_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    assessment = Database.get_assessment(decision_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Decision not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to decision")
    if not assessment.final_decision_metadata:
        raise HTTPException(status_code=400, detail="Decision is not finalized")

    borrower = Database.get_borrower(assessment.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")

    from utils.policy_config import get_policy_for_org
    from utils.policy_context import set_policy_context, reset_policy_context
    policy_values, _ = get_policy_for_org(assessment.organization_id)
    token = set_policy_context(policy_values)
    try:
        counterfactuals = DecisionCounterfactualAgent.get_or_compute(assessment, borrower, force=False)
    finally:
        reset_policy_context(token)
    AuditAgent.log_event("DECISION_COUNTERFACTUALS_VIEWED", user.email, {
        "decision_id": decision_id,
        "org": user.organization_id
    })
    return counterfactuals


@app.post("/decisions/{decision_id}/counterfactuals/recompute", response_model=List[DecisionCounterfactual])
async def recompute_decision_counterfactuals(
    decision_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    if user.role not in ["ORG_ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    assessment = Database.get_assessment(decision_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Decision not found")
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized access to decision")
    if not assessment.final_decision_metadata:
        raise HTTPException(status_code=400, detail="Decision is not finalized")

    borrower = Database.get_borrower(assessment.borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found")

    from utils.policy_config import get_policy_for_org
    from utils.policy_context import set_policy_context, reset_policy_context
    policy_values, _ = get_policy_for_org(assessment.organization_id)
    token = set_policy_context(policy_values)
    try:
        counterfactuals = DecisionCounterfactualAgent.get_or_compute(assessment, borrower, force=True)
    finally:
        reset_policy_context(token)
    AuditAgent.log_event("DECISION_COUNTERFACTUALS_RECOMPUTED", user.email, {
        "decision_id": decision_id,
        "org": user.organization_id
    })
    return counterfactuals

@app.get("/assessment/{assessment_id}/sms-logs", response_model=List[SMSLog])
async def get_assessment_sms_logs(
    assessment_id: str,
    user: AuthUser = Depends(AuthAgent.get_current_user)
):
    """Retrieves SMS history for a specific assessment."""
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
        
    if assessment.organization_id != user.organization_id and user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    return Database.list_sms_logs(assessment_id)


@app.get("/assessment/{assessment_id}/follow-ups", response_model=List[FollowUpTask])
async def list_follow_up_tasks(
    assessment_id: str,
    user: User = Depends(get_dashboard_user)
):
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user.organization_id != "PLATFORM_OWNER" and assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return Database.list_follow_up_tasks(
        organization_id=assessment.organization_id,
        assessment_id=assessment_id
    )


@app.get("/org/follow-ups", response_model=List[FollowUpTask])
async def list_org_follow_up_tasks(
    user: User = Depends(get_dashboard_user)
):
    organization_id = None if user.organization_id == "PLATFORM_OWNER" else (user.organization_id or "").strip().upper()
    return Database.list_follow_up_tasks(organization_id=organization_id)


def _normalize_follow_up_due_date(raw_due_date: Optional[str]) -> Optional[str]:
    if raw_due_date in (None, ""):
        return None
    try:
        return datetime.strptime(str(raw_due_date), "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Follow-up due_date must be in YYYY-MM-DD format.") from exc


@app.post("/assessment/{assessment_id}/follow-ups", response_model=FollowUpTask)
async def create_follow_up_task(
    assessment_id: str,
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(get_dashboard_user)
):
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user.organization_id != "PLATFORM_OWNER" and assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    note = (payload.get("note") or "").strip()
    if not note:
        raise HTTPException(status_code=400, detail="Follow-up note is required")
    title = (payload.get("title") or "").strip() or note[:72]
    due_date = _normalize_follow_up_due_date(payload.get("due_date"))
    reason_code = (payload.get("reason_code") or "").strip() or None
    task_type_raw = str(payload.get("task_type") or FollowUpType.OTHER)
    priority_raw = str(payload.get("priority") or FollowUpPriority.MEDIUM)
    try:
        task_type = FollowUpType(task_type_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported follow-up task_type '{task_type_raw}'.") from exc
    try:
        priority = FollowUpPriority(priority_raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported follow-up priority '{priority_raw}'.") from exc

    assigned_to_user_id = (payload.get("assigned_to_user_id") or "").strip() or None
    assigned_to_user_name = (payload.get("assigned_to_user_name") or "").strip() or None
    assigned_to_user_email = (payload.get("assigned_to_user_email") or "").strip() or None
    notify_assignee = bool(payload.get("notify_assignee")) and bool(assigned_to_user_id)
    send_email = bool(payload.get("send_email")) and bool(assigned_to_user_email)
    assigned_user = None

    if assigned_to_user_id:
        assigned_user = Database.get_user_by_id(assigned_to_user_id)
        if not assigned_user:
            raise HTTPException(status_code=400, detail="Assigned follow-up owner was not found.")
        if user.organization_id != "PLATFORM_OWNER" and assigned_user.organization_id != assessment.organization_id:
            raise HTTPException(status_code=403, detail="Assigned follow-up owner is outside your organization.")
        assigned_to_user_name = assigned_to_user_name or assigned_user.full_name or assigned_user.email
        assigned_to_user_email = assigned_to_user_email or assigned_user.email

    current_time = datetime.now(timezone.utc)

    task = FollowUpTask(
        task_id=f"FUP-{uuid.uuid4().hex[:10].upper()}",
        assessment_id=assessment_id,
        borrower_id=assessment.borrower_id,
        organization_id=assessment.organization_id,
        title=title,
        note=note,
        task_type=task_type,
        reason_code=reason_code,
        priority=priority,
        due_date=due_date,
        status=FollowUpStatus.OPEN,
        is_blocking=bool(payload.get("is_blocking")),
        created_by=user.id or user.email or "unknown",
        created_by_name=user.full_name or user.email,
        created_by_email=user.email,
        assigned_to_user_id=assigned_to_user_id,
        assigned_to_user_name=assigned_to_user_name,
        assigned_to_user_email=assigned_to_user_email,
        notify_assignee=notify_assignee,
        updated_at=current_time
    )

    if notify_assignee and assigned_user and assigned_user.id != user.id:
        notification = Notification(
            notification_id=f"NTF-{uuid.uuid4().hex[:12].upper()}",
            organization_id=assessment.organization_id,
            recipient_user_id=assigned_user.id,
            recipient_email=assigned_user.email,
            created_by_user_id=user.id,
            type="FOLLOW_UP_ASSIGNED",
            title=f"Follow-up assigned: {task.title}",
            message=(
                f"{user.full_name or user.email or 'A team member'} assigned you a "
                f"{task.task_type.replace('_', ' ').title()} task for assessment {assessment_id}."
            ),
            assessment_id=assessment_id,
            metadata={
                "task_id": task.task_id,
                "task_type": task.task_type,
                "priority": task.priority,
                "due_date": task.due_date,
                "reason_code": task.reason_code,
                "is_blocking": task.is_blocking
            }
        )
        Database.save_notification(notification)
        task.notification_sent_at = current_time

        if send_email and assigned_user.email:
            email_result = EmailService.send_email(
                to_email=assigned_user.email,
                subject=f"New follow-up assigned: {task.title}",
                body_text=(
                    f"You have been assigned a follow-up task in MIFI Pro.\n\n"
                    f"Assessment: {assessment_id}\n"
                    f"Title: {task.title}\n"
                    f"Type: {task.task_type}\n"
                    f"Priority: {task.priority}\n"
                    f"Due date: {task.due_date or 'Not set'}\n"
                    f"Reason code: {task.reason_code or 'Not provided'}\n"
                    f"Blocking: {'Yes' if task.is_blocking else 'No'}\n\n"
                    f"Task details:\n{task.note}"
                )
            )
            task.email_notification_status = email_result.get("status")
            task.email_notification_message = email_result.get("message") or email_result.get("environment")

    Database.save_follow_up_task(task)
    AuditAgent.log_event("FOLLOW_UP_TASK_CREATED", user.email, {
        "assessment_id": assessment_id,
        "task_id": task.task_id,
        "task_type": task.task_type,
        "priority": task.priority,
        "assigned_to_user_id": task.assigned_to_user_id,
        "notify_assignee": task.notify_assignee,
        "org": assessment.organization_id
    })
    return task


@app.patch("/assessment/{assessment_id}/follow-ups/{task_id}", response_model=FollowUpTask)
async def update_follow_up_task(
    assessment_id: str,
    task_id: str,
    payload: Dict[str, Any] = Body(...),
    user: User = Depends(get_dashboard_user)
):
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user.organization_id != "PLATFORM_OWNER" and assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    task = Database.get_follow_up_task(task_id)
    if not task or task.assessment_id != assessment_id:
        raise HTTPException(status_code=404, detail="Follow-up task not found")
    if task.organization_id != assessment.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    current_time = datetime.now(timezone.utc)
    next_status = task.status
    if payload.get("status"):
        try:
            next_status = FollowUpStatus(str(payload.get("status")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported follow-up status '{payload.get('status')}'.") from exc

    resolution_note = (payload.get("resolution_note") or "").strip() or task.resolution_note
    if next_status in {FollowUpStatus.COMPLETED, FollowUpStatus.CANCELED} and not resolution_note:
        raise HTTPException(status_code=400, detail="Resolution note is required when completing or canceling a follow-up.")

    if payload.get("priority"):
        try:
            task.priority = FollowUpPriority(str(payload.get("priority")))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Unsupported follow-up priority '{payload.get('priority')}'.") from exc

    if "due_date" in payload:
        task.due_date = _normalize_follow_up_due_date(payload.get("due_date"))

    task.status = next_status
    task.resolution_note = resolution_note
    task.updated_at = current_time

    if next_status in {FollowUpStatus.COMPLETED, FollowUpStatus.CANCELED}:
        task.completed_at = current_time
        task.completed_by = user.id or user.email
        task.completed_by_name = user.full_name or user.email
    else:
        task.completed_at = None
        task.completed_by = None
        task.completed_by_name = None

    Database.save_follow_up_task(task)
    AuditAgent.log_event("FOLLOW_UP_TASK_UPDATED", user.email, {
        "assessment_id": assessment_id,
        "task_id": task.task_id,
        "status": task.status,
        "priority": task.priority,
        "org": assessment.organization_id
    })
    return task

# ============================================================================
# DOCUMENT UPLOAD ENDPOINT (For Testing Behavioral Intelligence)
# ============================================================================

@app.post("/borrower/data/upload-document")
async def upload_transaction_document(
    borrower_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload a PDF or CSV file containing transaction data for behavioral analysis.
    
    This endpoint allows you to test the behavioral intelligence system by uploading
    bank statements, mobile money statements, or utility payment records.
    
    Supported formats:
    - PDF: Bank statements with transaction tables
    - CSV: Simple format (Date,Type,Amount,Description)
    - TXT: Plain text with transaction data
    
    Example CSV format:
    ```
    Date,Type,Amount,Description
    2024-01-15,DEPOSIT,5000,Salary
    2024-01-16,WITHDRAWAL,2000,ATM
    2024-01-17,PAYMENT,500,Electricity
    ```
    
    Returns:
    - Parsed transaction data
    - Behavioral metrics calculated
    - Risk assessment with behavioral intelligence
    """
    import io
    policy_token = None
    try:
        # Verify borrower exists
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found")

        from utils.policy_config import get_policy_for_org
        from utils.policy_context import set_policy_context
        policy_values, _ = get_policy_for_org(borrower.organization_id)
        policy_token = set_policy_context(policy_values)
        
        # Read file content
        content = await file.read()
        filename = file.filename.lower()
        
        # Use Standardized TransactionParser
        parser = TransactionParser()
        extraction_result = parser.parse(content, filename)
        
        # Validation (document-specific)
        if not extraction_result.transactions:
            if extraction_result.document_type == DocumentType.PAYSLIP:
                summary = extraction_result.payslip_summary
                is_success = bool(summary and (summary.net_pay is not None or summary.gross_pay is not None))
                if is_success:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "SUCCESS",
                            "message": "Payslip extracted successfully (no transactions expected).",
                            "data_summary": {
                                "doc_type": extraction_result.document_type,
                                "summary_profile": summary.summary_profile,
                                "net_pay": summary.net_pay,
                                "gross_pay": summary.gross_pay
                            },
                            "warnings": extraction_result.warnings
                        }
                    )
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "WARNING",
                        "message": "Payslip could not extract net/gross pay.",
                        "warnings": extraction_result.warnings
                    }
                )
            if extraction_result.document_type == DocumentType.NRC_ID:
                summary = extraction_result.nrc_summary
                is_success = bool(summary and (summary.id_number or summary.full_name))
                if is_success:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "SUCCESS",
                            "message": "NRC extracted successfully (no transactions expected).",
                            "data_summary": {
                                "doc_type": extraction_result.document_type,
                                "summary_profile": summary.summary_profile,
                                "full_name": summary.full_name,
                                "id_number": summary.id_number
                            },
                            "warnings": extraction_result.warnings
                        }
                    )
                return JSONResponse(
                    status_code=200,
                    content={
                        "status": "WARNING",
                        "message": "NRC could not extract identity details.",
                        "warnings": extraction_result.warnings
                    }
                )
            if extraction_result.document_type == DocumentType.BANK_STATEMENT:
                summary = extraction_result.bank_statement_summary
                is_success = bool(summary and summary.closing_balance is not None and summary.statement_period is not None)
                if is_success:
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "SUCCESS",
                            "message": "Bank statement summary extracted (no transactions parsed).",
                            "data_summary": {
                                "doc_type": extraction_result.document_type,
                                "summary_profile": summary.summary_profile,
                                "closing_balance": summary.closing_balance,
                                "statement_period": summary.statement_period.model_dump() if summary.statement_period else None
                            },
                            "warnings": extraction_result.warnings
                        }
                    )
            return JSONResponse(
                status_code=200,
                content={
                    "status": "WARNING",
                    "message": "No transactions found in the document. Please check the format.",
                    "warnings": extraction_result.warnings
                }
            )
            
        # Convert to Legacy AlternativeData for Database Storage
        # TODO: Refactor Database to use new Transaction model natively
        from models.alternative_data import AlternativeData, MobileMoneyTransaction, UtilityPayment
        
        mm_txs = []
        for t in extraction_result.transactions:
            # Map standardized Transaction to legacy MobileMoneyTransaction
            tx_type = "DEPOSIT" if t.direction == "INFLOW" else "WITHDRAWAL"
            if "SALARY" in t.description.upper(): tx_type = "DEPOSIT" # Enforce logic
            
            mm_txs.append(MobileMoneyTransaction(
                transaction_id=f"TX-{hash(t.description+t.date+str(t.amount)) % 1000000}",
                amount=t.amount,
                type=tx_type,
                timestamp=datetime.strptime(t.date, "%Y-%m-%d"),
                counterparty=t.description
            ))
            
        alt_data = AlternativeData(
            borrower_id=borrower_id,
            mobile_money_history=mm_txs,
            utility_history=[], # Utilities now inside transactions? or separate? New parser treats them as text.
            airtime_usage_avg=0.0
        )
        
        # Save alternative data
        Database.save_alternative_data(alt_data)
        
        # Run behavioral analysis (Using NEW Logic via list of transactions)
        from agents.behavioral_agent_v2 import BehavioralAgentV2
        behavioral_results = BehavioralAgentV2.analyze_transactions(
            extraction_result.transactions,
            statement_summary=extraction_result.bank_statement_summary
        )
        
        # Run full risk assessment
        risk_results = RiskAgent.evaluate(
            borrower,
            external_behavioral_results=behavioral_results,
            requested_duration_days=30,
        )
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30)
        explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)
        
        AuditAgent.log_event("DOCUMENT_UPLOAD", "BORROWER_PORTAL", {
            "borrower_id": borrower_id,
            "filename": file.filename,
            "transactions_found": len(extraction_result.transactions),
            "doc_type": extraction_result.document_type
        })
        
        return {
            "status": "SUCCESS",
            "message": "Document uploaded and analyzed successfully",
            "data_summary": {
                "transactions_parsed": len(extraction_result.transactions),
                "doc_type": extraction_result.document_type
            },
            "behavioral_analysis": behavioral_results,
            "risk_assessment": augment_assessment_payload({
                "risk_score": risk_results["risk_score"],
                "risk_level": risk_results["risk_level"],
                "decision": decision_results["decision"],
                "recommended_amount": decision_results["recommended_amount"],
                "recommended_interest_rate": decision_results["recommended_interest_rate"]
            }),
            "explanation": explanation
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        if policy_token is not None:
            from utils.policy_context import reset_policy_context
            reset_policy_context(policy_token)

# ============================================================================
# SAFE ALTERNATIVE DATA PIPELINE (Pilot Interface)
# ============================================================================

@app.post("/behavior/upload")
async def behavior_upload(
    borrower_id: str = Form(...),
    file: UploadFile = File(...)
):
    # This logic is also accessible via the /documents/upload alias
    return await process_document_upload(borrower_id, file)

@app.post("/documents/upload", tags=["Alternative Data"])
async def documents_upload_alias(
    borrower_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Alias for /behavior/upload to support legacy or Postman integrations.
    """
    return await process_document_upload(borrower_id, file)

async def process_document_upload(borrower_id: str, file: UploadFile):
    """
    REGULATOR-SAFE pipeline for ingesting user-provided transaction data.
    
    Safety Guarantees:
    1. Data source explicitly flagged as "USER_UPLOADED"
    2. Confidence weight capped at 0.6
    3. Behavioral impact on risk score capped at 20%
    4. Full transparency in generated explanations
    
    Supported: PDF (Zanaco), CSV
    """
    policy_token = None
    try:
        # 1. Validation
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found")

        from utils.policy_config import get_policy_for_org
        from utils.policy_context import set_policy_context, reset_policy_context
        policy_values, _ = get_policy_for_org(borrower.organization_id)
        policy_token = set_policy_context(policy_values)
            
        content = await file.read()
        
        # 2. Safe Parsing (Standardized Schema)
        parser = TransactionParser()
        try:
            extraction_result = parser.parse(content, file.filename)
            transactions = extraction_result.transactions
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if not transactions:
             AuditAgent.log_event("EXTRACTION_EMPTY", "SYSTEM", {
                "borrower_id": borrower_id,
                "filename": file.filename,
                "document_type": extraction_result.document_type,
                "warnings": extraction_result.warnings
             })
             return JSONResponse(
                status_code=200,
                content={
                    "status": "WARNING", 
                    "message": "No transactions extracted. Check file format.",
                    "document_type": extraction_result.document_type,
                    "quality_score": getattr(extraction_result, "quality_score", None),
                    "warnings": extraction_result.warnings
                }
            )

        # 3. Behavioral Analysis (With Confidence Weights)
        from agents.behavioral_agent_v2 import BehavioralAgentV2
        behavioral_results = BehavioralAgentV2.analyze_transactions(
            transactions,
            statement_summary=extraction_result.bank_statement_summary
        )
        
        # 4. Risk Assessment (With Impact Caps)
        risk_results = RiskAgent.evaluate(
            borrower,
            external_behavioral_results=behavioral_results,
            requested_duration_days=30,
        )
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30) # Default duration for pilot
        explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)
        
        # 5. Audit Logging
        AuditAgent.log_event("BEHAVIOR_UPLOAD_PILOT", "SYSTEM", {
            "borrower_id": borrower_id, 
            "tx_count": len(transactions),
            "source": "USER_UPLOADED"
        })
        
        return {
            "status": "SUCCESS",
            "data_source": "USER_UPLOADED_STATEMENT",
            "document_type": extraction_result.document_type,
            "quality_score": getattr(extraction_result, "quality_score", None),
            "transaction_count": len(transactions),
            "risk_assessment": {
                "score": risk_results["risk_score"],
                "level": risk_results["risk_level"],
                "decision": decision_results["decision"],
                "decision_legacy": decision_to_legacy(decision_results["decision"]),
                "risk_score_percent": round(risk_results["risk_score"] * 100.0, 1),
                "risk_score_scale": "0-1"
            },
            "behavioral_insights": behavioral_results,
            "explanation": explanation,
            "warnings": extraction_result.warnings
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")
    finally:
        if policy_token is not None:
            from utils.policy_context import reset_policy_context
            reset_policy_context(policy_token)

# ============================================================================
# SMS / USSD Borrower Journeys (Small MFI Onboarding)
# ============================================================================

@app.post("/channels/sms/inbound")
async def sms_inbound(payload: Dict[str, Any] = Body(...), user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Inbound SMS webhook for borrower journeys.
    Expected payload fields: phone, text (provider-agnostic).
    """
    raw_phone = payload.get("phone") or payload.get("from") or payload.get("msisdn")
    text = (payload.get("text") or payload.get("message") or "").strip()
    if not raw_phone:
        raise HTTPException(status_code=400, detail="Missing phone number")

    phone = normalize_phone(raw_phone)
    session_id = f"SMS:{user.organization_id}:{phone}"
    session = Database.get_channel_session(session_id) or {
        "session_id": session_id,
        "channel": "SMS",
        "organization_id": user.organization_id,
        "phone": phone,
        "step": "CONSENT",
        "data": {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    step = session.get("step", "CONSENT")
    data = session.get("data", {})
    lower = text.lower()

    if lower in ["start", "loan", "hi", "hello"]:
        step = "CONSENT"

    if step == "CONSENT":
        if lower not in ["yes", "y", "agree"]:
            reply = sms_next_prompt("CONSENT")
            SMSService.send_sms(phone, reply)
            session.update({"step": "CONSENT", "updated_at": datetime.now(timezone.utc).isoformat()})
            Database.save_channel_session(session_id, session)
            return {"status": "OK", "message": "Consent requested"}
        if not session.get("consent_event_id"):
            consent_event_id = f"CNS-{uuid.uuid4().hex[:10].upper()}"
            consent_time = datetime.now(timezone.utc).isoformat()
            Database.save_consent_event(consent_event_id, {
                "consent_event_id": consent_event_id,
                "organization_id": user.organization_id,
                "channel": "SMS",
                "phone": phone,
                "session_id": session_id,
                "consent_text": text,
                "consent_timestamp": consent_time
            })
            session.update({
                "consent_event_id": consent_event_id,
                "consent_timestamp": consent_time,
                "consent_channel": "SMS"
            })
        step = "NAME"
        reply = sms_next_prompt(step)
    elif step == "NAME":
        data["name"] = clean_name(text)
        step = "INCOME"
        reply = sms_next_prompt(step)
    elif step == "INCOME":
        val = parse_float_or_none(text)
        if val is None:
            reply = "Invalid income. Please enter a number."
        else:
            data["monthly_income"] = val
            step = "EXPENSES"
            reply = sms_next_prompt(step)
    elif step == "EXPENSES":
        val = parse_float_or_none(text)
        if val is None:
            reply = "Invalid expenses. Please enter a number."
        else:
            data["monthly_expenses"] = val
            step = "DEBT"
            reply = sms_next_prompt(step)
    elif step == "DEBT":
        val = parse_float_or_none(text)
        if val is None:
            reply = "Invalid debt amount. Please enter a number."
        else:
            data["existing_debt"] = val
            step = "AMOUNT"
            reply = sms_next_prompt(step)
    elif step == "AMOUNT":
        val = parse_float_or_none(text)
        if val is None:
            reply = "Invalid amount. Please enter a number."
        else:
            data["loan_amount_requested"] = val
            step = "PURPOSE"
            reply = sms_next_prompt(step)
    elif step == "PURPOSE":
        data["loan_purpose"] = text or "Not specified"
        step = "DONE"
        reply = sms_next_prompt(step)
    else:
        reply = "Reply START to begin a new assessment."

    # Persist session
    session.update({"step": step, "data": data, "updated_at": datetime.now(timezone.utc).isoformat()})
    Database.save_channel_session(session_id, session)

    if step == "DONE":
        # Create borrower and run assessment
        borrower_id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        borrower = Borrower(
            id=borrower_id,
            organization_id=user.organization_id,
            name=data.get("name", "Borrower"),
            phone=phone,
            employment_type="trader",
            monthly_income=data.get("monthly_income", 0.0),
            monthly_expenses=data.get("monthly_expenses", 0.0),
            existing_debt=data.get("existing_debt", 0.0),
            loan_amount_requested=data.get("loan_amount_requested", 0.0),
            loan_purpose=data.get("loan_purpose", "Not specified")
        )
        Database.save_borrower(borrower)
        assessment = await _run_assessment_core(
            borrower=borrower,
            requested_duration_days=30,
            assessment_source="SMS",
            consent_event_id=session.get("consent_event_id"),
            consent_channel=session.get("consent_channel"),
            consent_timestamp=session.get("consent_timestamp")
        )
        Database.save_assessment(assessment)

        decision = str(assessment.decision)
        upload_link = "https://yourdomain.com/borrower/u"
        if decision in ["APPROVE", "CONDITIONAL"]:
            out = (
                f"{decision}: Approved for {borrower.loan_amount_requested:.0f}. "
                f"Recommended {assessment.recommended_amount:.0f} at {assessment.recommended_interest_rate}% for "
                f"{assessment.recommended_duration_days or 30} days. "
                f"To strengthen your profile, upload documents: {upload_link}"
            )
        elif decision == "REFER":
            out = f"We need more information. Upload documents here: {upload_link}"
        else:
            out = f"Not approved at this time. You may reapply after 30 days. Upload documents to improve eligibility: {upload_link}"

        SMSService.send_sms(phone, out)
        session.update({"assessment_id": assessment.assessment_id})
        Database.save_channel_session(session_id, session)
        return {"status": "OK", "message": "Assessment completed", "assessment_id": assessment.assessment_id}

    # Send next prompt
    SMSService.send_sms(phone, reply)
    return {"status": "OK", "message": "Step updated", "next": step}


@app.post("/channels/ussd")
async def ussd_inbound(payload: Dict[str, Any] = Body(...), user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Inbound USSD webhook (provider-agnostic).
    Expects: sessionId, phoneNumber, text (USSD input chain).
    """
    session_id_raw = payload.get("sessionId") or payload.get("session_id") or payload.get("session")
    raw_phone = payload.get("phoneNumber") or payload.get("phone") or payload.get("msisdn")
    full_text = (payload.get("text") or "").strip()
    if not session_id_raw or not raw_phone:
        raise HTTPException(status_code=400, detail="Missing sessionId or phoneNumber")

    phone = normalize_phone(raw_phone)
    session_id = f"USSD:{user.organization_id}:{session_id_raw}"
    session = Database.get_channel_session(session_id) or {
        "session_id": session_id,
        "channel": "USSD",
        "organization_id": user.organization_id,
        "phone": phone,
        "step": "CONSENT",
        "data": {},
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    last_input = full_text.split("*")[-1] if full_text else ""
    step = session.get("step", "CONSENT")
    data = session.get("data", {})

    if step == "CONSENT":
        if not last_input:
            msg = "CON Welcome to Loan Officer AI\n1. Agree & Continue\n2. Exit"
            Database.save_channel_session(session_id, session)
            return PlainTextResponse(msg)
        if last_input not in ["1", "yes", "YES", "Y"]:
            msg = "END Thank you."
            Database.save_channel_session(session_id, session)
            return PlainTextResponse(msg)
        if not session.get("consent_event_id"):
            consent_event_id = f"CNS-{uuid.uuid4().hex[:10].upper()}"
            consent_time = datetime.now(timezone.utc).isoformat()
            Database.save_consent_event(consent_event_id, {
                "consent_event_id": consent_event_id,
                "organization_id": user.organization_id,
                "channel": "USSD",
                "phone": phone,
                "session_id": session_id,
                "consent_text": last_input,
                "consent_timestamp": consent_time
            })
            session.update({
                "consent_event_id": consent_event_id,
                "consent_timestamp": consent_time,
                "consent_channel": "USSD"
            })
        step = "NAME"
        msg = "CON Enter full name:"
    elif step == "NAME":
        data["name"] = clean_name(last_input)
        step = "INCOME"
        msg = "CON Monthly income (numbers only):"
    elif step == "INCOME":
        val = parse_float_or_none(last_input)
        if val is None:
            msg = "CON Invalid income. Enter monthly income:"
        else:
            data["monthly_income"] = val
            step = "EXPENSES"
            msg = "CON Monthly expenses (numbers only):"
    elif step == "EXPENSES":
        val = parse_float_or_none(last_input)
        if val is None:
            msg = "CON Invalid expenses. Enter monthly expenses:"
        else:
            data["monthly_expenses"] = val
            step = "DEBT"
            msg = "CON Existing debt (numbers only, 0 if none):"
    elif step == "DEBT":
        val = parse_float_or_none(last_input)
        if val is None:
            msg = "CON Invalid debt. Enter existing debt:"
        else:
            data["existing_debt"] = val
            step = "AMOUNT"
            msg = "CON Requested loan amount:"
    elif step == "AMOUNT":
        val = parse_float_or_none(last_input)
        if val is None:
            msg = "CON Invalid amount. Enter loan amount:"
        else:
            data["loan_amount_requested"] = val
            step = "PURPOSE"
            msg = "CON Loan purpose:"
    elif step == "PURPOSE":
        data["loan_purpose"] = last_input or "Not specified"
        step = "DONE"
        msg = "END Thank you. Processing your assessment."
    else:
        msg = "END Session ended."

    session.update({"step": step, "data": data, "updated_at": datetime.now(timezone.utc).isoformat()})
    Database.save_channel_session(session_id, session)

    if step == "DONE":
        borrower_id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        borrower = Borrower(
            id=borrower_id,
            organization_id=user.organization_id,
            name=data.get("name", "Borrower"),
            phone=phone,
            employment_type="trader",
            monthly_income=data.get("monthly_income", 0.0),
            monthly_expenses=data.get("monthly_expenses", 0.0),
            existing_debt=data.get("existing_debt", 0.0),
            loan_amount_requested=data.get("loan_amount_requested", 0.0),
            loan_purpose=data.get("loan_purpose", "Not specified")
        )
        Database.save_borrower(borrower)
        assessment = await _run_assessment_core(
            borrower=borrower,
            requested_duration_days=30,
            assessment_source="USSD",
            consent_event_id=session.get("consent_event_id"),
            consent_channel=session.get("consent_channel"),
            consent_timestamp=session.get("consent_timestamp")
        )
        Database.save_assessment(assessment)
        session.update({"assessment_id": assessment.assessment_id})
        Database.save_channel_session(session_id, session)

    return PlainTextResponse(msg)
# ============================================================================
# ASYNC DOCUMENT INGESTION (Robust, Idempotent, Webhook-Ready)
# ============================================================================

async def _run_document_ingestion_job(
    job_id: str,
    borrower_id: str,
    org_id: str,
    filename: str,
    content: bytes
):
    job = Database.get_ingestion_job(job_id) or {}
    job.update({
        "status": "PROCESSING",
        "updated_at": datetime.now(timezone.utc).isoformat()
    })
    Database.save_ingestion_job(job_id, job)

    try:
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise ValueError("Borrower not found for ingestion job.")

        parser = TransactionParser()
        extraction_result = parser.parse(content, filename)
        transactions = extraction_result.transactions

        if not transactions:
            job.update({
                "status": "FAILED",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "error": "No transactions extracted.",
                "warnings": extraction_result.warnings,
                "document_type": str(extraction_result.document_type),
                "quality_score": extraction_result.quality_score
            })
            Database.save_ingestion_job(job_id, job)
            org = Database.get_organization(org_id)
            WebhookService.send_event(org, "document.ingestion.failed", job)
            return

        # Behavioral analysis + full assessment
        from agents.behavioral_agent_v2 import BehavioralAgentV2
        behavioral_results = BehavioralAgentV2.analyze_transactions(
            transactions,
            statement_summary=extraction_result.bank_statement_summary
        )

        doc_info = {
            "document_type": str(extraction_result.document_type),
            "quality_score": extraction_result.quality_score,
            "warnings": extraction_result.warnings,
            "source": "USER_UPLOADED_STATEMENT",
            "ingestion_job_id": job_id
        }
        assessment = await _run_assessment_core(
            borrower=borrower,
            requested_duration_days=30,
            external_behavioral_results=behavioral_results,
            statement_summary=(
                extraction_result.bank_statement_summary
                or extraction_result.payslip_summary
                or extraction_result.nrc_summary
            ),
            assessment_source="ASYNC_INGEST",
            data_quality_score=extraction_result.quality_score,
            document_info=doc_info
        )

        assessment.metrics = assessment.metrics or {}
        assessment.metrics["document_summaries"] = build_document_summaries([extraction_result])
        if extraction_result.bank_statement_summary:
            assessment.metrics["summary_profile"] = extraction_result.bank_statement_summary.summary_profile
        elif extraction_result.payslip_summary:
            assessment.metrics["summary_profile"] = extraction_result.payslip_summary.summary_profile
        elif extraction_result.nrc_summary:
            assessment.metrics["summary_profile"] = extraction_result.nrc_summary.summary_profile

        Database.save_assessment(assessment)

        job.update({
            "status": "COMPLETED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "document_type": str(extraction_result.document_type),
            "quality_score": extraction_result.quality_score,
            "transaction_count": len(transactions),
            "assessment_id": assessment.assessment_id,
            "decision": str(assessment.decision),
            "risk_score": assessment.risk_score
        })
        Database.save_ingestion_job(job_id, job)

        org = Database.get_organization(org_id)
        WebhookService.send_event(org, "document.ingestion.completed", job)
        WebhookService.send_event(org, "assessment.completed", augment_assessment_payload(assessment.model_dump()))
    except Exception as e:
        job.update({
            "status": "FAILED",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        })
        Database.save_ingestion_job(job_id, job)
        org = Database.get_organization(org_id)
        WebhookService.send_event(org, "document.ingestion.failed", job)


@app.post("/documents/upload-async", tags=["Alternative Data"])
async def documents_upload_async(
    borrower_id: str = Form(...),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """
    Async document ingestion. Returns a job_id immediately and processes in background.
    """
    borrower = Database.get_borrower(borrower_id)
    if not borrower or borrower.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Borrower not found.")

    if idempotency_key:
        existing = Database.get_ingestion_job_by_idempotency_key(user.organization_id, idempotency_key)
        if existing:
            return existing

    job_id = f"JOB-{uuid.uuid4().hex[:10].upper()}"
    content = await file.read()

    job = {
        "job_id": job_id,
        "borrower_id": borrower_id,
        "organization_id": user.organization_id,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "filename": file.filename,
        "idempotency_key": idempotency_key
    }
    Database.save_ingestion_job(job_id, job)

    if background_tasks is not None:
        background_tasks.add_task(
            _run_document_ingestion_job,
            job_id,
            borrower_id,
            user.organization_id,
            file.filename,
            content
        )

    return job


@app.get("/documents/upload-status/{job_id}", tags=["Alternative Data"])
async def documents_upload_status(
    job_id: str,
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    job = Database.get_ingestion_job(job_id)
    if not job or job.get("organization_id") != user.organization_id:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job

# ============================================================================
# B2B DASHBOARD ENDPOINTS (PARTNER CONSOLE)
# ============================================================================

@app.post("/auth/login", response_model=Dict[str, str])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint for Dashboard Users (JWT).
    """
    logger.info(f"[LOGIN] ATTEMPT: {form_data.username}")
    user = await AuthAgent.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.error(f"[LOGIN] FAILED: auth_agent returned None for {form_data.username}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"✅ LOGIN SUCCESS: {user.email} ({user.role})")
    
    # 3. Create JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user.email, "role": str(user.role.value if hasattr(user.role, 'value') else user.role), "org": str(user.organization_id)}
    logger.info(f"[LOGIN] Creating token for: {token_data}")
    access_token = AuthAgent.create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    AuditAgent.log_event("DASHBOARD_LOGIN", str(user.role), {"user_id": user.id, "org": user.organization_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def read_users_me(request: Request):
    """
    Returns the current authenticated user's profile.
    Wrapped with try-except for better error diagnostics.
    """
    try:
        # Manually extract token from header
        auth_header = request.headers.get("Authorization", "")
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        
        if not token:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="No Bearer token found in Authorization header",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        current_user = await AuthAgent.get_current_user(token)
        return current_user
    except HTTPException:
        # Re-raise HTTPExceptions (401, 403, etc.)
        raise
    except Exception as e:
        import traceback
        error_detail = f"Auth processing failed: {str(e)}"
        logger.error(f"[AUTH/ME ERROR] {error_detail}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

# --- API KEY MANAGEMENT ---

@app.get("/api-keys", response_model=List[APIKey])
async def list_api_keys(current_user: User = Depends(AuthAgent.get_current_user)):
    """List all API keys for the user's organization."""
    return Database.list_api_keys(current_user.organization_id)

@app.post("/api-keys/create")
async def create_api_key(
    name: str = Body(..., embed=True),
    environment: str = Body(..., embed=True),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """Generate a new API Key (returned once)."""
    if current_user.role not in ["ORG_ADMIN", "DEVELOPER", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
        
    raw_key, key_record = AuthAgent.create_api_key(
        organization_id=current_user.organization_id,
        name=name,
        env=environment,
        created_by=current_user.id
    )
    
    # KEY_CREATE is already logged inside AuthAgent.create_api_key
    
    return {
        "api_key": raw_key,
        "key_record": key_record
    }

@app.post("/api-keys/revoke")
async def revoke_api_key(
    key_hash: str = Body(..., embed=True),
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """Revoke an API Key."""
    if current_user.role not in ["ORG_ADMIN", "DEVELOPER", "SUPER_ADMIN"]:
         raise HTTPException(status_code=403, detail="Insufficient permissions to revoke keys")
         
    key_record = Database.get_api_key(key_hash)
    if not key_record:
        raise HTTPException(status_code=404, detail="Key not found")
        
    if key_record.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    key_record.status = KeyStatus.REVOKED
    Database.save_api_key(key_record)
    
    AuditAgent.log_event("KEY_REVOKE", current_user.email, {"key_prefix": key_record.key_prefix, "org_id": current_user.organization_id})
    return {"status": "REVOKED"}

# --- DASHBOARD METRICS ---

# ============================================================================
# DOCUMENTATION VIEWER
# ============================================================================

@app.get("/documentation")
async def documentation_index():
    """Documentation hub - list all available documentation pages."""
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Loan Officer AI - Developer Documentation</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 40px 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }
            .header h1 { font-size: 2.5em; margin-bottom: 10px; }
            .header p { font-size: 1.2em; opacity: 0.9; }
            .content { padding: 40px; }
            .docs-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }
            .doc-card {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                padding: 20px;
                transition: all 0.3s ease;
                text-decoration: none;
                color: inherit;
                display: block;
            }
            .doc-card:hover {
                border-color: #667eea;
                box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
                transform: translateY(-2px);
            }
            .doc-card h3 {
                color: #667eea;
                margin-bottom: 10px;
                font-size: 1.3em;
            }
            .doc-card p {
                color: #666;
                font-size: 0.95em;
            }
            .quick-links {
                background: #f8f9fa;
                padding: 30px;
                border-radius: 8px;
                margin-bottom: 30px;
            }
            .quick-links h2 {
                margin-bottom: 15px;
                color: #333;
            }
            .quick-links a {
                display: inline-block;
                margin: 5px 10px 5px 0;
                padding: 8px 16px;
                background: #667eea;
                color: white;
                text-decoration: none;
                border-radius: 20px;
                font-size: 0.9em;
                transition: background 0.3s;
            }
            .quick-links a:hover {
                background: #5568d3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📚 Developer Documentation</h1>
                <p>Comprehensive guides for the Loan Officer AI Agent</p>
            </div>
            <div class="content">
                <div class="quick-links">
                    <h2>Quick Links</h2>
                    <a href="/docs">Swagger UI (Interactive API)</a>
                    <a href="/redoc">ReDoc (API Reference)</a>
                    <a href="/api/health">Health Check</a>
                </div>
                
                <h2 style="margin-bottom: 20px;">Documentation Pages</h2>
                <div class="docs-grid">
                    <a href="/documentation/getting-started" class="doc-card">
                        <h3>Getting Started</h3>
                        <p>Installation, setup, and your first API request</p>
                    </a>
                    
                    <a href="/documentation/api-reference" class="doc-card">
                        <h3>API Reference</h3>
                        <p>Complete endpoint documentation with examples</p>
                    </a>
                    
                    <a href="/documentation/architecture" class="doc-card">
                        <h3>Architecture Guide</h3>
                        <p>System design and multi-agent workflow</p>
                    </a>
                    
                    <a href="/documentation/agents" class="doc-card">
                        <h3>Agent System</h3>
                        <p>Deep dive into all 9 agents</p>
                    </a>
                    
                    <a href="/documentation/integration" class="doc-card">
                        <h3>Integration Guide</h3>
                        <p>Frontend/backend integration examples</p>
                    </a>
                    
                    <a href="/documentation/testing" class="doc-card">
                        <h3>Testing Guide</h3>
                        <p>Testing strategies and examples</p>
                    </a>
                    
                    <a href="/documentation/deployment" class="doc-card">
                        <h3>Deployment Guide</h3>
                        <p>Production deployment instructions</p>
                    </a>
                    
                    <a href="/documentation/troubleshooting" class="doc-card">
                        <h3>Troubleshooting</h3>
                        <p>Common issues and solutions</p>
                    </a>
                    
                    <a href="/documentation/CONTRIBUTING" class="doc-card">
                        <h3>Contributing</h3>
                        <p>How to contribute to the project</p>
                    </a>
                </div>
                
                <hr style="margin: 40px 0; border: none; border-top: 2px solid #e0e0e0;">
                
                <h2 style="margin-bottom: 20px; color: #764ba2;">Customer Documentation</h2>
                <div class="docs-grid">
                    <a href="/documentation/user-guide" class="doc-card">
                        <h3>MFI Staff Guide</h3>
                        <p>How to process loans and use the dashboard</p>
                    </a>
                    
                    <a href="/documentation/borrower-guide" class="doc-card">
                        <h3>Borrower Guide</h3>
                        <p>How to apply for a loan step-by-step</p>
                    </a>
                    
                    <a href="/documentation/customer-api-setup" class="doc-card">
                        <h3>API Setup Guide</h3>
                        <p>Integration guide for your IT team</p>
                    </a>
                    
                    <a href="/documentation/faq" class="doc-card">
                        <h3>FAQ</h3>
                        <p>Answers to common questions</p>
                    </a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/documentation/{doc_name}")
async def view_documentation(doc_name: str):
    """View a specific documentation page rendered as HTML."""
    try:
        import markdown2
    except ImportError:
        return HTMLResponse(content="<h1>Error: markdown2 not installed. Run: pip install markdown2</h1>")
    
    docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
    doc_file = os.path.join(docs_dir, f"{doc_name}.md")
    
    if not os.path.exists(doc_file):
        raise HTTPException(status_code=404, detail="Documentation page not found")
    
    with open(doc_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    html_content = markdown2.markdown(markdown_content, extras=['fenced-code-blocks', 'tables', 'header-ids'])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{doc_name.replace('-', ' ').title()} - Loan Officer AI Documentation</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #333;
                background: #f5f5f5;
            }}
            .nav {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .nav a {{
                color: white;
                text-decoration: none;
                margin-right: 20px;
                opacity: 0.9;
                transition: opacity 0.3s;
            }}
            .nav a:hover {{ opacity: 1; }}
            .container {{
                max-width: 900px;
                margin: 40px auto;
                background: white;
                padding: 60px;
                border-radius: 8px;
                box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            }}
            h1 {{ color: #667eea; margin-bottom: 20px; border-bottom: 3px solid #667eea; padding-bottom: 10px; }}
            h2 {{ color: #764ba2; margin-top: 40px; margin-bottom: 15px; }}
            h3 {{ color: #555; margin-top: 30px; margin-bottom: 10px; }}
            code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }}
            pre {{
                background: #2d2d2d;
                color: #f8f8f2;
                padding: 20px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 20px 0;
            }}
            pre code {{
                background: none;
                color: inherit;
                padding: 0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background: #667eea;
                color: white;
            }}
            a {{ color: #667eea; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            blockquote {{
                border-left: 4px solid #667eea;
                padding-left: 20px;
                margin: 20px 0;
                color: #666;
                font-style: italic;
            }}
            hr {{
                border: none;
                border-top: 2px solid #e0e0e0;
                margin: 40px 0;
            }}
        </style>
    </head>
    <body>
        <div class="nav">
            <a href="/documentation">← Back to Docs</a>
            <a href="/docs">Swagger UI</a>
            <a href="/">Home</a>
        </div>
        <div class="container">
            {html_content}
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

def _should_serve_spa_fallback(request: Request) -> bool:
    if request.scope.get("state", {}).get("api_prefixed"):
        return False

    accept_header = request.headers.get("accept", "")
    fetch_destination = request.headers.get("sec-fetch-dest", "")
    return "text/html" in accept_header or fetch_destination == "document"


# Catch-all for React Router (must be at the bottom)
@app.get("/{full_path:path}")
async def catch_all(full_path: str, request: Request):
    # Prevent API typos (e.g. /api/api/...) from silently returning index.html.
    # Those should fail as API 404s so the client can surface a real error.
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")

    # 1. Try serving from frontend/dist
    if os.path.exists(frontend_dist):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        if _should_serve_spa_fallback(request):
            return FileResponse(os.path.join(frontend_dist, "index.html"))
        raise HTTPException(status_code=404, detail="Not Found")

    # 2. Try serving from project root (Legacy)
    file_path = os.path.join(static_path, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path) and _should_serve_spa_fallback(request):
        return FileResponse(index_path)

    if index_path and os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="Not Found")

    return {"message": "Frontend not deployed. Please run 'npm run build' in the frontend directory."}

if __name__ == "__main__":
    import uvicorn
    import sys
    port = 8000
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    # Use 'api:app' string for reload support
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
