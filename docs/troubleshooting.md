# Troubleshooting Guide

Common issues and solutions for the Loan Officer AI Agent.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Server Startup Problems](#server-startup-problems)
- [API Errors](#api-errors)
- [Authentication Issues](#authentication-issues)
- [ML Model Errors](#ml-model-errors)
- [PDF Parsing Failures](#pdf-parsing-failures)
- [Firestore Connection Issues](#firestore-connection-issues)
- [Performance Problems](#performance-problems)

---

## Installation Issues

### Problem: Module Not Found

**Error:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Solution:**

1. Ensure virtual environment is activated:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

---

### Problem: Python Version Incompatibility

**Error:**
```
SyntaxError: invalid syntax
```

**Solution:**

Check Python version (requires 3.9+):
```bash
python --version
```

If using older version, install Python 3.9+:
```bash
# macOS (using Homebrew)
brew install python@3.9

# Ubuntu
sudo apt install python3.9

# Windows: Download from python.org
```

---

## Server Startup Problems

### Problem: Port Already in Use

**Error:**
```
ERROR: [Errno 48] Address already in use
```

**Solution:**

**Option 1: Use Different Port**
```bash
uvicorn main:app --port 8001
```

**Option 2: Kill Process Using Port 8000**

macOS/Linux:
```bash
lsof -ti:8000 | xargs kill
```

Windows (PowerShell):
```powershell
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process
```

---

### Problem: Import Errors at Startup

**Error:**
```
ImportError: cannot import name 'Database' from 'utils.db'
```

**Solution:**

Verify file structure:
```bash
# Check all required files exist
ls agents/
ls models/
ls utils/
```

If files are missing, re-clone repository or restore from backup.

---

## API Errors

### Problem: 404 Not Found for Valid Endpoint

**Error:**
```json
{"detail": "Not Found"}
```

**Solution:**

1. Verify server is running:
```bash
curl http://localhost:8000/api/health
```

2. Check endpoint spelling:
```bash
# Correct
curl http://localhost:8000/intake/start

# Incorrect (missing /intake/)
curl http://localhost:8000/start
```

---

### Problem: 422 Validation Error

**Error:**
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

**Solution:**

Ensure all required fields are included in request:

```json
{
  "name": "Jane Doe",
  "phone": "+254700000000",
  "employment_type": "trader",
  "monthly_income": 50000,  // This field was missing
  "monthly_expenses": 20000,
  "existing_debt": 5000,
  "loan_amount_requested": 15000,
  "loan_purpose": "Business"
}
```

---

### Problem: 500 Internal Server Error

**Error:**
```json
{"detail": "Internal server error"}
```

**Solution:**

1. Check server logs:
```bash
tail -f server_log.txt
```

2. Enable debug mode:
```python
# In main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
```

3. Common causes:
   - Database connection failure
   - Missing environment variables
   - Invalid data in database
   - ML model loading error

---

## Authentication Issues

### Problem: 401 Unauthorized with API Key

**Error:**
```json
{"detail": "Invalid API key"}
```

**Solution:**

1. Verify API key format:
```
loa_live_abc123...  ✅ Correct
abc123...           ❌ Incorrect (missing prefix)
```

2. Check key is not revoked:
```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api-keys
```

3. Verify header format:
```bash
# Correct
curl -H "X-API-Key: loa_live_abc123..." http://localhost:8000/borrowers

# Incorrect
curl -H "Authorization: loa_live_abc123..." http://localhost:8000/borrowers
```

---

### Problem: JWT Token Expired

**Error:**
```json
{"detail": "Token has expired"}
```

**Solution:**

Login again to get new token:
```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=your@email.com" \
  -d "password=yourpassword"
```

---

## ML Model Errors

### Problem: ML Model Not Loading

**Error:**
```
⚠️ ML model not found. Continuing with rule-based scoring.
```

**Solution:**

1. Verify model file exists:
```bash
ls ml_models/risk_model.json
ls ml_models/features.txt
```

2. Train initial model:
```bash
python ml_models/training_pipeline.py
```

3. Check model path in config:
```python
# config.py
ML_MODEL_PATH = "./ml_models/risk_model.json"  # Verify path is correct
```

---

### Problem: SHAP Errors

**Error:**
```
TypeError: TreeExplainer requires the model to support .save_raw()
```

**Solution:**

Install compatible XGBoost version:
```bash
pip install xgboost==1.7.6 shap==0.42.1
```

---

### Problem: Feature Mismatch

**Error:**
```
ValueError: Feature shape mismatch. Expected 15 features, got 12
```

**Solution:**

Ensure model was trained with same features as current extraction logic:

1. Retrain model:
```bash
curl -X POST http://localhost:8000/assessment/retrain \
  -H "X-API-Key: OFFICER_KEY"
```

2. Or disable ML temporarily:
```bash
export ENABLE_ML_RISK_SCORING=false
```

---

## PDF Parsing Failures

### Problem: PyPDF2 Not Installed

**Error:**
```
⚠️ PyPDF2 not installed. PDF upload will not work.
```

**Solution:**

```bash
pip install PyPDF2
```

---

### Problem: No Transactions Extracted from PDF

**Response:**
```json
{
  "status": "WARNING",
  "message": "No transactions found in the document."
}
```

**Solution:**

1. Verify PDF contains readable text (not scanned image)

2. Try CSV format instead:
```csv
Date,Type,Amount,Description
2024-01-15,DEPOSIT,5000,Salary
```

3. Use OCR for scanned PDFs:
```bash
pip install pytesseract pillow
# Required: Install Tesseract OCR separately
```

---

## Firestore Connection Issues

### Problem: Default Credentials Not Found

**Error:**
```
google.auth.exceptions.DefaultCredentialsError: Could not automatically determine credentials
```

**Solution:**

1. Verify service account key exists:
```bash
ls serviceAccountKey.json
```

2. Set environment variable:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
```

3. Or update config.py:
```python
import firebase_admin
from firebase_admin import credentials

cred = credentials.Certificate("./serviceAccountKey.json")
firebase_admin.initialize_app(cred)
```

---

### Problem: Permission Denied on Firestore

**Error:**
```
google.api_core.exceptions.PermissionDenied: 403 Missing or insufficient permissions
```

**Solution:**

1. Verify service account has correct IAM roles:
   - Cloud Datastore User
   - Firebase Admin

2. Update IAM permissions in Firebase Console:
   - Go to Project Settings → Service Accounts
   - Generate new key with correct permissions

---

## Performance Problems

### Problem: Slow Response Times

**Symptoms:** API requests taking > 2 seconds

**Solutions:**

1. **Enable ML Model Caching** (already implemented):
```python
# ML model loaded once at startup, not per request
```

2. **Add Database Indexing**:
```python
# In Firebase Console, create composite indexes for common queries
```

3. **Use Connection Pooling**:
```python
# For non-Firestore databases
from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL, pool_size=10)
```

4. **Enable GZIP Compression**:
```python
from fastapi.middleware.gzip import GZIPMiddleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)
```

---

### Problem: High Memory Usage

**Symptoms:** Server using > 1GB RAM

**Solutions:**

1. Limit worker processes:
```bash
uvicorn main:app --workers 2  # Instead of 4
```

2. Clear ML model cache if not needed:
```python
# Disable ML if not using
export ENABLE_ML_RISK_SCORING=false
```

3. Implement pagination for list endpoints:
```python
@app.get("/borrowers")
async def list_borrowers(limit: int = 50, offset: int = 0):
    # ... paginated query
```

---

## Debugging Tips

### Enable Verbose Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

### Inspect Request/Response

```bash
# Use -v flag with curl
curl -v http://localhost:8000/intake/start -X POST -d '{...}'
```

### Check Firestore Data

```python
# Quick script to inspect database
from utils.db import Database

borrowers = Database.list_borrowers()
print(f"Total borrowers: {len(borrowers)}")

for b in borrowers[:5]:
    print(f"{b.id}: {b.name}")
```

---

## Getting Help

If you're still experiencing issues:

1. **Check Logs**: Review `server_log.txt` and error traces
2. **Search Issues**: Look for similar issues in documentation
3. **Minimal Reproduction**: Create a minimal example that reproduces the bug
4. **Report Issue**: Contact support with:
   - Error message
   - Steps to reproduce
   - System information (OS, Python version)
   - Relevant logs

---

## Next Steps

- [Deployment Guide](./deployment.md) - Production deployment
- [API Reference](./api-reference.md) - Endpoint documentation
- [Contributing](./CONTRIBUTING.md) - Report bugs or contribute fixes
