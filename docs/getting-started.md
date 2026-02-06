# Getting Started with Loan Officer AI Agent

Welcome to the Loan Officer AI Agent! This guide will help you get up and running quickly.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Your First API Request](#your-first-api-request)
- [Next Steps](#next-steps)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9+** - [Download Python](https://www.python.org/downloads/)
- **pip** - Python package manager (comes with Python)
- **Git** - For cloning the repository
- **Firebase Account** (Optional) - For production use with Firestore

### Recommended Tools

- **Docker** - For containerized deployment
- **Postman** or **curl** - For API testing
- **VS Code** or **PyCharm** - For development

---

## Installation

### Option 1: Local Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd loan_officer_ai
```

2. **Create a virtual environment**

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Install optional dependencies** (for PDF support)

```bash
pip install PyPDF2
```

### Option 2: Docker Installation

1. **Build the Docker image**

```bash
docker build -t loan-officer-ai .
```

2. **Run the container**

```bash
docker run -p 8000:8000 loan-officer-ai
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# Feature Flags
ENABLE_ML_RISK_SCORING=true
ENABLE_BEHAVIORAL_V2=true
ENABLE_LLM_EXPLANATIONS=false

# Database (Optional - uses in-memory by default)
USE_FIRESTORE=false
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json

# Security
SECRET_KEY=your-secret-key-here-change-in-production
```

### Firebase Setup (Optional)

If you want to use Firebase Firestore for production:

1. **Create a Firebase project** at [Firebase Console](https://console.firebase.google.com/)

2. **Download service account key**
   - Go to Project Settings → Service Accounts
   - Click "Generate New Private Key"
   - Save as `serviceAccountKey.json` in project root

3. **Update `.env`**

```bash
USE_FIRESTORE=true
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
```

### Configuration File

The main configuration is in [`config.py`](../config.py). Key settings:

```python
# Business Rules
MIN_MONTHLY_INCOME = 100.0
MAX_DEBT_TO_INCOME_RATIO = 0.4
AFFORDABILITY_RATIO_TARGET = 0.3

# Interest Rates
BASE_INTEREST_RATE = 15.0          # Low risk
CONDITIONAL_INTEREST_RATE = 20.0   # Medium risk
CAUTION_INTEREST_RATE = 18.0       # Behavioral concerns

# ML Ensemble Weights
RULE_WEIGHT = 0.7  # 70% rules
ML_WEIGHT = 0.3    # 30% ML
```

---

## Running the Application

### Development Mode

```bash
# Activate virtual environment first
python main.py
```

Or use uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Verify Installation

Visit `http://localhost:8000/api/health` in your browser or run:

```bash
curl http://localhost:8000/api/health
```

Expected response:

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

## Your First API Request

### Step 1: Create a Borrower Profile

```bash
curl -X POST http://localhost:8000/intake/start \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "phone": "+254700000000",
    "employment_type": "trader",
    "monthly_income": 50000,
    "monthly_expenses": 20000,
    "existing_debt": 5000,
    "loan_amount_requested": 15000,
    "loan_purpose": "Business stock expansion"
  }'
```

**Response:**

```json
{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}
```

### Step 2: Run Risk Assessment

```bash
curl -X POST http://localhost:8000/assessment/run \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_id": "BOR-A1B2C3D4"
  }'
```

**Response:**

```json
{
  "assessment_id": "ASMT-X1Y2Z3A4",
  "borrower_id": "BOR-A1B2C3D4",
  "risk_score": 0.45,
  "risk_score_percent": 45.0,
  "risk_score_scale": "0-1",
  "risk_level": "MEDIUM",
  "decision": "CONDITIONAL",
  "decision_legacy": "CONDITIONAL_APPROVAL",
  "recommended_amount": 15000,
  "recommended_interest_rate": 20.0,
  "requested_amount": 15000,
  "explanation": {
    "summary": "Conditionally approved with elevated interest rate...",
    "risk_factors": [...],
    "recommendations": [...]
  },
  "flags": [...],
  "metrics": {...}
}
```

### Step 3: Upload Alternative Data (Optional)

Upload transaction history for enhanced behavioral analysis:

```bash
curl -X POST http://localhost:8000/behavior/upload \
  -F "borrower_id=BOR-A1B2C3D4" \
  -F "file=@sample_transactions.csv"
```

---

## Next Steps

Now that you have the basics working, explore more features:

### 📚 **Learn the System**
- [Architecture Guide](./architecture.md) - Understand the multi-agent system
- [Agent System Guide](./agents.md) - Deep dive into each agent
- [API Reference](./api-reference.md) - Complete API documentation

### 🔧 **Integration**
- [Integration Guide](./integration.md) - Frontend and backend integration patterns
- [Authentication](./api-reference.md#authentication) - JWT and API key setup

### 🧪 **Testing**
- [Testing Guide](./testing.md) - Run tests and write your own
- Run the test suite: `python tests/test_comprehensive.py`

### 🚀 **Deployment**
- [Deployment Guide](./deployment.md) - Production deployment checklist
- [Configuration Reference](./deployment.md#environment-variables) - All config options

### 🎯 **Contribute**
- [Contributing Guidelines](./CONTRIBUTING.md) - How to contribute
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions

---

## Troubleshooting

### Common Issues

#### 1. **Port Already in Use**

```
ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8000): address already in use
```

**Solution:** Change the port or stop the process using port 8000

```bash
# Use a different port
uvicorn main:app --port 8001

# Or find and stop the process (macOS/Linux)
lsof -ti:8000 | xargs kill

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

#### 2. **Module Not Found Errors**

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:** Ensure you've activated your virtual environment and installed dependencies

```bash
# Activate virtual environment first
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

#### 3. **Firebase Connection Issues**

```
google.auth.exceptions.DefaultCredentialsError
```

**Solution:** Check your service account key path

```bash
# Verify file exists
ls serviceAccountKey.json

# Update path in .env
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
```

#### 4. **PDF Parsing Not Working**

```
⚠️  PyPDF2 not installed. PDF upload will not work.
```

**Solution:** Install PyPDF2

```bash
pip install PyPDF2
```

### Getting Help

- **Documentation**: Check the [Troubleshooting Guide](./troubleshooting.md)
- **Issues**: Search existing issues or create a new one
- **Community**: Reach out to the development team

---

## What's Next?

You're now ready to start building with the Loan Officer AI Agent! Here are some recommended paths:

**For Integrators:**
- Set up authentication (API keys or JWT)
- Build a simple frontend dashboard
- Configure webhooks for real-time updates

**For Developers:**
- Explore the agent architecture
- Add custom risk rules
- Extend the ML pipeline

**For Operators:**
- Configure feature flags for your organization
- Set up monitoring and logging
- Plan your deployment strategy

Happy coding! 🚀
