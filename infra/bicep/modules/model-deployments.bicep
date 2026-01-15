// ============================================================================
// AI Model Deployments Module
// ============================================================================
// This module deploys AI models to the Microsoft Foundry project:
//
// 1. GPT-4o (gpt-4o-2024-05-13):
//    - Multimodal model supporting text and vision
//    - Used for agent orchestration and response generation
//    - Supports function calling for tool integration
//    - Context window: 128K tokens
//
// 2. GPT-4.1 (gpt-4.1-2025-04-14):
//    - Advanced reasoning, tool execution improvements
//    - Maintains GPT-4o multimodal support with higher reliability
//    - Ideal for complex workflows and structured outputs
//
// 3. Text-embedding-3-large:
//    - High-quality text embeddings (3072 dimensions)
//    - Used for document chunking and semantic search
//    - Superior performance on retrieval tasks
//
// Model capacity is measured in thousands of tokens per minute (TPM)
// Higher capacity = more concurrent requests and lower latency
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Name of the Microsoft Foundry account (Cognitive Services resource)')
param foundryAccountName string

@description('GPT-4o deployment capacity in thousands of tokens per minute (TPM)')
@minValue(1)
@maxValue(500)
param gpt4oCapacity int = 50

@description('Text-embedding-3-large deployment capacity in thousands of tokens per minute (TPM)')
@minValue(1)
@maxValue(500)
param embeddingCapacity int = 100

@description('GPT-4.1 deployment capacity in thousands of tokens per minute (TPM)')
@minValue(1)
@maxValue(500)
param gpt41Capacity int = 50

// ============================================================================
// Variables
// ============================================================================

// Deployment names - these are used in code to reference the models
var gpt4oDeploymentName = 'gpt-4o'
var embeddingDeploymentName = 'text-embedding-3-large'
var gpt41DeploymentName = 'gpt-4.1'

// Model versions - update these when newer versions are available
// Use specific versions in production for consistency
var gpt4oModelVersion = '2024-05-13' // Latest GPT-4o with vision capabilities
var embeddingModelVersion = '1' // Latest text-embedding-3-large
var gpt41ModelVersion = '2025-04-14' // Default version per Microsoft Foundry catalog

// SKU for deployments
// GPT-4 family requires GlobalStandard, embeddings remain Standard
var globalStandardSku = 'GlobalStandard'
var standardSku = 'Standard'

// ============================================================================
// Existing Resources
// ============================================================================

// Reference to the existing Microsoft Foundry account (replaces Azure OpenAI)
resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

// ============================================================================
// GPT-4o Model Deployment
// ============================================================================

// Deploy GPT-4o for agent orchestration and multimodal understanding
// This is the primary model for the DrivingManualAgent
//
// Key capabilities:
// - Text and image understanding in a single model
// - Function calling for tool integration (search, retrieval)
// - High reasoning capability for complex queries
// - JSON mode for structured outputs
//
// Capacity considerations:
// - 50K TPM: Good for development and testing
// - 100K+ TPM: Recommended for production with multiple concurrent users
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: gpt4oDeploymentName
  parent: foundryAccount
  sku: {
    name: globalStandardSku
    capacity: gpt4oCapacity // Tokens per minute (in thousands)
  }
  properties: {
    model: {
      format: 'OpenAI' // Microsoft Foundry still uses the OpenAI model format contract
      name: 'gpt-4o' // Model name in the Microsoft Foundry catalog
      version: gpt4oModelVersion // Specific model version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable' // Auto-upgrade to new versions
    raiPolicyName: 'Microsoft.Default' // Responsible AI policy
  }
}

// ============================================================================
// GPT-4.1 Model Deployment
// ============================================================================

// Deploy GPT-4.1 for advanced reasoning workloads
// GPT-4.1 provides improved tool use and structured output fidelity and is
// recommended for complex orchestration scenarios alongside GPT-4o.
resource gpt41Deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: gpt41DeploymentName
  parent: foundryAccount
  sku: {
    name: globalStandardSku
    capacity: gpt41Capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1'
      version: gpt41ModelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
  dependsOn: [
    gpt4oDeployment
  ]
}

// ============================================================================
// Text Embedding Model Deployment
// ============================================================================

// Deploy text-embedding-3-large for document embeddings
// Used in the indexing pipeline to create vector representations
//
// Key characteristics:
// - 3072 dimensions (high quality, but larger storage)
// - Optimized for retrieval and semantic search
// - Superior performance on MTEB benchmark
//
// Capacity considerations:
// - Embedding generation is typically faster than GPT inference
// - 100K TPM: Sufficient for indexing ~1000 pages/minute
// - Can be lower in production if re-indexing is infrequent
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  name: embeddingDeploymentName
  parent: foundryAccount
  sku: {
    name: standardSku
    capacity: embeddingCapacity // Tokens per minute (in thousands)
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large' // Model name in the Microsoft Foundry catalog
      version: embeddingModelVersion // Specific model version
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.Default'
  }
  // Ensure GPT-4o deploys first to avoid throttling
  dependsOn: [
    gpt4oDeployment
    gpt41Deployment
  ]
}

// ============================================================================
// Outputs
// ============================================================================

@description('GPT-4o deployment name for use in application code')
output gpt4oDeploymentName string = gpt4oDeployment.name

@description('GPT-4o model version deployed')
output gpt4oModelVersion string = gpt4oModelVersion

@description('GPT-4o deployment capacity (TPM in thousands)')
output gpt4oCapacity int = gpt4oCapacity

@description('GPT-4.1 deployment name for use in application code')
output gpt41DeploymentName string = gpt41Deployment.name

@description('GPT-4.1 model version deployed')
output gpt41ModelVersion string = gpt41ModelVersion

@description('GPT-4.1 deployment capacity (TPM in thousands)')
output gpt41Capacity int = gpt41Capacity

@description('Text-embedding-3-large deployment name for use in application code')
output embeddingDeploymentName string = embeddingDeployment.name

@description('Text-embedding model version deployed')
output embeddingModelVersion string = embeddingModelVersion

@description('Embedding deployment capacity (TPM in thousands)')
output embeddingCapacity int = embeddingCapacity
