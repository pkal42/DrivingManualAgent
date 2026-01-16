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

### 2. Configure the Agent

The agent uses hierarchical configuration with profiles for different use cases.

#### Set Required Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit .env and set required values:
# - AZURE_AI_PROJECT_ENDPOINT
# - AZURE_SEARCH_ENDPOINT
```

#### Choose a Configuration Profile

**Base (default)**: Balanced cost and quality
```bash
export CONFIG_PROFILE=base
```

**Cost-Optimized**: ~70-80% cost reduction
```bash
export CONFIG_PROFILE=cost-optimized
```

**Performance-Optimized**: Maximum quality (~2-3x cost)
```bash
export CONFIG_PROFILE=performance-optimized
```

#### Validate Configuration

```bash
# Test configuration loading
python src/agent/config_loader.py

# Validate all profiles
python scripts/validate_config.py --all
```

See [Configuration Guide](docs/configuration-guide.md) for detailed configuration options.

### 3. Deploy Infrastructure

See [Infrastructure Guide](infra/bicep/README.md) for detailed deployment instructions.

### 4. Generate Test PDFs

```bash
cd src/indexing
python generate_test_pdfs.py --output-dir ../../data/manuals
```

### 5. Upload to Blob Storage

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
├── config/                   # Configuration profiles
│   ├── base-config.json              # Base configuration (balanced)
│   ├── cost-optimized.json           # Cost-optimized profile
│   ├── performance-optimized.json    # Performance-optimized profile
│   └── agent-instructions.txt        # Agent system prompt
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
│   └── agent/                # Agent implementation
│       ├── config_loader.py         # Hierarchical configuration
│       ├── agent_factory.py         # Agent creation
│       └── ...                      # Other agent modules
├── scripts/                  # Automation scripts
│   └── validate_config.py           # Configuration validation
├── docs/                     # Documentation
│   ├── configuration-guide.md       # Configuration reference
│   ├── agent-architecture.md        # Agent design
│   └── ...                          # Other documentation
├── data/manuals/             # Sample PDF driving manuals
├── tests/                    # Unit and integration tests
├── .env.example              # Environment variable template
└── README.md                 # This file
```

## Configuration

The agent supports flexible configuration through hierarchical profiles:

- **Base**: Balanced configuration (gpt-4o, 5 search results)
- **Cost-Optimized**: ~70-80% cost savings (gpt-4o-mini, 3 search results)
- **Performance-Optimized**: Maximum quality (gpt-4.1, 10 search results, LLM judge)

See [Configuration Guide](docs/configuration-guide.md) for detailed configuration options and deployment scenarios.

## Features

### Configuration System

- ✅ Hierarchical configuration with JSON profiles
- ✅ Pydantic-based type-safe validation
- ✅ Environment variable overrides
- ✅ Multiple deployment profiles (cost-optimized, performance-optimized)
- ✅ Comprehensive validation script

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

- [Configuration Guide](docs/configuration-guide.md) - Complete configuration reference
- [Agent Architecture](docs/agent-architecture.md) - Agent design and implementation
- [Indexer Pipeline Guide](src/indexing/README.md) - Detailed indexer documentation
- [Bicep Templates Guide](infra/bicep/README.md) - Infrastructure deployment guide
- [Indexer Troubleshooting](docs/indexer-troubleshooting.md) - Common issues and solutions

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
