# Demo: Run pipeline for tenant A + url, then call /answer with sample query.
# Requires: Postgres running, API running (uvicorn), DATABASE_URL set.
#
# Usage: .\scripts\demo_pipeline_and_answer.ps1 -Url "https://example.com" [-Tenant "A"]

param(
    [Parameter(Mandatory=$true)]
    [string]$Url,
    [string]$Tenant = "A",
    [string]$Query = "What is this page about?",
    [string]$ApiBase = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

Write-Host "1. Running pipeline for tenant=$Tenant url=$Url"
python -m apps.api.services.pipeline --tenant $Tenant --url $Url
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "2. Calling POST /answer with query='$Query'"
$body = @{ query = $Query } | ConvertTo-Json
$resp = Invoke-RestMethod -Uri "$ApiBase/answer" -Method POST `
    -Headers @{ Authorization = "Bearer tenant:$Tenant"; "Content-Type" = "application/json" } `
    -Body $body

Write-Host ""
Write-Host "Answer JSON:"
$resp | ConvertTo-Json -Depth 5
