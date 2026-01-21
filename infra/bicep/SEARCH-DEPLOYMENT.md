# Search Components Deployment

This directory contains the PowerShell script and REST API JSON templates for deploying Azure AI Search components.

## Why PowerShell Instead of Bicep?

Azure AI Search resources (skillsets, indexes, datasources, indexers) have limited Bicep support. The Bicep resource types exist but:
- Deployments fail with empty error messages
- No IntelliSense or validation for resource properties
- API versions are in preview with frequent breaking changes

Using PowerShell with the Azure Search REST API provides:
- ✅ Better error messages and debugging
- ✅ Direct control over API parameters
- ✅ Faster iteration during development
- ✅ More stable deployments

## Deployment Script

**`deploy-search-components.ps1`**

Deploys all search components via Azure Search REST API:
1. Index with vector search and semantic ranking
2. Skillset for document extraction and embedding generation
3. Data source connected to blob storage
4. Indexer to orchestrate the pipeline

### Usage

```powershell
# Basic usage (uses default search service)
.\deploy-search-components.ps1

# Specify search service name
.\deploy-search-components.ps1 -SearchServiceName "srch-drvagnt2-dev-7vczbz"

# From deployment outputs
$searchService = az deployment sub show `
  --name driving-manual-main `
  --query properties.outputs.searchServiceName.value -o tsv

.\deploy-search-components.ps1 -SearchServiceName $searchService
```

### Parameters

- `SearchServiceName` - Azure AI Search service name (default: srch-drvagnt2-dev-7vczbz)
- `ApiVersion` - Azure Search REST API version (default: 2024-07-01)

## REST API Templates

Located in `modules/rest-*.json`:

### **rest-index.json**
Defines the search index schema:
- Fields: chunk_id, content, chunk_vector, document_id, state, page_number, etc.
- Vector search configuration (HNSW algorithm, 3072 dimensions)
- Semantic search configuration (optional)

### **rest-skillset.json**
Defines the enrichment pipeline:
- **DocumentExtractionSkill**: Extract text and images from PDFs
- **TextSplitSkill**: Chunk text (512 tokens, 100 overlap)
- **AzureOpenAIEmbeddingSkill**: Generate embeddings (text-embedding-3-large, 3072 dimensions)

### **rest-datasource.json**
Blob storage data source configuration:
- Managed identity authentication (no connection strings)
- Change detection (incremental indexing)
- Soft delete detection

### **rest-indexer.json**
Indexer configuration:
- Links data source → skillset → index
- Field mappings from blob metadata
- Output field mappings from enrichment tree
- Batch size and error handling

## Modifying Components

To update search components:

1. Edit the corresponding `rest-*.json` file
2. Update connection strings, resource names, or parameters as needed
3. Re-run `deploy-search-components.ps1`

The script uses PUT operations, so it will create or update existing resources.

## Troubleshooting

### Access Token Issues
```powershell
# Ensure you're logged in
az login
az account show
```

### REST API Errors
The script displays detailed error messages from the Azure Search API, including:
- Missing required parameters
- Invalid configuration
- Authentication failures

### Verify Deployment
```powershell
# Check index
$token = az account get-access-token --resource https://search.azure.com --query accessToken -o tsv
$headers = @{ "Authorization" = "Bearer $token" }
Invoke-RestMethod -Uri "https://srch-drvagnt2-dev-7vczbz.search.windows.net/indexes?api-version=2024-07-01" -Headers $headers

# Check skillset
Invoke-RestMethod -Uri "https://srch-drvagnt2-dev-7vczbz.search.windows.net/skillsets?api-version=2024-07-01" -Headers $headers
```

## Integration with Main Deployment

The main Bicep deployment (`main.bicep`) creates:
- Azure AI Search service
- Microsoft Foundry account with model deployments
- Storage account with blob containers
- RBAC assignments

After the main deployment completes, run this PowerShell script to deploy search components.

## Future Improvements

When Bicep support for Azure AI Search improves:
- Consider migrating back to Bicep for unified IaC
- Monitor for stable (non-preview) API versions
- Watch for improved resource type definitions

For now, PowerShell REST API provides the most reliable deployment experience.
