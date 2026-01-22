# Azure Infrastructure - Bicep Templates

This directory contains modular Bicep templates for deploying the Azure AI Search indexer pipeline infrastructure.

## Modules

All modules include comprehensive inline comments explaining:
- Azure resource purpose and configuration
- Parameter choices and trade-offs
- Security configurations
- Performance tuning options

### Infrastructure Modules

1. **main.bicep** - Orchestrator template
   - Deploys resource group
   - Coordinates submodule deployments
   - Configures RBAC assignments

2. **modules/foundry-project.bicep** - AI Studio & Models
   - Microsoft Foundry Hub & Project
   - Model deployments (gpt-4o, text-embedding-3-large)
   - OpenAI connection endpoints

3. **modules/ai-search.bicep** - Search Service
   - Azure AI Search resource
   - SKU configuration (Standard recommended for production)
   - Diagnostic settings

4. **modules/storage.bicep** - Data Lake Gen2
   - Blob containers for PDFs and normalized images
   - Hierarchical namespace enabled
   - Access tier configuration

5. **modules/role-assignments.bicep** - Identity & Access
   - Assigns "Storage Blob Data Contributor" to Search Service
   - Assigns "Cognitive Services OpenAI User" to Search Service
   - Ensures managed identity connectivity for the agent

### Search Data Plane Components

The actual search configuration (Index Schema, Skillset, Data Source, Indexer) is **not** managed by Bicep.
These data plane components are managed via the Python SDK to support complex logic and validation.

Please refer to the [Indexing Documentation](../../src/indexing/README.md) for details on deploying:
- `driving-manual-index`
- `driving-manual-skillset`
- `driving-manual-indexer`
- `driving-manual-datasource`

## Prerequisites

- Azure subscription
- Azure CLI (`az` command)
- Permission to deploy subscription-scoped resources (resource group, Microsoft Foundry project, Azure AI Search, Storage)
- Quota for Azure OpenAI (Microsoft Foundry) model deployments referenced in `modules/model-deployments.bicep`

## Deployment

### Full Environment Deployment

Use the subscription-scoped orchestrator to create the resource group, Foundry project, Azure AI Search, storage, and RBAC wiring in a single pass.

```powershell
# Navigate to the Bicep directory
cd infra/bicep

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

### Search Components & Data Ingestion

After the core infrastructure is deployed using Bicep, return to the repository root to allow the Python scripts to configure the data plane.

#### 1. Python Environment Setup

```powershell
# Return to root directory if currently in infra/bicep
cd ../..

# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

#### 2. Deploy and Ingest

```bash
# Deploy all search components (Index, Skillset, Indexer, Data Source)
python src/indexing/deploy_search_components.py --deploy-all

# Upload PDF documents to Blob Storage
python src/indexing/upload_documents.py --directory data/manuals --recursive

# Trigger the Indexing Pipeline
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait
```

For full details, see [src/indexing/README.md](../../src/indexing/README.md).

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

After deploying infrastructure through bicep:
1. **Deploy Search Components**: `python src/indexing/deploy_search_components.py --deploy-all`
2. **Upload Documents**: `python src/indexing/upload_documents.py --directory data/manuals --recursive`
3. **Run Indexer**: `python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait`
4. **Validate**: `python src/indexing/validate_enrichment.py`

## References

- [Azure AI Search Bicep Reference](https://learn.microsoft.com/azure/templates/microsoft.search/searchservices)
- [Bicep Documentation](https://learn.microsoft.com/azure/azure-resource-manager/bicep/)
- [Azure AI Search Skills Reference](https://learn.microsoft.com/azure/search/cognitive-search-predefined-skills)
