import uuid
from fastapi import FastAPI, HTTPException, Body, Depends, Security, UploadFile, File, Form, Request, Header, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Dict, List, Optional, Any
import io
import json
import hashlib
import secrets
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
from models.unified_profile import UnifiedFinancialProfile, AssessmentReadiness
from models.sms_log import SMSLog
from models.follow_up_task import FollowUpTask, FollowUpStatus
from services.sms_service import SMSService
from services.email_service import EmailService
from services.webhook_service import WebhookService
from utils.validators import normalize_phone, clean_name

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, PlainTextResponse
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
            summaries.append({
                "summary_profile": result.bank_statement_summary.summary_profile,
                "closing_balance": result.bank_statement_summary.closing_balance,
                "statement_period": result.bank_statement_summary.statement_period.model_dump()
                if result.bank_statement_summary.statement_period else None,
                "bank_name": result.bank_statement_summary.bank_name,
                "account_holder_name": result.bank_statement_summary.account_holder_name,
                "currency": result.bank_statement_summary.currency,
                "risk_flags": result.bank_statement_summary.risk_flags,
                "quality_score": result.quality_score,
                "raw_text_preview": result.raw_text_preview
            })
        if result.payslip_summary:
            summaries.append({
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
                "quality_score": result.quality_score,
                "raw_text_preview": result.raw_text_preview
            })
        if result.nrc_summary:
            summaries.append({
                "summary_profile": result.nrc_summary.summary_profile,
                "full_name": result.nrc_summary.full_name,
                "id_number": result.nrc_summary.id_number,
                "date_of_birth": result.nrc_summary.date_of_birth,
                "gender": result.nrc_summary.gender,
                "risk_flags": result.nrc_summary.risk_flags,
                "quality_score": result.quality_score,
                "raw_text_preview": result.raw_text_preview
            })
    return summaries


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
    
    for doc in loan_docs:
        try:
            l_data = doc.to_dict()
            status = l_data.get("status")
            amount = l_data.get("amount", 0.0)
            disbursed_at_val = l_data.get("disbursed_at")
            
            # Parse disbursed_at
            disbursed_dt = None
            if disbursed_at_val:
                if isinstance(disbursed_at_val, datetime):
                    disbursed_dt = disbursed_at_val
                elif isinstance(disbursed_at_val, str):
                    try:
                        disbursed_dt = datetime.fromisoformat(disbursed_at_val.replace('Z', '+00:00'))
                    except: pass
            
            # Exclusion: PENDING_DISBURSEMENT is not considered "disbursed" yet
            if status == "PENDING_DISBURSEMENT":
                continue

            # KPI 1: Lifetime Disbursed Volume (Actual Full Amount)
            # KPI 2: Current Active Snapshot
            disbursed_volume += float(amount)
            if status in ["DISBURSED", "ACTIVE"]:
                active_count += 1
                if disbursed_dt:
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
    
    par_base = active_count if active_count > 0 else 1
    return {
        "total_assessments": filtered_asmt_count,
        "active_loans": active_count,
        "disbursed_volume": round(disbursed_volume, 2),
        "default_rate": round(default_rate, 1),
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
        risk_results = RiskAgent.evaluate(borrower, external_behavioral_results=external_results)

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
    async def parse_upload(file_obj: UploadFile):
        if not file_obj: return []
        content = await file_obj.read()
        try:
            result = tx_parser.parse(content, file_obj.filename)
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
    
    res_bank = await parse_upload(bank_statement)
    if res_bank: extraction_results.append(res_bank)
    
    res_momo = await parse_upload(mobile_money_statement)
    if res_momo: extraction_results.append(res_momo)

    res_nrc = await parse_upload(nrc_id)
    if res_nrc: extraction_results.append(res_nrc)

    res_payslip = await parse_upload(payslip)
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
    
    if unified_profile.assessment_readiness == AssessmentReadiness.BLOCKED:
        error_msg = "Assessment Blocked: " + "; ".join(unified_profile.blocking_reasons)
        raise HTTPException(
            status_code=400,
            detail={
                "message": error_msg,
                "blocking_reasons": unified_profile.blocking_reasons,
                "missing_documents": unified_profile.document_coverage.missing_required_documents,
                "incomplete_documents": unified_profile.document_coverage.incomplete_documents,
                "borrower_id": borrower_id
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
            extra_data={"phone_number": phone_number}
        )
        return payment_init
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
    payments = Database.list_payments(current_user.organization_id)
    return sorted(payments, key=lambda x: x.timestamp, reverse=True)

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
    user: User = Depends(get_dashboard_user)
):
    if user.role not in ["OFFICER", "ORG_ADMIN"]:
        raise HTTPException(status_code=403, detail="Officer or Admin access required")
    
    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    if loan.organization_id != user.organization_id and user.organization_id != "PLATFORM_OWNER":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    if loan.status != LoanStatus.PENDING_DISBURSEMENT:
        raise HTTPException(status_code=400, detail=f"Loan is in {loan.status} state, cannot disburse.")

    loan.status = LoanStatus.DISBURSED
    loan.disbursed_at = datetime.now()
    loan.amount = amount # Allow slight adjustment if needed at point of sale
    loan.disbursement_method = method
    loan.disbursement_reference = reference
    loan.disbursed_by = user.email
    
    Database.save_loan(loan)
    AuditAgent.log_event("LOAN_DISBURSED_MANUAL", user.role, {
        "loan_id": loan.loan_id, 
        "amount": amount, 
        "method": method,
        "ref": reference
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
    if values:
        validate_policy_values(values)
    draft = create_policy_draft(current_user.organization_id, current_user.email, values)
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
    if values:
        validate_policy_values(values)
    version = update_policy_draft(version_id, current_user.organization_id, current_user.email, values)
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
    version = set_policy_status(version_id, current_user.organization_id, "SUBMITTED", current_user.email)
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
    version = set_policy_status(version_id, current_user.organization_id, "APPROVED", current_user.email)
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
    version = activate_policy_version(version_id, current_user.organization_id, current_user.email)
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
    Records a final human decision for an assessment.
    This does not change the AI recommendation but represents the institution's official verdict.
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

    # 3. Handle Decision Logic & Override Detection
    officer_decision = action_data.get("officer_decision")
    final_amount = action_data.get("final_amount", assessment.recommended_amount)
    final_duration = action_data.get("final_duration", assessment.recommended_duration_days)
    final_rate = action_data.get("final_interest_rate", assessment.recommended_interest_rate)

    is_override = (
        officer_decision != assessment.decision or
        abs((final_amount or 0) - (assessment.recommended_amount or 0)) > 0.01 or
        final_duration != assessment.recommended_duration_days
    )
    if is_override:
        if not action_data.get("officer_notes") or not str(action_data.get("officer_notes")).strip():
            raise HTTPException(status_code=400, detail="Override requires officer_notes for audit compliance.")
        if not action_data.get("override_reason_code") or not str(action_data.get("override_reason_code")).strip():
            raise HTTPException(status_code=400, detail="Override requires override_reason_code for audit compliance.")

    # 4. Create Action Metadata
    try:
        current_time = datetime.now(timezone.utc)
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
            "borrower_message": action_data.get("borrower_message"),
            "communication_channel": action_data.get("communication_channel", CommChannel.NONE),
            "created_at": current_time,
            "sealed_at": current_time.isoformat(), # Keep for legacy/frontend
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

    # 6. Seal Assessment
    assessment.final_decision_metadata = action
    Database.save_assessment(assessment)

    # 6.5 Create Loan Record if Approved (Pending Disbursement)
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

    # 7. Audit
    client_ip = request.client.host if request and request.client else "unknown"
    AuditAgent.log_event("FINAL_HUMAN_DECISION_SEALED", user.email, {
        "assessment_id": assessment_id,
        "decision": officer_decision,
        "is_override": is_override,
        "override_reason_code": action_data.get("override_reason_code"),
        "ip": client_ip,
        "org": user.organization_id
    })

    # 8. Auto-generate decision exports (best-effort)
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
    AuditAgent.log_event("BORROWER_SMS_SENT", user.email, {
        "assessment_id": assessment_id,
        "status": result["status"],
        "environment": result["environment"],
        "provider": "AfricaTalking"
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
    due_date = payload.get("due_date")

    task = FollowUpTask(
        task_id=f"FUP-{uuid.uuid4().hex[:10].upper()}",
        assessment_id=assessment_id,
        borrower_id=assessment.borrower_id,
        organization_id=assessment.organization_id,
        note=note,
        due_date=due_date,
        status=FollowUpStatus.OPEN,
        created_by=user.email or user.id
    )
    Database.save_follow_up_task(task)
    AuditAgent.log_event("FOLLOW_UP_TASK_CREATED", user.email, {
        "assessment_id": assessment_id,
        "task_id": task.task_id,
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
        behavioral_results = BehavioralAgentV2.analyze_transactions(extraction_result.transactions)
        
        # Run full risk assessment
        risk_results = RiskAgent.evaluate(borrower, external_behavioral_results=behavioral_results)
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
        behavioral_results = BehavioralAgentV2.analyze_transactions(transactions)
        
        # 4. Risk Assessment (With Impact Caps)
        risk_results = RiskAgent.evaluate(borrower, external_behavioral_results=behavioral_results)
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
        behavioral_results = BehavioralAgentV2.analyze_transactions(transactions)

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

# Catch-all for React Router (must be at the bottom)
@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    # Skip API/Auth/Docs
    # Skip API/Auth/Docs/etc. to allow 404s for missing API paths
    api_prefixes = ["api", "auth", "docs", "openapi", "billing", "admin/platform", "org", "borrower", "assessment", "loan"]
    if any(full_path.startswith(p) for p in api_prefixes):
        # But wait, if it's the Admin Dashboard path (no /api), we want index.html
        # Only block if it's a specific API endpoint or a missing asset
        if not full_path.endswith(".js") and not full_path.endswith(".css"):
             # If it's a known API prefix but NOT an actual route, we'll let it 404 below
             pass
    
    # 1. Try serving from frontend/dist
    if os.path.exists(frontend_dist):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))
    
    # 2. Try serving from project root (Legacy)
    file_path = os.path.join(static_path, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
        
    return {"message": "Frontend not deployed. Please run 'npm run build' in the frontend directory."}

if __name__ == "__main__":
    import uvicorn
    import sys
    port = 8000
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        port = int(sys.argv[2])
    # Use 'api:app' string for reload support
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=True)
