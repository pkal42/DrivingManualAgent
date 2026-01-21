# Indexing Pipeline

This directory contains Python scripts for managing Azure AI Search components and running the document indexing pipeline.

## Scripts

### 1. deploy_search_components.py

Creates and configures all Azure AI Search components using the Python SDK.

**Components Deployed:**
- Search Index with vector search and semantic ranking
- Skillset with document extraction, text chunking, and embedding generation  
- Data Source connected to Azure Blob Storage
- Indexer to orchestrate the enrichment pipeline

**Usage:**
```bash
# Deploy all components
python src/indexing/deploy_search_components.py --deploy-all

# Update individual components
python src/indexing/deploy_search_components.py --update-index
python src/indexing/deploy_search_components.py --update-skillset
python src/indexing/deploy_search_components.py --update-indexer
```

**Key Features:**
- Uses Azure AI Search SDK with API version 2025-09-01
- Managed identity authentication (no keys/secrets)
- Fixes common indexer issues:
  - Sets `imageAction: generateNormalizedImages` (enables document extraction)
  - Sets `allowSkillsetToReadFileData: True` (allows skillset to read PDFs)
  - Proper field mappings from enrichment tree

### 2. run_indexer_pipeline.py

Runs the indexer pipeline to process documents. Can be executed multiple times.

**Usage:**
```bash
# Run indexer and wait for completion
python src/indexing/run_indexer_pipeline.py

# Reset indexer before running (forces reprocessing ALL documents)
python src/indexing/run_indexer_pipeline.py --reset

# Run without waiting
python src/indexing/run_indexer_pipeline.py --no-wait

# Check status only
python src/indexing/run_indexer_pipeline.py --status-only

# Custom timeout
python src/indexing/run_indexer_pipeline.py --timeout 600
```

**When to reset:**
- Indexer shows "success" but processed 0 items (change tracking issue)
- After modifying skillset configuration
- Need to force complete reindexing

## Pipeline Architecture

### Skillset Flow

```
PDF Document (Blob Storage)
    ↓
DocumentExtractionSkill
    ├─→ Extracted Text (/document/extracted_content)
    └─→ Normalized Images
        ↓
TextSplitSkill (512 tokens, 100 overlap)
    ↓
Text Chunks (/document/pages/*/text)
    ↓
AzureOpenAIEmbeddingSkill (text-embedding-3-large)
    ↓
3072-dim Vector Embeddings (/document/pages/*/vector)
    ↓
Search Index (chunk_id, content, chunk_vector)
```

### Configuration

Default configuration in `deploy_search_components.py`:

```python
{
    "search_service_name": "srch-drvagnt2-dev-7vczbz",
    "index_name": "driving-manual-index",
    "skillset_name": "driving-manual-skillset",
    "datasource_name": "driving-manual-datasource",
    "indexer_name": "driving-manual-indexer",
    "storage_container": "pdfs",
    "embedding_deployment": "text-embedding-3-large",
    "embedding_dimensions": 3072,
    "chunk_size": 512,
    "chunk_overlap": 100
}
```

## Workflow

### Initial Setup

1. **Deploy infrastructure** (Bicep creates search service, storage, models):
```bash
cd infra/bicep
az deployment sub create --location eastus2 --template-file main.bicep --parameters parameters/dev.bicepparam
```

2. **Deploy search components** (Python SDK creates index, skillset, datasource, indexer):
```bash
python src/indexing/deploy_search_components.py --deploy-all
```

3. **Upload PDF documents** to blob storage:
```bash
az storage blob upload --account-name stdrvagd7vczbz --container-name pdfs --file data/manuals/Driving_MI.pdf --name Driving_MI.pdf --auth-mode login
```

4. **Run the indexer pipeline**:
```bash
python src/indexing/run_indexer_pipeline.py --reset
```

### Updating and Reprocessing

**After skillset changes:**
```bash
# Update the skillset
python src/indexing/deploy_search_components.py --update-skillset

# Reprocess all documents
python src/indexing/run_indexer_pipeline.py --reset
```

**After adding new documents:**
```bash
# Upload new PDFs
az storage blob upload --account-name stdrvagd7vczbz --container-name pdfs --file new_manual.pdf --name new_manual.pdf --auth-mode login

# Run indexer (processes only new/changed files)
python src/indexing/run_indexer_pipeline.py
```

## Troubleshooting

### Issue: Indexer shows success but processes 0 items

**Cause:** Change detection policy tracks `metadata_storage_last_modified`. If files haven't changed since the last run, they're skipped.

**Solution:**
```bash
python src/indexing/run_indexer_pipeline.py --reset
```

### Issue: DocumentExtractionSkill errors

**Common errors:**
- "Cannot read file data" → Missing `allowSkillsetToReadFileData: True`
- "Invalid file data" → Incorrect `imageAction` setting

**Solution:** Redeploy the indexer with fixed configuration:
```bash
python src/indexing/deploy_search_components.py --update-indexer
python src/indexing/run_indexer_pipeline.py --reset
```

### Issue: No embeddings generated

**Possible causes:**
- Azure OpenAI endpoint incorrect
- Embedding deployment name mismatch
- Missing "Cognitive Services User" role

**Check configuration:**
```python
python src/indexing/deploy_search_components.py --update-skillset
```

### Issue: Indexer timeout

**Solution:** Increase timeout or process in batches:
```bash
# Increase timeout to 10 minutes
python src/indexing/run_indexer_pipeline.py --timeout 600

# Or update indexer batch size
python src/indexing/deploy_search_components.py --update-indexer
```

## Other Scripts

### upload_documents.py
Uploads PDF documents from local directory to blob storage.

```bash
python src/indexing/upload_documents.py --directory data/manuals --container pdfs
```

### validate_indexer.py
Validates indexer execution and index health.

```bash
python src/indexing/validate_indexer.py --skillset-name driving-manual-skillset --indexer-name driving-manual-indexer
```

### monitor_skillset.py
Monitors skillset execution with detailed error reporting.

```bash
python src/indexing/monitor_skillset.py --skillset-name driving-manual-skillset
```

## Requirements

```bash
pip install azure-search-documents>=11.6.0 azure-identity>=1.12.0 azure-storage-blob>=12.0.0
```

Or install from project root:
```bash
pip install -r requirements.txt
```

## API Version

All scripts use **Azure AI Search API version 2025-09-01** which includes:
- Full vector search support
- Semantic ranking capabilities
- AzureOpenAIEmbeddingSkill with dimensions parameter
- Enhanced skillset execution monitoring

