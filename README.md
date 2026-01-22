# DrivingManualAgent

Multimodal RAG agent using Azure AI Agent Framework v2 for answering questions from state driving manuals with text citations and relevant images.

## Overview

This project implements an intelligent agent that can answer questions about state driving laws and regulations by:
- Extracting text and images from PDF driving manuals using Azure AI Search native text extraction
- Creating searchable embeddings for semantic search
- Providing accurate answers with citations and relevant images
- Supporting multiple US states with hybrid search capabilities

## Architecture

### Components

1. **Python Indexing Pipeline** (`src/indexing/`)
   - Azure AI Search native indexer for PDF text and image extraction
   - Character-based text chunking (1000 chars, 200 overlap)
   - Azure OpenAI for vector embeddings (text-embedding-3-large, 3072 dimensions)
   - Hybrid search index (keyword + vector + semantic) via Azure AI Search
   - Managed identity authentication throughout
   - Currently tested with Michigan DMV 2024 manual (286 chunks indexed)

2. **Agent Framework** (`src/agent/`) - *Coming soon*
   - Azure AI Agent Framework v2 implementation
   - Multimodal response generation with GPT-4o
   - Citation tracking and image inclusion

3. **Infrastructure as Code** (`infra/bicep/`)
   - Modular Bicep templates with comprehensive comments
   - Azure AI Search, Storage, and Foundry (Azure OpenAI) resources
   - Managed identity authentication (no keys)
   - RBAC-based security model

## Infrastructure Deployment (Bicep)

Execute the Bicep templates in this order to provision the Azure resources:

1. Authenticate and set defaults

   ```powershell
   az login
   az account set --subscription <subscription-id>
   cd infra/bicep
   ```
2. Validate templates locally to catch syntax errors early

   ```powershell
   az bicep build --file main.bicep
   az bicep build --file modules/search-skillset.bicep
   az bicep build --file modules/search-index.bicep
   az bicep build --file modules/search-datasource.bicep
   az bicep build --file modules/search-indexer.bicep
   ```
3. Preview the subscription-level deployment (optional but recommended)

   ```powershell
   az deployment sub what-if `
     --location eastus2 `
     --template-file main.bicep `
     --parameters parameters/dev.bicepparam
   ```
4. Deploy the full environment with the main orchestrator (assign a deployment name so you can reuse its outputs)

   ```powershell
   az deployment sub create `
     --location eastus2 `
     --name driving-manual-main `
     --template-file main.bicep `
     --parameters parameters/dev.bicepparam
   ```
5. Retrieve the resource group created by the main deployment (you will use it in subsequent commands)

   ```powershell
   az deployment sub show `
     --name driving-manual-main `
     --query properties.outputs.resourceGroupName.value -o tsv
   ```
6. Deploy the search components (index, skillset, datasource, indexer) using the PowerShell script

   ```powershell
   # Get the search service name from deployment outputs
   $searchService = az deployment sub show `
     --name driving-manual-main `
     --query properties.outputs.searchServiceName.value -o tsv

   # Deploy all search components via REST API
   .\ deploy-search-components.ps1 -SearchServiceName $searchService
   ```

   This script uses Azure Search REST API to deploy:
   - **Index**: `driving-manual-index` with vector search and semantic ranking
   - **Skillset**: Document extraction, text splitting, and embedding generation
   - **Data Source**: Blob storage connection with managed identity
   - **Indexer**: Orchestrates the enrichment pipeline
7. Upload PDF documents to blob storage for indexing

   ```powershell
   # Get the storage account name from deployment outputs
   $storageAccount = az deployment sub show `
     --name driving-manual-main `
     --query properties.outputs.storageAccountName.value -o tsv

   # Upload PDFs from local directory
   az storage blob upload-batch `
     -d pdfs `
     -s data/manuals `
     --account-name $storageAccount `
     --auth-mode login
   ```

   The indexer will automatically process uploaded documents through the enrichment pipeline.

## Quick Start

### Prerequisites

- Azure subscription
- Python 3.9+
- Azure CLI (authenticated with `az login`)
- Deployed Azure infrastructure (see Infrastructure Guide)

### 1. Install Dependencies

```powershell
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install required packages
pip install -r ../../requirements.txt
```

### 2. Upload PDFs to Blob Storage

Upload driving manual PDFs to the Azure Blob Storage container:

```powershell
az storage blob upload-batch `
  -d pdfs `
  -s data/manuals `
  --account-name <storage-account> `
  --auth-mode login
```

### 3. Run Python Indexing Pipeline

The indexing pipeline processes PDFs using Azure AI Search native indexer with integrated vectorization:

```powershell
# Manually trigger the indexer
cd src/indexing
python trigger_indexer.py --indexer driving-manual-indexer --wait
```

The pipeline will:
1. Detect new PDFs in the blob storage container
2. Extract text using native PDF parsing (with SplitSkill for chunking)
3. Generate embeddings using Azure OpenAI (text-embedding-3-large)
4. Populate the Azure AI Search index automatically

### 4. Verify Indexing

Check that documents were successfully indexed:

```powershell
# Query the search index
az search index show-statistics `
  --index-name driving-manual-index `
  --service-name <search-service> `
  --resource-group <rg-name>
```

## Repository Structure

```
.
├── config/                   # Configuration profiles (for future agent)
│   ├── base-config.json              # Base configuration (balanced)
│   ├── cost-optimized.json           # Cost-optimized profile
│   ├── performance-optimized.json    # Performance-optimized profile
│   └── agent-instructions.txt        # Agent system prompt
├── infra/bicep/              # Infrastructure as Code
│   ├── main.bicep                    # Main orchestration template
│   ├── parameters/                   # Environment-specific parameters
│   └── modules/                      # Bicep modules
│       ├── ai-search.bicep           # Azure AI Search service
│       ├── foundry-project.bicep     # AI Foundry project (Azure OpenAI)
│       ├── model-deployments.bicep   # Model deployments
│       ├── storage.bicep             # Blob storage for PDFs
│       └── role-assignments.bicep    # RBAC configurations
├── src/
│   ├── indexing/             # Python indexing pipeline
│   │   ├── trigger_indexer.py       # Indexer trigger script
│   │   ├── deploy_search_components.py # Indexer setup script
│   │   ├── generate_test_pdfs.py    # Test PDF generator
│   │   └── .venv/                   # Python virtual environment
│   └── agent/                # Agent implementation (coming soon)
│       ├── config_loader.py         # Hierarchical configuration
│       └── ...                      # Other agent modules
├── scripts/                  # Automation scripts
│   └── validate_config.py           # Configuration validation
├── docs/                     # Documentation
│   ├── configuration-guide.md       # Configuration reference
│   └── ...                          # Other documentation
├── data/manuals/             # Sample PDF driving manuals
│   └── MI_DMV_2024.pdf              # Michigan DMV 2024 manual (indexed)
├── tests/                    # Unit and integration tests
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
└── README.md                 # This file
```

## Features

### Indexing Pipeline (Completed)

- ✅ Python-based setup pipeline using Azure SDK
- ✅ Azure AI Search Indexer for text extraction (native PDF support)
- ✅ Page-based text chunking (SplitSkill)
- ✅ Vector embeddings with Azure OpenAI text-embedding-3-large (3072 dimensions)
- ✅ Hybrid search index (keyword + vector + semantic) via Azure AI Search (API 2024-07-01)
- ✅ Figure caption extraction from images
- ✅ Managed identity authentication (DefaultAzureCredential)
- ✅ Comprehensive Bicep templates with inline comments
- ✅ Successfully tested with Michigan DMV 2024 manual (286 chunks indexed)

### Configuration System (For Future Agent)

- ✅ Hierarchical configuration with JSON profiles
- ✅ Pydantic-based type-safe validation
- ✅ Environment variable overrides
- ✅ Multiple deployment profiles (cost-optimized, performance-optimized)
- ✅ Comprehensive validation script

### Coming Soon

- 🔄 Agent Framework v2 implementation
- 🔄 Multimodal response generation
- 🔄 Citation tracking
- 🔄 GitHub Actions CI/CD for automated indexing
- 🔄 Deployment to Azure Container Apps Jobs

## Documentation

- [Indexer Pipeline Guide](src/indexing/README.md) - Detailed indexing documentation
- [Bicep Templates Guide](infra/bicep/README.md) - Infrastructure deployment guide
- [Configuration Guide](docs/configuration-guide.md) - Agent configuration reference (for future agent)

## Roadmap

- [x] Azure infrastructure deployment (Storage, Search, Foundry)
- [x] Automated Azure AI Search Indexer setup code
- [x] Character-based chunking and embedding generation
- [x] Successfully indexed Michigan DMV 2024 manual
- [ ] GitHub Actions workflow for automated indexing
- [ ] Deployment to Azure Container Apps Jobs
- [ ] Azure AI Agent Framework v2 implementation
- [ ] Multimodal response generation with citations
- [ ] Support for additional state driving manuals
- [ ] Web UI for agent interaction

## Development

### Running the Indexing Pipeline

```powershell
# Activate virtual environment
cd src/indexing
.venv\Scripts\Activate.ps1

# Run indexing for all PDFs in blob storage
python trigger_indexer.py --indexer driving-manual-indexer --wait
```

The script will:
1. Connect to Azure AI Search using managed identity
2. Trigger the indexer to process any new PDFs in the 'pdfs' container
3. Monitor the execution status
4. Report total documents processed and any errors

### Configuration

Configuration is managed via `config.py` and infrastructure parameters.
- `src/indexing/config.py`: Indexer and skillset configuration
- `infra/bicep/parameters/`: Infrastructure deployment parameters

### Generating Sample PDFs

```powershell
cd src/indexing
python generate_test_pdfs.py --output-dir ../../data/manuals
```

## Security

All Azure resources use managed identity for authentication:
- No connection strings or access keys in code
- RBAC-based access control (least privilege)
- DefaultAzureCredential for local development and Azure deployments

Required RBAC roles:
- **User/Service Principal**:
  - Storage Blob Data Contributor (for uploading PDFs)
  - Storage Blob Data Reader (for reading PDFs)
  - Search Index Data Contributor (for uploading search documents)
- **Search Service Managed Identity**:
  - Storage Blob Data Reader (for reading PDFs during indexing)
- **Azure OpenAI** (Foundry):
  - Accessed via managed identity authentication (no API keys)
  - `disableLocalAuth=true` enforced for security

## Contributing

This project follows best practices for Azure AI development:
- Comprehensive inline comments in all Bicep templates and Python code
- Type hints and docstrings in Python code
- Managed identity for all Azure authentication
- Modular, reusable infrastructure components
- Stable API versions (e.g., Search API 2024-07-01)

### Development Workflow

1. Create a feature branch
2. Make your changes
3. Test locally using Azure CLI authentication
4. Ensure code follows existing patterns and style
5. Submit a pull request

## Related Issues

- [Issue #1: Repository Structure and IaC Foundation](https://github.com/pkal42/DrivingManualAgent/issues/1)
- [Issue #2: Azure AI Search Indexer Pipeline Setup](https://github.com/pkal42/DrivingManualAgent/issues/2)

## License

MIT License - See LICENSE file for details

