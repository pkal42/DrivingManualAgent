# Azure AI Search Indexer - Troubleshooting Guide

This guide provides step-by-step instructions for troubleshooting Azure AI Search indexer issues using Debug Sessions and other diagnostic tools.

## Debug Sessions API

Debug Sessions is a powerful Azure Portal feature for troubleshooting skillset execution in real-time.

### What are Debug Sessions?

Debug Sessions allow you to:
- Inspect the enrichment tree at each skill execution step
- View skill inputs and outputs in real-time
- Test skillset configuration changes without redeploying
- Debug failed enrichments with detailed error messages
- Validate field mappings and output mappings

### When to Use Debug Sessions

Use Debug Sessions when:
- Skillset execution fails or produces unexpected results
- Images are not being extracted correctly
- Embeddings are not generated
- Text chunks are malformed or empty
- Field mappings are not working as expected
- You need to validate a new skillset configuration

### How to Access Debug Sessions

#### Method 1: Azure Portal (Recommended)

1. Navigate to Azure Portal: https://portal.azure.com
2. Go to your Azure AI Search service
3. In the left menu, under "Search management", click **Debug sessions**
4. Click **+ Add debug session**
5. Configure the debug session:
   - **Session name**: `driving-manual-debug-session`
   - **Indexer**: Select `driving-manual-indexer`
   - **Document**: Choose a specific PDF to debug
   - **Storage account**: Select storage account for session data
   - **Container**: `debug-sessions` (created automatically)
6. Click **Create**

#### Method 2: REST API

```bash
# Create a debug session via REST API
curl -X PUT \
  "https://<search-service>.search.windows.net/debug/sessions/<session-id>?api-version=2024-05-01-preview" \
  -H "api-key: <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Debug session for driving manual indexer",
    "indexer": "driving-manual-indexer",
    "documentId": "<document-id>",
    "storageResourceId": "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>",
    "containerName": "debug-sessions"
  }'
```

### Using Debug Sessions

Once the session is created:

1. **View Enrichment Tree**
   - Expand the document node to see all enrichments
   - Navigate: `/document` → `/document/pages` → `/document/pages/*/vector`
   - Each node shows the data at that stage

2. **Inspect Skill Outputs**
   - Click on a skill in the Skills pane
   - View Input/Output tabs to see actual data
   - Check for errors or unexpected values

3. **Test Configuration Changes**
   - Modify skill parameters in the UI
   - Click **Run** to test changes
   - View updated enrichment tree
   - Changes are NOT saved automatically (test-only)

4. **Debug Common Issues**

   **Issue: No text extracted**
   - Navigate to `/document/extracted_content`
   - If empty, check DocumentExtractionSkill configuration
   - Verify `allowSkillsetToReadFileData: true` in indexer
   - Check blob permissions (Storage Blob Data Reader role)

   **Issue: Images not extracted**
   - Navigate to `/document/normalized_images`
   - If empty, verify `imageAction: generateNormalizedImages`
   - Check PDF actually contains images
   - Review DocumentExtractionSkill errors

   **Issue: Chunks too large/small**
   - Navigate to `/document/pages`
   - Check chunk count and text length
   - Verify `unit: azureOpenAITokens` is set
   - Adjust `maximumPageLength` if needed

   **Issue: Embeddings not generated**
   - Navigate to `/document/pages/*/vector`
   - If empty, check AzureOpenAIEmbeddingSkill errors
   - Verify Azure OpenAI endpoint and deployment name
   - Check "Cognitive Services User" role assignment

5. **Save Working Configuration**
   - Once you've fixed issues in Debug Session
   - Update your Bicep template with the changes
   - Redeploy the skillset
   - Delete and recreate the indexer
   - Run indexer to apply changes to all documents

### Debug Session Limitations

- **Performance**: Debug sessions run on a single document (not full indexer run)
- **State**: Changes in debug session don't persist to the skillset
- **Quota**: Limited number of concurrent debug sessions per service
- **Storage**: Debug session data stored in blob storage (incurs cost)

## Indexer Execution Logs

### View Indexer Status

```bash
# Get indexer status
az search indexer status \
  --name driving-manual-indexer \
  --service-name <search-service> \
  --resource-group <rg-name>
```

**Output includes:**
- Last execution status (success, failed, in progress)
- Items processed, items failed
- Start time, end time, duration
- Error messages and warnings
- Execution history (last 10 runs)

### Common Error Messages

#### Error: "Cannot read file data"

**Cause**: Indexer doesn't have permission to read blob files

**Solution**:
1. Verify `allowSkillsetToReadFileData: true` in indexer
2. Grant "Storage Blob Data Reader" role:
   ```bash
   SEARCH_PRINCIPAL_ID=$(az search service show \
     --name <search-service> \
     --resource-group <rg-name> \
     --query identity.principalId -o tsv)
   
   az role assignment create \
     --assignee $SEARCH_PRINCIPAL_ID \
     --role "Storage Blob Data Reader" \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>
   ```

#### Error: "Skill execution failed: AzureOpenAIEmbeddingSkill"

**Cause**: Azure OpenAI connection or quota issues

**Solution**:
1. Verify Azure OpenAI endpoint is correct
2. Check deployment name matches parameter
3. Grant "Cognitive Services User" role
4. Check quota limits (tokens per minute)
5. Verify model deployment is active

#### Error: "Invalid field mapping"

**Cause**: Source field doesn't exist or mapping syntax is incorrect

**Solution**:
1. Use Debug Sessions to inspect enrichment tree
2. Verify source field path (e.g., `/document/pages/*/text`)
3. Check output field mappings match enrichment tree
4. Ensure target field exists in index schema

#### Error: "Document exceeds maximum size"

**Cause**: PDF file too large for indexer

**Solution**:
1. Split large PDFs into smaller files
2. Increase indexer batch size (process fewer docs at once)
3. Check Azure AI Search tier limits

## Monitoring with Application Insights

### Enable Diagnostic Logging

1. Navigate to Azure AI Search service in Portal
2. Go to "Diagnostic settings" under Monitoring
3. Click **+ Add diagnostic setting**
4. Configure:
   - **Name**: `search-diagnostics`
   - **Logs**: Select "Indexer Operations", "Skillset Execution"
   - **Destination**: Log Analytics workspace or Application Insights
5. Click **Save**

### Query Indexer Logs

In Application Insights or Log Analytics:

```kusto
// Query indexer errors
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.SEARCH"
| where Category == "OperationLogs"
| where OperationName == "Indexer.Execute"
| where Level == "Error"
| project TimeGenerated, OperationName, ResultDescription, Resource
| order by TimeGenerated desc

// Query skillset execution
AzureDiagnostics
| where Category == "OperationLogs"
| where OperationName contains "Skillset"
| project TimeGenerated, OperationName, ResultDescription
| order by TimeGenerated desc
```

## Validation Script Usage

Use the validation script to check indexer health:

```bash
cd src/indexing

# Install dependencies
pip install azure-search-documents azure-identity

# Run validation
export AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
python validate_indexer.py \
  --skillset-name driving-manual-skillset \
  --indexer-name driving-manual-indexer
```

**Validation checks:**
- ✅ Skillset has all required skills
- ✅ Indexer executed successfully
- ✅ Documents indexed with expected fields
- ✅ Embeddings generated (3072 dimensions)
- ✅ Images extracted and referenced
- ✅ Field coverage meets thresholds

## Common Troubleshooting Workflows

### Workflow 1: No Documents Indexed

1. **Check indexer status**:
   ```bash
   az search indexer status --name driving-manual-indexer --service-name <search> --resource-group <rg>
   ```

2. **Verify data source**:
   - Check blob container exists and has PDFs
   - Verify connection string or managed identity
   - Test blob access manually

3. **Check RBAC roles**:
   - Search service has "Storage Blob Data Reader"
   - Verify role assignment scope (storage account level)

4. **Run indexer manually**:
   ```bash
   az search indexer run --name driving-manual-indexer --service-name <search> --resource-group <rg>
   ```

### Workflow 2: Images Not Appearing in Index

1. **Verify PDF has images**:
   - Open PDF manually and confirm images exist
   - Some PDFs have images as background (not extractable)

2. **Check skillset configuration**:
   - Verify `imageAction: generateNormalizedImages` in DocumentExtractionSkill
   - Check knowledge store or blob storage for extracted images

3. **Use Debug Session**:
   - Create session for a PDF with known images
   - Navigate to `/document/normalized_images`
   - If empty, review skill errors

4. **Check field mappings**:
   - Verify output field mapping for images
   - Ensure `image_blob_urls` field populated in index

### Workflow 3: Poor Search Quality

1. **Check chunk size**:
   - Use validation script to analyze chunk stats
   - If chunks too large (>800 tokens), reduce `maximumPageLength`
   - If chunks too small (<200 tokens), increase it

2. **Verify embeddings**:
   - Check embedding dimensions (should be 3072)
   - Test vector search returns results
   - Verify `vectorSearchProfile` configured correctly

3. **Enable semantic search**:
   - Add semantic configuration to index
   - Use `queryType=semantic` in queries
   - Configure `prioritizedFields` for better ranking

## Best Practices

1. **Always use Debug Sessions first** before modifying production skillset
2. **Test with small sample** (1-2 PDFs) before full indexing
3. **Monitor quota usage** for Azure OpenAI (tokens per minute)
4. **Enable diagnostic logging** for production environments
5. **Use validation script** after every indexer run
6. **Document configuration changes** in Bicep template comments
7. **Version control skillsets** with Git for rollback capability

## Additional Resources

- [Azure AI Search Troubleshooting Guide](https://learn.microsoft.com/azure/search/search-indexer-troubleshooting)
- [Debug Sessions Documentation](https://learn.microsoft.com/azure/search/cognitive-search-debug-session)
- [Skillset Execution Errors](https://learn.microsoft.com/azure/search/cognitive-search-common-errors-warnings)
- [Indexer Error Reference](https://learn.microsoft.com/azure/search/search-indexer-error-codes)
- [Monitoring Azure AI Search](https://learn.microsoft.com/azure/search/monitor-azure-cognitive-search)
