# Test SMS/USSD borrower journeys (local)
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\test_sms_ussd.ps1 -ApiKey "YOUR_API_KEY" -BaseUrl "http://localhost:8000"

param(
    [string]$ApiKey = "",
    [string]$BaseUrl = "http://localhost:8000"
)

if (-not $ApiKey) {
    Write-Host "API key is required. Use -ApiKey" -ForegroundColor Red
    exit 1
}

$headers = @{ "X-API-Key" = $ApiKey }

Write-Host "\n--- SMS FLOW ---" -ForegroundColor Cyan
$phone = "+254700000000"
$steps = @(
    "START",
    "YES",
    "Jane Doe",
    "50000",
    "20000",
    "5000",
    "15000",
    "Business stock"
)

foreach ($s in $steps) {
    $body = @{ phone = $phone; text = $s } | ConvertTo-Json
    $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/channels/sms/inbound" -Headers $headers -ContentType "application/json" -Body $body
    Write-Host "SMS -> $s" -ForegroundColor Yellow
    $res | ConvertTo-Json -Depth 6
}

Write-Host "\n--- USSD FLOW ---" -ForegroundColor Cyan
$sessionId = "test-session-1"
$ussdSteps = @("", "1", "Jane Doe", "50000", "20000", "5000", "15000", "Business stock")

foreach ($u in $ussdSteps) {
    $body = @{ sessionId = $sessionId; phoneNumber = $phone; text = $u } | ConvertTo-Json
    $res = Invoke-RestMethod -Method Post -Uri "$BaseUrl/channels/ussd" -Headers $headers -ContentType "application/json" -Body $body
    Write-Host "USSD -> $u" -ForegroundColor Yellow
    Write-Host $res
}
