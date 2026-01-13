# Deployment Guide

Production deployment guide for the Loan Officer AI Agent.

## Table of Contents

- [Production Checklist](#production-checklist)
- [Environment Variables](#environment-variables)
- [Docker Deployment](#docker-deployment)
- [Cloud Deployment](#cloud-deployment)
- [ML Model Deployment](#ml-model-deployment)
- [Monitoring & Logging](#monitoring--logging)
- [Backup & Recovery](#backup--recovery)

---

## Production Checklist

Before deploying to production:

- [ ] Environment variables configured
- [ ] Firebase service account key secured
- [ ] Secret key rotated (not using default)
- [ ] ML feature flags set appropriately
- [ ] Database backups enabled
- [ ] Monitoring configured
- [ ] SSL/TLS certificates installed
- [ ] Rate limiting configured
- [ ] Error tracking enabled (Sentry, etc.)
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] Backup strategy documented

---

## Environment Variables

### Required Variables

```bash
# Security (CRITICAL - Change in production!)
SECRET_KEY=your-random-256-bit-key-here

# Database
USE_FIRESTORE=true
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json

# Feature Flags
ENABLE_ML_RISK_SCORING=true
ENABLE_BEHAVIORAL_V2=true
ENABLE_LLM_EXPLANATIONS=false

# Business Rules
MIN_MONTHLY_INCOME=100.0
MAX_DEBT_TO_INCOME_RATIO=0.4
AFFORDABILITY_RATIO_TARGET=0.3

# Interest Rates
BASE_INTEREST_RATE=15.0
CONDITIONAL_INTEREST_RATE=20.0
CAUTION_INTEREST_RATE=18.0

# ML Ensemble Weights
RULE_WEIGHT=0.7
ML_WEIGHT=0.3

# CORS Origins (comma-separated)
ALLOWED_ORIGINS=https://yourdomain.com,https://dashboard.yourdomain.com

# Server
PORT=8000
HOST=0.0.0.0
WORKERS=4
```

### Generating SECRET_KEY

```python
import secrets
print(secrets.token_urlsafe(32))
```

Or via command line:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Docker Deployment

### Dockerfile

The project includes a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Build and Run

```bash
# Build image
docker build -t loan-officer-ai:latest .

# Run container
docker run -d \
  --name loan-officer-api \
  -p 8000:8000 \
  -e SECRET_KEY="your-secret-key" \
  -e USE_FIRESTORE=true \
  -v $(pwd)/serviceAccountKey.json:/app/serviceAccountKey.json \
  loan-officer-ai:latest
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - USE_FIRESTORE=true
      - ENABLE_ML_RISK_SCORING=true
      - ENABLE_BEHAVIORAL_V2=true
    volumes:
      - ./serviceAccountKey.json:/app/serviceAccountKey.json
      - ./ml_models:/app/ml_models
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Run:**

```bash
docker-compose up -d
```

---

## Cloud Deployment

### Google Cloud Platform (GCP)

#### Cloud Run Deployment

```bash
# 1. Build and push to Container Registry
gcloud builds submit --tag gcr.io/PROJECT_ID/loan-officer-ai

# 2. Deploy to Cloud Run
gcloud run deploy loan-officer-ai \
  --image gcr.io/PROJECT_ID/loan-officer-ai \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SECRET_KEY=your-key \
  --set-env-vars USE_FIRESTORE=true \
  --service-account loan-officer-sa@PROJECT_ID.iam.gserviceaccount.com
```

#### App Engine Deployment

```yaml
# app.yaml
runtime: python39

env_variables:
  SECRET_KEY: "your-secret-key"
  USE_FIRESTORE: "true"
  ENABLE_ML_RISK_SCORING: "true"

automatic_scaling:
  min_instances: 1
  max_instances: 10
  target_cpu_utilization: 0.65
```

**Deploy:**

```bash
gcloud app deploy
```

---

### AWS Deployment

#### Elastic Beanstalk

```bash
# 1. Install EB CLI
pip install awsebcli

# 2. Initialize
eb init -p python-3.9 loan-officer-ai

# 3. Create environment
eb create production-env

# 4. Set environment variables
eb setenv SECRET_KEY=your-key USE_FIRESTORE=true

# 5. Deploy
eb deploy
```

#### ECS (Elastic Container Service)

```bash
# 1. Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
docker tag loan-officer-ai:latest ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/loan-officer-ai:latest
docker push ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/loan-officer-ai:latest

# 2. Create ECS task definition and service via AWS Console or CLI
```

---

### Azure Deployment

#### Azure App Service

```bash
# 1. Create resource group
az group create --name loan-officer-rg --location eastus

# 2. Create App Service plan
az appservice plan create --name loan-officer-plan --resource-group loan-officer-rg --sku B1 --is-linux

# 3. Create web app
az webapp create --resource-group loan-officer-rg --plan loan-officer-plan --name loan-officer-api --runtime "PYTHON|3.9"

# 4. Configure environment
az webapp config appsettings set --resource-group loan-officer-rg --name loan-officer-api --settings SECRET_KEY=your-key USE_FIRESTORE=true

# 5. Deploy
az webapp up --name loan-officer-api --resource-group loan-officer-rg
```

---

## ML Model Deployment

### Model Storage

**Option 1: Include in Container**

```dockerfile
# In Dockerfile
COPY ml_models/ /app/ml_models/
```

**Option 2: Cloud Storage**

```python
# Download model at startup
import google.cloud.storage as storage

def download_model():
    client = storage.Client()
    bucket = client.bucket('your-ml-models-bucket')
    blob = bucket.blob('risk_model.json')
    blob.download_to_filename('./ml_models/risk_model.json')

# In main.py startup
@app.on_event("startup")
async def startup_event():
    download_model()
```

---

### Model Versioning Strategy

**Phase 1: Rule-Only (Week 1-2)**

```bash
export ENABLE_ML_RISK_SCORING=false
export ENABLE_BEHAVIORAL_V2=true
```

**Phase 2: Conservative ML (Week 3-4)**

```bash
export ENABLE_ML_RISK_SCORING=true
export RULE_WEIGHT=0.8
export ML_WEIGHT=0.2
```

**Phase 3: Balanced Production (Week 5+)**

```bash
export RULE_WEIGHT=0.7
export ML_WEIGHT=0.3
```

Monitor decision divergence and default rates at each phase.

---

## Monitoring & Logging

### Application Logging

```python
# In main.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Health Check Endpoint

Already included: `GET /api/health`

```json
{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true
}
```

---

### Sentry Integration (Error Tracking)

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

sentry_sdk.init(
    dsn="https://your-sentry-dsn",
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)
```

---

### Prometheus Metrics (Optional)

```python
from prometheus_client import Counter, Histogram

assessment_counter = Counter('assessments_total', 'Total assessments')
assessment_duration = Histogram('assessment_duration_seconds', 'Assessment duration')

@app.post("/assessment/run")
async def assessment_run(...):
    with assessment_duration.time():
        assessment_counter.inc()
        # ... existing code
```

---

## Backup & Recovery

### Firestore Backups

**Automated Backups (GCP):**

```bash
# Enable scheduled backups
gcloud firestore backups schedules create \
  --database='(default)' \
  --recurrence=weekly \
  --retention=4w
```

### Export Data

```bash
# Export to Cloud Storage
gcloud firestore export gs://your-backup-bucket/firestore-exports
```

### Disaster Recovery Plan

1. **Database Backup**: Daily Firestore exports
2. **Code Repository**: Git version control
3. **Secrets Backup**: Store in Google Secret Manager / AWS Secrets Manager
4. **ML Models**: Versioned in Cloud Storage
5. **Recovery Time Objective (RTO)**: < 4 hours
6. **Recovery Point Objective (RPO)**: < 24 hours

---

## Scaling Considerations

### Horizontal Scaling

```bash
# Run multiple workers
uvicorn main:app --workers 4 --host 0.0.0.0 --port 8000
```

### Load Balancer Configuration

```nginx
# nginx.conf
upstream api_backend {
    least_conn;
    server api1:8000;
    server api2:8000;
    server api3:8000;
}

server {
    listen 80;
    
    location / {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Caching Strategy

```python
# Add Redis caching for assessments
import redis

cache = redis.Redis(host='localhost', port=6379)

@app.get("/assessment/result/{assessment_id}")
async def get_assessment(assessment_id: str):
    # Check cache first
    cached = cache.get(f"assessment:{assessment_id}")
    if cached:
        return json.loads(cached)
    
    # Fetch from database
    assessment = Database.get_assessment(assessment_id)
    
    # Cache for 1 hour
    cache.setex(f"assessment:{assessment_id}", 3600, json.dumps(assessment.dict()))
    
    return assessment
```

---

## Security Hardening

### SSL/TLS Configuration

```python
# For production, use a reverse proxy (nginx) with SSL
# Or configure uvicorn with SSL:

uvicorn main:app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile ./ssl/privkey.pem \
  --ssl-certfile ./ssl/fullchain.pem
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/intake/start")
@limiter.limit("10/minute")
async def intake_start(request: Request, raw_data: dict = Body(...)):
    # ... existing code
```

---

## Next Steps

- [Monitoring Dashboard](./troubleshooting.md#monitoring) - Set up monitoring
- [Security Best Practices](./CONTRIBUTING.md#security) - Security guidelines
- [Troubleshooting](./troubleshooting.md) - Common deployment issues
