// ============================================================================
// Azure AI Search Service Module
// ============================================================================
// This module creates an Azure AI Search service configured for:
//
// - Vector Search: Store and query high-dimensional embeddings
// - Semantic Ranking: AI-powered relevance ranking using L2 re-ranker
// - Hybrid Search: Combine traditional keyword search with vector search
//
// The service will be used to:
// 1. Index document chunks with text and embeddings
// 2. Index extracted images with descriptions and embeddings
// 3. Perform semantic search based on user queries
// 4. Return relevant context to the AI agent
//
// SKU considerations:
// - Basic: Limited vector search support, no semantic ranking
// - Standard (S1): Full vector search, semantic ranking, 25GB storage
// - Standard2/3: Higher scale for production workloads
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Azure region for the search service')
param location string

@description('Project name prefix for resource naming')
param projectName string

@description('Environment name (dev, prod)')
param environmentName string

@description('Unique suffix for globally unique names')
param uniqueSuffix string

@description('Search service SKU. Standard or higher required for semantic ranking and vector search.')
@allowed([
  'basic'
  'standard'
  'standard2'
  'standard3'
  'storage_optimized_l1'
  'storage_optimized_l2'
])
param skuName string = 'standard'

@description('Resource tags')
param tags object

// ============================================================================
// Variables
// ============================================================================

// Search service name must be globally unique across Azure
var searchServiceName = 'srch-${projectName}-${environmentName}-${uniqueSuffix}'

// ============================================================================
// Azure AI Search Service
// ============================================================================

// Deploy Azure AI Search service
// Configured with managed identity for secure access to other Azure services
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: skuName
  }
  identity: {
    type: 'SystemAssigned' // Enable managed identity for authentication
  }
  properties: {
    // Replica configuration
    // Replicas provide query scale and high availability
    // Start with 1 for dev, increase for production based on query load
    replicaCount: environmentName == 'prod' ? 2 : 1
    
    // Partition configuration
    // Partitions provide index scale and storage
    // Each partition provides ~25GB storage on Standard SKU
    // Start with 1, increase if index size exceeds capacity
    partitionCount: 1
    
    // Hosting mode
    // 'default': Standard multi-tenant infrastructure
    // 'highDensity': For scenarios with many small indexes (not needed here)
    hostingMode: 'default'
    
    // Network access
    // 'enabled': Allow public access (suitable for dev/test)
    // 'disabled': Private endpoints only (recommended for production)
    // Consider using IP firewall rules or private endpoints for production
    publicNetworkAccess: 'enabled'
    
    // Semantic search configuration
    // Enables AI-powered relevance ranking using Microsoft's L2 re-ranker
    // Essential for high-quality retrieval in RAG scenarios
    // Available on Standard and higher SKUs
    semanticSearch: skuName != 'basic' ? 'standard' : 'disabled'
    
    // Disable local (API key) authentication in every environment for consistent managed identity usage
    disableLocalAuth: true
  }
  tags: tags
}

// ============================================================================
// Outputs
// ============================================================================

@description('Name of the Azure AI Search service')
output searchServiceName string = searchService.name

@description('Azure AI Search service endpoint')
output searchServiceEndpoint string = 'https://${searchService.name}.search.windows.net'

@description('Managed identity principal ID for RBAC assignments')
output searchServicePrincipalId string = searchService.identity.principalId

@description('Search service resource ID')
output searchServiceId string = searchService.id

@description('Semantic search enabled status')
output semanticSearchEnabled bool = skuName != 'basic'
