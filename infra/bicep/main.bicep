// ============================================================================
// Main Bicep Template - DrivingManualAgent Infrastructure
// ============================================================================
// This template orchestrates the deployment of all Azure resources required
// for the DrivingManualAgent project. It creates:
// - Azure AI Foundry project with model deployments
// - Azure AI Search service for vector and semantic search
// - Azure Storage account for documents and images
// - RBAC role assignments for secure access between services
//
// Usage:
//   az deployment sub create \
//     --location eastus \
//     --template-file main.bicep \
//     --parameters parameters/dev.bicepparam
// ============================================================================

targetScope = 'subscription'

// ============================================================================
// Parameters
// ============================================================================

@description('Environment name (e.g., dev, prod). Used for resource naming.')
@allowed([
  'dev'
  'prod'
])
param environmentName string

@description('Primary Azure region for resource deployment.')
param location string = 'eastus'

@description('Project name prefix. Used to ensure globally unique resource names.')
@minLength(3)
@maxLength(8)
param projectName string = 'drvagent'

@description('SKU for Azure AI Search service. S1 or higher required for vector search and semantic ranking.')
@allowed([
  'basic'
  'standard'
  'standard2'
  'standard3'
  'storage_optimized_l1'
  'storage_optimized_l2'
])
param searchServiceSku string = 'standard'

@description('GPT-4o model deployment capacity (in thousands of tokens per minute). Higher capacity = more concurrent requests.')
@minValue(1)
@maxValue(500)
param gpt4oCapacity int = 50

@description('Text-embedding-3-large model deployment capacity (in thousands of tokens per minute).')
@minValue(1)
@maxValue(500)
param embeddingCapacity int = 100

@description('Tags to apply to all resources for cost tracking and organization.')
param tags object = {
  project: 'DrivingManualAgent'
  environment: environmentName
  managedBy: 'Bicep'
}

// ============================================================================
// Variables
// ============================================================================

// Generate unique suffix based on subscription ID to ensure globally unique names
var uniqueSuffix = substring(uniqueString(subscription().id, projectName, environmentName), 0, 6)

// Resource group name following Azure naming conventions
var resourceGroupName = 'rg-${projectName}-${environmentName}-${location}'

// ============================================================================
// Resource Group
// ============================================================================

// Create a dedicated resource group for all project resources
// This simplifies management, cost tracking, and cleanup
resource resourceGroup 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

// ============================================================================
// Module Deployments
// ============================================================================

// Deploy Azure AI Foundry project and hub
// This includes the OpenAI connection and AI Services endpoint
module foundryProject 'modules/foundry-project.bicep' = {
  scope: resourceGroup
  name: 'deploy-foundry-project'
  params: {
    location: location
    projectName: projectName
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
    tags: tags
  }
}

// Deploy AI model deployments (GPT-4o, text-embedding-3-large)
// These models are deployed within the Azure OpenAI service
module modelDeployments 'modules/model-deployments.bicep' = {
  scope: resourceGroup
  name: 'deploy-models'
  params: {
    openAIName: foundryProject.outputs.openAIName
    gpt4oCapacity: gpt4oCapacity
    embeddingCapacity: embeddingCapacity
  }
}

// Deploy Azure AI Search service
// Configured with semantic search and vector search capabilities
module aiSearch 'modules/ai-search.bicep' = {
  scope: resourceGroup
  name: 'deploy-ai-search'
  params: {
    location: location
    projectName: projectName
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
    skuName: searchServiceSku
    tags: tags
  }
}

// Deploy Storage Account with containers for PDFs and extracted images
// Uses hierarchical namespace for better organization and performance
module storage 'modules/storage.bicep' = {
  scope: resourceGroup
  name: 'deploy-storage'
  params: {
    location: location
    projectName: projectName
    environmentName: environmentName
    uniqueSuffix: uniqueSuffix
    tags: tags
  }
}

// Configure RBAC role assignments
// Grants necessary permissions between services using managed identities
// Follows principle of least privilege
module roleAssignments 'modules/role-assignments.bicep' = {
  scope: resourceGroup
  name: 'deploy-role-assignments'
  params: {
    aiProjectPrincipalId: foundryProject.outputs.projectPrincipalId
    storageAccountName: storage.outputs.storageAccountName
    searchServiceName: aiSearch.outputs.searchServiceName
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Name of the deployed resource group')
output resourceGroupName string = resourceGroup.name

@description('Name of the Azure AI Foundry project')
output aiProjectName string = foundryProject.outputs.projectName

@description('Endpoint URL for the Azure AI project')
output aiProjectEndpoint string = foundryProject.outputs.projectEndpoint

@description('Name of the Azure AI Search service')
output searchServiceName string = aiSearch.outputs.searchServiceName

@description('Endpoint URL for the Azure AI Search service')
output searchServiceEndpoint string = aiSearch.outputs.searchServiceEndpoint

@description('Name of the storage account')
output storageAccountName string = storage.outputs.storageAccountName

@description('Name of the PDFs container')
output pdfsContainerName string = storage.outputs.pdfsContainerName

@description('Name of the extracted images container')
output extractedImagesContainerName string = storage.outputs.extractedImagesContainerName

@description('GPT-4o model deployment name')
output gpt4oDeploymentName string = modelDeployments.outputs.gpt4oDeploymentName

@description('Text-embedding-3-large model deployment name')
output embeddingDeploymentName string = modelDeployments.outputs.embeddingDeploymentName
