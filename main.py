import uuid
from fastapi import FastAPI, HTTPException, Body, Depends, Security, UploadFile, File
from typing import Dict, List
import io
import datetime

from fastapi.security import OAuth2PasswordRequestForm
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from models.borrower import Borrower
from models.assessment import Assessment
from models.loan import Loan, LoanStatus
from models.alternative_data import AlternativeData
from models.organization import Organization
from models.api_key import APIKey
from models.user import User
from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent
from agents.decision_agent import DecisionAgent
from agents.explanation_agent import ExplanationAgent
from agents.auth_agent import AuthAgent, AuthUser, ACCESS_TOKEN_EXPIRE_MINUTES, get_super_admin
from agents.audit_agent import AuditAgent
from agents.self_healing_agent import SelfHealingAgent
from utils.db import Database
from utils.pdf_parser import PDFTransactionParser, parse_simple_csv_format
from utils.transaction_parser import TransactionParser

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

# Serve static files (CSS, JS)
# Use the current directory for simplicity in V1
static_path = os.path.dirname(os.path.abspath(__file__))

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

# Database initialization happens via the Database class
# No local dictionaries needed for V2

@app.get(
    "/api/health",
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
async def intake_start(raw_data: dict = Body(
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
)):
    """
    Create a new borrower profile with validated information.
    """
    try:
        org_id = raw_data.get("organization_id", "DEFAULT_ORG")
        borrower_profile = IntakeAgent.process(raw_data)
        borrower_profile.id = f"BOR-{uuid.uuid4().hex[:8].upper()}"
        borrower_profile.organization_id = org_id
        Database.save_borrower(borrower_profile)
        AuditAgent.log_event("INTAKE_START", "BORROWER_PORTAL", {"borrower_id": borrower_profile.id, "org": org_id})
        return {"borrower_id": borrower_profile.id, "status": "INTAKE_COMPLETE"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post(
    "/assessment/run",
    response_model=Assessment,
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
    user: AuthUser = Depends(AuthAgent.get_api_key)
):
    """
    Runs the full analysis pipeline for a borrower with billing metering.
    """
    # Get borrower and validate
    borrower = Database.get_borrower(borrower_id)
    if not borrower:
        raise HTTPException(status_code=404, detail="Borrower not found. Please run /intake/start first.")
    
    # SCOPING: Enforce Organization Isolation
    if borrower.organization_id != user.organization_id:
        # We return 404 to avoid leaking existence of borrowers from other orgs
        raise HTTPException(status_code=404, detail="Borrower not found.")
    
    # BILLING: Get organization and check billing status
    org = Database.get_organization(user.organization_id)
    if not org:
        raise HTTPException(status_code=500, detail="Organization context missing")
    
    # BILLING: Check and reset billing cycle if needed
    from agents.billing_agent import BillingAgent
    org = BillingAgent.check_billing_cycle(org)
    
    # BILLING: Check if organization has exceeded limit
    is_allowed, error_response = BillingAgent.check_billing_limit(org)
    if not is_allowed:
       # Return HTTP 429 with billing error details
        raise HTTPException(status_code=429, detail=error_response)
    
    try:
        # Proceed with assessment
        # 1. Evaluate Risk
        risk_results = RiskAgent.evaluate(borrower)
        
        # 2. Recommmend Decision
        decision_results = DecisionAgent.recommend(risk_results, borrower)
        
        # 3. Generate Explanation
        explanation_text, explanation_source = ExplanationAgent.generate(risk_results, decision_results, borrower)
        
        # 4. Construct Final Assessment Object
        assessment = Assessment(
            assessment_id=f"ASMT-{uuid.uuid4().hex[:8].upper()}",
            borrower_id=borrower_id,
            organization_id=borrower.organization_id,
            risk_score=risk_results["risk_score"],
            risk_level=risk_results["risk_level"],
            decision=decision_results["decision"],
            recommended_amount=decision_results["recommended_amount"],
            recommended_interest_rate=decision_results["recommended_interest_rate"],
            requested_amount=borrower.loan_amount_requested,
            explanation=explanation_text,
            explanation_source=explanation_source,
            decision_source="rules_engine",
            flags=risk_results["flags"],
            metrics=risk_results["metrics"]
        )
        
        # Save assessment
        Database.save_assessment(assessment)
        
        # BILLING: Meter usage (only after successful assessment)
        # This gets called ONLY if we reach this point (HTTP 200)
        BillingAgent.meter_usage(
            org=org,
            api_key_id="API_KEY",  # We could pass the actual key ID if we threaded it through AuthUser
            endpoint="/assessment/run",
            assessment_id=assessment.assessment_id
        )
        
        # Audit log
        AuditAgent.log_event("ASSESSMENT_GENERATE", "SYSTEM", {
            "assessment_id": assessment.assessment_id,
            "borrower_id": borrower_id,
            "org": user.organization_id,
            "billed": True
        })
        
        print(f"DEBUG: Assessment generated and saved for {borrower_id} (metered)")
        return assessment
    except Exception as e:
        import traceback
        error_msg = f"🔥 ASSESSMENT CRASH in main.py: {e}\n{traceback.format_exc()}"
        print(error_msg)
        with open("crash_report.txt", "w", encoding="utf-8") as f:
            f.write(error_msg)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/assessment/result/{assessment_id}", response_model=Assessment)
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
        
    return assessment

@app.get("/assessments", response_model=List[Assessment])
async def list_assessments(user: AuthUser = Depends(AuthAgent.get_api_key)):
    """
    Returns assessments for the officer's organization.
    """
    if user.role != "OFFICER":
        raise HTTPException(status_code=403, detail="Officer access required")
    return Database.list_assessments(organization_id=user.organization_id)

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
        
    return BillingAgent.get_usage_summary(org)

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
        import datetime
        loan.closed_at = datetime.datetime.now()
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
        "total_assessments": len(all_assessments),
        "global_default_rate": (len([l for l in all_loans if l.status == LoanStatus.DEFAULTED]) / len(all_loans) * 100) if all_loans else 0
    }

# ============================================================================
# NEW V3/V4 ENDPOINTS
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
# DOCUMENT UPLOAD ENDPOINT (For Testing Behavioral Intelligence)
# ============================================================================

@app.post("/borrower/data/upload-document")
async def upload_transaction_document(
    borrower_id: str = Body(..., embed=True),
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
        decision_results = DecisionAgent.recommend(risk_results, borrower)
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
    borrower_id: str = Body(..., embed=True),
    file: UploadFile = File(...)
):
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
        decision_results = DecisionAgent.recommend(risk_results, borrower)
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
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": user.email, "role": str(user.role.value if hasattr(user.role, 'value') else user.role), "org": str(user.organization_id)}
    print(f"[LOGIN] Creating token for: {token_data}")
    access_token = AuthAgent.create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    
    AuditAgent.log_event("DASHBOARD_LOGIN", str(user.role), {"user_id": user.id, "org": user.organization_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: User = Depends(AuthAgent.get_current_user)):
    return current_user

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
    
    AuditAgent.log_event("KEY_CREATE", current_user.role, {"key_prefix": key_record.key_prefix, "org": current_user.organization_id})
    
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
        
    key_record.status = "REVOKED" # Use string or Enum if imported
    Database.save_api_key(key_record)
    
    AuditAgent.log_event("KEY_REVOKE", current_user.role, {"key_prefix": key_record.key_prefix})
    return {"status": "REVOKED"}

# --- DASHBOARD METRICS ---

@app.get("/org/metrics")
async def get_org_metrics(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Get usage metrics for the dashboard.
    """
    # Filter assessments by org
    assessments = Database.list_assessments(current_user.organization_id)
    loans = Database.list_loans(current_user.organization_id)
    
    total_assessments = len(assessments)
    today = datetime.datetime.now().date()
    # Note: Assessment object needs 'created_at' for 'today' filter.
    # Assuming standard Assessment doesn't have it explicitly yet in this context,
    # or it's embedded in ID/Audit logs. For V1 we'll mock 'today' with total.
    
    return {
        "total_assessments": total_assessments,
        "total_loans": len(loans),
        "active_loans": len([l for l in loans if l.status == "ACTIVE"]),
        "default_rate": (len([l for l in loans if l.status == "DEFAULTED"]) / len(loans) * 100) if loans else 0
    }

# ============================================================================
# BILLING ENDPOINTS
# ============================================================================

@app.get("/billing/usage", tags=["Billing"])
async def get_billing_usage(current_user: User = Depends(AuthAgent.get_current_user)):
    """
    Get current billing usage summary for the organization.
    
    **Permissions:** ORG_ADMIN or DEVELOPER can view usage count.
    Only ORG_ADMIN can see cost details.
    """
    org = Database.get_organization(current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    from agents.billing_agent import BillingAgent
    summary = BillingAgent.get_usage_summary(org)
    
    # Hide cost details for non-admins
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN"]:
        summary.pop("unit_cost", None)
        summary.pop("estimated_cost", None)
    
    return summary

@app.get("/billing/logs", tags=["Billing"])
async def get_billing_logs(
    limit: int = 100,
    current_user: User = Depends(AuthAgent.get_current_user)
):
    """
    Get usage log history for the organization.
    
    **Permissions:** ORG_ADMIN only
    """
    if current_user.role not in ["ORG_ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only admins can view billing logs")
    
    logs = Database.get_usage_logs(current_user.organization_id, limit=limit)
    
    # Convert to dict for JSON response
    return {
        "logs": [log.model_dump(mode='json') for log in logs],
        "count": len(logs)
    }

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

# Mount at bottom to avoid intercepting API routes
# Serve the React App from 'frontend/dist'
frontend_dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

if os.path.exists(frontend_dist):
    print(f"FRONTEND FOUND at {frontend_dist}")
    print("Serving React App...")
    # Mount assets folders (assets, etc)
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")
    
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(frontend_dist, "index.html"))

    # Catch-all for React Router
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        # Allow API requests, admin, and documentation to pass through
        if full_path.startswith("api/") or full_path.startswith("admin/") or full_path.startswith("docs") or full_path.startswith("openapi.json") or full_path.startswith("documentation"):
             raise HTTPException(status_code=404, detail="Not Found")
             
        # Serve index.html for any other route
        return FileResponse(os.path.join(frontend_dist, "index.html"))
else:
    print(f"FRONTEND NOT FOUND at {frontend_dist}")
    print("Running in LEGACY/API-ONLY mode")
    print(f"Fallback Static Path: {static_path}")
    # Fallback to serving old static folder if dist doesn't exist
    app.mount("/", StaticFiles(directory=static_path), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
