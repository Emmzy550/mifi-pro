# Loan Officer AI – API Documentation

## Overview

The **Loan Officer AI** is a decision-support engine that helps microfinance institutions, SACCOs, and digital lenders evaluate loan applications faster and more consistently.

### What This Platform Does

- Analyzes borrower data (income, expenses, existing debt)
- Provides risk assessments and loan recommendations
- Returns structured decisions in seconds

### What This Platform Does NOT Do

- **We do not disburse loans** – You remain in full control of your funds
- **We do not make final decisions** – Our recommendations support your judgment, not replace it
- **We do not store sensitive banking credentials** – You send us data, we return analysis

> **Important:** You are always the final decision-maker. Our API provides data-driven recommendations to help you work faster and maintain consistency.

---

## Environments

| Environment | Base URL | Purpose |
|-------------|----------|---------|
| **Sandbox** | `http://localhost:8000` | Testing and integration |
| **Production** | `https://api.loanofficerai.com` | Live operations |

> Start with Sandbox for all testing. Move to Production only after thorough validation.

---

## Authentication

### Generating an API Key

1. Log in to the **Partner Console** at `https://dashboard.loanofficerai.com`
2. Navigate to **Settings → API Keys**
3. Click **"Create New Key"**
4. Choose environment: `test` or `production`
5. **Copy the key immediately** – it will only be shown once

Your API key will look like this:
```
loa_test_abc123def456ghi789...
```

### Using Your API Key

Include your API key in every request using the `X-API-Key` header:

```bash
curl -H "X-API-Key: loa_test_abc123..." \
  https://api.loanofficerai.com/api/health
```

### Key Security

- **Never share API keys** in emails, Slack, or public repositories
- **Rotate keys quarterly** or if compromised
- **Use environment-specific keys** (test keys for testing, production keys for production)
- **Revoke unused keys** in the Partner Console

---

## Health Check Endpoint

### Verify API Connectivity

**Endpoint:** `GET /api/health`

**Authentication:** Not required

**Example Request:**
```bash
curl https://api.loanofficerai.com/api/health
```

**Example Response:**
```json
{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true
}
```

**Response Fields:**
- `message` – Confirmation that the API is running
- `version` – Current API version
- `ml_enabled` – Whether machine learning is active
- `behavioral_v2_enabled` – Whether transaction analysis is available

---

## Borrower Intake (Optional Step)

### When to Use This Endpoint

Use `/intake/start` if you want the platform to validate borrower data before running assessment. This is optional – you can skip directly to `/assessment/run` if you prefer.

**Endpoint:** `POST /intake/start`

**Authentication:** Not required (public-facing)

**Example Request:**
```json
POST /intake/start
Content-Type: application/json

{
  "name": "Jane Mwangi",
  "phone": "+254700123456",
  "email": "jane.mwangi@example.com",
  "employment_type": "trader",
  "monthly_income": 45000,
  "monthly_expenses": 18000,
  "existing_debt": 5000,
  "loan_amount_requested": 25000,
  "loan_purpose": "Purchase inventory for shop",
  "organization_id": "ORG-YOUR-ID"
}
```

**Example Response:**
```json
{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}
```

**Response Fields:**
- `borrower_id` – Unique identifier for this borrower (use in next request)
- `status` – Confirmation of successful validation

---

## Run Loan Assessment (CORE ENDPOINT)

### The Main Decision Endpoint

**Endpoint:** `POST /assessment/run`

**Authentication:** Not required

This is the primary endpoint. Send borrower information and receive a risk assessment with loan recommendation.

**Example Request:**
```json
POST /assessment/run
Content-Type: application/json

{
  "borrower_id": "BOR-A1B2C3D4"
}
```

> **Note:** If you skipped `/intake/start`, you can send full borrower data directly to `/assessment/run` (see alternative format in Best Practices section).

**Processing Time:** Typically 2-3 seconds

---

## Assessment Response

**Example Response:**
```json
{
  "assessment_id": "ASMT-X1Y2Z3W4",
  "borrower_id": "BOR-A1B2C3D4",
  "risk_score": 35,
  "risk_level": "LOW",
  "decision": "APPROVED",
  "recommended_amount": 25000,
  "recommended_interest_rate": 15.0,
  "requested_amount": 25000,
  "explanation": {
    "summary": "This borrower demonstrates strong financial health with manageable debt levels and sufficient income to support the requested loan amount.",
    "risk_factors": [
      {
        "factor": "Debt-to-Income Ratio",
        "value": "11.1%",
        "assessment": "POSITIVE",
        "impact": "Well below the 40% threshold"
      },
      {
        "factor": "Affordability",
        "value": "18.5%",
        "assessment": "POSITIVE",
        "impact": "Monthly payment represents only 18.5% of disposable income"
      }
    ],
    "recommendations": [
      "Approve at standard rate of 15%",
      "Strong repayment capacity indicated"
    ]
  },
  "flags": [],
  "metrics": {
    "debt_to_income": 0.111,
    "affordability_ratio": 0.185
  }
}
```

### Understanding Response Fields

| Field | Description |
|-------|-------------|
| `assessment_id` | Unique ID for this assessment (for your records) |
| `borrower_id` | ID of the borrower being assessed |
| `risk_score` | Risk score from 0-100 (lower is better) |
| `risk_level` | `LOW` (0-40), `MEDIUM` (41-70), or `HIGH` (71-100) |
| `decision` | Recommendation: `APPROVED`, `CONDITIONAL_APPROVAL`, or `REJECT` |
| `recommended_amount` | Suggested loan amount (may differ from requested) |
| `recommended_interest_rate` | Suggested annual interest rate (%) |
| `requested_amount` | Amount the borrower requested |
| `explanation` | Detailed reasoning for the decision |
| `flags` | Warning flags (e.g., "HIGH_DEBT", "LOW_INCOME") |
| `metrics` | Key financial ratios used in assessment |

---

## Understanding Decisions

### APPROVED

**What it means:**
- Low risk profile
- Strong ability to repay
- Income and expenses are healthy

**Your action:**
- Proceed with loan at recommended amount and rate
- Perform standard identity verification
- Disburse according to your internal procedures

---

### CONDITIONAL_APPROVAL

**What it means:**
- Medium risk profile
- Can afford the loan, but with elevated risk
- May benefit from additional documentation

**Your action:**
- Consider approving at a **higher interest rate** (suggested rate provided)
- Consider **reducing the loan amount** (recommended amount provided)
- Request additional verification (references, guarantors, etc.)
- Use your judgment based on customer relationship

---

### REJECT

**What it means:**
- High risk profile
- Insufficient income to support requested amount
- Debt levels are too high

**Your action:**
- Decline the application
- Provide constructive feedback to applicant
- Suggest reapplying after improving financial position
- **You may still approve** if you have additional context (long customer relationship, collateral, etc.)

---

## Example cURL Request

**Complete Example:**

```bash
curl -X POST https://api.loanofficerai.com/assessment/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: loa_test_abc123def456..." \
  -d '{
    "borrower_id": "BOR-A1B2C3D4"
  }'
```

**Response:**
```json
{
  "assessment_id": "ASMT-X1Y2Z3W4",
  "decision": "APPROVED",
  "risk_score": 35,
  "risk_level": "LOW",
  "recommended_amount": 25000,
  "recommended_interest_rate": 15.0,
  ...
}
```

---

## Best Practices

### 1. Start with Sandbox

Always test your integration in the Sandbox environment first:
- Use test API keys
- Verify your request/response handling
- Test error scenarios (invalid data, network issues)
- Only move to Production after successful testing

### 2. Secure Your API Keys

- Store keys in environment variables, not code
- Never commit keys to version control
- Use different keys for test and production
- Rotate keys regularly

### 3. Send Structured Data Only

The API expects clean, validated data:
- Phone numbers in international format (`+254700123456`)
- Currency values as numbers, not strings
- Employment type from allowed values: `salaried`, `trader`, `farmer`, `self-employed`

### 4. Implement Human-in-the-Loop Decisioning

**Critical:** Our recommendations are inputs to your decision, not the final decision itself.

- **Review each assessment** – Don't auto-approve based solely on API response
- **Use your expertise** – You know your customers better than any algorithm
- **Document your decisions** – Keep records of approvals/rejections for compliance
- **Override when appropriate** – You may approve a "REJECT" or reject an "APPROVED" based on context

### 5. Handle Errors Gracefully

The API may return errors. Handle them appropriately:

**Example Error Response:**
```json
{
  "detail": "Borrower not found. Please run /intake/start first."
}
```

Common errors:
- `400 Bad Request` – Invalid data format
- `401 Unauthorized` – Invalid or missing API key
- `404 Not Found` – Borrower ID doesn't exist
- `500 Internal Server Error` – Contact support

### 6. Monitor and Log

- Log all API requests and responses for audit trails
- Monitor response times (should be under 5 seconds)
- Track success/error rates
- Set up alerts for unusual patterns

---

## Alternative Request Format

If you skip `/intake/start`, you can send borrower data directly to `/assessment/run`:

```json
POST /assessment/run
Content-Type: application/json

{
  "name": "Jane Mwangi",
  "phone": "+254700123456",
  "employment_type": "trader",
  "monthly_income": 45000,
  "monthly_expenses": 18000,
  "existing_debt": 5000,
  "loan_amount_requested": 25000,
  "loan_purpose": "Purchase inventory for shop"
}
```

This is faster but provides less validation.

---

## Support & Contact

### Technical Support

**Email:** support@loanofficerai.com  
**Response Time:** Within 24 hours (business days)  
**Emergency Line:** [To be provided]

### Documentation

- **Full Developer Docs:** [http://localhost:8000/documentation](http://localhost:8000/documentation)
- **Interactive API Explorer:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **FAQ:** [http://localhost:8000/documentation/faq](http://localhost:8000/documentation/faq)

### Reporting Issues

When contacting support, please include:
1. Your organization ID
2. Assessment ID (if applicable)
3. Request/response examples (remove sensitive data)
4. Error messages received
5. Steps to reproduce the issue

---

## Quick Start Checklist

- [ ] Generate API key in Partner Console
- [ ] Test health check endpoint
- [ ] Submit test borrower via `/intake/start`
- [ ] Run assessment via `/assessment/run`
- [ ] Review response format
- [ ] Implement error handling
- [ ] Test in Sandbox thoroughly
- [ ] Get Production API key
- [ ] Deploy to Production
- [ ] Monitor first 10-20 assessments

---

**You're ready to integrate!** If you have questions, contact support or visit our documentation hub.

**Version:** 2.0.0 | **Last Updated:** January 2026
