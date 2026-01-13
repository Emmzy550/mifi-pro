# Integration Guide

Learn how to integrate the Loan Officer AI Agent into your applications.

## Table of Contents

- [Frontend Integration](#frontend-integration)
- [Backend Integration](#backend-integration)
- [Webhook Configuration](#webhook-configuration)
- [Alternative Data Upload](#alternative-data-upload)
- [Multi-Tenancy Setup](#multi-tenancy-setup)
- [Code Examples](#code-examples)

---

## Frontend Integration

### React Example

```jsx
import React, { useState } from 'react';

const LoanApplicationForm = () => {
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    employment_type: 'trader',
    monthly_income: '',
    monthly_expenses: '',
    existing_debt: '',
    loan_amount_requested: '',
    loan_purpose: ''
  });
  
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      // Step 1: Submit borrower profile
      const intakeResponse = await fetch('/intake/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData)
      });
      
      const { borrower_id } = await intakeResponse.json();
      
      // Step 2: Run assessment
      const assessmentResponse = await fetch('/assessment/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ borrower_id })
      });
      
      const assessment = await assessmentResponse.json();
      setResult(assessment);
      
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      <form onSubmit={handleSubmit}>
        {/* Form fields */}
        <input 
          type="text" 
          value={formData.name}
          onChange={(e) => setFormData({...formData, name: e.target.value})}
          placeholder="Full Name"
          required
        />
        {/* ... more fields */}
        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Apply for Loan'}
        </button>
      </form>
      
      {result && (
        <div className="result">
          <h3>Assessment Result</h3>
          <p><strong>Decision:</strong> {result.decision}</p>
          <p><strong>Risk Level:</strong> {result.risk_level}</p>
          <p><strong>Recommended Amount:</strong> ${result.recommended_amount}</p>
          <p><strong>Interest Rate:</strong> {result.recommended_interest_rate}%</p>
          <div>{result.explanation.summary}</div>
        </div>
      )}
    </div>
  );
};
```

---

### Vanilla JavaScript

```html
<!DOCTYPE html>
<html>
<head>
    <title>Loan Application</title>
</head>
<body>
    <form id="loanForm">
        <input type="text" id="name" placeholder="Full Name" required>
        <input type="tel" id="phone" placeholder="Phone Number" required>
        <input type="number" id="income" placeholder="Monthly Income" required>
        <button type="submit">Apply</button>
    </form>
    
    <div id="result"></div>
    
    <script>
        document.getElementById('loanForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('name').value,
                phone: document.getElementById('phone').value,
                monthly_income: parseFloat(document.getElementById('income').value),
                // ... other fields
            };
            
            // Step 1: Create borrower
            const intakeRes = await fetch('http://localhost:8000/intake/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });
            
            const { borrower_id } = await intakeRes.json();
            
            // Step 2: Run assessment
            const assessmentRes = await fetch('http://localhost:8000/assessment/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ borrower_id })
            });
            
            const assessment = await assessmentRes.json();
            
            // Display result
            document.getElementById('result').innerHTML = `
                <h3>${assessment.decision}</h3>
                <p>Risk: ${assessment.risk_level}</p>
                <p>Amount: $${assessment.recommended_amount}</p>
                <p>Rate: ${assessment.recommended_interest_rate}%</p>
            `;
        });
    </script>
</body>
</html>
```

---

## Backend Integration

### Python (FastAPI/Flask)

```python
import httpx

class LoanService:
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient()
    
    async def create_loan_application(self, borrower_data: dict):
        # Step 1: Create borrower profile
        intake_response = await self.client.post(
            f"{self.api_url}/intake/start",
            json=borrower_data
        )
        borrower_id = intake_response.json()["borrower_id"]
        
        # Step 2: Run assessment
        assessment_response = await self.client.post(
            f"{self.api_url}/assessment/run",
            json={"borrower_id": borrower_id}
        )
        
        return assessment_response.json()
    
    async def upload_transactions(self, borrower_id: str, file_path: str):
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'borrower_id': borrower_id}
            
            response = await self.client.post(
                f"{self.api_url}/behavior/upload",
                files=files,
                data=data
            )
            
        return response.json()
    
    async def get_assessment(self, assessment_id: str):
        response = await self.client.get(
            f"{self.api_url}/assessment/result/{assessment_id}"
        )
        return response.json()

# Usage
service = LoanService(
    api_url="http://localhost:8000",
    api_key="loa_live_abc123..."
)

assessment = await service.create_loan_application({
    "name": "Jane Doe",
    "phone": "+254700000000",
    "monthly_income": 50000,
    # ... other fields
})
```

---

### Node.js

```javascript
const axios = require('axios');

class LoanService {
  constructor(apiUrl, apiKey) {
    this.apiUrl = apiUrl;
    this.apiKey = apiKey;
    this.client = axios.create({
      baseURL: apiUrl,
      headers: {
        'X-API-Key': apiKey
      }
    });
  }
  
  async createLoanApplication(borrowerData) {
    // Step 1: Create borrower
    const intakeRes = await this.client.post('/intake/start', borrowerData);
    const { borrower_id } = intakeRes.data;
    
    // Step 2: Run assessment
    const assessmentRes = await this.client.post('/assessment/run', {
      borrower_id
    });
    
    return assessmentRes.data;
  }
  
  async uploadTransactions(borrowerId, filePath) {
    const FormData = require('form-data');
    const fs = require('fs');
    
    const formData = new FormData();
    formData.append('borrower_id', borrowerId);
    formData.append('file', fs.createReadStream(filePath));
    
    const res = await this.client.post('/behavior/upload', formData, {
      headers: formData.getHeaders()
    });
    
    return res.data;
  }
}

// Usage
const service = new LoanService(
  'http://localhost:8000',
  'loa_live_abc123...'
);

const assessment = await service.createLoanApplication({
  name: 'Jane Doe',
  phone: '+254700000000',
  monthly_income: 50000,
  // ... other fields
});

console.log(`Decision: ${assessment.decision}`);
```

---

## Webhook Configuration

Webhooks allow you to receive real-time notifications when loan decisions are made.

### Setup

1. **Configure Webhook URL**

```bash
curl -X PATCH http://localhost:8000/org/settings \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_url": "https://yourapp.com/webhooks/loan-decisions",
    "regenerate_secret": true
  }'
```

**Response:**
```json
{
  "webhook_url": "https://yourapp.com/webhooks/loan-decisions",
  "webhook_secret": "whsec_abc123...",
  "feature_flags": {...}
}
```

> [!IMPORTANT]
> Store the `webhook_secret` securely. It's used to verify webhook authenticity.

---

### Webhook Payload

When a loan decision is made, the system sends:

```json
{
  "event_type": "assessment.completed",
  "timestamp": "2024-01-15T10:35:00Z",
  "organization_id": "ORG-12345",
  "data": {
    "assessment_id": "ASMT-X1Y2Z3A4",
    "borrower_id": "BOR-A1B2C3D4",
    "decision": "CONDITIONAL_APPROVAL",
    "risk_score": 45,
    "risk_level": "MEDIUM",
    "recommended_amount": 15000,
    "recommended_interest_rate": 20.0
  }
}
```

---

### Verify Webhook Signature

```python
import hmac
import hashlib

def verify_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected_signature = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

# FastAPI endpoint
@app.post("/webhooks/loan-decisions")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature")
    
    if not verify_webhook(payload, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    data = await request.json()
    
    # Process webhook
    if data["event_type"] == "assessment.completed":
        assessment_id = data["data"]["assessment_id"]
        decision = data["data"]["decision"]
        
        # Update your system
        await update_loan_status(assessment_id, decision)
    
    return {"status": "received"}
```

---

## Alternative Data Upload

### CSV Format

Create a CSV file with transaction history:

```csv
Date,Type,Amount,Description
2024-01-15,DEPOSIT,5000,Salary
2024-01-16,WITHDRAWAL,2000,ATM
2024-01-17,PAYMENT,500,Electricity
2024-01-20,DEPOSIT,3000,Business Income
2024-01-25,PAYMENT,300,Water Bill
```

**Upload:**

```bash
curl -X POST http://localhost:8000/behavior/upload \
  -F "borrower_id=BOR-A1B2C3D4" \
  -F "file=@transactions.csv"
```

---

### PDF Bank Statements

The system can parse PDF bank statements (basic text extraction):

```bash
curl -X POST http://localhost:8000/borrower/data/upload-document \
  -F "borrower_id=BOR-A1B2C3D4" \
  -F "file=@bank_statement.pdf"
```

> [!NOTE]
> PDF parsing requires PyPDF2: `pip install PyPDF2`

---

### Programmatic Upload

```python
from models.alternative_data import AlternativeData, MobileMoneyTransaction

alt_data = AlternativeData(
    borrower_id="BOR-A1B2C3D4",
    mobile_money_history=[
        MobileMoneyTransaction(
            timestamp=datetime(2024, 1, 15),
            type="DEPOSIT",
            amount=5000,
            counterparty="Employer"
        ),
        # ... more transactions
    ]
)

response = requests.post(
    "http://localhost:8000/borrower/data/upload",
    headers={"X-API-Key": "loa_live_abc123..."},
    json=alt_data.dict()
)
```

---

## Multi-Tenancy Setup

### Organization Onboarding

1. **Create Organization**

```python
from models.organization import Organization

org = Organization(
    id="ORG-ACME",
    name="ACME Microfinance",
    webhook_url="https://acme.com/webhooks",
    feature_flags={
        "enable_ml": True,
        "enable_behavioral": True
    }
)

Database.save_organization(org)
```

2. **Create Admin User**

```python
from agents.auth_agent import AuthAgent

user = User(
    id="USER-001",
    email="admin@acme.com",
    role="ORG_ADMIN",
    organization_id="ORG-ACME"
)

user.password_hash = AuthAgent._hash_password("secure_password")
Database.save_user(user)
```

3. **Generate API Key**

```bash
curl -X POST http://localhost:8000/api-keys/create \
  -H "Authorization: Bearer ADMIN_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ACME Production Key",
    "environment": "production"
  }'
```

---

### Data Isolation

All API calls automatically filter by `organization_id`:

```python
# In endpoint
@app.get("/borrowers")
async def list_borrowers(user: AuthUser = Depends(AuthAgent.get_api_key)):
    # Automatically scoped to user's organization
    return Database.list_borrowers(organization_id=user.organization_id)
```

**Security:**
- Cross-org access blocked at API level
- Database queries filtered by `organization_id`
- Audit logs track all access attempts

---

## Code Examples

### Complete Integration Flow

```python
import asyncio
from loan_service import LoanService

async def complete_loan_flow():
    service = LoanService("http://localhost:8000", "loa_live_abc123...")
    
    # 1. Submit application
    borrower_data = {
        "name": "Jane Doe",
        "phone": "+254700000000",
        "employment_type": "trader",
        "monthly_income": 50000,
        "monthly_expenses": 20000,
        "existing_debt": 5000,
        "loan_amount_requested": 15000,
        "loan_purpose": "Business expansion"
    }
    
    assessment = await service.create_loan_application(borrower_data)
    print(f"Initial Decision: {assessment['decision']}")
    
    # 2. Upload transactions (optional)
    if assessment['decision'] == 'CONDITIONAL_APPROVAL':
        await service.upload_transactions(
            borrower_id=assessment['borrower_id'],
            file_path='transactions.csv'
        )
        
        # Re-run assessment
        new_assessment = await service.client.post(
            f"/assessment/run",
            json={"borrower_id": assessment['borrower_id']}
        )
        
        print(f"Updated Decision: {new_assessment.json()['decision']}")
    
    # 3. If approved, disburse loan
    if assessment['decision'] in ['APPROVED', 'CONDITIONAL_APPROVAL']:
        # Officer disburses via dashboard or API
        pass

asyncio.run(complete_loan_flow())
```

---

## Next Steps

- [API Reference](./api-reference.md) - Complete endpoint documentation
- [Testing Guide](./testing.md) - Test your integration
- [Troubleshooting](./troubleshooting.md) - Common issues
