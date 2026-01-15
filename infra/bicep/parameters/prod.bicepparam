// ============================================================================
// Production Environment Parameters
// ============================================================================
// Parameter file for production environment deployment
//
// Usage:
//   az deployment sub create \
//     --location eastus \
//     --template-file main.bicep \
//     --parameters parameters/prod.bicepparam
// ============================================================================

using '../main.bicep'

// Environment Configuration
param environmentName = 'prod'
param location = 'eastus'
param projectName = 'drivingagent'

// Azure AI Search Configuration
// Standard tier required for production workloads
// Provides:
// - Semantic ranking for improved search quality
// - Vector search support
// - 25GB storage per partition
// - High availability with multiple replicas
param searchServiceSku = 'standard'

// Model Deployment Capacity (in thousands of tokens per minute)
// Production capacity for handling concurrent users
// 150K TPM for GPT-4o supports ~30-50 concurrent users with typical query patterns
// Adjust based on expected load and latency requirements
param gpt4oCapacity = 150

// 200K TPM for embeddings allows fast re-indexing when needed
// Can be scaled down after initial indexing is complete
param embeddingCapacity = 200

// Resource Tags
// Used for cost tracking, resource organization, and governance
param tags = {
  project: 'DrivingManualAgent'
  environment: 'prod'
  managedBy: 'Bicep'
  costCenter: 'Production'
  owner: 'platform-team'
  criticality: 'high'
  dataClassification: 'internal'
}
