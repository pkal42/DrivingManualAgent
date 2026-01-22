# Document Ingestion Workflow

This guide explains the automated document ingestion pipeline for the DrivingManualAgent project, including manual and automated workflows, troubleshooting, and debugging techniques.

## Table of Contents

- [Overview](#overview)
- [Pipeline Architecture](#pipeline-architecture)
- [Manual Ingestion](#manual-ingestion)
- [Automated Ingestion](#automated-ingestion)
- [Validation and Monitoring](#validation-and-monitoring)
- [Troubleshooting](#troubleshooting)
- [Skillset Debugging](#skillset-debugging)
- [Best Practices](#best-practices)

## Overview

The document ingestion pipeline automates the process of:

1. **Uploading** PDF driving manuals to Azure Blob Storage
2. **Extracting** text using Azure AI Search native PDF extraction
3. **Chunking** text into 1000-character segments with 200-character overlap (via SplitSkill)
4. **Embedding** chunks using Azure OpenAI text-embedding-3-large (3072 dimensions)
5. **Indexing** to Azure AI Search with hybrid search support
6. **Validating** results and reporting statistics

### Key Features

- ✅ Python-based setup using Azure SDK (100% managed services)
- ✅ Native PDF text extraction (no external OCR service required)
- ✅ Figure caption extraction from embedded images
- ✅ Page-based chunking configuration
- ✅ Automated Indexer-based ingestion
- ✅ Managed identity authentication throughout (no API keys)
- ✅ Stable API versions (Search 2024-07-01 GA)
- ✅ Comprehensive error handling and logging

## Pipeline Architecture

```
┌─────────────────┐
│  PDF Files      │
│  (Local/GitHub) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Upload to      │ ← Upload to blob storage (pdfs container)
│  Blob Storage   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────┐
│  Azure AI Search Indexer Pipeline               │
│  ┌─────────────────────────────────────────────┐│
│  │ 1. Detect new blobs in 'pdfs' container     ││
│  │ 2. Document Cracking (Native PDF Support)   ││
│  │ 3. Skillset Execution:                      ││
│  │    a. Text Split (Page-based chunking)      ││
│  │    b. Image Analysis (Captioning)           ││
│  │    c. Generate Embeddings (Azure OpenAI)    ││
│  │ 4. Index Projection (Map fields to index)   ││
│  └─────────────────────────────────────────────┘│
└─────────────────┬───────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────┐
│  Azure AI Search Index          │
│  - 286 chunks (MI DMV 2024)     │
│  - Hybrid search enabled        │
│  - 3072-dim vectors             │
└─────────────────────────────────┘
```

## Manual Ingestion

### Prerequisites

1. **Azure Resources Deployed**
   - Storage account with `pdfs` container
   - Azure AI Search service with index
   - Azure OpenAI (Foundry) with text-embedding-3-large deployment
   - Proper RBAC permissions configured

2. **Environment Setup**
   ```powershell
   cd src/indexing
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   pip install -r ../../requirements.txt
   ```

3. **Authentication**
   Ensure you're authenticated with Azure CLI:
   ```powershell
   az login
   az account set --subscription <subscription-id>
   ```

### Step 1: Upload PDFs to Blob Storage

Upload PDFs manually using Azure CLI:

```powershell
az storage blob upload-batch ` `n  -d pdfs ` `n  -s data/manuals ` `n  --account-name <storage-account> ` `n  --auth-mode login
```

Or upload a single file:

```powershell
az storage blob upload ` `n  -f data/manuals/MI_DMV_2024.pdf ` `n  -c pdfs ` `n  -n MI_DMV_2024.pdf ` `n  --account-name <storage-account> ` `n  --auth-mode login
```

### Step 2: Trigger Search Indexer

The Azure AI Search Indexer handles extraction, chunking, and embedding automatically. To run it immediately:

```powershell
cd src/indexing
python trigger_indexer.py --indexer driving-manual-indexer --wait
```

The script will:
1. Trigger the indexer execution
2. Monitor status (queued -> running -> success)
3. Report processed document counts and errors

**Expected Output:**
```
INFO - Triggering indexer: driving-manual-indexer
INFO - Indexer started. Monitoring status...
INFO - Status: running | Items: 5 | Progress: 10%
...
INFO - Status: success | Items: 286 | Errors: 0
INFO - Indexer execution completed successfully! for driving-manual-indexer
```

### Step 3: Verify Indexing

Check that documents were indexed:

```powershell
az search index show-statistics ` `n  --index-name driving-manual-index ` `n  --service-name <search-service> ` `n  --resource-group <rg-name>
```

Query the index to verify:

```powershell
az search index search ` `n  --index-name driving-manual-index ` `n  --service-name <search-service> ` `n  --search-text "stop sign" ` `n  --query-type simple ` `n  --top 3
```

## Automated Ingestion

### GitHub Actions Workflow (Future)

The ingestion pipeline can be automated via GitHub Actions for scheduled or event-driven processing.

**Planned Features:**
- Automatic PDF detection in repository
- Scheduled daily/weekly indexing
- Manual workflow dispatch with parameters
- Status notifications and reporting
- Azure Container Apps Jobs deployment

**Potential Implementation:**
1. **Trigger on PDF commit**: Detect new PDFs in `data/manuals/`
2. **Upload to blob**: Use `az storage blob upload-batch`
3. **Run indexing**: Execute Python pipeline in container
4. **Validate results**: Check index statistics
5. **Report status**: Post summary to PR or issue

### Deployment Options

**Option 1: GitHub Actions**
- Runs on GitHub-hosted runners
- Good for occasional/manual indexing
- Uses OIDC for Azure authentication
- Free tier limits may apply

**Option 2: Azure Container Apps Jobs**
- Runs in Azure environment
- Better for scheduled/regular indexing
- Direct access to Azure resources
- No GitHub minutes consumed

**Option 3: Manual Local Execution**
- Current approach - works well for development
- Full control and debugging capability
- Requires local Azure CLI authentication
- Good for testing and validation

## Validation and Monitoring

### Index Validation

After running the indexing pipeline, verify results:

#### 1. Document Count
Check that all PDFs were processed:

```powershell
az search index show-statistics ` `n  --index-name driving-manual-index ` `n  --service-name <search-service> ` `n  --resource-group <rg-name> ` `n  --query 'documentCount'
```

Expected: Number of chunks (e.g., 286 for MI_DMV_2024.pdf)

#### 2. Search Functionality
Test hybrid search:

```powershell
az search index search ` `n  --index-name driving-manual-index ` `n  --service-name <search-service> ` `n  --search-text "stop sign" ` `n  --query-type semantic ` `n  --top 5
```

Verify results include relevant chunks with proper metadata.

#### 3. Field Population
Check that required fields are populated:

```python
from azure.search.documents import SearchClient
from azure.identity import DefaultAzureCredential

client = SearchClient(
    endpoint="https://<search-service>.search.windows.net",
    index_name="driving-manual-index",
    credential=DefaultAzureCredential()
)

# Get a sample document
results = client.search("*", top=1)
for doc in results:
    print(f"chunk_id: {doc['chunk_id']}")
    print(f"content: {doc['content'][:100]}...")
    print(f"document_id: {doc['document_id']}")
    print(f"page_number: {doc['page_number']}")
    print(f"Vector dims: {len(doc['chunk_vector'])}")
```

Expected: All fields populated, 3072-dim vectors

#### 4. Embedding Quality
Verify embeddings are non-zero:

```python
results = client.search("*", top=10)
for doc in results:
    vector = doc.get('chunk_vector', [])
    if vector:
        avg = sum(vector) / len(vector)
        print(f"Doc {doc['chunk_id']}: avg={avg:.6f}, dims={len(vector)}")
```

Expected: Non-zero averages, consistent dimensions

## Troubleshooting

### Common Issues

#### 1. Authentication Errors

**Symptom:**
```
Error: DefaultAzureCredential failed to retrieve a token
```

**Solutions:**
- Verify you're logged in: `az login`
- Check RBAC roles:
  - User needs "Storage Blob Data Contributor" and "Storage Blob Data Reader"
  - User needs "Search Index Data Contributor"
  - Search Service MI needs "Storage Blob Data Reader"
- Refresh credentials if stale: `az logout && az login`
- Wait 10-15 seconds after role assignment for propagation

#### 2. Indexer Document Cracking Fails

**Symptom:**
```
"Error with data source: Error detecting index schema from data source"
OR
"Could not read file"
```

**Solutions:**
- Verify `allowSkillsetToReadFileData` is set to `true` in Indexer configuration
- Verify PDF is not encrypted or password-protected
- Verify Search Service Identity has Storage Blob Data Reader role

#### 3. Embedding Generation Fails

**Symptom:**
```
Error generating embeddings
openai.RateLimitError: Rate limit exceeded
```

**Solutions:**
- Check Azure OpenAI deployment exists
- Verify text-embedding-3-large model is deployed
- Check TPM (tokens per minute) quota
- Reduce batch size in `index_documents.py`
- Implement retry logic with exponential backoff
- Request quota increase if needed

#### 4. Search Index Upload Fails (403 Forbidden)

**Symptom:**
```
RequestFailure: Failed to send batch - 403 Forbidden
```

**Solutions:**
- Verify user has "Search Index Data Contributor" role
- Wait 10-15 seconds after role assignment
- Check search endpoint URL is correct
- Verify index name matches deployed index
- Confirm search service allows managed identity access

#### 5. No Text Extracted from PDF

**Symptom:**
```
Extracted text from 0 pages
Created 0 chunks
```

**Solutions:**
- Verify PDF contains extractable text
- For scanned PDFs, ensure `imageAction` is set to `generateNormalizedImages`
- Try different PDF file to isolate issue
- Verify Skillset configuration and field mappings

#### 6. Chunk Count Unexpectedly Low/High

**Symptom:**
```
Created only 10 chunks from 200-page document
OR
Created 5000 chunks from 50-page document
```

**Solutions:**
- Check chunk_size and chunk_overlap settings
- Verify text extraction quality in debug sessions
- Review actual text length from extraction
- Adjust chunking parameters if needed
- For very dense documents, increase chunk_size
- For sparse documents, decrease chunk_size

#### 7. Memory or Performance Issues

**Symptom:**
```
Process killed (OOM)
OR
Processing very slow (>1 hour for single PDF)
```

**Solutions:**
- Reduce embedding batch size (default 100)
- Process PDFs one at a time instead of all at once
- Increase VM/container memory if running in cloud
- Check for memory leaks in long-running processes
- Monitor Azure service quotas and throttling

## Debugging Tips

### Enable Verbose Logging

Add logging to `index_documents.py`:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Test Individual Components

Test each step independently:

```python
# Test Embeddings
from openai import AzureOpenAI
client = AzureOpenAI(...)
response = client.embeddings.create(
    input=["test text"],
    model="text-embedding-3-large"
)
print(len(response.data[0].embedding))  # Should be 3072

# Test Search Upload
from azure.search.documents import SearchClient
client = SearchClient(...)
result = client.upload_documents([{"chunk_id": "test", ...}])
print(result)
```

### Monitor Azure Resources

Check Azure Portal metrics:
- Azure OpenAI: Token usage, rate limits, quotas
- AI Search: Index size, query rate, document count
- Storage: Blob operations, bandwidth

### Review Logs

Check logs in various locations:
- Application logs: `indexing.log`
- Azure Monitor: Application Insights logs
- Search service: Indexer status and execution history

## Best Practices

### 1. Document Organization

Organize PDFs by state and year in blob storage:
```
blob-storage/pdfs/
  MI_DMV_2024.pdf
  CA_DMV_2024.pdf
  TX_Driver_Handbook_2025.pdf
```

Use consistent naming: `{STATE}_{TITLE}_{YEAR}.pdf`

### 2. Incremental Processing

When adding new documents:
1. Upload new PDFs to blob storage
2. Run indexing pipeline - it processes all PDFs
3. Existing chunks are updated (based on chunk_id)
4. New chunks are added

To reprocess specific documents:
- Delete old chunks from index (filter by document_id)
- Run pipeline - will create fresh chunks

### 3. Configuration Management

Keep configuration values in a separate config file or environment variables:

```python
# config.py or .env
STORAGE_ACCOUNT = "stdrvagdbvxlqv"
CONTAINER_NAME = "pdfs"
FOUNDRY_ENDPOINT = "https://..."
SEARCH_ENDPOINT = "https://..."
INDEX_NAME = "driving-manual-index"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBEDDING_BATCH_SIZE = 100
```

This makes it easier to:
- Deploy to different environments (dev/prod)
- Share configuration across team
- Update parameters without code changes

### 4. Error Handling and Logging

The indexing pipeline logs detailed information:
- Save logs for debugging: `python index_documents.py 2>&1 | tee indexing.log`
- Review logs after failures
- Monitor for warnings (may indicate issues)

Common log messages to watch for:
- "Failed to read file" - Storage/Permission issues
- "Error generating embeddings" - Azure OpenAI throttling
- "Upload failed" - Search service issues

### 5. Cost Optimization

To minimize costs:
- Process PDFs in batches (avoid frequent small runs)
- Use appropriate chunk size (1000 chars balances quality/cost)
- Monitor OpenAI usage
- Consider using fewer embedding dimensions for large-scale deployments
- Clean up unused indexes and old data

### 6. Testing and Validation

Before processing large batches:
1. Test with a single small PDF
2. Verify chunks are created correctly
3. Check search results quality
4. Review costs for single document
5. Scale up gradually

### 7. Monitoring and Maintenance

Regularly check:
- Search index statistics (document count)
- Embedding quality (non-zero vectors)
- Search relevance (sample queries)
- Azure service health
- Storage account usage

### 8. Security Best Practices

- Use managed identity authentication everywhere
- Never commit API keys or connection strings
- Implement RBAC with least privilege
- Rotate credentials regularly
- Monitor access logs for anomalies
- Enable audit logging on storage and search

### 2. Metadata Strategy

Include rich metadata:
```powershell
python src/indexing/upload_documents.py ` `n  --file manual.pdf ` `n  --state California ` `n  --year 2024 ` `n  --version 2.0
```

Metadata enables:
- Better filtering in search
- State-specific queries
- Version tracking

### 3. Incremental Updates

For updates, only upload changed files:
```powershell
# Upload only new/modified PDFs
python src/indexing/upload_documents.py ` `n  --directory data/manuals ` `n  --recursive
  # Note: No --overwrite flag (skip existing)

# Trigger incremental indexing (don't reset)
python src/indexing/trigger_indexer.py --wait
```

### 4. Validation Frequency

- **After every upload**: Quick validation
- **Weekly**: Full validation with reports
- **Before production release**: Comprehensive validation

### 5. Error Handling

Set up monitoring:
```powershell
# Cron job for daily validation
0 2 * * * python src/indexing/validate_enrichment.py --json-output /logs/validation-$(date +\%Y\%m\%d).json
```

### 6. GitHub Actions Integration

For CI/CD pipelines:

1. **PR Checks**: Run validation on PR
2. **Main Branch**: Auto-upload new PDFs
3. **Scheduled**: Periodic re-indexing
4. **Manual**: On-demand ingestion

### 7. Cost Optimization

Minimize costs:
- Use incremental indexing (don't reset unnecessarily)
- Monitor Azure OpenAI usage
- Delete old validation reports
- Use appropriate search tier

## Examples

### Example 1: Upload California Manual

```powershell
# Upload with automatic metadata extraction
python src/indexing/upload_documents.py ` `n  --file data/manuals/California/2024/dmv-handbook.pdf ` `n  --verbose

# Output:
# Uploading data/manuals/California/2024/dmv-handbook.pdf -> California/2024/dmv-handbook.pdf
# Metadata: {'state': 'California', 'year': '2024', ...}
# ✓ Successfully uploaded (3.45 MB)
```

### Example 2: Batch Upload and Index

```powershell
# Upload all PDFs
python src/indexing/upload_documents.py ` `n  --directory data/manuals ` `n  --recursive ` `n  --overwrite

# Trigger indexer and wait
python src/indexing/trigger_indexer.py --wait --timeout 3600

# Validate results
python src/indexing/validate_enrichment.py ` `n  --json-output validation.json ` `n  --markdown-output validation.md
```

### Example 3: Debug Failed Indexer

```powershell
# 1. Check indexer status
python src/indexing/trigger_indexer.py --status-only

# 2. Analyze errors
python src/indexing/monitor_skillset.py --show-errors

# 3. Reset and retry
python src/indexing/trigger_indexer.py --reset --wait

# 4. Validate after fix
python src/indexing/validate_enrichment.py
```

### Example 4: GitHub Actions Manual Trigger

1. Go to GitHub Actions
2. Select "Ingest Documents" workflow
3. Click "Run workflow"
4. Fill in parameters:
   - **State**: California
   - **Document Paths**: data/manuals/California/2024/dmv-handbook.pdf
   - **Reset Indexer**: No
5. Click "Run workflow"
6. Monitor progress in Actions tab

## Support

For issues or questions:

1. **Check logs**: GitHub Actions logs or local console output
2. **Review documentation**: This guide and Azure AI Search docs
3. **Monitor resources**: Azure Portal for service health
4. **Create issue**: GitHub issue with logs and error messages
5. **Contact maintainers**: Via PR comments or Slack

## Related Documentation

- [Azure AI Search Indexer Documentation](https://learn.microsoft.com/azure/search/search-indexer-overview)
- [Skillset Concepts](https://learn.microsoft.com/azure/search/cognitive-search-working-with-skillsets)
- [Debug Sessions](https://learn.microsoft.com/azure/search/cognitive-search-debug-session)
- [Repository README](../README.md)
- [Infrastructure Guide](../infra/bicep/README.md)

