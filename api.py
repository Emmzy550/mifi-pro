import uuid
from fastapi import FastAPI, HTTPException, Body, Depends, Security, UploadFile, File, Form, Request, Header
from typing import Dict, List, Optional, Any
import io
from datetime import datetime, timedelta, timezone

from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from models.borrower import Borrower
from models.assessment import Assessment
from models.loan import Loan, LoanStatus
from models.alternative_data import AlternativeData
from models.organization import Organization, BillingPlan, BillingStatus, OrgEnvironment
from models.api_key import APIKey, KeyStatus
from models.user import User
from models.officer_action import OfficerAction, OfficerDecision, CommChannel
from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from agents.query_agent import QueryAgent
from agents.auth_agent import AuthAgent, AuthUser, ACCESS_TOKEN_EXPIRE_MINUTES, get_super_admin
from agents.audit_agent import AuditAgent
from agents.self_healing_agent import SelfHealingAgent
from utils.db import Database
from utils.pdf_parser import PDFTransactionParser, parse_simple_csv_format
from utils.transaction_parser import TransactionParser
from models.sms_log import SMSLog
from services.sms_service import SMSService

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
import os

# PDF parsing
try:
    import PyPDF2
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("WARNING: PyPDF2 not installed. PDF upload will not work. Install with: pip install PyPDF2")

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

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    print(f"STARTUP: FRONTEND: Serving from {frontend_dist}")
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    print(f"WARNING: FRONTEND: {frontend_dist} not found. Using root legacy mode.")
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
    print(f"DEBUG: Found {len(orgs)} orgs, {len(loans)} loans, {len(assessments)} assessments")
    
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
        "customer_message", "created_at"
    }
    
    # 2. OFFICER VIEW
    # Add metrics and professional rationale.
    officer_fields = public_fields | {
        "risk_level", "risk_score", "officer_view", "internal_notes", 
        "flags", "metrics", "blocking_factors"
    }
    
    # 3. AUDIT/ADMIN VIEW (Full Transparency)
    # Policy lineage, capacity anchors, and decision metadata.
    audit_fields = officer_fields | {
        "audit_view", "explanation", "explanation_source", "decision_source",
        "policy_version", "observed_deposit_volume", "transaction_count",
        "history_days", "policy_cap_amount", "policy_cap_reason",
        "capacity_based_max", "capacity_multiplier_used", "starter_loan_applied",
        "ml_advisory_only", "ml_attempted_override", "decision_metadata"
    }
    
    target_fields = public_fields
    if role in ["OFFICER", "API_USER", "BORROWER_PORTAL_ADMIN"]:
        target_fields = officer_fields
    if role in ["SUPER_ADMIN", "ADMIN", "COMPLIANCE"]:
        target_fields = audit_fields
        
    return {k: v for k, v in total_data.items() if k in target_fields}

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
            print(f"DEBUG: JWT auth failed: {e}")
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
            print(f"DEBUG: API Key auth failed: {e}")
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
    total_loans = 0
    disbursed_volume = 0.0
    
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
            
            # Time filter check
            is_in_range = False
            if disbursed_dt:
                ref_dt = disbursed_dt.replace(tzinfo=None) if disbursed_dt.tzinfo else disbursed_dt
                if ref_dt >= cutoff_date:
                    is_in_range = True
            
            if is_in_range:
                if status not in ["REPAID", "CANCELLED"]:
                    active_count += 1
                if status == "DEFAULTED":
                    default_count += 1
                total_loans += 1
                disbursed_volume += amount
        except: continue
        
    default_rate = (default_count / total_loans * 100) if total_loans > 0 else 0.0
    
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
    
    return {
        "total_assessments": filtered_asmt_count,
        "active_loans": active_count,
        "disbursed_volume": round(disbursed_volume, 2),
        "default_rate": round(default_rate, 1),
        "risk_distribution": risk_distribution,
        "decision_trends": decision_trends,
        "alerts": alerts
    }

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
        print(f"ERROR in intake_start: {e}\n{traceback.format_exc()}")
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
    - Calculates risk score (0-100, lower is better)
    - Provides AI recommendation (APPROVED/CONDITIONAL_APPROVAL/REJECT)
    - Generates detailed explanation of the decision
    
    **Assessment includes:**
    - Debt-to-income ratio analysis
    - Affordability calculations
    - Income stability evaluation
    - Alternative data analysis (if uploaded)
    - ML probability score (if enabled)
    
    **Returns:**
    - `risk_score`: 0-100 (0-40=LOW, 41-70=MEDIUM, 71-100=HIGH)
    - `decision`: APPROVED, CONDITIONAL_APPROVAL, or REJECT
    - `recommended_amount`: Suggested loan amount
    - `recommended_interest_rate`: Suggested interest rate (%)
    - `explanation`: Detailed reasoning for the decision
    
    **Authentication:** API Key Required
    
    **Processing time:** 2-3 seconds
    """
)
async def assessment_run(
    borrower_id: str = Body(..., embed=True, example="BOR-A1B2C3D4"),
    requested_duration_days: int = Body(30, embed=True, example=60),
    mobile_money_history: Optional[List[Dict[str, Any]]] = Body(None),
    utility_history: Optional[List[Dict[str, Any]]] = Body(None),
    airtime_usage_avg: Optional[float] = Body(None),
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """
    Runs the full analysis pipeline for a borrower with billing metering.
    """
    # 1. Get borrower and context
    borrower = Database.get_borrower(borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found. Please run /intake/start first.")
    
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
    Database.save_assessment(assessment)
    BillingAgent.meter_usage(
        org=org, 
        environment=user.environment, 
        api_key_id="API_KEY",
        endpoint="/assessment/run",
        assessment_id=assessment.assessment_id
    )

    return assessment

async def _run_assessment_core(
    borrower: Borrower,
    requested_duration_days: int,
    mobile_money_history: Optional[List[Dict[str, Any]]] = None,
    utility_history: Optional[List[Dict[str, Any]]] = None,
    airtime_usage_avg: Optional[float] = None,
    assessment_source: str = "API"
) -> Assessment:
    """
    Internal shared logic for running a credit assessment.
    Ensures identical results across all entry points.
    """
    # INSTANT DATA preparation
    external_results = None
    if mobile_money_history is not None or utility_history is not None:
        external_results = {
            "transactions": mobile_money_history or [],
            "utility_history": utility_history or [],
            "airtime_usage_avg": airtime_usage_avg or 0.0,
            "behavioral_stability": 0.7, 
            "saving_trend": 0.7,
            "utility_compliance": 0.7,
            "early_warnings": []
        }

    # 1. Evaluate Risk
    risk_results = RiskAgent.evaluate(borrower, external_behavioral_results=external_results)
    
    # 2. Recommmend Decision
    decision_results = DecisionAgent.recommend(risk_results, borrower, requested_duration_days)
    
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

    assessment = Assessment(
        assessment_id=f"ASMT-{uuid.uuid4().hex[:8].upper()}",
        borrower_id=borrower.id,
        organization_id=borrower.organization_id,
        requested_amount=borrower.loan_amount_requested,
        requested_duration_days=requested_duration_days,
        decision_timestamp=decision_timestamp,
        decision_reason_codes=reason_codes,
        data_used=data_used,
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

    # 2. Create Borrower
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
        loan_purpose=loan_purpose or "Not Specified"
    )
    Database.save_borrower(borrower)

    # 3. Parse Transactions (Evidence Handling)
    tx_parser = TransactionParser()
    all_parsed_transactions = []
    
    # Helper to parse upload files
    async def parse_upload(file_obj: UploadFile):
        if not file_obj: return []
        content = await file_obj.read()
        try:
            return tx_parser.parse(content, file_obj.filename)
        except Exception as e:
            print(f"WARN: Failed to parse {file_obj.filename}: {e}")
            return []

    # Parse primary statements
    bank_tx = await parse_upload(bank_statement)
    momo_tx = await parse_upload(mobile_money_statement)
    all_parsed_transactions.extend(bank_tx)
    all_parsed_transactions.extend(momo_tx)

    # 4. Run Core Assessment
    # Convert Transaction objects to Dicts for the core agent
    history_dicts = []
    for tx in all_parsed_transactions:
        history_dicts.append({
            "transaction_id": tx.transaction_id,
            "amount": tx.amount,
            "type": tx.type,
            "timestamp": tx.date.isoformat(),
            "direction": tx.direction
        })

    assessment = await _run_assessment_core(
        borrower=borrower,
        requested_duration_days=requested_duration_days,
        mobile_money_history=history_dicts if history_dicts else None,
        assessment_source="MANUAL_UI"
    )

    # 5. Persist and Meter
    Database.save_assessment(assessment)
    BillingAgent.meter_usage(
        org=org, 
        environment=org.environment, 
        api_key_id="MANUAL_UI",
        endpoint="/assessment/manual",
        assessment_id=assessment.assessment_id
    )

    return assessment

@app.get("/org/decisions", response_model=List[Assessment])
async def get_org_decisions(
    limit: int = 50,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Returns recent assessments for the authenticated user's organization.
    """
    # Use the helper we just added to DB
    assessments = Database.get_assessments_by_org(current_user.organization_id, limit=limit)
    return assessments

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

@app.get("/org/settings", response_model=Dict)
async def get_org_settings(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Returns the current configuration for the authenticated organization.
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
        
    return {
        "webhook_url": org.webhook_url,
        "webhook_secret": org.webhook_secret,
        "feature_flags": org.feature_flags
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
    except Exception as e:
        import traceback
        print(traceback.format_exc())
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
        "status": "SUCCESS",
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
async def loan_disburse(assessment_id: str = Body(..., embed=True), user: AuthUser = Depends(AuthAgent.get_api_key)):
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    
    assessment = Database.get_assessment(assessment_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    
    if assessment.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Unauthorized access to assessment")
    
    loan = Loan(
        loan_id=f"LOAN-{uuid.uuid4().hex[:8].upper()}",
        assessment_id=assessment_id,
        borrower_id=assessment.borrower_id,
        organization_id=user.organization_id,
        amount=assessment.recommended_amount,
        interest_rate=assessment.recommended_interest_rate,
        status=LoanStatus.ACTIVE
    )
    
    Database.save_loan(loan)
    AuditAgent.log_event("LOAN_DISBURSED", user.role, {"loan_id": loan.loan_id, "amount": loan.amount, "org": user.organization_id})
    return loan

@app.post("/loan/status")
async def loan_status_update(loan_id: str = Body(..., embed=True), status: LoanStatus = Body(..., embed=True), user: AuthUser = Depends(AuthAgent.get_api_key)):
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    
    loan = Database.get_loan(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    
    if loan.organization_id != user.organization_id:
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
async def list_loans(user: AuthUser = Depends(AuthAgent.get_api_key)):
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    return Database.list_loans(organization_id=user.organization_id)

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
    print(f"📝 INTAKE CREATED: {borrower_id} for {intake_data['name']}")

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

    # 7. Audit
    client_ip = request.client.host if request and request.client else "unknown"
    AuditAgent.log_event("FINAL_HUMAN_DECISION_SEALED", user.email, {
        "assessment_id": assessment_id,
        "decision": officer_decision,
        "is_override": is_override,
        "ip": client_ip,
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
        
    return assessment

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
    try:
        # Verify borrower exists
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found")
        
        # Read file content
        content = await file.read()
        filename = file.filename.lower()
        
        # Parse based on file type
        alt_data = None
        
        if filename.endswith('.pdf'):
            if not PDF_SUPPORT:
                raise HTTPException(
                    status_code=400,
                    detail="PDF support not installed. Please install PyPDF2: pip install PyPDF2"
                )
            
            # Extract text from PDF
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                
                # Parse transactions from text
                alt_data = PDFTransactionParser.parse_pdf_text(text, borrower_id)
                
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to parse PDF: {str(e)}. Ensure the PDF contains readable text."
                )
        
        elif filename.endswith('.csv') or filename.endswith('.txt'):
            # Parse CSV/TXT format
            text = content.decode('utf-8')
            alt_data = parse_simple_csv_format(text, borrower_id)
        
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Please upload PDF, CSV, or TXT file."
            )
        
        # Validate parsed data
        if not alt_data.mobile_money_history and not alt_data.utility_history:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "WARNING",
                    "message": "No transactions found in the document. Please check the format.",
                    "help": {
                        "csv_format": "Date,Type,Amount,Description",
                        "example": "2024-01-15,DEPOSIT,5000,Salary",
                        "supported_types": ["DEPOSIT", "WITHDRAWAL", "TRANSFER", "PAYMENT"]
                    }
                }
            )
        
        # Save alternative data
        Database.save_alternative_data(alt_data)
        
        # Run behavioral analysis
        from agents.behavioral_agent_v2 import BehavioralAgentV2
        behavioral_results = BehavioralAgentV2.analyze(alt_data)
        
        # Run full risk assessment
        risk_results = RiskAgent.evaluate(borrower)
        decision_results = DecisionAgent.recommend(risk_results, borrower, 30) # Default duration for legacy pilot
        explanation = ExplanationAgent.generate(risk_results, decision_results, borrower)
        
        AuditAgent.log_event("DOCUMENT_UPLOAD", "BORROWER_PORTAL", {
            "borrower_id": borrower_id,
            "filename": file.filename,
            "transactions_found": len(alt_data.mobile_money_history),
            "utilities_found": len(alt_data.utility_history)
        })
        
        return {
            "status": "SUCCESS",
            "message": "Document uploaded and analyzed successfully",
            "data_summary": {
                "transactions_parsed": len(alt_data.mobile_money_history),
                "utilities_parsed": len(alt_data.utility_history),
                "airtime_avg": alt_data.airtime_usage_avg
            },
            "behavioral_analysis": {
                "income_consistency": behavioral_results.get("income_consistency_score", 0),
                "transaction_stability": behavioral_results.get("transaction_stability", 0),
                "savings_behavior": behavioral_results.get("savings_behavior", 0),
                "savings_trend": behavioral_results.get("saving_trend", 0),
                "utility_compliance": behavioral_results.get("utility_compliance", 0),
                "early_warnings": behavioral_results.get("early_warnings", []),
                # Extract top 5 transactions from the full list for display
                "largest_transactions": [
                    {
                        "date": t.timestamp.strftime('%Y-%m-%d'),
                        "type": t.type,
                        "amount": t.amount,
                        "desc": t.counterparty
                    }
                    for t in sorted(alt_data.mobile_money_history, key=lambda x: x.amount, reverse=True)[:5]
                ]
            },
            "risk_assessment": {
                "risk_score": risk_results["risk_score"],
                "risk_level": risk_results["risk_level"],
                "decision": decision_results["decision"],
                "recommended_amount": decision_results["recommended_amount"],
                "recommended_interest_rate": decision_results["recommended_interest_rate"]
            },
            "explanation": explanation
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

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
    try:
        # 1. Validation
        borrower = Database.get_borrower(borrower_id)
        if not borrower:
            raise HTTPException(status_code=404, detail="Borrower not found")
            
        content = await file.read()
        
        # 2. Safe Parsing (Standardized Schema)
        parser = TransactionParser()
        try:
            transactions = parser.parse(content, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
            
        if not transactions:
             return JSONResponse(
                status_code=200,
                content={"status": "WARNING", "message": "No transactions extracted. Check file format."}
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
            "transaction_count": len(transactions),
            "risk_assessment": {
                "score": risk_results["risk_score"],
                "level": risk_results["risk_level"],
                "decision": decision_results["decision"]
            },
            "behavioral_insights": behavioral_results,
            "explanation": explanation
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline Error: {str(e)}")

# ============================================================================
# B2B DASHBOARD ENDPOINTS (PARTNER CONSOLE)
# ============================================================================

@app.post("/auth/login", response_model=Dict[str, str])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint for Dashboard Users (JWT).
    """
    print(f"[LOGIN] ATTEMPT: {form_data.username}")
    user = await AuthAgent.authenticate_user(form_data.username, form_data.password)
    if not user:
        print(f"[LOGIN] FAILED: auth_agent returned None for {form_data.username}")
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"✅ LOGIN SUCCESS: {user.email} ({user.role})")
    
    # 3. Create JWT
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user.email, "role": str(user.role.value if hasattr(user.role, 'value') else user.role), "org": str(user.organization_id)}
    print(f"[LOGIN] Creating token for: {token_data}")
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
        print(f"[AUTH/ME ERROR] {error_detail}")
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
    uvicorn.run(app, host="0.0.0.0", port=port)
