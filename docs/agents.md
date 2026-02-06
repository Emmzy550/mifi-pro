# Agent System Guide

Deep dive into each agent in the Loan Officer AI multi-agent system.

## Table of Contents

- [Overview](#overview)
- [IntakeAgent](#intakeagent)
- [RiskAgent](#riskagent)
- [BehavioralAgentV2](#behavioralagentv2)
- [MLRiskAgent](#mlriskagent)
- [DecisionAgent](#decisionagent)
- [ExplanationAgent](#explanationagent)
- [AuditAgent](#auditagent)
- [AuthAgent](#authagent)
- [SelfHealingAgent](#selfhealingagent)
- [Creating Custom Agents](#creating-custom-agents)

---

## Overview

Each agent follows the **Single Responsibility Principle** and communicates through well-defined interfaces. Agents are stateless and can be tested independently.

**Agent Pattern:**
```python
class ExampleAgent:
    @staticmethod
    def process(input_data):
        # Validate input
        # Perform core logic
        # Return structured output
        return result
```

---

## IntakeAgent

**File:** [`agents/intake_agent.py`](../agents/intake_agent.py)

**Purpose:** Validate and sanitize borrower data from external sources.

### Key Methods

```python
@staticmethod
def process(raw_data: dict) -> Borrower
```

### Implementation

```python
class IntakeAgent:
    @staticmethod
    def process(raw_data: dict) -> Borrower:
        name = raw_data.get("name", "").strip()
        phone = raw_data.get("phone", "").strip()
        
        # Validation
        if not name:
            raise ValueError("Borrower name is required")
        if not phone:
            raise ValueError("Phone number is required")
            
        # Create Borrower object
        return Borrower(
            name=name,
            phone=phone,
            employment_type=raw_data.get("employment_type"),
            monthly_income=float(raw_data.get("monthly_income", 0)),
            monthly_expenses=float(raw_data.get("monthly_expenses", 0)),
            existing_debt=float(raw_data.get("existing_debt", 0)),
            loan_amount_requested=float(raw_data.get("loan_amount_requested", 0)),
            loan_purpose=raw_data.get("loan_purpose", "")
        )
```

### Extension Points

Add custom validation rules:

```python
# Custom validator for specific employment types
APPROVED_EMPLOYMENT_TYPES = ["salaried", "trader", "farmer", "self_employed"]

if employment_type not in APPROVED_EMPLOYMENT_TYPES:
    raise ValueError(f"Invalid employment type: {employment_type}")
```

---

## RiskAgent

**File:** [`agents/risk_agent.py`](../agents/risk_agent.py)

**Purpose:** Core orchestrator for risk evaluation. Combines rules, behavioral analysis, and ML predictions.

### Key Methods

```python
@staticmethod
def evaluate(borrower: Borrower, external_behavioral_results: dict = None) -> dict
```

### Workflow

1. Run deterministic lending rules
2. Fetch alternative data (if exists)
3. Call BehavioralAgentV2 (if data available)
4. Call MLRiskAgent (if ML enabled)
5. Compute ensemble score
6. Apply safety gates
7. Return comprehensive risk results

### Critical Safety Gates

```python
# Gate 1: Critical flags force maximum risk
if any(flag["severity"] == "CRITICAL" for flag in flags):
    risk_score = 1.0
    risk_level = "HIGH"
    
# Gate 2: ML cannot reduce rule score
if ml_enabled:
    ensemble_score = (RULE_WEIGHT * rule_score) + (ML_WEIGHT * ml_prob)
    final_score = max(rule_score, ensemble_score)  # Rules override optimistic ML
```

### Customization

**Adding Custom Rules:**

```python
# In evaluate() method, add after existing rule checks:

# Custom: Reject if loan > 50% of annual income
annual_income = borrower.monthly_income * 12
if borrower.loan_amount_requested > (annual_income * 0.5):
    flags.append({
        "flag": "LOAN_TOO_LARGE",
        "severity": "CRITICAL",
        "message": f"Loan exceeds 50% of annual income"
    })
    risk_score = 1.0
```

---

## Behavioral AgentV2

**File:** [`agents/behavioral_agent_v2.py`](../agents/behavioral_agent_v2.py)

**Purpose:** Analyze alternative data (transactions, utilities) without ML. Pure statistical analysis.

### Key Methods

```python
@staticmethod
def analyze(alt_data: AlternativeData) -> dict

@staticmethod
def analyze_transactions(transactions: List[Transaction]) -> dict
```

### Metrics Computed

#### 1. Income Consistency Score (0-1)

Measures deposit regularity using coefficient of variation (CV):

```python
deposits = [t.amount for t in transactions if t.type == "DEPOSIT"]
mean_deposit = np.mean(deposits)
std_deposit = np.std(deposits)
cv = std_deposit / mean_deposit

# Lower CV = more consistent
consistency_score = max(0, 1 - cv)
```

**Interpretation:**
- `> 0.8`: Very consistent income
- `0.5-0.8`: Moderately consistent
- `< 0.5`: Irregular income

---

#### 2. Transaction Stability (0-1)

Inverse of spending volatility:

```python
withdrawals = [t.amount for t in transactions if t.type == "WITHDRAWAL"]
volatility = np.std(withdrawals) / np.mean(withdrawals)
stability = max(0, 1 - volatility)
```

---

#### 3. Savings Behavior (0-1)

Net cash flow analysis:

```python
total_deposits = sum(t.amount for t in deposits)
total_withdrawals = sum(t.amount for t in withdrawals)
net_savings = total_deposits - total_withdrawals

savings_score = min(1.0, net_savings / (total_deposits + 1))
```

---

#### 4. Utility Compliance (0-1)

On-time payment percentage:

```python
on_time_count = sum(1 for u in utilities if u.paid_on_time)
total_count = len(utilities)
compliance = on_time_count / total_count if total_count > 0 else 0
```

---

### Early Warning Detection

```python
early_warnings = []

# Warning 1: Spending spike
recent_spending = sum(last_30_days_withdrawals)
avg_spending = sum(all_withdrawals) / len(all_withdrawals)
if recent_spending > avg_spending * 1.5:
    early_warnings.append("SPENDING_SPIKE_DETECTED")

# Warning 2: Missed utility payment
if any(not u.paid_on_time for u in recent_utilities):
    early_warnings.append("MISSED_UTILITY_PAYMENT")
```

---

## MLRiskAgent

**File:** [`agents/ml_risk_agent.py`](../agents/ml_risk_agent.py)

**Purpose:** Predictive ML scoring using XGBoost + SHAP explainability.

### Key Methods

```python
@staticmethod
def predict(borrower: Borrower) -> dict
```

### Model Loading

```python
@classmethod
def _load_model(cls):
    if cls._model is None:
        try:
            cls._model = xgb.Booster()
            cls._model.load_model(config.ML_MODEL_PATH)
            
            with open(config.ML_FEATURES_PATH) as f:
                cls._feature_names = [line.strip() for line in f]
        except:
            print("⚠️ ML model not found. Continuing with rule-based scoring.")
            cls._model = "UNAVAILABLE"
```

### Feature Engineering

```python
def _extract_features(borrower: Borrower) -> np.array:
    return np.array([[
        borrower.monthly_income,
        borrower.monthly_expenses,
        borrower.existing_debt,
        borrower.loan_amount_requested,
        borrower.monthly_income - borrower.monthly_expenses,  # disposable income
        borrower.existing_debt / max(borrower.monthly_income, 1),  # DTI
        # ... more features
    ]])
```

### SHAP Explanation

```python
import shap

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(features)

feature_importance = [
    {"feature": name, "impact": float(shap_val)}
    for name, shap_val in zip(feature_names, shap_values[0])
]
```

---

## DecisionAgent

**File:** [`agents/decision_agent.py`](../agents/decision_agent.py)

**Purpose:** Translate risk scores into loan decisions and recommendations.

### Key Methods

```python
@staticmethod
def recommend(risk_results: dict, borrower: Borrower) -> dict
```

### Decision Logic

```python
risk_score = risk_results["risk_score"]

if risk_score < 0.3:  # LOW RISK
    return {
        "decision": "APPROVE",
        "recommended_amount": borrower.loan_amount_requested,
        "recommended_interest_rate": config.BASE_INTEREST_RATE  # 15%
    }
    
elif risk_score < 0.7:  # MEDIUM RISK
    # Conditional approval with higher rate
    reduction_factor = 1.0  # Can add haircut if needed
    return {
        "decision": "CONDITIONAL",
        "recommended_amount": borrower.loan_amount_requested * reduction_factor,
        "recommended_interest_rate": config.CONDITIONAL_INTEREST_RATE  # 20%
    }
    
else:  # HIGH RISK
    return {
        "decision": "REJECT",
        "recommended_amount": 0,
        "recommended_interest_rate": 0
    }
```

### Customization

Add graduated interest rates:

```python
if 0 <= risk_score <= 0.25:
    interest_rate = 12.0  # Best rate
elif 0.26 <= risk_score <= 0.4:
    interest_rate = 15.0  # Standard rate
elif 0.41 <= risk_score <= 0.55:
    interest_rate = 18.0  # Moderate risk
elif 0.56 <= risk_score <= 0.7:
    interest_rate = 22.0  # Higher risk
else:
    return {"decision": "REJECT", ...}
```

---

## ExplanationAgent

**File:** [`agents/explanation_agent.py`](../agents/explanation_agent.py)

**Purpose:** Generate human-readable, structured explanations for loan decisions.

### Key Methods

```python
@staticmethod
def generate(risk_results: dict, decision_results: dict, borrower: Borrower) -> dict
```

### Output Structure

```python
{
  "summary": "One-sentence executive summary",
  "risk_factors": ["Factor 1", "Factor 2", ...],
  "recommendations": ["Action 1", "Action 2", ...],
  "behavioral_insights": {
    "income_consistency": 0.85,
    "early_warnings": []
  },
  "ml_insights": {
    "probability_of_default": 0.23,
    "top_features": [...]
  }
}
```

### Explanation Templates

```python
# LOW RISK
if decision == "APPROVE":
    summary = f"✅ Approved at {interest_rate}% interest rate. Strong financial profile."

# MEDIUM RISK
elif decision == "CONDITIONAL":
    summary = f"⚠️ Conditionally approved with elevated rate ({interest_rate}%)."

# HIGH RISK
else:
    summary = "❌ Loan not recommended due to high risk factors."
```

---

## AuditAgent

**File:** [`agents/audit_agent.py`](../agents/audit_agent.py)

**Purpose:** Comprehensive event logging for compliance and debugging.

### Key Methods

```python
@staticmethod
def log_event(event_type: str, actor: str, metadata: dict)

@staticmethod
def list_org_logs(org_id: str, limit: int = 50) -> List[dict]
```

### Event Types

- `INTAKE_START` - Borrower profile created
- `ASSESSMENT_GENERATE` - Risk assessment completed
- `LOAN_DISBURSED` - Loan approved and disbursed
- `LOAN_STATUS_CHANGE` - Loan status updated
- `DATA_UPLOAD` - Alternative data uploaded
- `MODEL_RETRAIN` - ML model retrained
- `CONFIG_UPDATE` - Configuration changed
- `KEY_CREATE` / `KEY_REVOKE` - API key lifecycle

### Usage

```python
AuditAgent.log_event(
    event_type="ASSESSMENT_GENERATE",
    actor="SYSTEM",
    metadata={
        "assessment_id": assessment.assessment_id,
        "borrower_id": borrower.id,
        "risk_score": assessment.risk_score,
        "decision": assessment.decision,
        "org": borrower.organization_id
    }
)
```

---

## AuthAgent

**File:** [`agents/auth_agent.py`](../agents/auth_agent.py)

**Purpose:** Authentication, authorization, and API key management.

### Key Methods

```python
@staticmethod
def authenticate_user(email: str, password: str) -> User

@staticmethod
def create_access_token(data: dict, expires_delta: timedelta) -> str

@staticmethod
def create_api_key(org_id: str, name: str, env: str, created_by: str) -> (str, APIKey)

@staticmethod
def get_current_user(token: str) -> User

@staticmethod
def get_api_key(api_key: str) -> AuthUser
```

### JWT Token Generation

```python
from jose import jwt
import datetime

payload = {
    "sub": user.email,
    "role": user.role,
    "org": user.organization_id,
    "exp": datetime.datetime.utcnow() + timedelta(minutes=30)
}

token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
```

### API Key Format

```
loa_{environment}_{random_32_chars}

Examples:
- loa_live_abc123def456ghi789...
- loa_test_xyz987uvw654rst321...
```

---

## SelfHealingAgent

**File:** [`agents/self_healing_agent.py`](../agents/self_healing_agent.py)

**Purpose:** Monitor model performance and trigger retraining.

### Key Concepts

1. **Outcome Registration**: When loans are paid/defaulted, register actual outcomes
2. **Drift Detection**: Compare predicted vs actual default rates
3. **Auto-Retraining**: Trigger model retraining if accuracy degrades

### Usage

```python
# When loan is closed
if loan.status in [LoanStatus.PAID, LoanStatus.DEFAULTED]:
    SelfHealingAgent.register_outcome(loan.loan_id, loan.status)
    
    # Check if retraining needed
    if SelfHealingAgent.check_model_drift():
        trigger_retraining()
```

---

## Creating Custom Agents

### Template

```python
# agents/custom_agent.py

class CustomAgent:
    """
    Purpose: [What does this agent do?]
    
    Inputs:
    - param1: Description
    - param2: Description
    
    Outputs:
    - dict: Structured result
    """
    
    @staticmethod
    def process(input_data):
        # 1. Validate inputs
        if not input_data:
            raise ValueError("Input required")
        
        # 2. Core logic
        result = perform_analysis(input_data)
        
        # 3. Return structured output
        return {
            "status": "SUCCESS",
            "result": result,
            "metadata": {...}
        }
```

### Integration

1. Import in `main.py`:
```python
from agents.custom_agent import CustomAgent
```

2. Call in endpoint:
```python
@app.post("/custom/analyze")
async def custom_analyze(data: dict):
    result = CustomAgent.process(data)
    return result
```

---

## Next Steps

- [Architecture Guide](./architecture.md) - System design overview
- [Integration Guide](./integration.md) - Using agents in your app
- [Testing Guide](./testing.md) - Testing agents

