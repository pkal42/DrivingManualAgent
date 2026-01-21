# ============================================================================
# Deploy Azure AI Search Components via REST API
# ============================================================================
# This script deploys the search skillset, index, datasource, and indexer
# using Azure Search REST API (Bicep deployments don't work for these resources)
#
# Prerequisites:
# - Azure CLI authenticated (az login)
# - Search service deployed from main.bicep
# - Managed identity RBAC configured
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$SearchServiceName = "srch-drvagnt2-dev-7vczbz",
    
    [Parameter(Mandatory=$false)]
    [string]$ApiVersion = "2024-07-01"
)

$ErrorActionPreference = "Stop"

$searchEndpoint = "https://$SearchServiceName.search.windows.net"
$modulesPath = Join-Path $PSScriptRoot "modules"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Azure AI Search Components Deployment" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Search Endpoint: $searchEndpoint" -ForegroundColor White
Write-Host "API Version: $ApiVersion" -ForegroundColor White
Write-Host ""

# Get access token
Write-Host "Getting access token..." -ForegroundColor Yellow
$token = az account get-access-token --resource https://search.azure.com --query accessToken -o tsv

if (-not $token) {
    Write-Host "✗ Failed to get access token. Ensure you're logged in with 'az login'" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer $token"
}

Write-Host "✓ Access token obtained" -ForegroundColor Green
Write-Host ""

# ============================================================================
# 1. Deploy Index
# ============================================================================
Write-Host "[1/4] Deploying Search Index..." -ForegroundColor Cyan
$indexJson = Get-Content (Join-Path $modulesPath "rest-index.json") -Raw

try {
    $result = Invoke-RestMethod -Method Put `
        -Uri "$searchEndpoint/indexes/driving-manual-index?api-version=$ApiVersion" `
        -Headers $headers `
        -Body $indexJson
    
    Write-Host "✓ Index 'driving-manual-index' created successfully" -ForegroundColor Green
} catch {
    $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✗ Index creation failed:" -ForegroundColor Red
    Write-Host "  Error: $($errorDetails.error.message)" -ForegroundColor Red
    Write-Host "  Continuing with remaining deployments..." -ForegroundColor Yellow
}

Write-Host ""

# ============================================================================
# 2. Deploy Skillset
# ============================================================================
Write-Host "[2/4] Deploying Skillset..." -ForegroundColor Cyan
$skillsetJson = Get-Content (Join-Path $modulesPath "rest-skillset.json") -Raw

try {
    $result = Invoke-RestMethod -Method Put `
        -Uri "$searchEndpoint/skillsets/driving-manual-skillset?api-version=$ApiVersion" `
        -Headers $headers `
        -Body $skillsetJson
    
    Write-Host "✓ Skillset 'driving-manual-skillset' created successfully" -ForegroundColor Green
} catch {
    $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✗ Skillset creation failed:" -ForegroundColor Red
    Write-Host "  Error: $($errorDetails.error.message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# 3. Deploy Data Source
# ============================================================================
Write-Host "[3/4] Deploying Data Source..." -ForegroundColor Cyan
$datasourceJson = Get-Content (Join-Path $modulesPath "rest-datasource.json") -Raw

try {
    $result = Invoke-RestMethod -Method Put `
        -Uri "$searchEndpoint/datasources/driving-manual-datasource?api-version=$ApiVersion" `
        -Headers $headers `
        -Body $datasourceJson
    
    Write-Host "✓ Data Source 'driving-manual-datasource' created successfully" -ForegroundColor Green
} catch {
    $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✗ Data Source creation failed:" -ForegroundColor Red
    Write-Host "  Error: $($errorDetails.error.message)" -ForegroundColor Red
    exit 1
}

Write-Host ""

# ============================================================================
# 4. Deploy Indexer
# ============================================================================
Write-Host "[4/4] Deploying Indexer..." -ForegroundColor Cyan
$indexerJson = Get-Content (Join-Path $modulesPath "rest-indexer.json") -Raw

try {
    $result = Invoke-RestMethod -Method Put `
        -Uri "$searchEndpoint/indexers/driving-manual-indexer?api-version=$ApiVersion" `
        -Headers $headers `
        -Body $indexerJson
    
    Write-Host "✓ Indexer 'driving-manual-indexer' created successfully" -ForegroundColor Green
} catch {
    $errorDetails = $_.ErrorDetails.Message | ConvertFrom-Json
    Write-Host "✗ Indexer creation failed:" -ForegroundColor Red
    Write-Host "  Error: $($errorDetails.error.message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "✓ All search components deployed successfully!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Upload PDFs to blob storage 'pdfs' container" -ForegroundColor White
Write-Host "2. Run the indexer:" -ForegroundColor White
Write-Host "   az search indexer run --name driving-manual-indexer --service-name $SearchServiceName" -ForegroundColor Gray
Write-Host ""
