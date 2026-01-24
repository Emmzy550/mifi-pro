# Deploy Loan Officer AI to Google Cloud

$PROJECT_ID = "mfi--pro"
$REGION = "us-central1"
$SERVICE_NAME = "api"

Write-Host "🚀 Starting Deployment for $PROJECT_ID..." -ForegroundColor Cyan

# 1. Build Frontend
Write-Host "📦 Building Frontend..." -ForegroundColor Yellow
Set-Location frontend
npm run build
if ($LASTEXITCODE -ne 0) { Write-Error "Frontend build failed!"; exit 1 }
Set-Location ..

# 2. Deploy Backend (Firebase Functions)
Write-Host "☁️ Deploying Backend as Firebase Functions..." -ForegroundColor Yellow
# We deploy functions AND hosting together ensures rewrites bind correctly
firebase deploy --only functions
if ($LASTEXITCODE -ne 0) { Write-Error "Functions deployment failed!"; exit 1 }

# 3. Deploy Hosting
Write-Host "🔥 Deploying Frontend to Firebase Hosting..." -ForegroundColor Yellow
firebase deploy --only hosting
if ($LASTEXITCODE -ne 0) { Write-Error "Firebase deployment failed!"; exit 1 }

Write-Host "✅ Deployment Complete!" -ForegroundColor Green
