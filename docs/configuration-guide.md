# Configuration Guide

Complete guide to configuring the DrivingManualAgent for different deployment scenarios using hierarchical configuration profiles.

## Table of Contents

- [Overview](#overview)
- [Configuration Hierarchy](#configuration-hierarchy)
- [Configuration Profiles](#configuration-profiles)
- [Environment Variables](#environment-variables)
- [Deployment Scenarios](#deployment-scenarios)
- [Adding Custom Profiles](#adding-custom-profiles)
- [Troubleshooting](#troubleshooting)

## Overview

The DrivingManualAgent uses a hierarchical configuration system that allows you to:

- **Choose pre-configured profiles** for different cost/performance tradeoffs
- **Override settings via environment variables** for deployment-specific customization
- **Validate configuration** before deployment to catch errors early
- **Switch configurations easily** without code changes

### Configuration Architecture

```
Environment Variables (highest priority)
          ↓
Profile Configuration (cost-optimized.json, performance-optimized.json)
          ↓
Base Configuration (base-config.json)
```

## Configuration Hierarchy

Configuration values are loaded in three layers, with later sources overriding earlier ones:

### 1. Base Configuration (`config/base-config.json`)

The foundation layer that provides sensible defaults for all settings:

- **Chat Model**: gpt-4o with temperature 0.7, max_tokens 4000
- **Embedding Model**: text-embedding-3-large with 3072 dimensions
- **Vision Model**: gpt-4o for image analysis
- **Search**: 5 results, hybrid search enabled, semantic reranking enabled
- **Images**: 0.75 relevance threshold, max 3 images, LLM judge disabled
- **Agent**: Streaming enabled, 24-hour thread retention

**When to use**: Production deployments requiring balanced cost and quality.

### 2. Profile Configuration (Optional)

Profile-specific overrides that modify base settings for specific use cases:

#### Cost-Optimized Profile (`config/cost-optimized.json`)

Reduces Azure costs by ~70-80% while maintaining acceptable quality:

**Overrides**:
- Chat model: gpt-4o-mini
- Embedding model: text-embedding-3-small (1536 dimensions)
- Search results: 3 (down from 5)
- Max images: 2 (down from 3)

**Use cases**:
- Development and testing
- Budget-constrained production workloads
- High-volume applications where cost is critical

**Tradeoffs**:
- Slightly lower response quality
- Less comprehensive search context
- Fewer images in responses

#### Performance-Optimized Profile (`config/performance-optimized.json`)

Maximizes quality and accuracy at ~2-3x base cost:

**Overrides**:
- Chat model: gpt-4.1 (1M context window)
- Max tokens: 8000 (up from 4000)
- Search results: 10 (up from 5)
- Max images: 5 (up from 3)
- LLM judge: enabled (vision model validates image relevance)

**Use cases**:
- Critical production applications
- Demos and evaluations
- Applications requiring highest accuracy

**Benefits**:
- Best reasoning and accuracy
- Comprehensive search context
- Validated image relevance
- Longer, more detailed responses

### 3. Environment Variables (Highest Priority)

Environment variables override both base and profile settings, useful for:

- Deployment-specific configuration (dev vs staging vs production)
- CI/CD pipeline customization
- Temporary overrides for testing
- Sensitive values (endpoints, storage accounts)

## Configuration Profiles

### Selecting a Profile

Set the `CONFIG_PROFILE` environment variable:

```powershell
# Use base profile (default)
$env:CONFIG_PROFILE = base

# Use cost-optimized profile
$env:CONFIG_PROFILE = cost-optimized

# Use performance-optimized profile
$env:CONFIG_PROFILE = performance-optimized
```

Or pass the profile when loading configuration in code:

```python
from agent.config_loader import load_config

# Load cost-optimized profile
config = load_config(profile="cost-optimized")
```

### Profile Comparison

| Setting | Base | Cost-Optimized | Performance-Optimized |
|---------|------|----------------|----------------------|
| **Chat Model** | gpt-4o | gpt-4o-mini | gpt-4.1 |
| **Embedding Model** | text-embedding-3-large (3072) | text-embedding-3-small (1536) | text-embedding-3-large (3072) |
| **Search Results** | 5 | 3 | 10 |
| **Max Images** | 3 | 2 | 5 |
| **LLM Judge** | No | No | Yes |
| **Max Tokens** | 4000 | 4000 | 8000 |
| **Relative Cost** | 1.0x | 0.2-0.3x | 2-3x |

## Environment Variables

### Required Variables

These must be set for the agent to function:

```powershell
# Azure AI Foundry project endpoint
AZURE_AI_PROJECT_ENDPOINT=https://your-project.api.azureml.ms

# Azure AI Search service endpoint
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
```

### Optional Overrides

#### Model Deployments

Override which model deployments to use:

```powershell
# Chat model (must be deployed in Azure AI Foundry)
CHAT_MODEL_DEPLOYMENT=gpt-4o

# Embedding model
EMBEDDING_MODEL_DEPLOYMENT=text-embedding-3-large

# Vision model (for LLM-as-judge)
VISION_MODEL_DEPLOYMENT=gpt-4o
```

#### Model Parameters

Fine-tune model behavior:

```powershell
# Temperature (0.0-1.0, higher = more creative)
AGENT_TEMPERATURE=0.7

# Maximum tokens in response
AGENT_MAX_TOKENS=4000
```

#### Search Configuration

Control search behavior:

```powershell
# Search index name
AZURE_SEARCH_INDEX=driving-rules-hybrid

# Number of results to retrieve
SEARCH_TOP_K=5

# Enable/disable semantic reranking
ENABLE_SEMANTIC_RERANKING=true

# Enable/disable hybrid search
ENABLE_HYBRID_SEARCH=true
```

#### Image Settings

Control image inclusion:

```powershell
# Relevance threshold (0.0-1.0)
IMAGE_RELEVANCE_THRESHOLD=0.75

# Maximum images per response
MAX_IMAGES_PER_RESPONSE=3

# Enable vision model validation
ENABLE_LLM_JUDGE=false
```

#### Runtime Settings

```powershell
# Enable streaming responses
ENABLE_STREAMING=true

# Enable telemetry
ENABLE_TELEMETRY=true

# Use managed identity (vs API keys)
USE_MANAGED_IDENTITY=true
```

#### Storage Settings

```powershell
# Storage account for images
AZURE_STORAGE_ACCOUNT=your-storage-account

# Container for extracted images
AZURE_STORAGE_CONTAINER_IMAGES=extracted-images
```

## Deployment Scenarios

### Development: Fast Iteration with Low Cost

**Goal**: Quick testing and debugging without high Azure costs.

**Configuration**:
```powershell
CONFIG_PROFILE=cost-optimized
ENABLE_STREAMING=true
ENABLE_TELEMETRY=false
SEARCH_TOP_K=1  # Minimal for fast testing
```

**Characteristics**:
- Fastest responses (smaller models)
- Lowest cost
- Sufficient quality for development
- No telemetry overhead

---

### Staging: Production-Like Testing

**Goal**: Test with production-like configuration before deploying.

**Configuration**:
```powershell
CONFIG_PROFILE=base
ENABLE_TELEMETRY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=...
ENVIRONMENT=staging
```

**Characteristics**:
- Same models as production
- Full telemetry for debugging
- Separate environment for isolation

---

### Production (Budget-Conscious): Cost-Effective at Scale

**Goal**: Serve production traffic with minimal Azure costs.

**Configuration**:
```powershell
CONFIG_PROFILE=cost-optimized
ENABLE_TELEMETRY=true
ENABLE_STREAMING=true
USE_MANAGED_IDENTITY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=...
ENVIRONMENT=production
```

**Characteristics**:
- 70-80% cost savings
- Acceptable quality for most use cases
- Full monitoring and security

---

### Production (Quality-Critical): Maximum Accuracy

**Goal**: Highest quality responses for critical applications.

**Configuration**:
```powershell
CONFIG_PROFILE=performance-optimized
ENABLE_TELEMETRY=true
ENABLE_STREAMING=true
USE_MANAGED_IDENTITY=true
APPLICATIONINSIGHTS_CONNECTION_STRING=...
ENVIRONMENT=production
```

**Characteristics**:
- Best available models
- Most comprehensive search
- Validated image relevance
- Full monitoring

---

### Demo/Evaluation: Show Best Capabilities

**Goal**: Demonstrate the system's full potential.

**Configuration**:
```powershell
CONFIG_PROFILE=performance-optimized
SEARCH_TOP_K=15  # Extra comprehensive
ENABLE_LLM_JUDGE=true
MAX_IMAGES_PER_RESPONSE=8
ENABLE_STREAMING=true
```

**Characteristics**:
- Maximum quality
- Extensive context
- Rich multimodal responses
- Impressive user experience

---

### Custom Hybrid: Tailored Configuration

**Goal**: Custom balance of cost and performance.

**Configuration**:
```powershell
CONFIG_PROFILE=base
CHAT_MODEL_DEPLOYMENT=gpt-4.1  # Upgrade chat model
SEARCH_TOP_K=8  # More results than base
ENABLE_LLM_JUDGE=true  # Validate images
```

**Characteristics**:
- Start with base profile
- Selectively upgrade specific components
- Fine-tune for specific requirements

## Adding Custom Profiles

You can create custom configuration profiles for specific use cases.

### Step 1: Create Profile File

Create a new JSON file in the `config/` directory:

```powershell
config/my-custom-profile.json
```

### Step 2: Define Overrides

Add only the settings you want to override from base:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "My custom profile for specialized use case",
  
  "models": {
    "chat": {
      "deployment_name": "gpt-4-turbo",
      "temperature": 0.5,
      "description": "Lower temperature for more deterministic responses"
    }
  },
  
  "search": {
    "top_k": 7
  },
  
  "_profile_notes": {
    "use_case": "Specialized scenario requiring specific configuration",
    "benefits": "Custom balance of features"
  }
}
```

### Step 3: Use Custom Profile

Load the custom profile:

```powershell
CONFIG_PROFILE=my-custom-profile
```

Or in code:

```python
config = load_config(profile="my-custom-profile")
```

### Best Practices for Custom Profiles

1. **Start minimal**: Only override what's necessary
2. **Document choices**: Use description and notes fields
3. **Validate early**: Run `python scripts/validate_config.py --profile my-custom-profile`
4. **Test thoroughly**: Verify behavior matches expectations

## Troubleshooting

### Configuration Won't Load

**Problem**: `FileNotFoundError: Configuration file not found`

**Solutions**:
1. Verify config files exist: `ls config/`
2. Check profile name spelling: `cost-optimized` not `cost_optimized`
3. Ensure you're in project root directory

---

### Validation Errors

**Problem**: `ValueError: Invalid temperature: 1.5`

**Solutions**:
1. Check value ranges in error message
2. Verify JSON syntax (no trailing commas)
3. Run validation: `python scripts/validate_config.py`

---

### Environment Variables Not Applied

**Problem**: Changes to env vars don't affect configuration

**Solutions**:
1. Verify env vars are set: `echo $CHAT_MODEL_DEPLOYMENT`
2. Check exact variable names (case-sensitive)
3. Ensure .env file is loaded (`python-dotenv` installed)
4. Test: `python src/agent/config_loader.py` shows active config

---

### Wrong Model Deployed

**Problem**: `Model deployment 'gpt-4.1' not found`

**Solutions**:
1. Verify model is deployed in Azure AI Foundry
2. Check deployment name matches exactly
3. Use `az ml model list` to see available deployments
4. Update config to use available model

---

### Profile Not Found

**Problem**: `Unknown configuration profile: my-profile`

**Solutions**:
1. Check profile file exists: `ls config/my-profile.json`
2. Verify CONFIG_PROFILE value
3. Available profiles: base, cost-optimized, performance-optimized

---

### Configuration Validation

Always validate configuration before deploying:

```powershell
# Validate all profiles
python scripts/validate_config.py --all

# Validate specific profile
python scripts/validate_config.py --profile cost-optimized

# Show configuration summary
python scripts/validate_config.py --all --summary
```

---

### Testing Configuration

Test configuration loading without deploying:

```powershell
# Set required env vars
$env:AZURE_AI_PROJECT_ENDPOINT = https://test.api.azureml.ms
$env:AZURE_SEARCH_ENDPOINT = https://test.search.windows.net

# Test with different profiles
$env:CONFIG_PROFILE = base
python src/agent/config_loader.py

$env:CONFIG_PROFILE = cost-optimized
python src/agent/config_loader.py

# Test with env var overrides
$env:SEARCH_TOP_K = 15
python src/agent/config_loader.py
```

## Best Practices

### 1. Use Profiles for Major Configuration Differences

- Development vs Production
- Cost vs Performance tradeoffs
- Different application tiers

### 2. Use Environment Variables for Deployment-Specific Values

- Endpoints (different per environment)
- Storage accounts
- Temporary testing overrides

### 3. Validate Early and Often

Run validation after any configuration change:

```powershell
python scripts/validate_config.py
```

### 4. Document Custom Profiles

Include description and notes in custom profile JSON files to explain the purpose and tradeoffs.

### 5. Version Control Configuration

- **Commit**: All profile JSON files
- **Don't commit**: .env file (contains secrets)
- **Do commit**: .env.example (template)

### 6. Monitor Configuration in Production

Log active configuration at startup to ensure correct settings are applied:

```python
config = load_config()
logger.info(f"Loaded profile: {os.getenv('CONFIG_PROFILE', 'base')}")
logger.info(f"Chat model: {config.chat_model.deployment_name}")
logger.info(f"Search top_k: {config.search.top_k}")
```

## Related Documentation

- [Agent Architecture](agent-architecture.md) - How the agent uses configuration
- [Indexer Troubleshooting](indexer-troubleshooting.md) - Search index configuration
- [Ingestion Workflow](ingestion-workflow.md) - Document indexing pipeline
- [README](../README.md) - Project overview and quickstart

## Support

For configuration issues:

1. Check this guide for your specific scenario
2. Run validation script: `python scripts/validate_config.py`
3. Review error messages carefully (they include suggestions)
4. Check environment variables are set correctly
5. Open an issue with configuration details (without secrets!)

