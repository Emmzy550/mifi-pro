# Customer API Setup Guide

This guide is for **IT teams and developers** at lending institutions who want to integrate the Loan Officer AI Agent with their existing systems.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Authentication](#authentication)
- [Basic Integration](#basic-integration)
- [Testing Your Integration](#testing-your-integration)
- [Going Live Checklist](#going-live-checklist)
- [Support](#support)

---

## Overview

### What You Can Do

Integrate the Loan Officer AI with your:
- 📱 Mobile apps
- 💻 Web applications
- 🖥️ Core banking systems
- 📊 CRM platforms

### Integration Methods

1. **REST API** - Direct API calls
2. **Webhooks** - Real-time notifications
3. **Batch Upload** - Bulk processing

---

## Prerequisites

### Technical Requirements

- **Programming Knowledge**: Working knowledge of REST APIs
- **HTTP Client**: Ability to make HTTP requests (curl, Postman, or code)
- **JSON Processing**: Can parse and generate JSON
- **HTTPS**: Your systems support HTTPS

### What You'll Need from Your Admin

- ✅ API credentials (provided after account setup)
- ✅ Organization ID
- ✅ Dashboard access (for testing)

---

## Getting Started

### Step 1: Get API Credentials

1. **Log in to the dashboard** with your admin account
2. Go to **Settings → API Keys**
3. Click **"Create New API Key"**
4. Fill in:
   - **Name**: e.g., "Production Mobile App"
   - **Environment**: Choose "Test" first, then "Production" later

5. **Copy the API key** - You'll only see it once!

```
Example API Key: loa_test_abc123def456ghi789jkl012
```

⚠️ **Keep this secret!** Never commit it to code repositories.

### Step 2: Test Connection

Try a simple health check:

```bash
curl https://api.your-lender.com/api/health
```

**Expected Response:**
```json
{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true
}
```

---

## Authentication

### Using API Keys

Include your API key in the request header:

```bash
curl -H "X-API-Key: loa_test_abc123..." \
  https://api.your-lender.com/borrowers
```

### Error Responses

**401 Unauthorized**
```json
{"detail": "Invalid API key"}
```
- Check your API key is correct
- Verify it hasn't been revoked
- Ensure you're using the header `X-API-Key`

---

## Basic Integration

### Use Case 1: Submit Loan Application

**Scenario:** A borrower completes an application in your mobile app. You want to submit it to the AI for assessment.

**Step 1: Create Borrower Profile**

```bash
POST /intake/start
Content-Type: application/json

{
  "name": "Jane Doe",
  "phone": "+254700000000",
  "email": "jane@example.com",
  "employment_type": "trader",
  "monthly_income": 50000,
  "monthly_expenses": 20000,
  "existing_debt": 5000,
  "loan_amount_requested": 15000,
  "loan_purpose": "Business stock purchase",
  "organization_id": "YOUR_ORG_ID"
}
```

**Response:**
```json
{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}
```

**Step 2: Run Risk Assessment**

```bash
POST /assessment/run
Content-Type: application/json

{
  "borrower_id": "BOR-A1B2C3D4"
}
```

**Response:**
```json
{
  "assessment_id": "ASMT-X1Y2Z3A4",
  "borrower_id": "BOR-A1B2C3D4",
  "risk_score": 45,
  "risk_level": "MEDIUM",
  "decision": "CONDITIONAL_APPROVAL",
  "recommended_amount": 15000,
  "recommended_interest_rate": 20.0,
  "explanation": {
    "summary": "Conditionally approved...",
    "risk_factors": [...],
    "recommendations": [...]
  }
}
```

### Use Case 2: Upload Transaction Data

**Scenario:** Borrower provides bank statements. You want to upload them for enhanced assessment.

```bash
POST /behavior/upload
Content-Type: multipart/form-data

borrower_id=BOR-A1B2C3D4
file=@transactions.csv
```

**Response:**
```json
{
  "status": "SUCCESS",
  "transaction_count": 45,
  "behavioral_insights": {
    "income_consistency": 0.85,
    "transaction_stability": 0.72
  },
  "risk_assessment": {
    "score": 38,
    "level": "LOW",
    "decision": "APPROVED"
  }
}
```

### Use Case 3: Get Assessment Results

**Scenario:** Retrieve a previously generated assessment.

```bash
GET /assessment/result/ASMT-X1Y2Z3A4
X-API-Key: your_api_key_here
```

---

## Testing Your Integration

### Test Environment

Always test in the **test environment** first:

```
Base URL: https://api-test.your-lender.com
```

Use test API keys (starting with `loa_test_`)

### Test Scenarios

**Scenario 1: Low Risk Borrower (Should Approve)**
```json
{
  "monthly_income": 100000,
  "monthly_expenses": 30000,
  "existing_debt": 5000,
  "loan_amount_requested": 20000
}
```

**Scenario 2: High Risk Borrower (Should Reject)**
```json
{
  "monthly_income": 10000,
  "monthly_expenses": 8000,
  "existing_debt": 5000,
  "loan_amount_requested": 50000
}
```

**Scenario 3: Medium Risk (Conditional Approval)**
```json
{
  "monthly_income": 50000,
  "monthly_expenses": 25000,
  "existing_debt": 10000,
  "loan_amount_requested": 25000
}
```

### Testing Checklist

- [ ] Health check returns 200
- [ ] Can create borrower profile
- [ ] Can run assessment
- [ ] Can retrieve assessment results
- [ ] Can upload transaction files
- [ ] Error handling works (400, 401, 404, 500)
- [ ] Response times are acceptable (< 3 seconds)
- [ ] All required fields validated

---

## Going Live Checklist

### Pre-Launch

- [ ] **Testing Complete** - All test scenarios pass
- [ ] **Error Handling** - Your app handles all API errors gracefully
- [ ] **API Keys Secured** - Production keys stored in environment variables
- [ ] **Rate Limiting** - Implemented backoff/retry logic
- [ ] **Logging** - Request/response logging for debugging

### Security

- [ ] **HTTPS Only** - All requests use HTTPS
- [ ] **API Key Storage** - Never in source code or client apps
- [ ] **Input Validation** - Validate user input before sending to API
- [ ] **Data Encryption** - Sensitive data encrypted in transit and at rest

### Production Setup

1. **Generate Production API Key**
   - Use "production" environment
   - Store securely (AWS Secrets Manager, Azure Key Vault, etc.)

2. **Update Base URL**
   ```
   https://api.your-lender.com  # Production
   ```

3. **Configure Webhooks** (optional)
   - Set webhook URL in dashboard
   - Verify webhook signatures

4. **Monitor Performance**
   - Set up alerts for API errors
   - Track response times
   - Monitor success/fail rates

### Launch

- [ ] Deploy to production
- [ ] Run smoke tests
- [ ] Process 5-10 real applications manually
- [ ] Monitor for 24 hours
- [ ] Scale up gradually

---

## Code Examples

### Python

```python
import requests

API_KEY = "loa_live_abc123..."
BASE_URL = "https://api.your-lender.com"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Create borrower
borrower_data = {
    "name": "Jane Doe",
    "phone": "+254700000000",
    "monthly_income": 50000,
    # ... other fields
}

response = requests.post(
    f"{BASE_URL}/intake/start",
    json=borrower_data,
    headers=headers
)

borrower_id = response.json()["borrower_id"]

# Run assessment
assessment_response = requests.post(
    f"{BASE_URL}/assessment/run",
    json={"borrower_id": borrower_id},
    headers=headers
)

assessment = assessment_response.json()
print(f"Decision: {assessment['decision']}")
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const API_KEY = 'loa_live_abc123...';
const BASE_URL = 'https://api.your-lender.com';

const client = axios.create({
  baseURL: BASE_URL,
  headers: {
    'X-API-Key': API_KEY,
    'Content-Type': 'application/json'
  }
});

async function submitApplication(borrowerData) {
  // Create borrower
  const intakeRes = await client.post('/intake/start', borrowerData);
  const borrowerId = intakeRes.data.borrower_id;
  
  // Run assessment
  const assessmentRes = await client.post('/assessment/run', {
    borrower_id: borrowerId
  });
  
  return assessmentRes.data;
}

// Usage
const result = await submitApplication({
  name: 'Jane Doe',
  phone: '+254700000000',
  monthly_income: 50000,
  // ... other fields
});

console.log(`Decision: ${result.decision}`);
```

---

## Support

### Documentation

- **Developer Docs**: [/documentation](http://localhost:8000/documentation)
- **API Reference**: [/docs](http://localhost:8000/docs) (Swagger UI)
- **Interactive Explorer**: [/redoc](http://localhost:8000/redoc)

### Getting Help

**Technical Support:**
- Email: dev-support@your-lender.com
- Response Time: 24 hours (business days)
- Emergency: [Support phone]

**Best Practices:**
- Search documentation first
- Include request/response examples
- Provide error messages
- Share your code (remove API keys!)

---

## Next Steps

1. ✅ Get your test API key
2. ✅ Run your first test request
3. ✅ Build your integration
4. ✅ Test thoroughly
5. ✅ Get production API key
6. ✅ Launch!

**Good luck with your integration!** 🚀

For more technical details, see the [Developer Documentation](./architecture.md).
