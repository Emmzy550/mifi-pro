# Google Cloud Run Deployment Script for Loan Officer AI

param(
    [string]$ProjectId = "mfi--pro",
    [string]$Region = "us-central1",
    [string]$ServiceName = "loan-officer-api"
)

$ErrorActionPreference = "Stop"

Write-Host "Deploying Loan Officer AI to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project ID: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Service Name: $ServiceName"
Write-Host ""

# Step 1: Verify Prerequisites
Write-Host "Step 1/4: Verifying prerequisites..." -ForegroundColor Yellow

# Check if gcloud is installed
try {
    $gcloudVersion = gcloud --version 2>&1 | Select-Object -First 1
    Write-Host "OK - gcloud CLI found: $gcloudVersion" -ForegroundColor Green
}
catch {
    Write-Error "ERROR - gcloud CLI not found. Please install from https://cloud.google.com/sdk/docs/install"
    exit 1
}

# Set the active project
Write-Host "Setting active project to $ProjectId..."
gcloud config set project $ProjectId
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR - Failed to set project. Run: gcloud auth login"
    exit 1
}

Write-Host ""

# Step 2: Read Environment Variables
Write-Host "Step 2/4: Reading environment variables..." -ForegroundColor Yellow

if (-Not (Test-Path ".env")) {
    Write-Error "ERROR - .env file not found"
    exit 1
}

# Read .env file and prepare environment variables for Cloud Run
$envVars = @()
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        $parts = $line -split "=", 2
        if ($parts.Length -eq 2) {
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            $envVars += "$key=$value"
        }
    }
}

$envVarsString = $envVars -join ","
Write-Host "OK - Loaded $($envVars.Count) environment variables" -ForegroundColor Green
Write-Host ""

# Step 3: Build and Push Container Image
Write-Host "Step 3/4: Building and pushing container image..." -ForegroundColor Yellow

# Enable required APIs
Write-Host "Enabling required Google Cloud APIs..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com --project=$ProjectId

# Build using Cloud Build
Write-Host "Building container image using Cloud Build..."
gcloud builds submit --tag gcr.io/$ProjectId/$ServiceName --project=$ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR - Cloud Build failed"
    exit 1
}

Write-Host "OK - Container image built successfully" -ForegroundColor Green
Write-Host ""

# Step 4: Deploy to Cloud Run
Write-Host "Step 4/4: Deploying to Cloud Run..." -ForegroundColor Yellow

# Deploy to Cloud Run with environment variables
gcloud run deploy $ServiceName `
    --image gcr.io/$ProjectId/$ServiceName `
    --platform managed `
    --region $Region `
    --allow-unauthenticated `
    --memory 2Gi `
    --cpu 2 `
    --timeout 300 `
    --max-instances 10 `
    --set-env-vars $envVarsString `
    --project $ProjectId

if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR - Cloud Run deployment failed"
    exit 1
}

Write-Host ""
Write-Host "DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host ""

# Get the service URL
$serviceUrl = gcloud run services describe $ServiceName --platform managed --region $Region --format "value(status.url)" --project $ProjectId
Write-Host "Service URL: $serviceUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Test the API at: $serviceUrl"
Write-Host "  2. View logs in GCP Console"
Write-Host "  3. Monitor metrics at: https://console.cloud.google.com/run"
Write-Host ""
