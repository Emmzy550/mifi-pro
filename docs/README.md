# Developer Documentation

Welcome to the Loan Officer AI Agent developer documentation!

## 📚 Documentation Index

### Getting Started
- **[Getting Started Guide](./getting-started.md)** - Installation, setup, and your first API request
- **[API Reference](./api-reference.md)** - Complete API documentation with examples

### Architecture & Design
- **[Architecture Guide](./architecture.md)** - System design, multi-agent workflow, and database schema
- **[Agent System Guide](./agents.md)** - Detailed documentation for each agent component

### Integration & Development
- **[Integration Guide](./integration.md)** - Frontend/backend integration, webhooks, and multi-tenancy
- **[Testing Guide](./testing.md)** - Running tests, writing new tests, and test scenarios
- **[Contributing Guidelines](./CONTRIBUTING.md)** - How to contribute to the project

### Operations
- **[Deployment Guide](./deployment.md)** - Production deployment, Docker, cloud platforms
- **[Troubleshooting Guide](./troubleshooting.md)** - Common issues and solutions

---

## 🚀 Quick Links

### For New Developers
1. Start with [Getting Started](./getting-started.md)
2. Explore [API Reference](./api-reference.md)
3. Understand [Architecture](./architecture.md)

### For Integrators
1. Review [Integration Guide](./integration.md)
2. Check [API Reference](./api-reference.md)
3. Test with [Testing Guide](./testing.md)

### For DevOps/SREs
1. Read [Deployment Guide](./deployment.md)
2. Configure monitoring per [Deployment Guide](./deployment.md#monitoring--logging)
3. Reference [Troubleshooting Guide](./troubleshooting.md)

---

## 📖 What is  This System?

The **Loan Officer AI Agent** is a fintech-grade credit decision engine designed for microfinance institutions. It combines:

- ✅ **Rule-based lending logic** - Deterministic, auditable decisions
- 🤖 **Optional ML predictions** - XGBoost + SHAP for enhanced risk assessment
- 📊 **Behavioral intelligence** - Alternative data analysis (transactions, utilities)
- 🔐 **Multi-tenancy** - Isolated data per organization
- 📝 **Full auditability** - Complete event logging for compliance

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI REST API                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────────┐
       │               │                   │
  ┌────▼────┐     ┌────▼────┐        ┌────▼────┐
  │ Intake  │     │  Risk   │        │Decision │
  │ Agent   │────▶│ Agent   │───────▶│ Agent   │
  └─────────┘     └────┬────┘        └────┬────┘
                       │                   │
       ┌───────────────┼───────────────┐   │
       │               │               │   │
  ┌────▼────┐    ┌────▼────┐    ┌────▼───▼────┐
  │Behavioral│    │   ML    │    │ Explanation │
  │Agent V2  │    │  Risk   │    │   Agent     │
  └──────────┘    └─────────┘    └─────────────┘
```

See [Architecture Guide](./architecture.md) for details.

---

## 🔑 Key Features

### Rule-Based Foundation
- Debt-to-income ratio checks
- Affordability calculations
- Income stability verification
- Safety gates and overrides

### ML Enhancement (Optional)
- XGBoost ensemble scoring
- SHAP explainability
- Feature importance ranking
- Configurable rule/ML weights

### Alternative Data
- Transaction history analysis
- Income consistency scoring
- Savings behavior tracking
- Utility payment compliance

### Security & Compliance
- Multi-tenancy isolation
- JWT + API key authentication
- Complete audit trail
- GDPR-ready data handling

---

## 🛠️ Technology Stack

- **Backend**: Python 3.9+, FastAPI
- **Database**: Firebase Firestore (optional, uses in-memory by default)
- **ML**: XGBoost, SHAP
- **Auth**: JWT (python-jose), bcrypt
- **Frontend**: React (optional dashboard)
- **Deployment**: Docker, cloud-agnostic

---

## 📊 API Overview

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | System health check |
| `/intake/start` | POST | Create borrower profile |
| `/assessment/run` | POST | Run risk assessment |
| `/assessment/result/{id}` | GET | Get assessment result |
| `/behavior/upload` | POST | Upload transaction data |
| `/loan/disburse` | POST | Disburse approved loan |

See [API Reference](./api-reference.md) for complete documentation.

---

## 💡 Example Workflow

```python
# 1. Create borrower profile
response = requests.post("http://localhost:8000/intake/start", json={
    "name": "Jane Doe",
    "phone": "+254700000000",
    "monthly_income": 50000,
    "monthly_expenses": 20000,
    "existing_debt": 5000,
    "loan_amount_requested": 15000,
    "loan_purpose": "Business expansion",
    "employment_type": "trader"
})
borrower_id = response.json()["borrower_id"]

# 2. Run assessment
response = requests.post("http://localhost:8000/assessment/run", json={
    "borrower_id": borrower_id
})
assessment = response.json()

# 3. Review decision
print(f"Decision: {assessment['decision']}")
print(f"Risk Level: {assessment['risk_level']}")
print(f"Recommended Amount: ${assessment['recommended_amount']}")
print(f"Interest Rate: {assessment['recommended_interest_rate']}%")
```

---

## 🧪 Testing

```bash
# Run comprehensive test suite
python tests/test_comprehensive.py

# Or use pytest
pytest tests/ -v

# With coverage
pytest --cov=agents --cov=models tests/
```

See [Testing Guide](./testing.md) for details.

---

## 🚀 Deployment

### Docker (Recommended)

```bash
docker build -t loan-officer-ai .
docker run -p 8000:8000 -e SECRET_KEY=your-key loan-officer-ai
```

### Cloud Platforms

- **GCP**: Cloud Run, App Engine
- **AWS**: ECS, Elastic Beanstalk
- **Azure**: App Service

See [Deployment Guide](./deployment.md) for platform-specific instructions.

---

## 🤝 Contributing

We welcome contributions! Please read:

1. [Contributing Guidelines](./CONTRIBUTING.md)
2. [Testing Guide](./testing.md)
3. [Architecture Guide](./architecture.md)

---

## 📞 Support

- **Documentation Issues**: Check [Troubleshooting Guide](./troubleshooting.md)
- **Bug Reports**: Create an issue with reproduction steps
- **Feature Requests**: Describe use case and expected behavior
- **Security Issues**: Email security contact (do not create public issues)

---

## 📄 License

See main [README](../README.md) for license information.

---

## 🗺️ Documentation Navigation

```
docs/
├── README.md                    # This file - documentation hub
├── getting-started.md           # Installation and quickstart
├── api-reference.md             # Complete API documentation
├── architecture.md              # System design and architecture
├── agents.md                    # Multi-agent system guide
├── integration.md               # Integration patterns
├── testing.md                   # Testing guide
├── deployment.md                # Deployment guide
├── troubleshooting.md           # Common issues and solutions
└── CONTRIBUTING.md              # Contributing guidelines
```

---

**Happy coding!** 🎉

For questions or feedback, refer to the specific documentation pages above.
