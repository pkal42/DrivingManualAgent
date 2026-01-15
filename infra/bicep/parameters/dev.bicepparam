// ============================================================================
// Development Environment Parameters
// ============================================================================
// Parameter file for dev environment deployment
// 
// Usage:
//   az deployment sub create \
//     --location eastus \
//     --template-file main.bicep \
//     --parameters parameters/dev.bicepparam
// ============================================================================

using '../main.bicep'

// Environment Configuration
param environmentName = 'dev'
param location = 'eastus'
param projectName = 'drvagent'

// Azure AI Search Configuration
// Basic tier is sufficient for development and testing
// Note: Basic tier has limited vector search and no semantic ranking
// Consider 'standard' for testing semantic search features
param searchServiceSku = 'standard'

// Model Deployment Capacity (in thousands of tokens per minute)
// Lower capacity for dev environment to reduce costs
// 50K TPM for GPT-4o is sufficient for single-developer testing
param gpt4oCapacity = 50

// 100K TPM for embeddings allows reasonable indexing speed
// Can be lowered to 50 if indexing performance is acceptable
param embeddingCapacity = 100

// Resource Tags
// Used for cost tracking, resource organization, and governance
param tags = {
  project: 'DrivingManualAgent'
  environment: 'dev'
  managedBy: 'Bicep'
  costCenter: 'Engineering'
  owner: 'development-team'
}
