<#
.SYNOPSIS
    Deploys the infrastructure and automatically assigns access to the current user.

.DESCRIPTION
    This script wraps the 'az deployment sub create' command.
    It automatically detects the currently signed-in Azure user's Principal ID
    and passes it to the Bicep template, ensuring you have immediate access
    to the deployed resources (like Search Index and Storage Containers).

.EXAMPLE
    .\deploy-infra.ps1
    
.EXAMPLE
    .\deploy-infra.ps1 -Environment prod
#>

param(
    [string]$Environment = "dev",
    [string]$Location = "eastus2"
)

$ErrorActionPreference = "Stop"

Write-Host "=== DrivingManualAgent Infrastructure Deployment ===" -ForegroundColor Cyan
Write-Host "Environment: $Environment" -ForegroundColor Gray
Write-Host "Location:    $Location" -ForegroundColor Gray
Write-Host ""

# 1. Get Current User Principal ID
Write-Host "Getting current user principal ID..." -ForegroundColor Yellow
try {
    $principalId = az ad signed-in-user show --query id -o tsv
    if (-not $principalId) {
        throw "Could not retrieve principal ID. Please run 'az login' first."
    }
    Write-Host "✓ Found Principal ID: $principalId" -ForegroundColor Green
}
catch {
    Write-Error "Failed to get user ID. Ensure you are logged in with 'az login'."
    exit 1
}

# 2. Deploy Infrastructure
$paramFile = Join-Path $PSScriptRoot "parameters\$Environment.bicepparam"
$templateFile = Join-Path $PSScriptRoot "main.bicep"

Write-Host "Deploying infrastructure..." -ForegroundColor Yellow
Write-Host "Template:  $templateFile" -ForegroundColor Gray
Write-Host "Params:    $paramFile" -ForegroundColor Gray
Write-Host ""

try {
    az deployment sub create `
        --name "driving-manual-$Environment-$(Get-Date -Format 'yyyyMMdd-HHmm')" `
        --location $Location `
        --template-file $templateFile `
        --parameters $paramFile `
        --parameters principalId=$principalId
        
    Write-Host ""
    Write-Host "✓ Deployment Complete!" -ForegroundColor Green
    Write-Host "  You have been assigned 'Search Index Data Contributor' and 'Storage Blob Data Contributor'." -ForegroundColor Green
}
catch {
    Write-Error "Deployment failed: $_"
    exit 1
}
