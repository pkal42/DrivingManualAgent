// ============================================================================
// RBAC Role Assignments Module
// ============================================================================
// This module configures Role-Based Access Control (RBAC) between services
// using managed identities. This follows the principle of least privilege
// and eliminates the need for connection strings or API keys.
//
// Role assignments:
//
// 1. AI Project → Storage Account:
//    - Storage Blob Data Contributor: Read/write access to blob containers
//    - Needed for: Reading source PDFs, writing extracted images

// 1b. Search Service → Storage Account:
//    - Storage Blob Data Reader: Enables indexer to fetch blobs via managed identity
//    - Storage Blob Data Contributor: Required for change detection metadata updates
//    - Needed because local auth is disabled on storage

// 2. AI Project → Search Service:
//    - Search Index Data Contributor: Read/write access to search indexes
//    - Needed for: Agent to query search indexes for retrieval
//
// 3. AI Project → Microsoft Foundry account:
//    - Cognitive Services User: Access to AI models
//    - Note: Direct connections are configured via Foundry service principals
//
// All role assignments use managed identities (no secrets/keys)
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Principal ID of the Azure AI Project managed identity')
param aiProjectPrincipalId string

@description('Name of the storage account')
param storageAccountName string

@description('Name of the search service')
param searchServiceName string

// ============================================================================
// Existing Resources
// ============================================================================

// Reference existing storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

// Reference existing search service
resource searchService 'Microsoft.Search/searchServices@2023-11-01' existing = {
  name: searchServiceName
}

var searchServicePrincipalId = searchService.identity.principalId

// ============================================================================
// Built-in Role Definitions
// ============================================================================
// These are Azure built-in roles with specific permissions
// Reference: https://docs.microsoft.com/en-us/azure/role-based-access-control/built-in-roles

// Storage Blob Data Contributor role
// Permissions: Read, write, and delete Azure Storage containers and blobs
var storageBlobDataContributorRoleId = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

// Storage Blob Data Reader role
// Permissions: Read blob content (required for search service indexer)
var storageBlobDataReaderRoleId = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'

// Search Index Data Contributor role
// Permissions: Read, write, and delete search indexes and documents
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

// Search Service Contributor role
// Permissions: Manage search service, but not access data
// Useful for administrative tasks
var searchServiceContributorRoleId = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

// ============================================================================
// Role Assignment: AI Project → Storage Account
// ============================================================================

// Grant the AI Project managed identity access to read/write blobs
// This allows:
// - Reading source PDFs during indexing
// - Writing extracted images to storage
// - Agent to access documents and images for context
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, aiProjectPrincipalId, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: aiProjectPrincipalId
    principalType: 'ServicePrincipal' // Managed identity is a service principal
    description: 'Grants AI Project access to read/write blob storage for documents and images'
  }
}

// ============================================================================
// Role Assignment: Search Service → Storage Account (Read Only)
// ============================================================================

// Grant the search service managed identity read access to blob data so indexers
// can pull documents using managed identity instead of storage keys
resource searchStorageReaderRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, searchService.id, storageBlobDataReaderRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataReaderRoleId)
    principalId: searchServicePrincipalId
    principalType: 'ServicePrincipal'
    description: 'Grants Azure AI Search permission to read blobs for indexer ingestion'
  }
}

// ============================================================================
// Role Assignment: Search Service → Storage Account (Contributor)
// ============================================================================

// Change detection requires write access to track high-watermark metadata
resource searchStorageContributorRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, searchService.id, storageBlobDataContributorRoleId)
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRoleId)
    principalId: searchServicePrincipalId
    principalType: 'ServicePrincipal'
    description: 'Grants Azure AI Search permission to manage blob metadata for change detection'
  }
}

// ============================================================================
// Role Assignment: AI Project → Search Service (Index Data)
// ============================================================================

// Grant the AI Project managed identity access to search index data
// This allows:
// - Agent to query search indexes
// - Indexing pipeline to create and update indexes
// - Reading and writing search documents
resource searchIndexDataRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, aiProjectPrincipalId, searchIndexDataContributorRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalId: aiProjectPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Grants AI Project access to query and manage search indexes'
  }
}

// ============================================================================
// Role Assignment: AI Project → Search Service (Service Management)
// ============================================================================

// Grant the AI Project managed identity access to manage search service
// This allows:
// - Creating and configuring search indexes
// - Managing indexers and skillsets
// - Administrative operations
resource searchServiceRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, aiProjectPrincipalId, searchServiceContributorRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributorRoleId)
    principalId: aiProjectPrincipalId
    principalType: 'ServicePrincipal'
    description: 'Grants AI Project access to manage search service configuration'
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Storage role assignment ID')
output storageRoleAssignmentId string = storageRoleAssignment.id

@description('Search index data role assignment ID')
output searchIndexDataRoleAssignmentId string = searchIndexDataRoleAssignment.id

@description('Search service role assignment ID')
output searchServiceRoleAssignmentId string = searchServiceRoleAssignment.id
