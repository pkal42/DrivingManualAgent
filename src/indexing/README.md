# Indexing Pipeline

This directory contains Python scripts for managing Azure AI Search components and running the document indexing pipeline.

## Scripts

### 1. deploy_search_components.py

Creates and configures all Azure AI Search components using the Python SDK.

**Components Deployed:**
- **Search Index**: Hybrid search enabled (vector + keyword + semantic).
- **Skillset**: Defines the enrichment pipeline (Text Split, Azure OpenAI Embeddings, Image Analysis).
- **Data Source**: Connection to Azure Blob Storage `pdfs` container.
- **Indexer**: Orchestrates the data ingestion and enrichment process.

**Usage:**
```bash
# Deploy/Update all components
python src/indexing/deploy_search_components.py --deploy-all

# Update individual components
python src/indexing/deploy_search_components.py --update-index
python src/indexing/deploy_search_components.py --update-skillset
python src/indexing/deploy_search_components.py --update-indexer
```

### 2. trigger_indexer.py

Triggers the indexer execution and monitors its progress. This is the primary script for running the pipeline.

**Usage:**
```bash
# Trigger indexer and wait for completion
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait

# Trigger with custom timeout (seconds)
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait --timeout 3600
```

### 3. validate_enrichment.py

Validates the integrity and quality of the indexed data. Ensures documents were processed, chunks were created, and fields are populated correctly.

**Usage:**
```bash
# Validate all documents in the index
python src/indexing/validate_enrichment.py

# Validate a specific document
python src/indexing/validate_enrichment.py --document california-dmv-handbook-2024.pdf

# Generate validation reports
python src/indexing/validate_enrichment.py --json-output report.json --markdown-output report.md
```

### 4. monitor_skillset.py

Advanced debugging tool for inspecting skillset execution history and debugging specific documents using the Search Debug Sessions API.

**Usage:**
```bash
# Monitor recent indexer executions for errors
python src/indexing/monitor_skillset.py --indexer driving-manual-indexer

# Analyze specific skillset errors
python src/indexing/monitor_skillset.py --skillset driving-manual-skillset --show-errors
```

### 5. upload_documents.py

Utility to upload PDF manuals to Blob Storage with appropriate metadata.

**Usage:**
```bash
# Upload a single file
python src/indexing/upload_documents.py --file data/manuals/MI_DMV_2024.pdf --state Michigan --year 2024

# Batch upload
python src/indexing/upload_documents.py --directory data/manuals --recursive
```

### 6. generate_test_pdfs.py

Generates synthetic PDF documents for testing the pipeline without relying on external files.

**Usage:**
```bash
python src/indexing/generate_test_pdfs.py
```

## Configuration

Configuration is centralized in `src/indexing/config.py`. It loads settings from the environment variables (see `.env.example`) or uses default values.

**Key Configuration Parameters:**
- `AZURE_STORAGE_ACCOUNT`: Storage account name.
- `AZURE_SEARCH_ENDPOINT`: Search service endpoint.
- `AZURE_SEARCH_INDEX_NAME`: Default `driving-manual-index`.
- `AZURE_SEARCH_INDEXER_NAME`: Default `driving-manual-indexer`.
- `AZURE_SEARCH_SKILLSET_NAME`: Default `driving-manual-skillset`.


## Pipeline Architecture

```
PDF Document (Blob Storage)
    ↓
[Indexer] Document Cracking
    ├─→ Extracted Text (/document/content)
    └─→ Normalized Images (/document/normalized_images)
        ↓
[Skillset]
    │
    ├─→ SplitSkill (Page-based chunking)
    │     ↓
    │   Text Chunks (/document/pages/*)
    │
    ├─→ ImageAnalysisSkill (Captioning)
    │     ↓
    │   Image Descriptions
    │
    └─→ AzureOpenAIEmbeddingSkill (text-embedding-3-large)
          ↓
        3072-dim Vector Embeddings
    ↓
[Index Projections]
    ↓
Azure AI Search Index
(chunk_id, content, chunk_vector, image_blob_name, etc.)
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
python src/indexing/upload_documents.py --directory data/manuals --recursive
```

4. **Run the indexer pipeline**:
```bash
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait
```

### Updating and Reprocessing

**After skillset changes:**
```bash
# Update the skillset
python src/indexing/deploy_search_components.py --update-skillset

# Reset and reprocess all documents
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --reset --wait
```

**After adding new documents:**
```bash
# Upload new PDFs
python src/indexing/upload_documents.py --file new_manual.pdf --state "State" --year 2024

# Trigger indexer (processes only new/changed files)
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --wait
```

## Troubleshooting

### Issue: Indexer shows success but processes 0 items

**Cause:** Change detection policy tracks `metadata_storage_last_modified`. If files haven't changed since the last run, they're skipped.

**Solution:**
```bash
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --reset --wait
```

### Issue: DocumentExtractionSkill errors

**Common errors:**
- "Cannot read file data" → Missing `allowSkillsetToReadFileData: True`
- "Invalid file data" → Incorrect `imageAction` setting

**Solution:** Redeploy the indexer with fixed configuration:
```bash
python src/indexing/deploy_search_components.py --update-indexer
python src/indexing/trigger_indexer.py --indexer driving-manual-indexer --reset --wait
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

## Environment Setup

Before running any scripts, ensure your Python environment is configured:

```powershell
# Create virtual environment
python -m venv .venv

# Activate environment
.\.venv\Scripts\Activate.ps1    # Windows
# source .venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

