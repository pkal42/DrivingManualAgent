// ============================================================================
// Azure AI Search Index Module
// ============================================================================
// This module defines the search index schema for the driving manual chunks
// with hybrid search capabilities (keyword + vector + semantic search).
//
// Index Design:
// - Hybrid search: Combines keyword matching with vector similarity
// - Vector search: HNSW algorithm for efficient approximate nearest neighbor
// - Semantic search: AI-powered reranking for improved relevance
// - Filterable fields: Enable filtering by state, document, page, etc.
// ============================================================================

// Parameters
// ----------------------------------------------------------------------------

@description('Name of the Azure AI Search service where index will be created')
param searchServiceName string

@description('Name for the search index resource')
param indexName string = 'driving-manual-index'

@description('Dimensions for vector embeddings (text-embedding-3-large = 3072)')
param vectorDimensions int = 3072

@description('Enable semantic search configuration for AI-powered reranking')
param enableSemanticSearch bool = true

// Resource Reference
// ----------------------------------------------------------------------------

// Reference to existing Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

// Search Index Resource
// ----------------------------------------------------------------------------

resource searchIndex 'Microsoft.Search/searchServices/indexes@2024-06-01-preview' = {
  parent: searchService
  name: indexName
  properties: {
    // ========================================================================
    // Field Definitions
    // ========================================================================
    // Fields define the schema for indexed documents with search, filter,
    // facet, and sort capabilities.
    //
    // Field Attribute Explanations:
    // - key: Unique identifier for each document (required, exactly one)
    // - searchable: Full-text searchable via keyword queries
    // - filterable: Can be used in $filter expressions (e.g., state eq 'California')
    // - sortable: Can be used in $orderby expressions
    // - facetable: Can be used for faceted navigation (e.g., count by state)
    // - retrievable: Returned in search results (default: true)
    // ========================================================================
    fields: [
      // ======================================================================
      // Field: chunk_id (Key)
      // ======================================================================
      // Unique identifier for each text chunk
      // Format: {document_id}_{page_number}_{chunk_index}
      // Example: "california-manual_5_2" (document ID, page 5, chunk 2)
      //
      // Trade-offs:
      // - Composite key enables tracking chunk provenance
      // - String type allows human-readable IDs (vs GUID)
      // - Filterable enables exact lookups by ID
      // ======================================================================
      {
        name: 'chunk_id'
        type: 'Edm.String'
        key: true
        searchable: false
        filterable: true
        sortable: false
        facetable: false
        retrievable: true
      }
      
      // ======================================================================
      // Field: content (Text Content)
      // ======================================================================
      // The actual text content of the chunk for keyword search
      //
      // Trade-offs:
      // - Searchable: Enables full-text search with BM25 ranking
      // - Not filterable: Large text fields not suitable for filters
      // - Analyzer: 'standard.lucene' for English text (alternatives: 'en.microsoft')
      //   - Lowercasing, stop word removal, stemming
      //   - Trade-off: Better recall vs exact matching
      // ======================================================================
      {
        name: 'content'
        type: 'Edm.String'
        searchable: true
        filterable: false
        sortable: false
        facetable: false
        retrievable: true
        analyzer: 'standard.lucene'
      }
      
      // ======================================================================
      // Field: chunk_vector (Vector Embedding)
      // ======================================================================
      // 3072-dimensional vector embedding from text-embedding-3-large
      // Used for semantic/vector search to find similar content
      //
      // Vector Search Benefits:
      // - Semantic similarity: Finds conceptually similar content (not just keywords)
      // - Cross-lingual: Can match queries in different phrasing
      // - Handles synonyms and context better than keyword search
      //
      // Trade-offs:
      // - Collection(Edm.Single): Array of floating-point values
      // - Dimensions: 3072 (text-embedding-3-large) vs 1536 (ada-002)
      //   - Higher dimensions = better quality but more storage/compute
      // - Not retrievable: Embeddings are large, not useful in results
      // ======================================================================
      {
        name: 'chunk_vector'
        type: 'Collection(Edm.Single)'
        searchable: true
        filterable: false
        sortable: false
        facetable: false
        retrievable: false
        // Vector search configuration (HNSW algorithm)
        vectorSearchDimensions: vectorDimensions
        vectorSearchProfileName: 'default-vector-profile'
      }
      
      // ======================================================================
      // Field: document_id (Source Document)
      // ======================================================================
      // Identifier for the source PDF document
      // Format: "california-dmv-2024" or "texas-dps-2023"
      //
      // Use Cases:
      // - Filter results to specific state manual
      // - Track document provenance for citations
      // - Enable faceted navigation by document
      //
      // Trade-offs:
      // - Filterable: Enable queries like "find in California manual only"
      // - Facetable: Show document distribution in results
      // - Searchable: Allow searching by document name
      // ======================================================================
      {
        name: 'document_id'
        type: 'Edm.String'
        searchable: true
        filterable: true
        sortable: true
        facetable: true
        retrievable: true
      }
      
      // ======================================================================
      // Field: state (US State)
      // ======================================================================
      // US state for the driving manual (e.g., "California", "Texas")
      // Normalized state names for consistent filtering
      //
      // Use Cases:
      // - Filter results by state: "Find Texas driving laws"
      // - Faceted navigation: "Show results by state"
      // - Multi-state comparison: "Compare CA and TX rules"
      //
      // Trade-offs:
      // - Filterable: Critical for state-specific queries
      // - Facetable: Enable state distribution in UI
      // - Not searchable: Use for exact matching only
      // ======================================================================
      {
        name: 'state'
        type: 'Edm.String'
        searchable: false
        filterable: true
        sortable: true
        facetable: true
        retrievable: true
      }
      
      // ======================================================================
      // Field: page_number (Page Reference)
      // ======================================================================
      // Page number in the source PDF document (1-based indexing)
      //
      // Use Cases:
      // - Provide precise citations: "California DMV Manual, Page 42"
      // - Sort results by page order
      // - Filter to specific page ranges
      //
      // Trade-offs:
      // - Int32: Efficient storage and sorting
      // - Filterable: Enable range queries (e.g., pages 1-50)
      // - Sortable: Display results in document order
      // ======================================================================
      {
        name: 'page_number'
        type: 'Edm.Int32'
        searchable: false
        filterable: true
        sortable: true
        facetable: false
        retrievable: true
      }
      
      // ======================================================================
      // Field: has_related_images (Image Flag)
      // ======================================================================
      // Boolean flag indicating if this chunk has related images
      //
      // Use Cases:
      // - Prioritize chunks with visual content
      // - Filter to only image-containing results
      // - Improve multimodal responses
      //
      // Trade-offs:
      // - Boolean: Simple, efficient filtering
      // - Set during indexing based on image extraction
      // ======================================================================
      {
        name: 'has_related_images'
        type: 'Edm.Boolean'
        searchable: false
        filterable: true
        sortable: false
        facetable: true
        retrievable: true
      }
      
      // ======================================================================
      // Field: image_blob_urls (Image References)
      // ======================================================================
      // Array of blob storage URLs for images extracted from this chunk
      // Format: ["https://<storage>.blob.core.windows.net/extracted-images/doc1/page5/img1.jpg"]
      //
      // Use Cases:
      // - Retrieve images for display in search results
      // - Support multimodal agent responses
      // - Enable image-based citations
      //
      // Trade-offs:
      // - Collection(Edm.String): Multiple images per chunk
      // - Retrievable: Required for displaying images
      // - Not searchable: URLs not useful for search
      // ======================================================================
      {
        name: 'image_blob_urls'
        type: 'Collection(Edm.String)'
        searchable: false
        filterable: false
        sortable: false
        facetable: false
        retrievable: true
      }
      
      // ======================================================================
      // Field: image_descriptions (Image Text Descriptions)
      // ======================================================================
      // Text descriptions of images generated by GPT-4o vision
      // Array with one description per image
      //
      // Use Cases:
      // - Search for images by content description
      // - Provide alt-text for accessibility
      // - Improve context understanding
      //
      // Trade-offs:
      // - Collection(Edm.String): Multiple descriptions per chunk
      // - Searchable: Enable finding images via text search
      // - Generated by vision model: Cost vs quality trade-off
      // ======================================================================
      {
        name: 'image_descriptions'
        type: 'Collection(Edm.String)'
        searchable: true
        filterable: false
        sortable: false
        facetable: false
        retrievable: true
      }
      
      // ======================================================================
      // Field: image_vectors (Image Embeddings) - Optional
      // ======================================================================
      // Vector embeddings of image descriptions for semantic search
      // Note: This is a flattened array (all image vectors concatenated)
      //
      // Use Cases:
      // - Semantic search across image content
      // - Find visually similar content via text descriptions
      // - Multimodal retrieval
      //
      // Trade-offs:
      // - Complex: Multiple vectors per chunk (not well-supported)
      // - Alternative: Create separate index for images
      // - Commented out by default due to complexity
      // ======================================================================
      // {
      //   name: 'image_vectors'
      //   type: 'Collection(Edm.Single)'
      //   searchable: true
      //   filterable: false
      //   sortable: false
      //   facetable: false
      //   retrievable: false
      //   vectorSearchDimensions: vectorDimensions
      //   vectorSearchProfileName: 'default-vector-profile'
      // }
      
      // ======================================================================
      // Field: metadata_storage_name (Original Filename)
      // ======================================================================
      // Original filename of the PDF (e.g., "california-dmv-handbook-2024.pdf")
      //
      // Use Cases:
      // - Display source document in results
      // - Track document versions
      // - Debugging and auditing
      //
      // Trade-offs:
      // - Searchable: Enable finding documents by filename
      // - Filterable: Enable exact filename matching
      // ======================================================================
      {
        name: 'metadata_storage_name'
        type: 'Edm.String'
        searchable: true
        filterable: true
        sortable: true
        facetable: false
        retrievable: true
      }
    ]
    
    // ========================================================================
    // Vector Search Configuration
    // ========================================================================
    // Defines how vector similarity search is performed using HNSW algorithm
    //
    // HNSW (Hierarchical Navigable Small World):
    // - Approximate nearest neighbor search (vs exact brute force)
    // - Trade-off: Speed vs accuracy
    // - Industry standard for vector search at scale
    //
    // Parameters Explained:
    // - m: Number of bi-directional links per node (default: 4)
    //   - Higher m = better recall but more memory
    //   - Range: 4-10, recommended: 4 for most cases
    // - efConstruction: Size of dynamic candidate list during index build
    //   - Higher = better quality graph but slower indexing
    //   - Range: 100-1000, recommended: 400 for balanced quality
    //
    // Note: efSearch is a query-time parameter (not configured in index schema)
    // - Specified per query to tune recall vs latency
    // - Higher = better recall but slower queries
    // - Recommended: 500 for high accuracy (adjust per query needs)
    //
    // Similarity Metric:
    // - cosine: Measures angle between vectors (standard for embeddings)
    //   - Range: -1 to 1 (1 = identical, -1 = opposite)
    //   - Alternative: dotProduct, euclidean
    // ========================================================================
    vectorSearch: {
      // Algorithm configurations
      algorithms: [
        {
          name: 'hnsw-config'
          kind: 'hnsw'
          hnswParameters: {
            // Number of bi-directional links created for each node
            // Trade-off: Higher m = better recall but more memory
            // m=4 is optimal for most scenarios (balanced quality/cost)
            m: 4
            
            // Dynamic candidate list size during index construction
            // Trade-off: Higher = better graph quality but slower indexing
            // 400 provides good quality without excessive build time
            efConstruction: 400
            
            // Distance metric for vector similarity
            // cosine: Standard for embedding vectors (angle-based similarity)
            metric: 'cosine'
          }
        }
      ]
      
      // Vector search profiles define algorithm + vectorizer
      profiles: [
        {
          name: 'default-vector-profile'
          algorithm: 'hnsw-config'
          // No vectorizer needed (embeddings pre-computed in skillset)
          // efSearch is a query-time parameter, not configured here
        }
      ]
    }
    
    // ========================================================================
    // Semantic Search Configuration (Optional)
    // ========================================================================
    // AI-powered reranking of search results for improved relevance
    //
    // How it works:
    // 1. Initial retrieval: Hybrid search (keyword + vector)
    // 2. Reranking: AI model re-scores top results for relevance
    // 3. Response: Semantic captions and answers extracted
    //
    // Benefits:
    // - Improved ranking quality beyond keyword/vector scores
    // - Semantic captions: Highlighted relevant passages
    // - Semantic answers: Direct answers to questions
    //
    // Trade-offs:
    // - Additional cost per query
    // - Slight latency increase
    // - Requires S1+ tier (not available on Free tier)
    //
    // Configuration:
    // - prioritizedFields: Define which fields are most important
    //   - titleField: Short title/summary (high weight)
    //   - contentFields: Main text content (medium weight)
    //   - keywordFields: Metadata for context (low weight)
    // ========================================================================
    semantic: enableSemanticSearch ? {
      configurations: [
        {
          name: 'default-semantic-config'
          prioritizedFields: {
            // Title field: Highest weight in ranking
            // Using document_id as title (could use custom title field)
            titleField: {
              fieldName: 'document_id'
            }
            
            // Content fields: Primary text for semantic understanding
            contentFields: [
              {
                fieldName: 'content'
              }
            ]
            
            // Keyword fields: Additional context for ranking
            keywordsFields: [
              {
                fieldName: 'state'
              }
              {
                fieldName: 'metadata_storage_name'
              }
            ]
          }
        }
      ]
    } : null
  }
}

// Outputs
// ----------------------------------------------------------------------------

@description('Resource ID of the created search index')
output indexId string = searchIndex.id

@description('Name of the created search index')
output indexName string = searchIndex.name
