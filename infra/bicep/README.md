# Azure Infrastructure - Bicep Templates

This directory contains modular Bicep templates for deploying the Azure AI Search indexer pipeline infrastructure.

## Modules

All modules include comprehensive inline comments explaining:
- Azure resource purpose and configuration
- Parameter choices and trade-offs
- Security configurations
- Performance tuning options

### Indexer Pipeline Modules

1. **search-skillset.bicep** - Enrichment pipeline definition
   - DocumentExtractionSkill (PDF text/image extraction)
   - TextSplitSkill (token-based chunking)
   - AzureOpenAIEmbeddingSkill (embedding generation)
   - Optional image description skill (GPT-4o vision)

2. **search-index.bicep** - Hybrid search index schema
   - Vector search configuration (HNSW algorithm)
   - Semantic search configuration
   - Complete field schema with metadata

3. **search-datasource.bicep** - Blob storage data source
   - Managed identity authentication
   - Change detection for incremental indexing
   - Soft delete detection

4. **search-indexer.bicep** - Indexer orchestration
  - Data source -> Skillset -> Index flow
   - Field mappings and output mappings
   - Error handling and scheduling

## Prerequisites

- Azure subscription
- Azure CLI (`az` command)
- Permission to deploy subscription-scoped resources (resource group, Microsoft Foundry project, Azure AI Search, Storage)
- Quota for Azure OpenAI (Microsoft Foundry) model deployments referenced in `modules/model-deployments.bicep`

## Deployment

### Full Environment Deployment

Use the subscription-scoped orchestrator to create the resource group, Foundry project, Azure AI Search, storage, and RBAC wiring in a single pass.

```powershell
# Optional preview (what-if)
az deployment sub what-if `
  --location eastus2 `
  --template-file main.bicep `
  --parameters parameters/dev.bicepparam

# Deploy and name the run so you can query outputs later
az deployment sub create `
  --location eastus2 `
  --name driving-manual-main `
  --template-file main.bicep `
  --parameters parameters/dev.bicepparam

# Retrieve the resource group emitted by the deployment
az deployment sub show `
  --name driving-manual-main `
  --query properties.outputs.resourceGroupName.value -o tsv
```

### Search Components Deployment (PowerShell REST API)

After the core infrastructure is deployed, use the PowerShell script to deploy search components via REST API. Bicep doesn't fully support Azure AI Search skillsets/indexes yet, so we use the REST API directly.

```powershell
# Get search service name from deployment
$searchService = az deployment sub show `
  --name driving-manual-main `
  --query properties.outputs.searchServiceName.value -o tsv

# Deploy all search components (index, skillset, datasource, indexer)
.\deploy-search-components.ps1 -SearchServiceName $searchService
```

The script deploys:
- **Index**: `driving-manual-index` with vector search (3072 dimensions) and semantic ranking
- **Skillset**: Document extraction → text chunking → embedding generation pipeline
- **Data Source**: Blob storage connection with managed identity authentication
- **Indexer**: Orchestrates document processing through the enrichment pipeline

REST API JSON templates are located in `modules/rest-*.json`.

### Validation

Validate Bicep templates before deployment:

```powershell
# Validate core infrastructure syntax
az bicep build --file main.bicep
az bicep build --file modules/foundry-project.bicep
az bicep build --file modules/ai-search.bicep
az bicep build --file modules/storage.bicep

# Preview changes (what-if)
az deployment sub what-if `
  --location eastus2 `
  --template-file main.bicep `
  --parameters parameters/dev.bicepparam
```

**Note**: Search components (skillset, index, datasource, indexer) are deployed via PowerShell REST API script, not Bicep.

## Configuration

### Parameters

Each module accepts parameters for customization. See inline comments in each module for detailed parameter descriptions.

**Common Parameters:**
- `searchServiceName`: Azure AI Search service name (required)
- `foundryEndpoint`: Microsoft Foundry endpoint URL (required for skillset)
- `storageAccountName`: Storage account name (required for data source)

**Optional Parameters:**
- `enableImageDescriptions`: Enable GPT-4o image descriptions (default: true)
- `enableSemanticSearch`: Enable semantic search configuration (default: true)
- `enableChangeDetection`: Enable incremental indexing (default: true)
- `vectorDimensions`: Embedding dimensions (default: 3072)

### Resource Naming

Follow Azure naming conventions:
- Search service: `srch-<project>-<env>-<region>`
- Index: `<project>-index`
- Skillset: `<project>-skillset`
- Data source: `<project>-datasource`
- Indexer: `<project>-indexer`

## Security

All modules use managed identity for authentication:
- No connection strings or access keys in templates
- RBAC assignments handled separately
- Secure parameter handling via Key Vault references (where applicable)

### Required RBAC Roles

```powershell
# Get search service principal ID
$searchPrincipalId = az search service show `
  --name <search-service> `
  --resource-group <rg-name> `
  --query identity.principalId -o tsv

# Grant storage access
az role assignment create `
  --assignee $searchPrincipalId `
  --role "Storage Blob Data Contributor" `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>

# Grant Azure OpenAI access
az role assignment create `
  --assignee $searchPrincipalId `
  --role "Cognitive Services User" `
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai>
```

## Troubleshooting

### Common Issues

**1. Bicep build errors**
- Ensure Azure CLI is updated: `az upgrade`
- Validate syntax: `az bicep build --file <template>`

**2. Deployment failures**
- Check parameter values and required dependencies
- Verify RBAC permissions on target resource group
- Review deployment logs: `az deployment group show`

**3. Runtime errors**
- Verify RBAC roles are assigned correctly
- Check resource connectivity (network rules, firewalls)
- Review indexer execution history in Azure Portal

## Best Practices

1. **Use parameter files** for environment-specific configurations
2. **Validate before deploy** with `az bicep build` and `what-if`
3. **Modular deployment** - Deploy modules independently for easier troubleshooting
4. **Comment thoroughly** - All templates include comprehensive inline comments
5. **Version control** - Track all infrastructure changes in Git

## Next Steps

After deploying infrastructure:
1. Upload sample PDFs to blob storage
2. Run indexer manually: `az search indexer run`
3. Validate with `src/indexing/validate_indexer.py`
4. Configure automatic scheduling if needed

## References

- [Azure AI Search Bicep Reference](https://learn.microsoft.com/azure/templates/microsoft.search/searchservices)
- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure AI Search Skills Reference](https://learn.microsoft.com/azure/search/cognitive-search-predefined-skills)
