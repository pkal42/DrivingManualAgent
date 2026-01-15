// ============================================================================
// Azure AI Foundry Project Module
// ============================================================================
// This module creates an Azure AI Foundry (formerly Azure AI Studio) project
// which provides:
// - Centralized hub for AI model deployments
// - Built-in connections to Azure OpenAI and AI Services
// - Managed identity for secure service-to-service authentication
// - Integration with Azure Machine Learning for advanced scenarios
//
// The hub-project model allows:
// - Hub: Shared resources and governance across multiple projects
// - Project: Isolated workspace for specific applications
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Azure region for deployment')
param location string

@description('Project name prefix for resource naming')
param projectName string

@description('Environment name (dev, prod)')
param environmentName string

@description('Unique suffix for globally unique names')
param uniqueSuffix string

@description('Resource tags')
param tags object

// ============================================================================
// Variables
// ============================================================================

// Azure AI Hub name (shared resource)
var hubName = 'aih-${projectName}-${environmentName}-${uniqueSuffix}'

// Azure AI Project name (workspace)
var aiProjectName = 'aip-${projectName}-${environmentName}-${uniqueSuffix}'

// Azure OpenAI service name
// Must be globally unique across all of Azure
var openAIName = 'aoai-${projectName}-${environmentName}-${uniqueSuffix}'

// AI Services multi-service account name
// Provides access to various Cognitive Services APIs
var aiServicesName = 'ais-${projectName}-${environmentName}-${uniqueSuffix}'

// Storage account for AI project artifacts and logs
// Shorten name to fit 24-char limit
var projectShortName = substring(projectName, 0, min(length(projectName), 5))
var envShortName = substring(environmentName, 0, 1)
var projectStorageName = 'staip${projectShortName}${envShortName}${uniqueSuffix}'

// Key Vault for storing secrets and connection strings
// Key Vault names have 24-char limit
var keyVaultName = 'kv-${projectShortName}-${envShortName}-${uniqueSuffix}'

// Application Insights for monitoring and telemetry
var appInsightsName = 'appi-${projectName}-${environmentName}-${uniqueSuffix}'

// ============================================================================
// Azure OpenAI Service
// ============================================================================

// Deploy Azure OpenAI service for hosting GPT and embedding models
// SKU: S0 is the standard tier with pay-as-you-go pricing
resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: openAIName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0' // Standard SKU required for GPT-4o and embedding models
  }
  properties: {
    customSubDomainName: openAIName // Required for API endpoint
    publicNetworkAccess: 'Enabled' // Allow access from internet; use 'Disabled' for private endpoints
    networkAcls: {
      defaultAction: 'Allow' // Control network access; use 'Deny' with IP rules for production
    }
  }
  tags: tags
}

// ============================================================================
// AI Services Multi-Service Account
// ============================================================================

// Deploy AI Services account for additional cognitive capabilities
// Provides access to Computer Vision, Language, etc.
resource aiServices 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: aiServicesName
  location: location
  kind: 'AIServices' // Multi-service account
  sku: {
    name: 'S0' // Standard tier
  }
  properties: {
    customSubDomainName: aiServicesName
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

// ============================================================================
// Supporting Resources
// ============================================================================

// Storage account for AI project metadata and logs
resource projectStorage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: projectStorageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS' // Locally redundant storage for cost efficiency
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false // Security best practice
    minimumTlsVersion: 'TLS1_2' // Enforce secure connections
  }
  tags: tags
}

// Key Vault for secure secret storage
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true // Use RBAC instead of access policies
    enableSoftDelete: true // Protect against accidental deletion
    softDeleteRetentionInDays: 7
  }
  tags: tags
}

// Application Insights for telemetry and monitoring
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
  tags: tags
}

// ============================================================================
// Azure AI Foundry Hub
// ============================================================================

// Create AI Hub (shared resource layer)
// The hub provides governance and shared resources for multiple projects
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: hubName
  location: location
  kind: 'Hub' // Designates this as a hub workspace
  identity: {
    type: 'SystemAssigned' // Enable managed identity
  }
  properties: {
    friendlyName: 'DrivingManualAgent Hub - ${environmentName}'
    description: 'Azure AI Foundry Hub for DrivingManualAgent project'
    storageAccount: projectStorage.id
    keyVault: keyVault.id
    applicationInsights: appInsights.id
    // Hub does not have a container registry requirement
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

// ============================================================================
// Azure AI Foundry Project
// ============================================================================

// Create AI Project (application workspace)
// The project is where model deployments and agent code execute
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: aiProjectName
  location: location
  kind: 'Project' // Designates this as a project workspace
  identity: {
    type: 'SystemAssigned' // Enable managed identity for secure access
  }
  properties: {
    friendlyName: 'DrivingManualAgent Project - ${environmentName}'
    description: 'Azure AI Foundry Project for DrivingManualAgent application'
    hubResourceId: aiHub.id // Link to parent hub
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

// ============================================================================
// Hub Connections
// ============================================================================

// Create connection from Hub to Azure OpenAI
// This makes the OpenAI service available to all projects in the hub
resource openAIConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name: 'aoai-connection'
  properties: {
    category: 'AzureOpenAI' // Connection type
    authType: 'AAD' // Use Azure AD authentication (managed identity)
    isSharedToAll: true // Share with all projects in hub
    target: openAI.properties.endpoint
    metadata: {
      ApiVersion: '2024-02-01'
      ApiType: 'Azure'
      ResourceId: openAI.id
    }
  }
}

// Create connection from Hub to AI Services
resource aiServicesConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name: 'aiservices-connection'
  properties: {
    category: 'AIServices'
    authType: 'AAD'
    isSharedToAll: true
    target: aiServices.properties.endpoint
    metadata: {
      ResourceId: aiServices.id
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Azure AI Project name')
output projectName string = aiProject.name

@description('Azure AI Project endpoint')
output projectEndpoint string = aiProject.properties.discoveryUrl

@description('Azure AI Project managed identity principal ID')
output projectPrincipalId string = aiProject.identity.principalId

@description('Azure OpenAI service name')
output openAIName string = openAI.name

@description('Azure OpenAI endpoint')
output openAIEndpoint string = openAI.properties.endpoint

@description('AI Services name')
output aiServicesName string = aiServices.name
