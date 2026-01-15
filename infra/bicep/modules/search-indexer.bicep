// ============================================================================
// Azure AI Search Indexer Module
// ============================================================================
// This module defines the indexer that orchestrates the enrichment pipeline,
// connecting the data source → skillset → index.
//
// Indexer Flow:
// 1. Read PDFs from blob storage (data source)
// 2. Execute skillset (extract, chunk, embed)
// 3. Map enriched fields to index schema
// 4. Store results in search index
// ============================================================================

// Parameters
// ----------------------------------------------------------------------------

@description('Name of the Azure AI Search service where indexer will be created')
param searchServiceName string

@description('Name of the data source to read from')
param dataSourceName string

@description('Name of the skillset to execute')
param skillsetName string

@description('Name of the target index')
param indexName string

@description('Name for the indexer resource')
param indexerName string = 'driving-manual-indexer'

@description('Indexer schedule (cron expression) - empty for on-demand only')
param schedule string = ''

@description('Enable automatic indexer execution on schedule')
param enableSchedule bool = false

@description('Maximum number of items to process in a single indexer run (0 = unlimited)')
param batchSize int = 10

@description('Maximum number of parallel threads for indexing')
param maxFailedItems int = 0

@description('Maximum number of failed items before indexer run fails')
param maxFailedItemsPerBatch int = 0

// Resource Reference
// ----------------------------------------------------------------------------

// Reference to existing Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

// Indexer Resource
// ----------------------------------------------------------------------------

resource indexer 'Microsoft.Search/searchServices/indexers@2024-06-01-preview' = {
  parent: searchService
  name: indexerName
  properties: {
    description: 'Indexer for processing PDF driving manuals with text extraction, chunking, and embedding generation'
    
    // ========================================================================
    // Data Source Configuration
    // ========================================================================
    // Points to the blob storage container with PDF files
    // The indexer reads documents from this data source
    // ========================================================================
    dataSourceName: dataSourceName
    
    // ========================================================================
    // Target Index Configuration
    // ========================================================================
    // Specifies where enriched documents are stored
    // Field mappings define how data flows to index fields
    // ========================================================================
    targetIndexName: indexName
    
    // ========================================================================
    // Skillset Configuration
    // ========================================================================
    // Defines the enrichment pipeline to execute
    // Skills process documents before indexing
    // ========================================================================
    skillsetName: skillsetName
    
    // ========================================================================
    // Indexer Schedule
    // ========================================================================
    // Determines when the indexer runs automatically
    //
    // Schedule Options:
    // 1. On-demand: No schedule, manual trigger only
    //    - Use: Development, testing, controlled updates
    //    - Trigger: Azure Portal, REST API, GitHub Actions
    //
    // 2. Scheduled: Cron expression for automatic runs
    //    - Use: Production, regular updates
    //    - Examples:
    //      - "0 0 * * *" - Daily at midnight
    //      - "0 */4 * * *" - Every 4 hours
    //      - "0 0 * * 0" - Weekly on Sunday
    //
    // Trade-offs:
    // - On-demand: Full control, no automatic costs
    // - Scheduled: Automatic updates, potential unnecessary runs
    //
    // Best Practice: Use on-demand for manual datasets,
    // scheduled for frequently updated sources
    // ========================================================================
    schedule: enableSchedule && !empty(schedule) ? {
      interval: schedule
    } : null
    
    // ========================================================================
    // Indexer Parameters
    // ========================================================================
    // Control indexer behavior, error handling, and performance
    // ========================================================================
    parameters: {
      // Batch size: Number of documents processed in parallel
      // Trade-off: Higher = faster but more memory/quota usage
      // Recommended: 10-50 for PDF processing (resource-intensive)
      batchSize: batchSize
      
      // Maximum failed items before indexer run fails
      // -1: Never fail, continue on all errors
      // 0: Fail on first error (strict)
      // N: Tolerate N failures before failing run
      // Trade-off: Strictness vs resilience
      maxFailedItems: maxFailedItems
      
      // Maximum failed items per batch before failing
      // Similar to maxFailedItems but per batch
      maxFailedItemsPerBatch: maxFailedItemsPerBatch
      
      // ======================================================================
      // Configuration: Skillset File Access
      // ======================================================================
      // Critical: Must be true for DocumentExtractionSkill
      //
      // Purpose: Grants skillset access to blob file data
      // - DocumentExtractionSkill reads raw PDF bytes
      // - Without this, skill cannot process binary files
      //
      // Security: Uses search service managed identity
      // - No additional permissions needed if RBAC configured
      // ======================================================================
      configuration: {
        // Enable skillset to read file data from blobs
        // Required for DocumentExtractionSkill to process PDFs
        allowSkillsetToReadFileData: true
        
        // Parsing mode for text extraction (optional)
        // - "default": Standard parsing (recommended)
        // - "text": Plain text extraction only
        // - "json": JSON document parsing
        parsingMode: 'default'
        
        // Image extraction mode
        // - Handled by skillset, not indexer parameter
        // - Keep this commented to avoid duplication
        // imageAction: 'generateNormalizedImages'
        
        // Data to extract from documents
        // - Handled by skillset, not indexer parameter
        // dataToExtract: 'contentAndMetadata'
        
        // ======================================================================
        // Error Handling Strategy
        // ======================================================================
        // How to handle errors during indexing
        //
        // Options:
        // - failOnUnsupportedContentType: false
        //   - Continue if file type not supported (e.g., .txt in PDF-only skillset)
        // - failOnUnprocessableDocument: false
        //   - Continue if document cannot be parsed (corrupted PDF)
        //
        // Trade-offs:
        // - false: Resilient, logs errors, continues processing
        // - true: Strict, fails entire run on any error
        //
        // Best Practice: Set to false for production (resilience)
        // Set to true for development (catch issues early)
        // ======================================================================
        failOnUnsupportedContentType: false
        failOnUnprocessableDocument: false
      }
    }
    
    // ========================================================================
    // Field Mappings (Blob Metadata → Index Fields)
    // ========================================================================
    // Maps blob storage metadata to index fields
    //
    // Mapping Flow:
    // 1. Blob metadata (system-generated)
    // 2. Field mapping (transform/rename)
    // 3. Index field (searchable)
    //
    // Common Blob Metadata Fields:
    // - metadata_storage_name: Filename (e.g., "california-dmv-2024.pdf")
    // - metadata_storage_path: Full blob URL
    // - metadata_storage_size: File size in bytes
    // - metadata_storage_last_modified: Last modified timestamp
    // - metadata_content_type: MIME type (e.g., "application/pdf")
    //
    // Mapping Functions:
    // - base64Encode(): Encode value as base64 (for IDs)
    // - base64Decode(): Decode base64 value
    // - extractTokenAtPosition(): Extract token from delimited string
    // - jsonArrayToStringCollection(): Convert JSON array to string collection
    //
    // Example: Extract state from filename
    // - Filename: "california-dmv-2024.pdf"
    // - Function: extractTokenAtPosition(metadata_storage_name, "-", 0)
    // - Result: "california"
    // ========================================================================
    fieldMappings: [
      // Map blob URL to document_id (using base64-encoded path)
      // Alternative: Use filename or custom metadata
      {
        sourceFieldName: 'metadata_storage_path'
        targetFieldName: 'document_id'
        mappingFunction: {
          name: 'base64Encode'
        }
      }
      
      // Map filename to index field for display
      {
        sourceFieldName: 'metadata_storage_name'
        targetFieldName: 'metadata_storage_name'
      }
    ]
    
    // ========================================================================
    // Output Field Mappings (Enrichment → Index Fields)
    // ========================================================================
    // Maps skillset outputs (enrichment tree) to index fields
    //
    // Enrichment Tree Structure:
    // /document
    //   /extracted_content (DocumentExtractionSkill output)
    //   /normalized_images/* (DocumentExtractionSkill output)
    //   /pages/* (TextSplitSkill output)
    //     /text (chunk text)
    //     /vector (AzureOpenAIEmbeddingSkill output)
    //
    // Mapping Context:
    // - Most mappings use /document/pages/* context (one index doc per chunk)
    // - Each chunk becomes a separate search document
    // - Enables fine-grained search and citation
    //
    // Complex Mappings:
    // - Arrays: /document/normalized_images/* → image_blob_urls (collection)
    // - Nested: /document/pages/*/vector → chunk_vector (per chunk)
    //
    // Note: Output field mappings are defined at the /document/pages/* level
    // because we create one index document per chunk (not per source document)
    // ========================================================================
    outputFieldMappings: [
      // Map text chunk to content field
      {
        sourceFieldName: '/document/pages/*/text'
        targetFieldName: 'content'
      }
      
      // Map embedding vector to chunk_vector field
      {
        sourceFieldName: '/document/pages/*/vector'
        targetFieldName: 'chunk_vector'
      }
      
      // Map page number (needs custom logic in skillset or field mapping)
      // This is simplified - actual implementation may need additional skill
      // {
      //   sourceFieldName: '/document/pages/*/pageNumber'
      //   targetFieldName: 'page_number'
      // }
      
      // Map normalized images to blob URLs (if knowledge store enabled)
      // This requires knowledge store configuration to generate URLs
      // {
      //   sourceFieldName: '/document/normalized_images/*/imageStoreUri'
      //   targetFieldName: 'image_blob_urls'
      // }
      
      // Map image descriptions to index field
      // {
      //   sourceFieldName: '/document/normalized_images/*/description'
      //   targetFieldName: 'image_descriptions'
      // }
      
      // Set has_related_images flag based on image count
      // This requires a custom skill or mapping function
      // {
      //   sourceFieldName: '/document/normalized_images/*/count'
      //   targetFieldName: 'has_related_images'
      // }
    ]
  }
}

// Outputs
// ----------------------------------------------------------------------------

@description('Resource ID of the created indexer')
output indexerId string = indexer.id

@description('Name of the created indexer')
output indexerName string = indexer.name

@description('Indexer execution mode (scheduled or on-demand)')
output executionMode string = enableSchedule ? 'scheduled' : 'on-demand'
