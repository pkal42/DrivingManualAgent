// ============================================================================
// Azure AI Search Data Source Module
// ============================================================================
// This module defines the data source connection for Azure AI Search indexer
// to access PDF driving manuals in Azure Blob Storage.
//
// Key Features:
// - Managed identity authentication (no connection strings/keys)
// - Change detection for incremental indexing
// - Soft delete detection for automatic removal
// ============================================================================

// Parameters
// ----------------------------------------------------------------------------

@description('Name of the Azure AI Search service where data source will be created')
param searchServiceName string

@description('Name of the storage account containing PDF documents')
param storageAccountName string

@description('Name of the blob container with PDF files')
param containerName string = 'pdfs'

@description('Name for the data source resource')
param dataSourceName string = 'driving-manual-datasource'

@description('Enable change detection for incremental indexing')
param enableChangeDetection bool = true

@description('Enable soft delete detection for automatic removal from index')
param enableSoftDelete bool = true

@description('Metadata field name for soft delete flag (e.g., "isDeleted")')
param softDeleteColumnName string = 'isDeleted'

@description('Value indicating soft delete (e.g., "true")')
param softDeleteMarkerValue string = 'true'

// Variables
// ----------------------------------------------------------------------------

// Construct blob storage connection string using managed identity
// This avoids storing access keys in configuration
// The indexer will use the search service's managed identity to access storage
var storageConnectionString = 'ResourceId=/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Storage/storageAccounts/${storageAccountName};'

// Resource Reference
// ----------------------------------------------------------------------------

// Reference to existing Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

// Data Source Resource
// ----------------------------------------------------------------------------

resource dataSource 'Microsoft.Search/searchServices/dataSources@2024-06-01-preview' = {
  parent: searchService
  name: dataSourceName
  properties: {
    // ========================================================================
    // Data Source Type: Azure Blob Storage
    // ========================================================================
    // Azure AI Search supports multiple data source types:
    // - azureblob: Azure Blob Storage (used here for PDFs)
    // - azuretable: Azure Table Storage
    // - azuresql: Azure SQL Database
    // - cosmosdb: Azure Cosmos DB
    //
    // We use azureblob for storing and indexing PDF documents
    // ========================================================================
    type: 'azureblob'
    
    description: 'Data source for PDF driving manuals in blob storage with managed identity authentication'
    
    // ========================================================================
    // Credentials: Managed Identity Authentication
    // ========================================================================
    // Security Best Practice: Use managed identity instead of access keys
    //
    // Benefits:
    // - No credentials stored in code or configuration
    // - Automatic credential rotation
    // - Fine-grained RBAC (Storage Blob Data Reader role)
    // - Audit trail via Azure AD logs
    //
    // Alternative Approaches:
    // - Connection string with access key (NOT RECOMMENDED - security risk)
    // - SAS token (better than key, but still requires rotation)
    //
    // Required RBAC Roles:
    // - Search service managed identity needs:
    //   - "Storage Blob Data Reader" on storage account
    //   - "Storage Blob Data Contributor" if using change detection
    // ========================================================================
    credentials: {
      // Managed identity connection string (no keys)
      // Format: ResourceId=/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Storage/storageAccounts/{account};
      connectionString: storageConnectionString
    }
    
    // ========================================================================
    // Container Configuration
    // ========================================================================
    // Specifies which container and path to index
    //
    // Container Structure:
    // - pdfs/ (container)
    //   - california/
    //     - california-dmv-2024.pdf
    //   - texas/
    //     - texas-dps-2023.pdf
    //
    // Query Options:
    // - query: Optional path prefix to limit scope
    //   - Example: "california/" indexes only California manuals
    //   - Empty/null: Index entire container
    // ========================================================================
    container: {
      // Container name in storage account
      name: containerName
      
      // Optional: Path prefix to limit indexing scope
      // Example: "california/" to index only California folder
      // Leave empty to index all PDFs in container
      query: ''
    }
    
    // ========================================================================
    // Change Detection Policy (Incremental Indexing)
    // ========================================================================
    // Enables efficient incremental indexing by tracking changes
    //
    // How it works:
    // 1. Blob storage tracks LastModified timestamp for each blob
    // 2. Indexer only processes blobs modified since last run
    // 3. Dramatically reduces processing time and cost
    //
    // Policy Type: HighWaterMark
    // - Tracks a monotonically increasing value (LastModified)
    // - On each run, processes only items with value > last tracked value
    //
    // Alternative: No change detection
    // - Re-indexes all documents every run (inefficient)
    // - Use only for small datasets or one-time indexing
    //
    // Trade-offs:
    // - Enabled: Fast incremental updates, efficient
    // - Disabled: Simple but inefficient, re-processes all files
    // ========================================================================
    dataChangeDetectionPolicy: enableChangeDetection ? {
      '@odata.type': '#Microsoft.Azure.Search.HighWaterMarkChangeDetectionPolicy'
      // Built-in metadata field tracking last modification time
      // Automatically maintained by Azure Blob Storage
      highWaterMarkColumnName: 'metadata_storage_last_modified'
    } : null
    
    // ========================================================================
    // Deletion Detection Policy (Automatic Removal)
    // ========================================================================
    // Automatically removes deleted documents from the search index
    //
    // Problem: When a blob is deleted from storage, the index entry persists
    // Solution: Use soft delete detection to mark and remove deleted docs
    //
    // How Soft Delete Works:
    // 1. Instead of deleting blob, set metadata flag (e.g., isDeleted=true)
    // 2. Indexer detects soft delete flag and removes from index
    // 3. Later, manually delete the blob (or use lifecycle policy)
    //
    // Alternative: Hard Delete Detection
    // - Requires blob soft delete feature enabled in storage
    // - Indexer detects natively deleted blobs
    // - More complex setup, requires storage configuration
    //
    // Implementation Steps:
    // 1. Before deleting blob, set metadata: isDeleted=true
    //    az storage blob metadata update --container pdfs --name file.pdf --metadata isDeleted=true
    // 2. Run indexer (automatically removes from index)
    // 3. Delete blob: az storage blob delete --container pdfs --name file.pdf
    //
    // Trade-offs:
    // - Enabled: Automatic cleanup, consistent state
    // - Disabled: Manual cleanup required (orphaned index entries)
    // ========================================================================
    dataDeletionDetectionPolicy: enableSoftDelete ? {
      '@odata.type': '#Microsoft.Azure.Search.SoftDeleteColumnDeletionDetectionPolicy'
      // Metadata field name indicating soft delete
      // Set this on blob before deletion: isDeleted=true
      softDeleteColumnName: softDeleteColumnName
      
      // Value indicating the blob is soft deleted
      // When metadata field equals this value, document is removed from index
      softDeleteMarkerValue: softDeleteMarkerValue
    } : null
  }
}

// Outputs
// ----------------------------------------------------------------------------

@description('Resource ID of the created data source')
output dataSourceId string = dataSource.id

@description('Name of the created data source')
output dataSourceName string = dataSource.name

@description('Connection type used for data source authentication')
output connectionType string = 'ManagedIdentity'
