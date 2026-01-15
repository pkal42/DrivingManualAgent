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
   - Data source → Skillset → Index flow
   - Field mappings and output mappings
   - Error handling and scheduling

## Prerequisites

- Azure subscription
- Azure CLI (`az` command)
- Existing resources from Issue #1:
  - Azure AI Search service
  - Azure Storage account with `pdfs` container
  - Azure OpenAI service with deployments

## Deployment

### Individual Module Deployment

Deploy each module separately for granular control:

```bash
# 1. Deploy skillset
az deployment group create \
  --resource-group <rg-name> \
  --template-file modules/search-skillset.bicep \
  --parameters searchServiceName=<search-service> \
               openAiEndpoint=https://<openai>.openai.azure.com \
               embeddingDeploymentName=text-embedding-3-large \
               visionDeploymentName=gpt-4o

# 2. Deploy index
az deployment group create \
  --resource-group <rg-name> \
  --template-file modules/search-index.bicep \
  --parameters searchServiceName=<search-service> \
               indexName=driving-manual-index \
               vectorDimensions=3072

# 3. Deploy data source
az deployment group create \
  --resource-group <rg-name> \
  --template-file modules/search-datasource.bicep \
  --parameters searchServiceName=<search-service> \
               storageAccountName=<storage-account> \
               containerName=pdfs

# 4. Deploy indexer
az deployment group create \
  --resource-group <rg-name> \
  --template-file modules/search-indexer.bicep \
  --parameters searchServiceName=<search-service> \
               dataSourceName=driving-manual-datasource \
               skillsetName=driving-manual-skillset \
               indexName=driving-manual-index
```

### Validation

Validate Bicep templates before deployment:

```bash
# Validate syntax
az bicep build --file modules/search-skillset.bicep
az bicep build --file modules/search-index.bicep
az bicep build --file modules/search-datasource.bicep
az bicep build --file modules/search-indexer.bicep

# Preview changes (what-if)
az deployment group what-if \
  --resource-group <rg-name> \
  --template-file modules/search-skillset.bicep \
  --parameters searchServiceName=<search-service> ...
```

## Configuration

### Parameters

Each module accepts parameters for customization. See inline comments in each module for detailed parameter descriptions.

**Common Parameters:**
- `searchServiceName`: Azure AI Search service name (required)
- `openAiEndpoint`: Azure OpenAI endpoint URL (required for skillset)
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

```bash
# Get search service principal ID
SEARCH_PRINCIPAL_ID=$(az search service show \
  --name <search-service> \
  --resource-group <rg-name> \
  --query identity.principalId -o tsv)

# Grant storage access
az role assignment create \
  --assignee $SEARCH_PRINCIPAL_ID \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>

# Grant Azure OpenAI access
az role assignment create \
  --assignee $SEARCH_PRINCIPAL_ID \
  --role "Cognitive Services User" \
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
