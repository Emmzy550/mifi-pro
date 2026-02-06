# Testing Guide

Learn how to test the Loan Officer AI Agent system effectively.

## Table of Contents

- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing New Tests](#writing-new-tests)
- [Manual Testing](#manual-testing)
- [Behavioral Data Testing](#behavioral-data-testing)

---

## Running Tests

### Comprehensive Test Suite

Run the full test suite:

```bash
python tests/test_comprehensive.py
```

**What it tests:**
- ✅ Rule-only mode (ML disabled)
- ✅ Ensemble mode (ML enabled) 
- ✅ Critical flag overrides
- ✅ Behavioral V2 integration
- ✅ Config snapshot auditing

### Expected Output

```
Running Comprehensive Test Suite...
✅ Test 1: Rule-Only Mode (ML Disabled)
✅ Test 2: Ensemble Mode (ML Enabled)
✅ Test 3: Critical Flag Override
✅ Test 4: Behavioral Intelligence Integration
✅ Test 5: Config Snapshot in Assessment

All tests passed! ✅
```

---

## Test Coverage

### Unit Tests

Test individual agents:

```python
# test_intake_agent.py
from agents.intake_agent import IntakeAgent

def test_intake_validation():
    valid_data = {
        "name": "Jane Doe",
        "phone": "+254700000000",
        "monthly_income": 50000,
        "monthly_expenses": 20000,
        "existing_debt": 5000,
        "loan_amount_requested": 15000,
        "loan_purpose": "Business",
        "employment_type": "trader"
    }
    
    borrower = IntakeAgent.process(valid_data)
    assert borrower.name == "Jane Doe"
    assert borrower.monthly_income == 50000

def test_intake_missing_fields():
    invalid_data = {"name": "Jane"}
    
    try:
        IntakeAgent.process(invalid_data)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "phone" in str(e).lower()
```

### Integration Tests

Test complete workflows:

```python
# test_assessment_flow.py
from utils.db import Database
from agents.intake_agent import IntakeAgent
from agents.risk_agent import RiskAgent

def test_complete_assessment():
    # 1. Create borrower
    borrower_data = {...}
    borrower = IntakeAgent.process(borrower_data)
    borrower.id = "BOR-TEST"
    Database.save_borrower(borrower)
    
    # 2. Run assessment
    risk_results = RiskAgent.evaluate(borrower)
    
    # 3. Verify results
    assert "risk_score" in risk_results
    assert risk_results["risk_level"] in ["LOW", "MEDIUM", "HIGH"]
    assert len(risk_results["flags"]) > 0
```

---

## Writing New Tests

### Test Template

```python
import pytest
from models.borrower import Borrower
from agents.risk_agent import RiskAgent

class TestCustomFeature:
    """Test suite for custom feature"""
    
    @pytest.fixture
    def sample_borrower(self):
        """Reusable test borrower"""
        return Borrower(
            name="Test User",
            phone="+254700000000",
            employment_type="salaried",
            monthly_income=50000,
            monthly_expenses=20000,
            existing_debt=5000,
            loan_amount_requested=15000,
            loan_purpose="Test"
        )
    
    def test_feature_success_case(self, sample_borrower):
        """Test successful scenario"""
        result = RiskAgent.evaluate(sample_borrower)
        assert result["risk_score"] <= 0.7
    
    def test_feature_edge_case(self, sample_borrower):
        """Test edge case"""
        sample_borrower.monthly_income = 0
        result = RiskAgent.evaluate(sample_borrower)
        assert result["risk_score"] == 1.0
        
    def test_feature_error_handling(self):
        """Test error handling"""
        with pytest.raises(ValueError):
            RiskAgent.evaluate(None)
```

### Running Pytest

```bash
# Install pytest
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=agents --cov=models tests/

# Run specific test file
pytest tests/test_risk_agent.py

# Run specific test
pytest tests/test_risk_agent.py::TestRiskAgent::test_high_risk_scenario
```

---

## Manual Testing

### Using curl

**Test 1: Health Check**

```bash
curl http://localhost:8000/api/health
```

**Test 2: Create Borrower**

```bash
curl -X POST http://localhost:8000/intake/start \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test User",
    "phone": "+254700000000",
    "employment_type": "trader",
    "monthly_income": 50000,
    "monthly_expenses": 20000,
    "existing_debt": 5000,
    "loan_amount_requested": 15000,
    "loan_purpose": "Test"
  }'
```

**Test 3: Run Assessment**

```bash
# Replace BOR-XXX with actual borrower_id from step 2
curl -X POST http://localhost:8000/assessment/run \
  -H "Content-Type: application/json" \
  -d '{"borrower_id": "BOR-XXX"}'
```

---

### Using Postman/Swagger

1. **Swagger UI**: Visit `http://localhost:8000/docs`
2. Click on any endpoint to expand
3. Click "Try it out"
4. Fill in parameters
5. Click "Execute"

---

### Test Scenarios

#### Scenario 1: Low Risk Borrower

```json
{
  "name": "Low Risk User",
  "phone": "+254700000001",
  "employment_type": "salaried",
  "monthly_income": 100000,
  "monthly_expenses": 30000,
  "existing_debt": 5000,
  "loan_amount_requested": 20000,
  "loan_purpose": "Home improvement"
}
```

**Expected:** `APPROVE` at 15% interest

---

#### Scenario 2: High Risk Borrower

```json
{
  "name": "High Risk User",
  "phone": "+254700000002",
  "employment_type": "trader",
  "monthly_income": 10000,
  "monthly_expenses": 8000,
  "existing_debt": 3000,
  "loan_amount_requested": 50000,
  "loan_purpose": "Emergency"
}
```

**Expected:** `REJECT` due to low affordability and high DTI

---

#### Scenario 3: Conditional Approval

```json
{
  "name": "Medium Risk User",
  "phone": "+254700000003",
  "employment_type": "trader",
  "monthly_income": 50000,
  "monthly_expenses": 25000,
  "existing_debt": 10000,
  "loan_amount_requested": 25000,
  "loan_purpose": "Business"
}
```

**Expected:** `CONDITIONAL` at 20% interest

---

## Behavioral Data Testing

### Sample Transaction CSV

Create `test_transactions.csv`:

```csv
Date,Type,Amount,Description
2024-01-01,DEPOSIT,50000,Salary
2024-01-05,WITHDRAWAL,10000,Rent
2024-01-08,PAYMENT,500,Electricity
2024-01-10,DEPOSIT,15000,Freelance
2024-01-15,WITHDRAWAL,5000,Groceries
2024-01-20,PAYMENT,300,Water
2024-02-01,DEPOSIT,50000,Salary
2024-02-05,WITHDRAWAL,10000,Rent
2024-02-08,PAYMENT,500,Electricity
2024-02-15,WITHDRAWAL,7000,Transport
```

### Upload and Test

```bash
# 1. Create borrower
curl -X POST http://localhost:8000/intake/start \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Behavioral Test User",
    "phone": "+254700000010",
    "employment_type": "salaried",
    "monthly_income": 50000,
    "monthly_expenses": 20000,
    "existing_debt": 0,
    "loan_amount_requested": 10000,
    "loan_purpose": "Test"
  }'

# 2. Upload transactions (replace BOR-XXX)
curl -X POST http://localhost:8000/behavior/upload \
  -F "borrower_id=BOR-XXX" \
  -F "file=@test_transactions.csv"
```

**Expected Response:**

```json
{
  "status": "SUCCESS",
  "transaction_count": 10,
  "behavioral_insights": {
    "income_consistency": 0.85,
    "transaction_stability": 0.72,
    "savings_behavior": 0.65,
    "utility_compliance": 1.0
  },
  "risk_assessment": {
    "score": 32,
    "level": "LOW",
    "decision": "APPROVE"
  }
}
```

---

### Testing ML Mode

**Enable ML:**

```bash
# Set environment variable
export ENABLE_ML_RISK_SCORING=true

# Restart server
python main.py
```

**Verify ML is Active:**

```bash
curl http://localhost:8000/model/version
```

**Expected:**

```json
{
  "model_version": "1.0.0",
  "ml_enabled": true,
  "ensemble_weights": {
    "rule_weight": 0.7,
    "ml_weight": 0.3
  }
}
```

---

## Continuous Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-cov
    
    - name: Run tests
      run: pytest tests/ --cov=agents --cov=models
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

## Next Steps

- [Deployment Guide](./deployment.md) - Deploy to production
- [Troubleshooting](./troubleshooting.md) - Debug common issues
- [Contributing](./CONTRIBUTING.md) - Contribute new tests

