# Azure AI Search Indexer Pipeline

This module implements the Azure AI Search skillset-based indexer pipeline for processing PDF driving manuals with text extraction, chunking, embedding generation, and hybrid search capabilities.

## Overview

The indexer pipeline processes PDF driving manuals through the following stages:

1. **Document Extraction** - Extract text and images from PDFs using DocumentExtractionSkill
2. **Text Chunking** - Split text into 512-token chunks with 100-token overlap using TextSplitSkill
3. **Embedding Generation** - Generate 3072-dimensional embeddings using text-embedding-3-large
4. **Image Processing** (Optional) - Generate descriptions and embeddings for extracted images
5. **Indexing** - Store enriched content in hybrid search index (keyword + vector + semantic)

## Architecture

### Skillset Pipeline

```
PDF Document (Blob Storage)
    ↓
DocumentExtractionSkill
    ├─→ Extracted Text
    └─→ Normalized Images (2000x2000px)
        ↓
TextSplitSkill (512 tokens, 100 overlap)
    ↓
Text Chunks (azureOpenAITokens, cl100k_base)
    ↓
AzureOpenAIEmbeddingSkill (text-embedding-3-large)
    ↓
3072-dim Vector Embeddings
    ↓
Search Index (Hybrid: Keyword + Vector + Semantic)
```

### Search Index Schema

| Field | Type | Purpose | Searchable | Filterable |
|-------|------|---------|------------|------------|
| `chunk_id` | String | Unique identifier | No | Yes |
| `content` | String | Text content | Yes | No |
| `chunk_vector` | Collection(Single) | 3072-dim embedding | Yes (vector) | No |
| `document_id` | String | Source document | Yes | Yes |
| `state` | String | US state | No | Yes |
| `page_number` | Int32 | Page reference | No | Yes |
| `has_related_images` | Boolean | Image flag | No | Yes |
| `image_blob_urls` | Collection(String) | Image URLs | No | No |
| `image_descriptions` | Collection(String) | Image descriptions | Yes | No |
| `metadata_storage_name` | String | Filename | Yes | Yes |

## Infrastructure as Code (Bicep)

### Modules

All Bicep modules are located in `infra/bicep/modules/` with comprehensive inline comments:

#### 1. search-skillset.bicep
Defines the enrichment pipeline with:
- **DocumentExtractionSkill**: PDF text and image extraction
  - Parsing mode: `default` for PDFs
  - Image normalization: 2000x2000px
  - Data extraction: `contentAndMetadata`
- **TextSplitSkill**: Token-based chunking
  - Unit: `azureOpenAITokens` (accurate token counting)
  - Max length: 512 tokens
  - Overlap: 100 tokens
  - Tokenizer: `cl100k_base` (for text-embedding-3-large)
- **AzureOpenAIEmbeddingSkill**: Embedding generation
  - Model: text-embedding-3-large
  - Dimensions: 3072
- **Image Description Skill** (Optional): GPT-4o vision descriptions

**Parameters:**
- `searchServiceName`: Azure AI Search service name
- `openAiEndpoint`: Azure OpenAI endpoint URL
- `embeddingDeploymentName`: Embedding model deployment name
- `visionDeploymentName`: Vision model deployment name (for image descriptions)
- `enableImageDescriptions`: Enable/disable image description skill

#### 2. search-index.bicep
Defines the hybrid search index with:
- **Vector Search**: HNSW algorithm (m=4, efConstruction=400)
- **Semantic Search**: AI-powered reranking (optional)
- **Field Schema**: Complete schema with all required fields

**Parameters:**
- `searchServiceName`: Azure AI Search service name
- `indexName`: Name for the search index
- `vectorDimensions`: Embedding dimensions (default: 3072)
- `enableSemanticSearch`: Enable semantic search configuration

#### 3. search-datasource.bicep
Configures blob storage data source with:
- **Managed Identity**: No connection strings or keys
- **Change Detection**: Incremental indexing via LastModified
- **Soft Delete Detection**: Automatic cleanup via metadata flag

**Parameters:**
- `searchServiceName`: Azure AI Search service name
- `storageAccountName`: Storage account name
- `containerName`: Blob container name (default: `pdfs`)
- `enableChangeDetection`: Enable incremental indexing
- `enableSoftDelete`: Enable soft delete detection

#### 4. search-indexer.bicep
Orchestrates the indexer execution with:
- **Data Flow**: Data source → Skillset → Index
- **Field Mappings**: Blob metadata → Index fields
- **Output Field Mappings**: Enrichment tree → Index fields
- **Error Handling**: Continue on errors, log to Application Insights

**Parameters:**
- `searchServiceName`: Azure AI Search service name
- `dataSourceName`: Data source name
- `skillsetName`: Skillset name
- `indexName`: Target index name
- `schedule`: Cron expression for scheduled runs (empty = on-demand)
- `batchSize`: Number of documents per batch (default: 10)

### Deployment

```bash
# Deploy all indexer components
az deployment group create \
  --resource-group <rg-name> \
  --template-file infra/bicep/modules/search-skillset.bicep \
  --parameters searchServiceName=<search-service> \
               openAiEndpoint=<openai-endpoint> \
               embeddingDeploymentName=text-embedding-3-large \
               visionDeploymentName=gpt-4o

az deployment group create \
  --resource-group <rg-name> \
  --template-file infra/bicep/modules/search-index.bicep \
  --parameters searchServiceName=<search-service> \
               indexName=driving-manual-index

az deployment group create \
  --resource-group <rg-name> \
  --template-file infra/bicep/modules/search-datasource.bicep \
  --parameters searchServiceName=<search-service> \
               storageAccountName=<storage-account> \
               containerName=pdfs

az deployment group create \
  --resource-group <rg-name> \
  --template-file infra/bicep/modules/search-indexer.bicep \
  --parameters searchServiceName=<search-service> \
               dataSourceName=driving-manual-datasource \
               skillsetName=driving-manual-skillset \
               indexName=driving-manual-index
```

## Testing

### 1. Generate Sample PDFs

Create test driving manual PDFs:

```bash
cd src/indexing
pip install reportlab Pillow
python generate_test_pdfs.py --output-dir ../../data/manuals
```

This generates:
- `california-dmv-handbook-2024.pdf` (3 pages)
- `texas-driver-handbook-2024.pdf` (3 pages)

### 2. Upload to Blob Storage

```bash
az storage blob upload-batch \
  -d pdfs \
  -s data/manuals \
  --account-name <storage-account> \
  --auth-mode login
```

### 3. Run Indexer

Trigger manual indexer run:

```bash
az search indexer run \
  --name driving-manual-indexer \
  --service-name <search-service> \
  --resource-group <rg-name>
```

### 4. Validate Pipeline

Run validation script to check:
- Skillset execution status
- Image extraction count
- Chunk count and token distribution
- Embedding dimensions
- Index field population

```bash
cd src/indexing
pip install azure-search-documents azure-identity python-dotenv

# Using managed identity
export AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
export AZURE_SEARCH_INDEX_NAME=driving-manual-index

python validate_indexer.py \
  --skillset-name driving-manual-skillset \
  --indexer-name driving-manual-indexer

# Or using API key
python validate_indexer.py \
  --search-endpoint https://<search-service>.search.windows.net \
  --index-name driving-manual-index \
  --api-key <api-key>
```

### 5. Debug Sessions API

Use Azure Portal Debug Sessions for troubleshooting:

1. Navigate to Azure AI Search service in Portal
2. Go to "Debug sessions" under Search management
3. Select the indexer to debug
4. Examine the enrichment tree and skill outputs
5. Test skill configuration changes in real-time

## Configuration Details

### Chunking Strategy

**Token-based chunking** (512 tokens, 100 overlap):
- **Why 512 tokens?** Balances retrieval precision with context
  - Smaller chunks = more precise retrieval but less context
  - Larger chunks = more context but less precise
  - 512 is optimal for most Q&A scenarios
- **Why 100-token overlap?** Prevents information loss at chunk boundaries
  - ~20% overlap is standard
  - Ensures no context is lost when content spans chunks

**Tokenizer: cl100k_base**
- Must match embedding model's tokenizer (text-embedding-3-large)
- Accurate token counting prevents exceeding model limits (8191 tokens)

### Embedding Model

**text-embedding-3-large (3072 dimensions)**:
- State-of-the-art retrieval quality
- Better than text-embedding-ada-002 (1536-dim)
- Trade-off: Higher storage/compute cost vs quality

**Alternative: text-embedding-3-small**
- 1536 dimensions
- Lower cost, faster inference
- Slightly lower quality

### Vector Search Configuration

**HNSW Algorithm Parameters:**
- `m=4`: Bi-directional links per node (standard)
- `efConstruction=400`: Index build quality (high quality)
- `efSearch=500`: Query-time recall (high accuracy)
- `metric=cosine`: Angle-based similarity for embeddings

**Trade-offs:**
- Higher m = Better recall, more memory
- Higher efConstruction = Better graph quality, slower indexing
- Higher efSearch = Better recall, slower queries

### Image Extraction

**DocumentExtractionSkill Configuration:**
- `imageAction: generateNormalizedImages`
- `normalizedImageMaxWidth/Height: 2000px`

**Why 2000px?**
- GPT-4o vision supports up to 2048px
- Higher resolution = better quality but more tokens/storage
- 2000px balances quality with cost

**Image Storage:**
- Knowledge store projects images to blob storage
- Unique blob names: `{document-id}/{page-number}/{image-index}.jpg`
- Container: `extracted-images`

### Error Handling

**Indexer Configuration:**
- `maxFailedItems: 0` - Fail on first error (development)
- `maxFailedItemsPerBatch: 0` - Strict error handling
- `failOnUnsupportedContentType: false` - Continue on unsupported files
- `failOnUnprocessableDocument: false` - Continue on corrupted files

**Best Practices:**
- Development: Strict (fail on errors) to catch issues early
- Production: Resilient (continue on errors) for reliability

## Troubleshooting

### Common Issues

**1. Indexer fails with "Cannot read file data"**
- Ensure `allowSkillsetToReadFileData: true` in indexer
- Verify search service has "Storage Blob Data Reader" role on storage account

**2. No images extracted**
- Check `imageAction: generateNormalizedImages` in DocumentExtractionSkill
- Verify PDFs contain images (not just text)
- Review indexer execution history for skill errors

**3. Embeddings not generated**
- Verify Azure OpenAI deployment is active
- Check endpoint URL and deployment name
- Ensure search service has "Cognitive Services User" role

**4. Chunks too large or too small**
- Adjust `maximumPageLength` in TextSplitSkill (default: 512)
- Verify `unit: azureOpenAITokens` for accurate counting
- Check `encoderModelName: cl100k_base` matches embedding model

**5. Change detection not working**
- Ensure storage account has LastModified metadata enabled
- Verify `dataChangeDetectionPolicy` is configured
- Check search service has "Storage Blob Data Contributor" role

### Monitoring

**Indexer Execution History:**
```bash
az search indexer status \
  --name driving-manual-indexer \
  --service-name <search-service> \
  --resource-group <rg-name>
```

**Skill Execution Metrics:**
- View in Azure Portal → Search Service → Indexers → Execution History
- Check for errors, warnings, and processing times
- Use Debug Sessions for detailed skill output inspection

## Security

### Managed Identity Authentication

All connections use managed identity (no keys):
- **Storage Access**: Search service → Blob Storage
  - Role: "Storage Blob Data Reader" (or "Contributor" for change detection)
- **Azure OpenAI**: Search service → Azure OpenAI
  - Role: "Cognitive Services User"
- **Search Index**: Application → Search Service
  - Role: "Search Index Data Contributor"

### RBAC Configuration

```bash
# Grant search service access to storage
az role assignment create \
  --assignee <search-service-principal-id> \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<storage>

# Grant search service access to Azure OpenAI
az role assignment create \
  --assignee <search-service-principal-id> \
  --role "Cognitive Services User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<openai>
```

## Next Steps

1. **Deploy infrastructure** using Bicep templates
2. **Generate test PDFs** with `generate_test_pdfs.py`
3. **Upload PDFs** to blob storage
4. **Run indexer** manually or via schedule
5. **Validate results** with `validate_indexer.py`
6. **Integrate with agent** for multimodal RAG queries

## References

- [Azure AI Search Documentation](https://learn.microsoft.com/azure/search/)
- [Document Extraction Skill](https://learn.microsoft.com/azure/search/cognitive-search-skill-document-extraction)
- [Text Split Skill](https://learn.microsoft.com/azure/search/cognitive-search-skill-textsplit)
- [Azure OpenAI Embedding Skill](https://learn.microsoft.com/azure/search/cognitive-search-skill-azure-openai-embedding)
- [HNSW Vector Search](https://learn.microsoft.com/azure/search/vector-search-ranking)
- [Debug Sessions](https://learn.microsoft.com/azure/search/cognitive-search-debug-session)
