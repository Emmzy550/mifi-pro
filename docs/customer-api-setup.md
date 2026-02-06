# Loan Officer AI – Customer API Documentation

## Overview

**Loan Officer AI** is a decision-support API that helps lending institutions evaluate loan applications efficiently and consistently.

### What This API Does

- Analyzes borrower financial information
- Provides risk assessments and loan recommendations
- Returns structured data for your internal review

### What This API Does NOT Do

- **Does not approve or reject loans** – All final decisions remain with you
- **Does not disburse funds** – You control all disbursement processes
- **Does not replace human judgment** – Our recommendations support your expertise

> **Important:** You are always the final decision-maker. This API provides data-driven insights to help you make informed lending decisions.

---

## Quick Start

Get started in 3 simple steps:

1. **Generate an API Key**  
   Log into the Partner Console → API Keys → Create New Key

2. **Send a Loan Assessment Request**  
   POST your borrower data to `/assessment/run`

3. **Receive Decision & Explanation**  
   Review the risk score, recommendation, and detailed explanation

4. **Verify with Postman**  
   Use our [Postman Testing Guide](file:///C:/Users/SwiftVib Electronics/.gemini/antigravity/scratch/loan_officer_ai/docs/postman_guide.md) for a step-by-step walkthrough.

---

## Authentication

All API requests require authentication using an API key.

### Generating Your API Key

1. Log into the **Partner Console**
2. Navigate to **API Keys**
3. Click **"Create New Key"**
4. Choose environment: `test` or `production`
5. **Copy the key immediately** – it's shown only once

### Using Your API Key

Include your API key in every request:

```
X-API-Key: loa_live_abc123def456...
Content-Type: application/json
```

### Security Best Practices

- Store keys securely (environment variables, secrets manager)
- Never commit keys to source code or public repositories
- Rotate keys quarterly or if compromised
- Use test keys for development, production keys for live operations

---

## Health Check (Optional)

### Verify API Availability

**Endpoint:** `GET /api/health`

**Purpose:** Confirm the API is online and view system status

**Authentication:** Not required

**Example Response:**
```json
{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true
}
```

Use this endpoint for:
- Service monitoring
- Connectivity verification
- Integration testing

---

## Core Endpoint – Run Loan Assessment

### The Main Integration Point

**Endpoint:** `POST /assessment/run`

**Purpose:** Submit borrower information and receive loan recommendation

**Authentication:** Required (X-API-Key header)

### Request Format

```json
{
  "borrower_id": "BOR-A1B2C3D4"
}
```

Or send full borrower data directly:

```json
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

### Transaction Data

If available, transaction history improves assessment accuracy. Transactions may come from:

- Bank statements (processed by you into structured data)
- Mobile money records (M-Pesa, Airtel Money, etc.)
- CSV exports from financial institutions

**Important:** Send structured JSON data, not raw documents or PDFs.

### Processing Time

Typical response time: **2-3 seconds**

---

## Response Format

### Example Response

```json
{
  "assessment_id": "ASMT-X1Y2Z3W4",
  "borrower_id": "BOR-A1B2C3D4",
  "risk_score": 0.35,
  "risk_score_percent": 35.0,
  "risk_score_scale": "0-1",
  "risk_level": "LOW",
  "decision": "APPROVE",
  "decision_legacy": "APPROVED",
  "recommended_amount": 25000,
  "recommended_interest_rate": 15.0,
  "requested_amount": 25000,
  "decision_summary": "Approved based on strong capacity.",
  "customer_message": "Congratulations! Your loan request has been approved.",
  "flags": [],
  "metrics": {
    "debt_to_income": 0.111,
    "affordability_ratio": 0.185,
    "capacity_based_max": 28000
  },
  "policy_cap_amount": null,
  "policy_cap_reason": null
}
```

### Understanding Response Fields

| Field | Description |
|-------|-------------|
| `decision` | **APPROVE**, **CONDITIONAL**, **REJECT**, or **REFER** |
| `decision_legacy` | Legacy label for backwards compatibility (**APPROVED**/**CONDITIONAL_APPROVAL**) |
| `risk_score` | Normalized risk score from **0.0–1.0** (lower is better) |
| `risk_score_percent` | Convenience percent (0–100) |
| `customer_message` | Safe, ready-to-display message for the borrower |
| `recommended_amount` | Suggested loan amount (capped by capacity) |
| `policy_cap_amount` | The maximum safe amount if the request was capped |
| `policy_cap_reason` | Reason for the cap (e.g. "Exceeds 30% DTI Limit") |
| `recommended_interest_rate` | Suggested annual interest rate (%) |

### Capacity Guardrails (Creating Safe Loans)
Our engine uses strictly Conservative Capacity Logic.
- **We never recommend a loan that exceeds the borrower's repaying power.**
- If `recommended_amount` < `requested_amount`, check `policy_cap_reason`.
- This protects you from default and the borrower from over-indebtedness.

### Decision Types

**APPROVE**
- Low risk profile
- Strong repayment capacity
- **Your action:** Proceed with standard loan terms

**CONDITIONAL**
- Medium risk profile
- Acceptable with conditions
- **Your action:** Consider higher interest rate or reduced amount

**REJECT**
- High risk profile
- Insufficient capacity to repay
- **Your action:** Decline or request additional documentation

> **Note:** You may override any recommendation based on your expertise and customer knowledge.

### About Explanations

The `explanation` field contains detailed reasoning for internal review. **Do not share raw explanations directly with borrowers.** Use them to:
- Inform your decision-making process
- Document your approval rationale
- Identify areas needing further review

---

## Common Errors & How to Fix Them

### HTTP 401 Unauthorized

**Cause:** Missing or invalid API key

**Fix:**
- Verify `X-API-Key` header is present
- Check key hasn't been revoked
- Ensure using correct key for environment (test vs production)

**Example:**
```
X-API-Key: loa_live_abc123...  ✅ Correct
Authorization: Bearer xxx      ❌ Wrong header name
```

---

### HTTP 403 Forbidden

**Cause:** API key revoked or inactive

**Fix:**
- Check key status in Partner Console
- Generate new key if needed
- Verify organization access hasn't changed

---

### HTTP 422 Validation Error

**Cause:** Missing required fields or invalid data types

**Example Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "monthly_income"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**Fix:**
- Review required fields list
- Ensure all fields have correct data types
- Check for typos in field names

**Required Fields:**
- `name`, `phone`, `employment_type`
- `monthly_income`, `monthly_expenses`, `existing_debt`
- `loan_amount_requested`, `loan_purpose`

---

### HTTP 400 Bad Request

**Cause:** Malformed JSON

**Fix:**
- Validate JSON formatting (use online validator)
- Check for missing commas, brackets, or quotes
- Ensure proper encoding (UTF-8)

---

---

### HTTP 402 Payment Required

**Cause:** Organization has reached its plan limit (Production only)

**Fix:**
- Upgrade your plan
- Top-up credits in the dashboard

### HTTP 429 Too Many Requests

**Cause:** Rate limit exceeded OR Sandbox usage limit reached.

**Fix:**
- Reduce request frequency
- If in Sandbox: Upgrade to Production for unlimited volume
- Contact support for higher limits if needed

---

### HTTP 500 Internal Server Error

**Cause:** Temporary system issue

**Fix:**
- Retry after 1-2 minutes
- Check status page for incidents
- Contact support if persists

---

## Common Missing or Incorrect Data

### Frequent Integration Issues

**1. Missing Borrower Income**
- **Problem:** `monthly_income` not provided or set to 0
- **Result:** Assessment will likely return REJECT
- **Fix:** Ensure accurate income data is collected

**2. Expenses Greater Than Income**
- **Problem:** `monthly_expenses > monthly_income`
- **Result:** Automatic REJECT or very high risk score
- **Fix:** Validate data before submission

**3. No Transaction Data Provided**
- **Problem:** Assessment based only on stated income/expenses
- **Result:** Less accurate risk assessment
- **Fix:** When possible, include transaction history for better accuracy

**4. Incorrect Phone Number Format**
- **Problem:** Phone missing country code or contains invalid characters
- **Result:** Validation error (422)
- **Fix:** Use international format: `+254700123456`

**5. Sending Documents Instead of Structured Data**
- **Problem:** Uploading PDFs or images directly
- **Result:** API cannot process unstructured data
- **Fix:** Extract data from documents first, then send structured JSON

**6. Negative or Zero Loan Amounts**
- **Problem:** `loan_amount_requested <= 0`
- **Result:** Validation error
- **Fix:** Ensure positive loan amounts

**7. Missing Loan Purpose**
- **Problem:** `loan_purpose` empty or generic ("personal use")
- **Result:** Lower quality assessment
- **Fix:** Collect specific purpose ("school fees", "business inventory", etc.)

### Data Quality Responsibility

- **You are responsible for data accuracy** – The API processes data as provided
- **Missing or inconsistent data** may result in CONDITIONAL or REJECT decisions
- **Better data = better recommendations** – Complete, accurate data improves assessment quality

---

## Best Practices

### 1. Always Test in Sandbox First

- Use `test` environment for all development
- Use test API keys (starting with `loa_test_`)
- Verify integration fully before production

### 2. Perform Human Review Before Approval

- **Never auto-approve based solely on API response**
- Review explanation and metrics
- Apply your institutional knowledge
- Document your final decision

### 3. Secure API Keys

- Store in environment variables or secrets manager
- Rotate keys quarterly
- Revoke unused keys immediately
- Never log full API keys

### 4. Log Assessment Responses

- Keep assessment records for audit purposes
- Store assessment_id for reference
- Maintain decision history
- Support regulatory compliance

### 5. Do Not Expose Raw Explanations to Borrowers

- Explanations are for internal review
- Translate technical details into customer-friendly language
- Focus on constructive feedback
- Avoid sharing raw metrics or scores

### 6. Validate Data Before Submission

- Check required fields are present
- Ensure data types are correct
- Verify phone number format
- Confirm loan amounts are positive

### 7. Implement Error Handling

- Gracefully handle API errors
- Retry on temporary failures (500, 503)
- Log errors for troubleshooting
- Provide user-friendly error messages

---

## Support

### Technical Support

**Email:** support@yourdomain.com  
**Response Time:** Within 24 hours (business days)

### When Contacting Support

Please include:
- Organization ID
- Assessment ID (if applicable)
- Request/response examples (remove sensitive data)
- Error messages received
- Steps to reproduce the issue

### Additional Resources

- **Partner Console:** Manage API keys, view analytics
- **Interactive API Explorer:** Test endpoints in browser
- **Integration Guide:** Detailed technical documentation

---

## Testing with Postman

We provide a comprehensive Postman collection and guide to help you test the integration without writing any code.

### Prerequisites

1.  **Install Postman**: Download it from [postman.com](https://www.postman.com/downloads/).
2.  **API Key**: Obtain your test API key from the Partner Console.
3.  **Base URL**: Your local development server is usually at `http://localhost:8000`.

### Step-by-Step Guide

Our [Detailed Postman Guide](file:///C:/Users/SwiftVib Electronics/.gemini/antigravity/scratch/loan_officer_ai/docs/postman_guide.md) covers:

- **Environment Setup**: Setting up variables for Base URL and API Keys.
- **Workflow Testing**:
    1.  **Intake**: Create a borrower profile.
    2.  **Data Enrichment**: Upload behavioral transaction data.
    3.  **Assessment**: Run the engine and analyze the JSON response.

### Troubleshooting Common Postman Issues

- **403 Forbidden**: Ensure both `Authorization: Bearer <KEY>` and `X-API-KEY: <KEY>` headers are present and checked.
- **422 Unprocessable Content**: Ensure you have selected **Body** → **raw** → **JSON** in Postman.

---

## Appendix: Full Request Example

```bash
curl -X POST https://api.loanofficerai.com/assessment/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: loa_live_abc123def456..." \
  -d '{
    "name": "Jane Mwangi",
    "phone": "+254700123456",
    "employment_type": "trader",
    "monthly_income": 45000,
    "monthly_expenses": 18000,
    "existing_debt": 5000,
    "loan_amount_requested": 25000,
    "loan_purpose": "Purchase inventory for shop"
  }'
```

**Expected Response:**
```json
{
  "assessment_id": "ASMT-XXX",
  "decision": "APPROVE",
  "decision_legacy": "APPROVED",
  "risk_score": 0.35,
  "risk_score_percent": 35.0,
  "risk_score_scale": "0-1",
  "risk_level": "LOW",
  "recommended_amount": 25000,
  "recommended_interest_rate": 15.0,
  ...
}
```

---

**You're ready to integrate!**

For additional help, contact support@yourdomain.com

**Version:** 2.0.0 | **Last Updated:** January 2026
