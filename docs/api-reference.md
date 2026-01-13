# API Reference

Complete API documentation for the Loan Officer AI Agent system.

## Table of Contents

- [Authentication](#authentication)
- [Core Endpoints](#core-endpoints)
  - [Health Check](#health-check)
  - [Borrower Intake](#borrower-intake)
  - [Risk Assessment](#risk-assessment)
  - [Borrower Management](#borrower-management)
- [Alternative Data](#alternative-data)
- [Loan Management](#loan-management)
- [Organization Management](#organization-management)
- [Configuration & Monitoring](#configuration--monitoring)
- [Dashboard Endpoints](#dashboard-endpoints)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

---

## Authentication

The API supports two authentication methods:

### 1. API Keys (Recommended for M2M)

Use for machine-to-machine communication. Include the API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: loa_live_abc123..." http://localhost:8000/borrowers
```

**Creating an API Key:**

```bash
curl -X POST http://localhost:8000/api-keys/create \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production API Key",
    "environment": "production"
  }'
```

**Response:**

```json
{
  "api_key": "loa_live_abc123def456...",
  "key_record": {
    "key_hash": "hash...",
    "key_prefix": "loa_live_abc1",
    "name": "Production API Key",
    "environment": "production",
    "status": "ACTIVE"
  }
}
```

> [!WARNING]
> The full API key is shown **only once**. Store it securely!

### 2. JWT Tokens (For Dashboard Users)

Use for user-based authentication in web applications:

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=officer@example.com&password=securepassword"
```

**Response:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

**Using the Token:**

```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/auth/me
```

---

## Core Endpoints

### Health Check

Check system status and feature flags.

**Endpoint:** `GET /api/health`

**Authentication:** None required

**Response:**

```json
{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true,
  "llm_enabled": false
}
```

---

### Borrower Intake

Initialize a new borrower profile and loan application.

**Endpoint:** `POST /intake/start`

**Authentication:** None required (public endpoint for borrower portal)

**Request Body:**

```json
{
  "name": "Jane Doe",
  "phone": "+254700000000",
  "email": "jane@example.com",
  "employment_type": "trader",
  "monthly_income": 50000,
  "monthly_expenses": 20000,
  "existing_debt": 5000,
  "loan_amount_requested": 15000,
  "loan_purpose": "Business stock expansion",
  "organization_id": "ORG-12345"
}
```

**Field Descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Full name of borrower |
| `phone` | string | Yes | Phone number (E.164 format recommended) |
| `email` | string | No | Email address |
| `employment_type` | string | Yes | One of: `salaried`, `trader`, `farmer`, `self_employed` |
| `monthly_income` | number | Yes | Monthly income in local currency |
| `monthly_expenses` | number | Yes | Monthly expenses |
| `existing_debt` | number | Yes | Total existing debt obligations |
| `loan_amount_requested` | number | Yes | Requested loan amount |
| `loan_purpose` | string | Yes | Purpose of the loan |
| `organization_id` | string | No | MFI/SACCO organization ID (defaults to DEFAULT_ORG) |

**Response:**

```json
{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}
```

---

### Risk Assessment

Run a complete risk assessment on a borrower.

**Endpoint:** `POST /assessment/run`

**Authentication:** None required

**Request Body:**

```json
{
  "borrower_id": "BOR-A1B2C3D4"
}
```

**Response:**

```json
{
  "assessment_id": "ASMT-X1Y2Z3A4",
  "borrower_id": "BOR-A1B2C3D4",
  "organization_id": "DEFAULT_ORG",
  "risk_score": 45,
  "risk_level": "MEDIUM",
  "decision": "CONDITIONAL_APPROVAL",
  "recommended_amount": 15000,
  "recommended_interest_rate": 20.0,
  "requested_amount": 15000,
  "explanation": {
    "summary": "Conditionally approved with elevated interest rate due to medium risk profile.",
    "risk_factors": [
      "Debt-to-income ratio is 10.0% (healthy)",
      "Loan affordability is acceptable at 29.2%"
    ],
    "recommendations": [
      "Monitor repayment behavior closely",
      "Consider reducing loan term if payment struggles occur"
    ],
    "behavioral_insights": {
      "income_consistency": 0,
      "transaction_stability": 0,
      "early_warnings": []
    }
  },
  "flags": [
    {
      "flag": "DTI_OK",
      "severity": "INFO",
      "message": "Debt-to-income ratio is 10.0%"
    }
  ],
  "metrics": {
    "debt_to_income_ratio": 0.1,
    "affordability_ratio": 0.292,
    "rule_based_score": 45,
    "ml_probability": null,
    "ensemble_score": 45,
    "override_applied": false
  }
}
```

**Risk Levels:**

- `LOW` (0-40): Low risk, standard approval
- `MEDIUM` (41-70): Medium risk, conditional approval with higher rates
- `HIGH` (71-100): High risk, rejection recommended

**Decision Types:**

- `APPROVED`: Standard approval at base interest rate
- `CONDITIONAL_APPROVAL`: Approved with conditions (higher interest rate or reduced amount)
- `REJECT`: Loan not recommended

---

#### Get Assessment Result

Retrieve a previously generated assessment.

**Endpoint:** `GET /assessment/result/{assessment_id}`

**Authentication:** None required

**Response:** Same as assessment/run response

---

### Borrower Management

#### List Borrowers

Get all borrowers for your organization.

**Endpoint:** `GET /borrowers`

**Authentication:** API Key (OFFICER role required)

**Response:**

```json
[
  {
    "id": "BOR-A1B2C3D4",
    "name": "Jane Doe",
    "phone": "+254700000000",
    "employment_type": "trader",
    "monthly_income": 50000,
    "loan_amount_requested": 15000,
    "organization_id": "ORG-12345"
  }
]
```

#### List Assessments

Get all assessments for your organization.

**Endpoint:** `GET /assessments`

**Authentication:** API Key (OFFICER role required)

**Response:** Array of assessment objects

---

## Alternative Data

Upload transaction history, bank statements, or utility records for enhanced behavioral analysis.

### Upload Document (PDF/CSV)

**Endpoint:** `POST /borrower/data/upload-document`

**Authentication:** None required

**Request:** Multipart form data

```bash
curl -X POST http://localhost:8000/borrower/data/upload-document \
  -F "borrower_id=BOR-A1B2C3D4" \
  -F "file=@transactions.csv"
```

**Supported Formats:**

**CSV Format:**

```csv
Date,Type,Amount,Description
2024-01-15,DEPOSIT,5000,Salary
2024-01-16,WITHDRAWAL,2000,ATM
2024-01-17,PAYMENT,500,Electricity
2024-01-20,DEPOSIT,3000,Business Income
```

**Supported Transaction Types:**
- `DEPOSIT` - Money received
- `WITHDRAWAL` - Cash withdrawal
- `PAYMENT` - Bill payment or purchase
- `TRANSFER` - Money transfer

**Response:**

```json
{
  "status": "SUCCESS",
  "message": "Document uploaded and analyzed successfully",
  "data_summary": {
    "transactions_parsed": 45,
    "utilities_parsed": 3,
    "airtime_avg": 500
  },
  "behavioral_analysis": {
    "income_consistency": 0.85,
    "transaction_stability": 0.72,
    "savings_behavior": 0.65,
    "savings_trend": 0.58,
    "utility_compliance": 1.0,
    "early_warnings": [],
    "largest_transactions": [...]
  },
  "risk_assessment": {
    "risk_score": 38,
    "risk_level": "LOW",
    "decision": "APPROVED",
    "recommended_amount": 15000,
    "recommended_interest_rate": 15.0
  },
  "explanation": {...}
}
```

---

### Upload Transactions (Regulator-Safe Pipeline)

**Endpoint:** `POST /behavior/upload`

**Authentication:** None required

**Safety Guarantees:**
- Data source flagged as `USER_UPLOADED`
- Confidence weight capped at 60%
- Behavioral impact capped at 20% of risk score
- Full transparency in explanations

**Request:** Multipart form data (same as upload-document)

**Response:**

```json
{
  "status": "SUCCESS",
  "data_source": "USER_UPLOADED_STATEMENT",
  "transaction_count": 45,
  "risk_assessment": {
    "score": 38,
    "level": "LOW",
    "decision": "APPROVED"
  },
  "behavioral_insights": {...},
  "explanation": {...}
}
```

---

## Loan Management

### Disburse Loan

Convert an approved assessment into an active loan.

**Endpoint:** `POST /loan/disburse`

**Authentication:** API Key (OFFICER role required)

**Request Body:**

```json
{
  "assessment_id": "ASMT-X1Y2Z3A4"
}
```

**Response:**

```json
{
  "loan_id": "LOAN-B5C6D7E8",
  "assessment_id": "ASMT-X1Y2Z3A4",
  "borrower_id": "BOR-A1B2C3D4",
  "organization_id": "ORG-12345",
  "amount": 15000,
  "interest_rate": 20.0,
  "status": "ACTIVE",
  "disbursed_at": "2024-01-15T10:30:00Z"
}
```

---

### Update Loan Status

Update the status of an active loan.

**Endpoint:** `POST /loan/status`

**Authentication:** API Key (OFFICER role required)

**Request Body:**

```json
{
  "loan_id": "LOAN-B5C6D7E8",
  "status": "PAID"
}
```

**Loan Statuses:**
- `ACTIVE` - Loan is currently active
- `PAID` - Loan fully repaid
- `DEFAULTED` - Loan in default
- `WRITTEN_OFF` - Loan written off

**Response:**

```json
{
  "status": "SUCCESS",
  "loan_id": "LOAN-B5C6D7E8",
  "new_status": "PAID"
}
```

> [!NOTE]
> Marking a loan as `PAID` or `DEFAULTED` triggers the self-healing feedback loop for model improvement.

---

### List Loans

Get all loans for your organization.

**Endpoint:** `GET /loans`

**Authentication:** API Key (OFFICER role required)

**Response:** Array of loan objects

---

## Organization Management

### Get Organization Decisions

Get recent loan decisions for your organization.

**Endpoint:** `GET /org/decisions?limit=50`

**Authentication:** JWT Token required

**Query Parameters:**
- `limit` (optional): Maximum number of results (default: 50)

**Response:** Array of assessment objects

---

### Get Audit Logs

Get audit trail for your organization.

**Endpoint:** `GET /org/audit-logs?limit=50`

**Authentication:** JWT Token required

**Response:**

```json
[
  {
    "event_type": "ASSESSMENT_GENERATE",
    "actor": "SYSTEM",
    "timestamp": "2024-01-15T10:30:00Z",
    "metadata": {
      "assessment_id": "ASMT-X1Y2Z3A4",
      "borrower_id": "BOR-A1B2C3D4",
      "org": "ORG-12345"
    }
  }
]
```

---

### Get Organization Settings

**Endpoint:** `GET /org/settings`

**Authentication:** JWT Token required

**Response:**

```json
{
  "webhook_url": "https://yourapp.com/webhooks/loan-decisions",
  "webhook_secret": "whsec_abc123...",
  "feature_flags": {
    "enable_ml": true,
    "enable_behavioral": true
  }
}
```

---

### Update Organization Settings

**Endpoint:** `PATCH /org/settings`

**Authentication:** JWT Token required

**Request Body:**

```json
{
  "webhook_url": "https://yourapp.com/webhooks/loan-decisions",
  "feature_flags": {
    "enable_ml": true,
    "enable_behavioral": true
  },
  "regenerate_secret": true
}
```

**Response:** Updated settings object

---

## Configuration & Monitoring

### Get Model Version

Get information about the active ML model.

**Endpoint:** `GET /model/version`

**Authentication:** None required

**Response:**

```json
{
  "model_version": "1.0.0",
  "model_path": "./ml_models/risk_model.json",
  "model_exists": true,
  "ml_enabled": true,
  "ensemble_weights": {
    "rule_weight": 0.7,
    "ml_weight": 0.3
  }
}
```

---

### Get Feature Flags

Get current system configuration.

**Endpoint:** `GET /config/flags`

**Authentication:** None required

**Response:**

```json
{
  "ENABLE_ML_RISK_SCORING": true,
  "ENABLE_BEHAVIORAL_V2": true,
  "ENABLE_LLM_EXPLANATIONS": false,
  "RULE_WEIGHT": 0.7,
  "ML_WEIGHT": 0.3,
  "MIN_MONTHLY_INCOME": 100.0,
  "MAX_DEBT_TO_INCOME_RATIO": 0.4
}
```

---

### Update Feature Flags (SUPER_ADMIN only)

**Endpoint:** `POST /config/flags/update`

**Authentication:** API Key (SUPER_ADMIN role required)

**Request Body:**

```json
{
  "flag_name": "ENABLE_ML_RISK_SCORING",
  "value": false
}
```

**Allowed Flags:**
- `ENABLE_ML_RISK_SCORING`
- `ENABLE_LLM_EXPLANATIONS`
- `ENABLE_BEHAVIORAL_V2`

**Response:**

```json
{
  "status": "SUCCESS",
  "flag": "ENABLE_ML_RISK_SCORING",
  "new_value": false,
  "warning": "Runtime change only. Restart server to revert to environment defaults."
}
```

> [!WARNING]
> Feature flag changes are **runtime only** and will reset on server restart. For persistent changes, update environment variables.

---

### Trigger Model Retraining

**Endpoint:** `POST /assessment/retrain`

**Authentication:** API Key (OFFICER role required)

**Response:**

```json
{
  "status": "RETRAIN_SUCCESS",
  "message": "Model updated with latest data"
}
```

---

## Dashboard Endpoints

### Get Current User

**Endpoint:** `GET /auth/me`

**Authentication:** JWT Token required

**Response:**

```json
{
  "id": "USER-123",
  "email": "officer@example.com",
  "role": "OFFICER",
  "organization_id": "ORG-12345"
}
```

---

### Get Organization Metrics

**Endpoint:** `GET /org/metrics`

**Authentication:** JWT Token required

**Response:**

```json
{
  "total_assessments": 150,
  "total_loans": 120,
  "active_loans": 95,
  "default_rate": 4.2
}
```

---

### API Key Management

#### List API Keys

**Endpoint:** `GET /api-keys`

**Authentication:** JWT Token required

**Response:**

```json
[
  {
    "key_hash": "hash...",
    "key_prefix": "loa_live_abc1",
    "name": "Production API Key",
    "environment": "production",
    "status": "ACTIVE",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

#### Revoke API Key

**Endpoint:** `POST /api-keys/revoke`

**Authentication:** JWT Token (ORG_ADMIN role required)

**Request Body:**

```json
{
  "key_hash": "hash..."
}
```

**Response:**

```json
{
  "status": "REVOKED"
}
```

---

## Error Handling

All errors follow this format:

```json
{
  "detail": "Error message explaining what went wrong"
}
```

**Common HTTP Status Codes:**

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 400 | Bad Request | Invalid input data, validation errors |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions for the operation |
| 404 | Not Found | Resource (borrower, assessment, loan) not found |
| 500 | Internal Server Error | Server-side error, check logs |

**Example Error Response:**

```json
{
  "detail": "Borrower not found. Please run /intake/start first."
}
```

---

## Rate Limiting

Currently, there is **no rate limiting** implemented in V1. For production deployments, consider adding:

- API gateway rate limiting (e.g., Kong, Tyk)
- Nginx rate limiting
- Application-level throttling

**Recommended Limits:**
- Public endpoints (`/intake/start`, `/assessment/run`): 100 requests/minute
- Authenticated endpoints: 1000 requests/minute
- Admin endpoints: 100 requests/minute

---

## Interactive API Documentation

The API includes automatically generated interactive documentation:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

Use these for exploring endpoints and testing requests directly in your browser.

---

## Next Steps

- [Integration Guide](./integration.md) - Learn how to integrate with your application
- [Agent System Guide](./agents.md) - Understand the multi-agent architecture
- [Testing Guide](./testing.md) - Test your API integration
