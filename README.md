# Loan Officer AI Agent (V1 → V4)

## Overview

The **Loan Officer AI Agent** is a fintech-grade credit decision engine designed for microfinance institutions, SACCOs, and digital lenders in emerging markets. The system has evolved through 4 stages to combine rule-based reliability with AI-powered insights while maintaining regulatory compliance.

**CRITICAL PRINCIPLE:** This system does NOT auto-approve loans. Rules ALWAYS override ML predictions. All decisions are auditable and explainable.

---

## 📚 Documentation

Comprehensive developer documentation is available in the [`docs/`](./docs/) directory:

- **[Getting Started](./docs/getting-started.md)** - Installation, setup, and quickstart
- **[API Reference](./docs/api-reference.md)** - Complete API documentation
- **[Architecture Guide](./docs/architecture.md)** - System design and multi-agent workflow
- **[Agent System Guide](./docs/agents.md)** - Deep dive into each agent
- **[Integration Guide](./docs/integration.md)** - Frontend/backend integration examples
- **[Testing Guide](./docs/testing.md)** - Testing strategies and examples
- **[Deployment Guide](./docs/deployment.md)** - Production deployment instructions
- **[Troubleshooting](./docs/troubleshooting.md)** - Common issues and solutions
- **[Contributing](./docs/CONTRIBUTING.md)** - How to contribute

> **New to the project?** Start with the [Getting Started Guide](./docs/getting-started.md)

---

## System Evolution: V1 → V4

### V1: Rule-Based Foundation (Baseline)
- ✅ Deterministic lending rules (DTI, affordability, income stability)
- ✅ Multi-agent architecture (Intake, Risk, Decision, Explanation)
- ✅ Audit logging and multi-tenancy support
- ✅ REST API with structured JSON responses

### V2: Behavioral Intelligence (Alternative Data)
- ✅ Enhanced behavioral analysis without ML
- ✅ Income consistency scoring (deposit regularity)
- ✅ Transaction stability metrics (volatility analysis)
- ✅ Savings behavior trends (cash flow analysis)
- ✅ Utility payment compliance tracking

### V3: Predictive ML (Ensemble Engine)
- ✅ XGBoost + SHAP for explainable predictions
- ✅ Ensemble scoring (weighted rule + ML scores)
- ✅ Hard rule overrides (safety gates)
- ✅ Model versioning and performance tracking
- ✅ Feature flags for gradual rollout

### V4: Explanation Polish (Optional NLP)
- ✅ Structured explanation formatting
- ✅ Behavioral metrics in explanations
- ⚠️ LLM-powered rephrasing (optional, disabled by default)
- ✅ Primary/secondary reason prioritization

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI REST API                        │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
   ┌────▼────┐         ┌────▼────┐        ┌────▼────┐
   │ Intake  │         │  Risk   │        │Decision │
   │ Agent   │────────▶│ Agent   │───────▶│ Agent   │
   └─────────┘         └────┬────┘        └────┬────┘
                            │                   │
                ┌───────────┼───────────────┐   │
                │           │               │   │
           ┌────▼────┐ ┌────▼────┐    ┌────▼───▼────┐
           │Behavioral│ │   ML    │    │ Explanation │
           │Agent V2  │ │  Risk   │    │   Agent     │
           └──────────┘ │ Agent   │    └─────────────┘
                        └─────────┘
                             │
                    ┌────────▼────────┐
                    │ Ensemble Engine │
                    │ (Rule Override) │
                    └─────────────────┘
```

### Key Components

#### 1. **RiskAgent** (Core Orchestrator)
- Runs deterministic lending rules
- Calls ML predictor if enabled
- Analyzes behavioral data if available
- Combines scores with safety gates
- **Safety**: Critical flags force max risk score

#### 2. **BehavioralAgentV2** (Alternative Data)
- Income consistency (coefficient of variation)
- Transaction stability (volatility inverse)
- Savings behavior (net cash flow trends)
- Expense volatility (spending pattern analysis)
- **No ML**: Pure statistical analysis

#### 3. **MLRiskAgent** (Predictive Intelligence)
- XGBoost classifier for probability of default
- SHAP explainability (feature importance)
- Loads model from disk (no inline training)
- **Fallback**: System works without ML model

#### 4. **DecisionAgent** (Business Logic)
- Translates risk scores to loan decisions
- Adjusts interest rates based on risk
- Applies loan amount haircuts for medium risk
- **Deterministic**: Same inputs = same outputs

#### 5. **ExplanationAgent** (Transparency)
- Structured explanations with sections
- Behavioral intelligence insights
- ML feature importance (if enabled)
- Loan officer guidance

---

## Configuration & Feature Flags

All system behavior is controlled via `config.py`:

```python
# Feature Flags (can be set via environment variables)
ENABLE_ML_RISK_SCORING = True      # V3: ML predictions
ENABLE_BEHAVIORAL_V2 = True        # V2: Enhanced behavioral metrics
ENABLE_LLM_EXPLANATIONS = False    # V4: LLM rephrasing (disabled by default)

# Ensemble Weights (V3)
RULE_WEIGHT = 0.7  # 70% rules
ML_WEIGHT = 0.3    # 30% ML

# Business Rules
MIN_MONTHLY_INCOME = 100.0
MAX_DEBT_TO_INCOME_RATIO = 0.4
AFFORDABILITY_RATIO_TARGET = 0.3

# Interest Rates
BASE_INTEREST_RATE = 15.0          # Low risk
CONDITIONAL_INTEREST_RATE = 20.0   # Medium risk
CAUTION_INTEREST_RATE = 18.0       # Behavioral concerns
```

### Environment Variable Override

```bash
export ENABLE_ML_RISK_SCORING=false  # Disable ML
export ENABLE_LLM_EXPLANATIONS=true  # Enable LLM
python main.py
```

---

## API Endpoints

### Core Endpoints (V1)

#### `POST /intake/start`
Initialize borrower assessment
```json
{
  "name": "Jane Doe",
  "phone": "+254700000000",
  "employment_type": "trader",
  "monthly_income": 50000,
  "monthly_expenses": 20000,
  "existing_debt": 5000,
  "loan_amount_requested": 15000,
  "loan_purpose": "Business stock expansion"
}
```

#### `POST /assessment/run`
Run complete risk assessment
```json
{
  "borrower_id": "BOR-A1B2C3D4"
}
```

#### `GET /assessment/result/{assessment_id}`
Retrieve assessment results

### New Endpoints (V3/V4)

#### `GET /model/version`
Returns active ML model version and ensemble weights

#### `GET /config/flags`
Returns current feature flag configuration

#### `POST /config/flags/update` (SUPER_ADMIN only)
Dynamically update feature flags at runtime

---

## Deployment Strategy

### Phase 1: Rule-Only Mode (Safest)
```bash
export ENABLE_ML_RISK_SCORING=false
export ENABLE_BEHAVIORAL_V2=true
uvicorn main:app --host 0.0.0.0 --port 8000
```
- ✅ Deterministic, auditable decisions
- ✅ Behavioral intelligence active
- ✅ No ML dependencies

### Phase 2: Conservative Ensemble
```python
# config.py
ENABLE_ML_RISK_SCORING = True
RULE_WEIGHT = 0.8  # 80% rules
ML_WEIGHT = 0.2    # 20% ML
```
- ✅ ML provides insights but limited influence
- ✅ Rules still dominate decisions
- ✅ Monitor decision divergence

### Phase 3: Balanced Ensemble (Production)
```python
# config.py
RULE_WEIGHT = 0.7  # 70% rules
ML_WEIGHT = 0.3    # 30% ML
```
- ✅ Optimal balance of reliability + accuracy
- ✅ ML improves borderline case decisions
- ✅ Rules still override critical violations

---

## Testing

### Run Comprehensive Test Suite
```bash
python tests/test_comprehensive.py
```

Tests cover:
- ✅ Rule-only mode (ML disabled)
- ✅ Ensemble mode (ML enabled)
- ✅ Critical flag overrides
- ✅ Behavioral V2 integration
- ✅ Config snapshot auditing

### Manual Verification
```bash
# 1. Check system status
curl http://localhost:8000/

# 2. Check model version
curl http://localhost:8000/model/version

# 3. Check feature flags
curl http://localhost:8000/config/flags
```

---

## Regulatory Compliance

### Audit Trail
Every assessment includes:
- ✅ Rule-based score (deterministic)
- ✅ ML probability (if enabled)
- ✅ Final ensemble score
- ✅ Override applied (yes/no + reason)
- ✅ Config snapshot (feature flags at decision time)
- ✅ Model version (if ML used)

### Explainability
- ✅ SHAP feature importance for ML predictions
- ✅ Structured explanations with clear sections
- ✅ Behavioral metrics in plain language
- ✅ Primary/secondary reason prioritization

### Safety Gates
1. **Critical flags force rejection** (income too low, DTI too high)
2. **Rules override ML optimism** (ensemble cannot reduce risk below rule score)
3. **Behavioral warnings visible** (spending spikes, missed payments)
4. **Human-in-the-loop** (all decisions are recommendations, not auto-approvals)

---

## Production Checklist

- [ ] Deploy with `ENABLE_ML_RISK_SCORING=false` initially
- [ ] Verify all existing assessments produce same results
- [ ] Enable ML with conservative weighting (80% rules, 20% ML)
- [ ] Monitor decision divergence for 1 week
- [ ] Gradually increase ML weight if performance is good
- [ ] Set up model retraining pipeline (monthly)
- [ ] Configure audit log retention (7 years for compliance)
- [ ] Document configuration changes in audit trail

---

## Support & Maintenance

### Model Retraining
```bash
# Trigger retraining (requires OFFICER role)
curl -X POST http://localhost:8000/assessment/retrain \
  -H "X-API-Key: YOUR_API_KEY"
```

### Feature Flag Management
```bash
# Disable ML at runtime (requires SUPER_ADMIN)
curl -X POST http://localhost:8000/config/flags/update \
  -H "X-API-Key: SUPER_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"flag_name": "ENABLE_ML_RISK_SCORING", "value": false}'
```

---

## Project Structure

```
loan_officer_ai/
├── config.py                      # Central configuration
├── main.py                        # FastAPI application
├── agents/
│   ├── risk_agent.py              # Core risk orchestrator
│   ├── behavioral_agent_v2.py     # Enhanced behavioral analysis
│   ├── ml_risk_agent.py           # ML predictions + SHAP
│   ├── decision_agent.py          # Loan recommendations
│   └── explanation_agent.py       # Structured explanations
├── models/
│   ├── borrower.py                # Borrower data model
│   ├── alternative_data.py        # Mobile money, utilities
│   └── assessment.py              # Assessment results
├── rules/
│   └── lending_rules.py           # Deterministic business logic
├── ml_models/
│   ├── risk_model.json            # XGBoost model
│   ├── features.txt               # Feature names
│   └── training_pipeline.py       # Model training
├── tests/
│   └── test_comprehensive.py      # Full test suite
└── requirements.txt
```

---

## License & Credits

**Developed by Antigravity AI** for Advanced Agentic Coding.

This system is designed to be:
- **Regulator-safe**: Full audit trail, explainable decisions
- **Operator-friendly**: Feature flags, gradual rollout
- **Borrower-fair**: Transparent, non-discriminatory
- **Production-ready**: Tested, versioned, monitored

For questions or support, contact your system administrator.

