# Indexer Diagnostic Script
# Retrieves detailed indexer status and error information

param(
    [string]$SearchServiceName = "srch-drvagnt2-dev-7vczbz",
    [string]$IndexerName = "driving-manual-indexer"
)

$searchEndpoint = "https://$SearchServiceName.search.windows.net"
$apiVersion = "2024-07-01"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Indexer Diagnostics" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Service: $SearchServiceName" -ForegroundColor White
Write-Host "Indexer: $IndexerName" -ForegroundColor White
Write-Host ""

# Get access token
$token = az account get-access-token --resource https://search.azure.com --query accessToken -o tsv
if (-not $token) {
    Write-Host "Failed to get access token" -ForegroundColor Red
    exit 1
}

$headers = @{
    "Authorization" = "Bearer $token"
}

try {
    # Get indexer status
    $status = Invoke-RestMethod -Uri "$searchEndpoint/indexers/$IndexerName/status?api-version=$apiVersion" -Headers $headers
    
    Write-Host "Current Status: $($status.status)" -ForegroundColor $(if($status.status -eq 'running'){'Yellow'}else{'White'})
    Write-Host ""
    
    # Last execution result
    if ($status.lastResult) {
        Write-Host "=== Last Execution ===" -ForegroundColor Cyan
        Write-Host "Status: $($status.lastResult.status)" -ForegroundColor $(
            switch($status.lastResult.status) {
                'success' { 'Green' }
                'transientFailure' { 'Yellow' }
                'persistentFailure' { 'Red' }
                default { 'White' }
            }
        )
        Write-Host "Start Time: $($status.lastResult.startTime)"
        Write-Host "End Time: $($status.lastResult.endTime)"
        Write-Host "Items Processed: $($status.lastResult.itemsProcessed)"
        Write-Host "Items Failed: $($status.lastResult.itemsFailed)" -ForegroundColor $(if($status.lastResult.itemsFailed -gt 0){'Red'}else{'Green'})
        Write-Host ""
        
        # Errors
        if ($status.lastResult.errors -and $status.lastResult.errors.Count -gt 0) {
            Write-Host "=== ERRORS ($($status.lastResult.errors.Count)) ===" -ForegroundColor Red
            $status.lastResult.errors | Select-Object -First 5 | ForEach-Object {
                Write-Host "┌─ Document: $($_.key)" -ForegroundColor Yellow
                Write-Host "│  Error Message: $($_.errorMessage)" -ForegroundColor Red
                if ($_.statusCode) {
                    Write-Host "│  Status Code: $($_.statusCode)" -ForegroundColor Gray
                }
                if ($_.details) {
                    Write-Host "│  Details: $($_.details)" -ForegroundColor Gray
                }
                Write-Host "└─" -ForegroundColor Gray
                Write-Host ""
            }
        }
        
        # Warnings
        if ($status.lastResult.warnings -and $status.lastResult.warnings.Count -gt 0) {
            Write-Host "=== WARNINGS ($($status.lastResult.warnings.Count)) ===" -ForegroundColor Yellow
            $status.lastResult.warnings | Select-Object -First 5 | ForEach-Object {
                Write-Host "┌─ Document: $($_.key)" -ForegroundColor Yellow
                Write-Host "│  Warning: $($_.message)" -ForegroundColor Yellow
                if ($_.details) {
                    Write-Host "│  Details: $($_.details)" -ForegroundColor Gray
                }
                Write-Host "└─" -ForegroundColor Gray
                Write-Host ""
            }
        }
    }
    
    # Execution history
    Write-Host "=== Execution History ===" -ForegroundColor Cyan
    $status.executionHistory | Select-Object -First 5 | ForEach-Object {
        $statusColor = switch($_.status) {
            'success' { 'Green' }
            'transientFailure' { 'Yellow' }
            'persistentFailure' { 'Red' }
            default { 'White' }
        }
        Write-Host "[$($_.status)]" -ForegroundColor $statusColor -NoNewline
        Write-Host " Start: $($_.startTime) | End: $($_.endTime) | Processed: $($_.itemsProcessed) | Failed: $($_.itemsFailed)"
    }
    Write-Host ""
    
    # Check if there are documents in the data source
    Write-Host "=== Data Source Check ===" -ForegroundColor Cyan
    try {
        $datasource = Invoke-RestMethod -Uri "$searchEndpoint/datasources/driving-manual-datasource?api-version=$apiVersion" -Headers $headers
        Write-Host "Data Source: $($datasource.name)" -ForegroundColor White
        Write-Host "Type: $($datasource.type)" -ForegroundColor White
        Write-Host "Container: $($datasource.container.name)" -ForegroundColor White
        
        # Check blob storage for PDFs
        $storageAccount = "stdrvagd7vczbz"
        Write-Host ""
        Write-Host "Checking blob storage..." -ForegroundColor Yellow
        $blobs = az storage blob list --account-name $storageAccount --container-name pdfs --auth-mode login --query "[].name" -o json | ConvertFrom-Json
        if ($blobs) {
            Write-Host "PDFs in container: $($blobs.Count)" -ForegroundColor Green
            $blobs | ForEach-Object { Write-Host "  - $_" -ForegroundColor Gray }
        } else {
            Write-Host "No PDFs found in container" -ForegroundColor Red
        }
    } catch {
        Write-Host "Could not check data source: $_" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "Error retrieving indexer status:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    if ($_.ErrorDetails) {
        Write-Host $_.ErrorDetails.Message -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
