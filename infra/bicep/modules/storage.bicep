// ============================================================================
// Azure Storage Account Module
// ============================================================================
// This module creates an Azure Storage Account with blob containers for:
//
// 1. Source PDFs (pdfs container):
//    - Uploaded driving manual PDF files
//    - Source documents for indexing pipeline
//
// 2. Extracted Images (extracted-images container):
//    - Images extracted from PDFs during indexing
//    - Referenced in agent responses for visual context
//
// Storage configuration:
// - Hierarchical namespace enabled (Azure Data Lake Gen2)
//   - Better performance for large-scale analytics
//   - Improved security with ACLs
//   - Required for certain AI Search indexer scenarios
//
// - Hot access tier
//   - Optimized for frequent access
//   - Suitable for active document repositories
// ============================================================================

targetScope = 'resourceGroup'

// ============================================================================
// Parameters
// ============================================================================

@description('Azure region for storage account')
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

// Storage account name must be globally unique and alphanumeric only (3-24 chars)
// Format: st<short project><env><suffix>
// Use first 5 chars of project name to ensure length constraints
var projectShortName = substring(projectName, 0, min(length(projectName), 5))
var envShortName = substring(environmentName, 0, 1) // Use first letter (d/p)
var storageAccountName = 'st${projectShortName}${envShortName}${uniqueSuffix}'

// Container names for different data types
var pdfsContainerName = 'pdfs'
var extractedImagesContainerName = 'extracted-images'

// ============================================================================
// Storage Account
// ============================================================================

// Deploy Azure Storage Account with Data Lake Gen2 capabilities
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2' // General-purpose v2 account
  sku: {
    name: 'Standard_LRS' // Locally redundant storage (cost-effective)
    // For production, consider:
    // - 'Standard_ZRS': Zone-redundant (higher availability)
    // - 'Standard_GRS': Geo-redundant (disaster recovery)
  }
  identity: {
    type: 'SystemAssigned' // Enable managed identity
  }
  properties: {
    // Access tier
    // 'Hot': Optimized for frequent access (our use case)
    // 'Cool': Lower storage cost, higher access cost (for archival)
    accessTier: 'Hot'
    
    // Hierarchical namespace (Azure Data Lake Gen2)
    // Enables file system semantics and improved performance
    // Required for: ACL-based security, better analytics integration
    // Cannot be disabled after creation
    isHnsEnabled: true
    
    // Security settings
    // Minimum TLS version for secure connections
    minimumTlsVersion: 'TLS1_2'
    
    // Disable public blob access for security
    // Blobs must be accessed via SAS tokens or managed identity
    allowBlobPublicAccess: false
    
    // Block shared key authentication so callers must use Azure AD tokens
    allowSharedKeyAccess: false
    
    // HTTPS-only traffic
    supportsHttpsTrafficOnly: true
    
    // Network access
    // Default action 'Allow' permits access from all networks
    // For production, consider 'Deny' with selected virtual networks/IPs
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices' // Allow trusted Azure services
    }
    
    // Encryption
    // Microsoft-managed keys by default
    // For enhanced security, can use customer-managed keys in Key Vault
    encryption: {
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
  tags: tags
}

// ============================================================================
// Blob Service Configuration
// ============================================================================

// Configure blob service properties
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    // Soft delete for blobs (recoverability)
    // Protects against accidental deletion
    // Retention period: 7 days for dev, 30 days for production
    deleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'prod' ? 30 : 7
    }
    
    // Soft delete for containers
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environmentName == 'prod' ? 30 : 7
    }
    
    // Versioning (optional)
    // Automatically maintain previous versions of blobs
    // Useful for audit trails and rollback
    // Disabled by default due to storage cost
    isVersioningEnabled: false
    
    // Change feed (optional)
    // Provides transaction logs of all changes
    // Useful for event-driven architectures
    // Disabled by default
    changeFeed: {
      enabled: false
    }
  }
}

// ============================================================================
// Blob Containers
// ============================================================================

// Container for source PDF documents
// This is where users upload driving manual PDFs
resource pdfsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: pdfsContainerName
  properties: {
    // Public access level
    // 'None': Private container (recommended)
    // 'Blob': Public read access to blobs
    // 'Container': Public read access to container and blobs
    publicAccess: 'None'
    
    // Metadata for container purpose
    metadata: {
      description: 'Source PDF documents for indexing pipeline'
      contentType: 'application/pdf'
    }
  }
}

// Container for extracted images from PDFs
// Generated during the indexing pipeline
resource extractedImagesContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: blobService
  name: extractedImagesContainerName
  properties: {
    publicAccess: 'None'
    metadata: {
      description: 'Images extracted from PDF documents during indexing'
      contentType: 'image/*'
    }
  }
}

// ============================================================================
// Outputs
// ============================================================================

@description('Name of the storage account')
output storageAccountName string = storageAccount.name

@description('Storage account resource ID')
output storageAccountId string = storageAccount.id

@description('Storage account managed identity principal ID')
output storageAccountPrincipalId string = storageAccount.identity.principalId

@description('Primary blob endpoint')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('Name of the PDFs container')
output pdfsContainerName string = pdfsContainer.name

@description('Name of the extracted images container')
output extractedImagesContainerName string = extractedImagesContainer.name
