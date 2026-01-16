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
2. **Triggering** Azure AI Search indexer to process documents
3. **Monitoring** indexer execution and skillset processing
4. **Validating** enrichment results (chunks, images, embeddings)
5. **Reporting** results and errors

### Key Features

- ✅ Automatic metadata extraction from file paths and names
- ✅ Directory structure preservation in blob storage
- ✅ Real-time indexer monitoring with progress tracking
- ✅ Comprehensive validation of enrichment results
- ✅ Error detection and reporting
- ✅ GitHub Actions automation
- ✅ Managed identity authentication (no secrets in code)

## Pipeline Architecture

```
┌─────────────────┐
│  PDF Files      │
│  (Local/GitHub) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validation     │ ← Check size, format, naming
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Upload to      │ ← Add metadata, preserve structure
│  Blob Storage   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Trigger        │ ← Start indexer run
│  Indexer        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Monitor        │ ← Poll status until completion
│  Execution      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate       │ ← Check chunks, images, embeddings
│  Enrichment     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Generate       │ ← JSON/Markdown reports
│  Reports        │
└─────────────────┘
```

## Manual Ingestion

### Prerequisites

1. **Azure Resources Deployed**
   - Storage account with `pdfs` container
   - Azure AI Search service with indexer and skillset
   - Proper RBAC permissions configured

2. **Environment Variables**
   ```bash
   export AZURE_STORAGE_ACCOUNT="<storage-account-name>"
   export AZURE_SEARCH_ENDPOINT="https://<search-service>.search.windows.net"
   export USE_MANAGED_IDENTITY="true"  # or false for local dev with keys
   ```

3. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Step 1: Upload Documents

Upload a single PDF:

```bash
python src/indexing/upload_documents.py \
  --file data/manuals/california-dmv-handbook-2024.pdf \
  --state California \
  --year 2024 \
  --verbose
```

Upload a directory (batch):

```bash
python src/indexing/upload_documents.py \
  --directory data/manuals \
  --recursive \
  --overwrite \
  --verbose
```

**Metadata Extraction:**
The script automatically extracts metadata from paths:
- `California/2024/manual.pdf` → `state=California, year=2024`
- `texas-handbook-2023.pdf` → `year=2023`
- `manual-v2.pdf` → `version=2`

### Step 2: Trigger Indexer

Trigger and wait for completion:

```bash
python src/indexing/trigger_indexer.py \
  --wait \
  --timeout 1800 \
  --verbose
```

Just trigger (don't wait):

```bash
python src/indexing/trigger_indexer.py --verbose
```

Check status without triggering:

```bash
python src/indexing/trigger_indexer.py --status-only
```

### Step 3: Validate Enrichment

Run validation and generate reports:

```bash
python src/indexing/validate_enrichment.py \
  --json-output validation.json \
  --markdown-output validation.md \
  --verbose
```

### Step 4: Monitor Skillset (Optional)

Analyze indexer errors:

```bash
python src/indexing/monitor_skillset.py \
  --show-errors \
  --show-warnings \
  --output monitoring-report.json
```

## Automated Ingestion

### GitHub Actions Workflow

The ingestion pipeline is automated via GitHub Actions (`.github/workflows/ingest-documents.yml`).

#### Trigger Methods

**1. Manual Trigger**

Go to Actions → Ingest Documents → Run workflow

Options:
- **State**: US state name (e.g., California)
- **Document Paths**: Comma-separated paths to PDFs
- **Skip Validation**: Skip pre-upload checks
- **Reset Indexer**: Reprocess all documents

**2. Automatic Trigger**

Push PDF files to `data/manuals/`:

```bash
git add data/manuals/california-manual.pdf
git commit -m "Add California driving manual"
git push
```

The workflow automatically:
- Validates PDFs
- Uploads to blob storage
- Triggers indexer
- Monitors execution
- Validates results
- Posts report to PR (if applicable)

### Workflow Jobs

1. **validate-pdfs**: Check file format, size, corruption
2. **upload**: Upload PDFs with metadata to blob storage
3. **trigger-indexer**: Start indexer run (optional reset)
4. **monitor**: Poll indexer status until completion
5. **validate**: Check enrichment completeness and quality
6. **notify-failure**: Create issue if pipeline fails
7. **summary**: Generate workflow summary

### Viewing Results

- **Workflow Summary**: GitHub Actions run page
- **Validation Reports**: Download from Artifacts section
- **PR Comments**: Inline validation results (for PRs)
- **Issues**: Automatic issue creation on failure

## Validation and Monitoring

### Validation Checks

The validation script checks:

#### 1. Document Completeness
- All uploaded PDFs are indexed
- No missing documents

#### 2. Chunk Generation
- Appropriate number of chunks per document
- No documents with too few/many chunks
- Chunk size distribution

#### 3. Image Extraction
- Images detected and extracted
- Image URLs and descriptions populated
- Reasonable image extraction rate

#### 4. Field Population
- Required fields populated in all chunks
- Metadata fields present
- No missing data

#### 5. Embedding Presence
- Vector embeddings generated
- Embedding dimensions correct

### Monitoring Skillset

Monitor indexer execution history:

```bash
# View recent executions
python src/indexing/monitor_skillset.py --indexer driving-manual-indexer

# Analyze errors
python src/indexing/monitor_skillset.py --show-errors --limit 50

# View skillset definition
python src/indexing/monitor_skillset.py --show-skillset
```

## Troubleshooting

### Common Issues

#### 1. Upload Fails - Authentication Error

**Symptom:**
```
Error: DefaultAzureCredential failed to retrieve a token
```

**Solutions:**
- Verify you're logged in: `az login`
- Check RBAC roles: User needs "Storage Blob Data Contributor"
- For GitHub Actions: Verify OIDC configuration

#### 2. Indexer Doesn't Start

**Symptom:**
```
Error: Indexer not found: driving-manual-indexer
```

**Solutions:**
- Verify indexer exists: `az search indexer show --name driving-manual-indexer --service-name <service>`
- Check resource deployment
- Verify search endpoint is correct

#### 3. Indexer Fails with Errors

**Symptom:**
```
Indexer completed with errors
Items failed: 5
```

**Solutions:**

1. **Check Error Details:**
   ```bash
   python src/indexing/monitor_skillset.py --show-errors
   ```

2. **Common Skillset Errors:**
   - **DocumentExtractionSkill**: PDF corrupted or unsupported format
   - **SplitSkill**: Text too long or encoding issues
   - **EmbeddingSkill**: Azure OpenAI throttling or quota exceeded

3. **Fix and Retry:**
   ```bash
   # Reset indexer to reprocess
   python src/indexing/trigger_indexer.py --reset --wait
   ```

#### 4. Validation Fails - Missing Documents

**Symptom:**
```
Validation failed: Missing documents
- california-manual.pdf
```

**Solutions:**
- Check upload was successful
- Verify blob exists: `az storage blob list -c pdfs --account-name <account>`
- Re-upload missing files
- Trigger indexer again

#### 5. Low Image Extraction Rate

**Symptom:**
```
Warning: Low image extraction rate: 2.5%
```

**Solutions:**
- Check if PDFs contain images (not just text)
- Verify DocumentExtractionSkill configuration
- Check skillset imageAction parameter (should be "generateNormalizedImages")

#### 6. Timeout Waiting for Indexer

**Symptom:**
```
Timeout waiting for indexer (elapsed: 1800s)
```

**Solutions:**
- Increase timeout: `--timeout 3600`
- Check indexer isn't stuck: `az search indexer status`
- Monitor Azure portal for resource throttling
- Reset if needed: `--reset`

### Debug Sessions API

For deep debugging of skillset enrichment:

1. **Enable Debug Sessions** (in Azure Portal)
   - Go to Search service → Skillset
   - Enable "Save enrichments to debug session cache"

2. **Inspect Enrichment Tree**
   - View output of each skill
   - Identify which skill is failing
   - See intermediate data transformations

3. **Fix and Test**
   - Modify skillset configuration
   - Re-run indexer
   - Validate changes

## Skillset Debugging

### Understanding the Enrichment Pipeline

The skillset processes documents in stages:

```
PDF Document
    ↓
DocumentExtractionSkill
    ├─ Text content
    └─ Normalized images (PNG)
        ↓
SplitSkill (Token-based chunking)
    ├─ Chunk 1 (512 tokens)
    ├─ Chunk 2 (512 tokens)
    └─ ...
        ↓
AzureOpenAIEmbeddingSkill
    └─ Vector embeddings (3072-dim)
```

### Analyzing Errors by Skill

#### DocumentExtractionSkill Errors

**Common Issues:**
- Corrupted PDF files
- Password-protected PDFs
- Unsupported PDF versions
- Very large files (>100MB)

**Debugging:**
```bash
# Check PDF validity
pdfinfo data/manuals/problematic.pdf

# Try manual extraction
pdftotext data/manuals/problematic.pdf output.txt
```

#### SplitSkill Errors

**Common Issues:**
- Text encoding problems
- Very long documents exceeding limits
- Special characters causing parsing issues

**Debugging:**
```bash
# Check text content
python -c "
from indexing.validate_enrichment import EnrichmentValidator
v = EnrichmentValidator()
docs = v.get_indexed_documents()
for doc in docs:
    print(f\"Chunk length: {len(doc.get('content', ''))} chars\")
"
```

#### EmbeddingSkill Errors

**Common Issues:**
- Azure OpenAI throttling (429 errors)
- Quota exceeded
- Empty text chunks
- Text too long for embedding model

**Debugging:**
```bash
# Check Azure OpenAI metrics in Azure Portal
# Monitor rate limits and quotas

# Verify embedding deployment exists
az cognitiveservices account deployment list \
  --name <openai-account> \
  --resource-group <rg>
```

### Performance Optimization

**Reduce Indexer Run Time:**

1. **Batch Size**: Adjust indexer configuration
2. **Parallel Processing**: Enable in skillset
3. **Caching**: Enable skillset cache for incremental indexing
4. **Resource Scaling**: Increase Azure AI Search tier

**Monitor Performance:**
```bash
python src/indexing/monitor_skillset.py --output report.json

# Analyze execution times
cat report.json | jq '.execution_history[] | {start_time, end_time, items_processed}'
```

## Best Practices

### 1. Document Organization

Organize PDFs by state and year:
```
data/manuals/
  California/
    2024/
      dmv-handbook.pdf
    2025/
      dmv-handbook.pdf
  Texas/
    2024/
      driver-handbook.pdf
```

### 2. Metadata Strategy

Include rich metadata:
```bash
python src/indexing/upload_documents.py \
  --file manual.pdf \
  --state California \
  --year 2024 \
  --version 2.0
```

Metadata enables:
- Better filtering in search
- State-specific queries
- Version tracking

### 3. Incremental Updates

For updates, only upload changed files:
```bash
# Upload only new/modified PDFs
python src/indexing/upload_documents.py \
  --directory data/manuals \
  --recursive
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
```bash
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

```bash
# Upload with automatic metadata extraction
python src/indexing/upload_documents.py \
  --file data/manuals/California/2024/dmv-handbook.pdf \
  --verbose

# Output:
# Uploading data/manuals/California/2024/dmv-handbook.pdf -> California/2024/dmv-handbook.pdf
# Metadata: {'state': 'California', 'year': '2024', ...}
# ✓ Successfully uploaded (3.45 MB)
```

### Example 2: Batch Upload and Index

```bash
# Upload all PDFs
python src/indexing/upload_documents.py \
  --directory data/manuals \
  --recursive \
  --overwrite

# Trigger indexer and wait
python src/indexing/trigger_indexer.py --wait --timeout 3600

# Validate results
python src/indexing/validate_enrichment.py \
  --json-output validation.json \
  --markdown-output validation.md
```

### Example 3: Debug Failed Indexer

```bash
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
