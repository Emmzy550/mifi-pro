# 🚀 Postman Testing Guide: Loan Officer AI

This guide provides step-by-step instructions on how to test the **Borrower Intake**, **Alternative Data Ingestion**, and **Loan Assessment Engine** using Postman.

---

## 🛠️ Step 0: Environment Setup

Before sending requests, ensure you have the following information:

1.  **Base URL**: `https://api-139601123738.us-central1.run.app` (Deployed Production API)
2.  **API Key**: You need an active API key. You can find or create one in the Dashboard settings.

### Required Headers
For **all** requests, include these headers in Postman:

| Key | Value |
| :--- | :--- |
| `Authorization` | `Bearer YOUR_API_KEY` |
| `X-API-KEY` | `YOUR_API_KEY` |
| `Content-Type` | `application/json` |

---

## 📝 Step 1: Create a Borrower (Intake)

The engine needs a borrower profile to analyze.

*   **Endpoint**: `POST {{BaseURL}}/intake/start`
*   **Body Type**: `JSON`

### Request Body Example:
```json
{
  "name": "Jane Doe",
  "phone": "+254700000000",
  "email": "jane@example.com",
  "employment_type": "trader",
  "monthly_income": 50000,
  "monthly_expenses": 20000,
  "loan_amount_requested": 15000,
  "loan_purpose": "Business stock purchase"
}
```

> [!TIP]
> **Automatic Organization Detection:** If you include your `X-API-KEY` in the headers (as described in Step 0), the system will automatically associate the borrower with your organization. You no longer need to manually pass `organization_id` in the JSON body unless you want to override it.

> [!IMPORTANT]
> **Save the `borrower_id`** from the response (e.g., `BOR-12345`). You will need it for the next steps.

---

## 📊 Step 2: Upload Alternative Data (Optional but Recommended)

To test how the engine handles behavioral data (Mobile Money, Utilities), upload context for the borrower.

*   **Endpoint**: `POST {{BaseURL}}/behavior/upload`
*   **Body Type**: `JSON`

### Request Body Example:
```json
{
  "borrower_id": "BOR-12345",
  "airtime_usage_avg": 500.0,
  "mobile_money_history": [
    {"transaction_id": "TX1001", "amount": 5000, "type": "DEPOSIT", "timestamp": "2024-03-01T10:00:00"},
    {"transaction_id": "TX1002", "amount": 2000, "type": "PAYMENT", "timestamp": "2024-03-05T14:30:00"}
  ],
  "utility_history": [
    {"utility_name": "ZESCO", "amount": 500, "timestamp": "2024-03-01T00:00:00", "status": "PAID"}
  ]
}
```

---

## ⚡ Step 3: Run the Assessment

This is where the engine analyzes the data and provides a result.

*   **Endpoint**: `POST {{BaseURL}}/assessment/run`
*   **Body Type**: `JSON`

### Request Body Example:
```json
{
  "borrower_id": "BOR-12345"
}
```

---

## 🔍 Step 4: Understanding the Results

The engine will return a detailed JSON response. Key fields to look for:

- **`decision`**: `APPROVE`, `CONDITIONAL`, `REJECT`, or `REFER`.
- **`decision_legacy`**: Backward-compatible label for older clients.
- **`risk_score`**: A value between 0 and 1 (lower is better).
- **`explanation`**: A detailed breakdown of why the decision was made.
- **`recommended_terms`**: Suggested loan amount and interest rate.
- **`behavioral_insights`**: (If data was uploaded) Analysis of the alternative data.

### Example Response Snippet:
```json
{
  "assessment_id": "ASSESS-ABC123",
  "decision": "APPROVE",
  "decision_legacy": "APPROVED",
  "risk_score": 0.15,
  "explanation": "Borrower has stable income and high affordability ratio...",
  "recommended_terms": {
    "amount": 15000,
    "interest_rate": 15.0
  }
}
```
---

## 🛡️ Step 5: Testing AI Governance (Vertex AI)

If you have connected Vertex AI, you can toggle it on/off via the Admin API and see the difference in explanations.

### 5.1 Enable/Disable AI Explanations
*   **Endpoint**: `PATCH {{BaseURL}}/admin/platform/settings`
*   **Auth**: Requires Super Admin login/token.

**Request Body (Enable):**
```json
{
  "llm_enabled": true
}
```

### 5.2 Verify AI in Assessments
Once enabled, run **Step 3** (Assessment) again. Look for these specific fields in the JSON response:

*   **`explanation`**: Will be rephrased into a more professional, natural paragraph.
*   **`explanation_source`**: Should say `"vertex_ai"`.
*   **`decision_source`**: Should say `"engine"` (since the AI *only* rephrases, never decides).

---
