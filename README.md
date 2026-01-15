# DrivingManualAgent

Multimodal RAG agent using Azure AI Agent Framework v2 for answering questions from state driving manuals with text citations and relevant images.

## Overview

This project implements an intelligent agent that can answer questions about state driving laws and regulations by:
- Extracting text and images from PDF driving manuals
- Creating searchable embeddings for semantic search
- Providing accurate answers with citations and relevant images
- Supporting multiple US states with hybrid search capabilities

## Architecture

### Components

1. **Azure AI Search Indexer Pipeline** (`src/indexing/`)
   - DocumentExtractionSkill for PDF text and image extraction
   - TextSplitSkill for token-based chunking (512 tokens, 100 overlap)
   - AzureOpenAIEmbeddingSkill for vector embeddings (text-embedding-3-large)
   - Hybrid search index (keyword + vector + semantic)

2. **Agent Framework** (`src/agent/`) - *Coming soon*
   - Azure AI Agent Framework v2 implementation
   - Multimodal response generation with GPT-4o
   - Citation tracking and image inclusion

3. **Infrastructure as Code** (`infra/bicep/`)
   - Modular Bicep templates with comprehensive comments
   - Managed identity authentication (no keys)
   - RBAC-based security model

## Quick Start

### Prerequisites

- Azure subscription
- Python 3.9+
- Azure CLI

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Deploy Infrastructure

See [Infrastructure Guide](infra/bicep/README.md) for detailed deployment instructions.

### 3. Generate Test PDFs

```bash
cd src/indexing
python generate_test_pdfs.py --output-dir ../../data/manuals
```

### 4. Upload to Blob Storage

```bash
az storage blob upload-batch \
  -d pdfs \
  -s data/manuals \
  --account-name <storage-account> \
  --auth-mode login
```

### 5. Run Indexer

```bash
az search indexer run \
  --name driving-manual-indexer \
  --service-name <search-service> \
  --resource-group <rg-name>
```

### 6. Validate Pipeline

```bash
cd src/indexing
export AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
python validate_indexer.py
```

## Repository Structure

```
.
├── infra/bicep/              # Infrastructure as Code
│   └── modules/              # Bicep modules
│       ├── search-skillset.bicep    # Skillset definition
│       ├── search-index.bicep       # Index schema
│       ├── search-datasource.bicep  # Blob data source
│       └── search-indexer.bicep     # Indexer orchestration
├── src/
│   ├── indexing/             # Indexer pipeline tools
│   │   ├── validate_indexer.py      # Pipeline validation
│   │   ├── generate_test_pdfs.py    # Test PDF generator
│   │   └── README.md                # Indexing documentation
│   └── agent/                # Agent implementation (coming soon)
├── data/manuals/             # Sample PDF driving manuals
├── tests/                    # Unit and integration tests
└── README.md                 # This file
```

## Features

### Indexer Pipeline

- ✅ PDF text and image extraction with DocumentExtractionSkill
- ✅ Token-based text chunking (512 tokens, 100 overlap)
- ✅ Vector embeddings with text-embedding-3-large (3072-dim)
- ✅ Hybrid search (keyword + vector + semantic)
- ✅ Image extraction and storage
- ✅ Managed identity authentication
- ✅ Comprehensive Bicep templates with inline comments

### Coming Soon

- 🔄 Agent Framework v2 implementation
- 🔄 Multimodal response generation
- 🔄 Citation tracking
- 🔄 GitHub Actions CI/CD
- 🔄 Production deployment workflows

## Documentation

- [Indexer Pipeline Guide](src/indexing/README.md) - Detailed indexer documentation
- [Bicep Templates Guide](infra/bicep/README.md) - Infrastructure deployment guide
- [Configuration Guide](docs/configuration-guide.md) - Configuration options (coming soon)
DrivingManualAgent is an intelligent agent system that leverages Azure AI services to provide accurate, context-aware answers from state driving manuals. The system uses:

- **Azure AI Agent Framework v2** for agent orchestration
- **Azure AI Search** with vector and semantic search capabilities
- **GPT-4o** for multimodal understanding (text and images)
- **Text-embedding-3-large** for document embeddings
- **Azure Blob Storage** for document and image storage

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Query (Natural Language)               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Azure AI Agent Framework v2                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Agent Orchestration (gpt-4o)                            │  │
│  │  - Query understanding                                   │  │
│  │  - Tool selection and execution                          │  │
│  │  - Response generation with citations                    │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬─────────────────────────────────────┬───────────────┘
            │                                     │
            ▼                                     ▼
┌───────────────────────────┐      ┌────────────────────────────┐
│   Azure AI Search         │      │   Azure Blob Storage       │
│   - Vector Search         │      │   - Source PDFs            │
│   - Semantic Ranking      │      │   - Extracted Images       │
│   - Hybrid Search         │      │   - Document Metadata      │
└───────────────────────────┘      └────────────────────────────┘
            │                                     │
            └─────────────┬───────────────────────┘
                          ▼
              ┌───────────────────────┐
              │  Indexing Pipeline    │
              │  - PDF Processing     │
              │  - Image Extraction   │
              │  - Chunking           │
              │  - Embedding          │
              └───────────────────────┘
```

## Project Structure

```
DrivingManualAgent/
├── src/
│   ├── agent/              # Azure AI Agent Framework v2 implementation
│   │   ├── __init__.py
│   │   └── driving_agent.py
│   └── indexing/           # Azure AI Search indexer pipeline
│       ├── __init__.py
│       └── document_indexer.py
├── tests/                  # Unit and integration tests
│   ├── test_agent.py
│   └── test_indexing.py
├── infra/
│   └── bicep/              # Infrastructure as Code
│       ├── main.bicep
│       ├── modules/
│       │   ├── foundry-project.bicep
│       │   ├── model-deployments.bicep
│       │   ├── ai-search.bicep
│       │   ├── storage.bicep
│       │   └── role-assignments.bicep
│       └── parameters/
│           ├── dev.bicepparam
│           └── prod.bicepparam
├── data/
│   └── manuals/            # Sample driving manuals (PDFs)
├── .github/
│   └── workflows/
│       └── deploy-infrastructure.yml
├── .gitignore
├── requirements.txt
└── README.md
```

## Prerequisites

- **Azure Subscription** with appropriate permissions
- **Azure CLI** (v2.50.0 or later)
- **Python** 3.10 or later
- **Git**

## Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/pkal42/DrivingManualAgent.git
cd DrivingManualAgent
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Azure OIDC for GitHub Actions

To enable secure, secret-less deployments from GitHub Actions, set up OIDC workload identity federation:

#### Step 1: Create Azure AD Application

```bash
az ad app create --display-name "DrivingManualAgent-GitHub-OIDC"
```

Note the `appId` from the output.

#### Step 2: Create Service Principal

```bash
az ad sp create --id <appId>
```

#### Step 3: Configure Federated Credentials

For the **dev** environment:
```bash
az ad app federated-credential create \
  --id <appId> \
  --parameters '{
    "name": "DrivingManualAgent-Dev",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:pkal42/DrivingManualAgent:environment:dev",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

For the **prod** environment:
```bash
az ad app federated-credential create \
  --id <appId> \
  --parameters '{
    "name": "DrivingManualAgent-Prod",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:pkal42/DrivingManualAgent:environment:prod",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

#### Step 4: Assign Permissions

```bash
# Get your subscription ID
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Assign Contributor role to the service principal
az role assignment create \
  --assignee <appId> \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID
```

#### Step 5: Configure GitHub Secrets

Add the following secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `AZURE_CLIENT_ID`: The `appId` from Step 1
- `AZURE_TENANT_ID`: Your Azure AD tenant ID
- `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID

### 4. Deploy Infrastructure

#### Using GitHub Actions (Recommended)

1. Go to **Actions** tab in GitHub
2. Select **Deploy Infrastructure** workflow
3. Click **Run workflow**
4. Select environment: `dev` or `prod`
5. Click **Run workflow**

#### Manual Deployment

For development environment:
```bash
cd infra/bicep
az deployment sub create \
  --location eastus \
  --template-file main.bicep \
  --parameters parameters/dev.bicepparam
```

For production environment:
```bash
cd infra/bicep
az deployment sub create \
  --location eastus \
  --template-file main.bicep \
  --parameters parameters/prod.bicepparam
```

### 5. Upload Sample Documents

```bash
# Set environment variables
STORAGE_ACCOUNT_NAME="<your-storage-account-name>"
RESOURCE_GROUP="<your-resource-group>"

# Upload PDFs to the storage account
az storage blob upload-batch \
  --account-name $STORAGE_ACCOUNT_NAME \
  --destination pdfs \
  --source data/manuals \
  --auth-mode login
```

### 6. Run the Indexing Pipeline

```bash
python -m src.indexing.document_indexer
```

### 7. Test the Agent

```bash
python -m src.agent.driving_agent
```

## Development

### Running Tests

```bash
# Install test dependencies
pip install -r requirements.txt

# Run validation
cd src/indexing
python validate_indexer.py --help
```

### Generating Sample PDFs

The project includes a script to generate realistic sample driving manual PDFs:

```bash
cd src/indexing
python generate_test_pdfs.py --output-dir ../../data/manuals
```

This creates:
- `california-dmv-handbook-2024.pdf` (3 pages)
- `texas-driver-handbook-2024.pdf` (3 pages)

## Security

All Azure resources use managed identity for authentication:
- No connection strings or access keys in code
- RBAC-based access control
- Principle of least privilege

Required RBAC roles:
- Search service → Storage: "Storage Blob Data Contributor"
- Search service → Azure OpenAI: "Cognitive Services User"
- Application → Search: "Search Index Data Contributor"

## Contributing

This project follows best practices for Azure AI development:
- Comprehensive inline comments in all Bicep templates
- Type hints and docstrings in Python code
- Validation scripts for testing
- Modular, reusable infrastructure components

## License

MIT License - See LICENSE file for details

## Related Issues

- [Issue #1: Repository Structure and IaC Foundation](https://github.com/pkal42/DrivingManualAgent/issues/1)
- [Issue #2: Azure AI Search Indexer Pipeline Setup](https://github.com/pkal42/DrivingManualAgent/issues/2)
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_agent.py
```

### Code Style

This project follows PEP 8 style guidelines. Format code using:

```bash
# Install development dependencies
pip install black flake8 mypy

# Format code
black src/ tests/

# Check linting
flake8 src/ tests/

# Type checking
mypy src/
```

## Key Features

- **Multimodal Understanding**: Processes both text and images from driving manuals
- **Accurate Citations**: Provides source references for all answers
- **Semantic Search**: Uses Azure AI Search for intelligent document retrieval
- **Scalable Architecture**: Modular design for easy extension
- **Observability**: Built-in telemetry and monitoring with Azure Monitor
- **Infrastructure as Code**: Fully automated deployment with Bicep
- **Secure by Default**: Managed identities and RBAC for least-privilege access

## Security

- All Azure resources use **Managed Identity** for authentication
- **RBAC** assignments follow the principle of least privilege
- No secrets or connection strings in code
- **OIDC** for GitHub Actions (no stored credentials)

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError` when running Python scripts
- **Solution**: Ensure virtual environment is activated and dependencies are installed

**Issue**: Bicep deployment fails with permission errors
- **Solution**: Verify service principal has Contributor role on subscription

**Issue**: GitHub Actions deployment fails
- **Solution**: Check OIDC federated credentials are configured correctly

**Issue**: Search returns no results
- **Solution**: Verify indexing pipeline ran successfully and documents were uploaded

## Contributing

1. Create a feature branch
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
- Create an issue in the GitHub repository
- Contact the maintainers

## Roadmap

- [ ] Support for multiple state driving manuals
- [ ] Web UI for agent interaction
- [ ] Advanced citation formatting
- [ ] Multi-language support
- [ ] Conversation history and context retention
