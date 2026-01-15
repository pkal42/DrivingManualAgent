// ============================================================================
// Azure AI Search Skillset Module
// ============================================================================
// This module defines the enrichment pipeline (skillset) for processing PDF
// driving manuals. The skillset extracts text and images, chunks content for
// optimal embedding generation, and creates vector representations.
//
// Skills Pipeline Flow:
// 1. DocumentExtractionSkill - Extract text/images from PDFs
// 2. TextSplitSkill - Chunk text into token-based segments
// 3. AzureOpenAIEmbeddingSkill - Generate embeddings for chunks
// 4. (Optional) Image Description - Generate descriptions for images
// ============================================================================

// Parameters
// ----------------------------------------------------------------------------

@description('Name of the Azure AI Search service where skillset will be created')
param searchServiceName string

@description('Azure OpenAI endpoint URL for embedding generation')
param openAiEndpoint string

@description('Name of the text embedding model deployment (text-embedding-3-large)')
param embeddingDeploymentName string = 'text-embedding-3-large'

@description('Name of the vision model deployment for image description (gpt-4o)')
param visionDeploymentName string = 'gpt-4o'

@description('Name for the skillset resource')
param skillsetName string = 'driving-manual-skillset'

@description('Enable image description skill using GPT-4o vision model')
param enableImageDescriptions bool = true

// Variables
// ----------------------------------------------------------------------------

// Knowledge store configuration for storing extracted images
var knowledgeStoreConfig = {
  // Storage connection string - should use managed identity in production
  // This connection is used to store extracted images in blob storage
  storageConnectionString: '@Microsoft.KeyVault(SecretUri=${storageAccountConnectionStringSecretUri})'
  
  // Projections define how enriched data is stored
  projections: [
    {
      // Files projection - stores binary data (images) in blob storage
      // Each normalized image is saved to the 'extracted-images' container
      files: [
        {
          // Store all normalized images extracted from PDFs
          storageContainer: 'extracted-images'
          source: '/document/normalized_images/*'
          // Generate unique blob names: {document-id}/{page-number}/{image-index}.jpg
          generatedKeyName: 'image_id'
        }
      ]
      // Object projection - stores enriched metadata as JSON blobs
      // Useful for debugging and auditing the enrichment process
      objects: [
        {
          storageContainer: 'enrichment-metadata'
          source: '/document/metadata'
          generatedKeyName: 'metadata_id'
        }
      ]
    }
  ]
}

// Resource Reference
// ----------------------------------------------------------------------------

// Reference to existing Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

// Skillset Resource
// ----------------------------------------------------------------------------

resource skillset 'Microsoft.Search/searchServices/skillsets@2024-06-01-preview' = {
  parent: searchService
  name: skillsetName
  properties: {
    description: 'Skillset for extracting and enriching content from PDF driving manuals with text chunking, image extraction, and embedding generation'
    
    // Skills are executed in order, with outputs from one skill becoming inputs to subsequent skills
    skills: [
      // ======================================================================
      // Skill 1: DocumentExtractionSkill
      // ======================================================================
      // Purpose: Extract text content and images from PDF files
      // 
      // Why this skill?
      // - Handles complex PDF layouts with text, images, tables
      // - Extracts images in normalized format for consistent processing
      // - Preserves document structure and metadata
      //
      // Configuration trade-offs:
      // - parsingMode "default" is optimal for general PDFs (vs "json" for structured data)
      // - dataToExtract "contentAndMetadata" provides both text and file properties
      // - imageAction "generateNormalizedImages" ensures consistent image dimensions
      //   (alternative: "generateNormalizedImagePerPage" for page-level extraction)
      // - Max dimensions 2000px balances quality vs. storage/processing costs
      //   (GPT-4o vision supports up to 2048px, higher res = more tokens)
      // ======================================================================
      {
        '@odata.type': '#Microsoft.Skills.Util.DocumentExtractionSkill'
        name: 'extract-content'
        description: 'Extract text and images from PDF driving manuals'
        context: '/document'
        
        // Input: Raw file data from blob storage
        inputs: [
          {
            name: 'file_data'
            source: '/document/file_data'
          }
        ]
        
        // Outputs: Extracted text and normalized images
        outputs: [
          {
            name: 'content'
            targetName: 'extracted_content'
          }
          {
            name: 'normalized_images'
            targetName: 'normalized_images'
          }
        ]
        
        // Configuration parameters
        configuration: {
          // Parsing mode for PDF documents (alternatives: "json", "text")
          parsingMode: 'default'
          
          // Extract both content and metadata from documents
          dataToExtract: 'contentAndMetadata'
          
          // Generate normalized images for consistent downstream processing
          // This resizes images to standard dimensions for vision models
          imageAction: 'generateNormalizedImages'
          
          // Maximum dimensions for extracted images (in pixels)
          // Trade-off: Higher resolution = better quality but more storage/tokens
          // 2000px is optimal for GPT-4o vision (max 2048px) while managing costs
          normalizedImageMaxWidth: 2000
          normalizedImageMaxHeight: 2000
        }
      }
      
      // ======================================================================
      // Skill 2: TextSplitSkill
      // ======================================================================
      // Purpose: Chunk extracted text into token-based segments for optimal
      //          embedding generation and retrieval
      //
      // Why this skill?
      // - Embeddings have token limits (text-embedding-3-large: 8191 tokens)
      // - Smaller chunks improve retrieval precision (find exact relevant content)
      // - Token-based splitting ensures accurate chunk sizes (vs character-based)
      //
      // Configuration trade-offs:
      // - textSplitMode "pages": Creates semantic chunks (vs "sentences")
      // - unit "azureOpenAITokens": Accurate token counting for embeddings
      //   (alternative: "characters" - less accurate, may exceed token limits)
      // - maximumPageLength 512 tokens: Balances context vs precision
      //   (smaller = more precise retrieval, larger = more context per chunk)
      // - pageOverlapLength 100 tokens: Maintains context across chunk boundaries
      //   (prevents information loss at chunk edges, ~20% overlap is standard)
      // - encoderModelName "cl100k_base": Tokenizer for text-embedding-3-large
      //   (must match embedding model's tokenizer)
      // ======================================================================
      {
        '@odata.type': '#Microsoft.Skills.Text.V3.SplitSkill'
        name: 'split-text'
        description: 'Split extracted text into token-based chunks optimized for embedding generation'
        context: '/document'
        
        // Input: Extracted text content from DocumentExtractionSkill
        inputs: [
          {
            name: 'text'
            source: '/document/extracted_content'
          }
        ]
        
        // Output: Array of text chunks (each will get its own embedding)
        outputs: [
          {
            name: 'textItems'
            targetName: 'pages'
          }
        ]
        
        // Configuration parameters
        configuration: {
          // Split mode: "pages" creates semantic chunks vs "sentences"
          textSplitMode: 'pages'
          
          // Use Azure OpenAI token counting for accurate chunk sizes
          // Critical for staying within embedding model's token limit
          unit: 'azureOpenAITokens'
          
          // Maximum chunk size in tokens
          // 512 tokens balances retrieval precision with context
          // (text-embedding-3-large supports up to 8191 tokens)
          maximumPageLength: 512
          
          // Overlap between consecutive chunks to maintain context
          // 100 tokens (~20% overlap) prevents information loss at boundaries
          pageOverlapLength: 100
          
          // Tokenizer configuration
          azureOpenAITokenizerParameters: {
            // Tokenizer for text-embedding-3-large (cl100k_base encoding)
            // Must match the embedding model's tokenizer
            encoderModelName: 'cl100k_base'
          }
        }
      }
      
      // ======================================================================
      // Skill 3: AzureOpenAIEmbeddingSkill
      // ======================================================================
      // Purpose: Generate vector embeddings for text chunks using
      //          text-embedding-3-large model
      //
      // Why this skill?
      // - Enables semantic/vector search (vs keyword-only search)
      // - text-embedding-3-large: State-of-the-art retrieval performance
      //   (3072 dimensions, better than text-embedding-ada-002)
      // - Essential for hybrid search (keyword + vector)
      //
      // Configuration trade-offs:
      // - Model choice: text-embedding-3-large vs text-embedding-3-small
      //   (large: better quality, 3072-dim; small: faster, cheaper, 1536-dim)
      // - Context: /document/pages/* processes each chunk independently
      //   (alternative: /document for single document embedding)
      // ======================================================================
      {
        '@odata.type': '#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill'
        name: 'generate-embeddings'
        description: 'Generate vector embeddings for text chunks using text-embedding-3-large'
        // Context: Process each text chunk independently
        context: '/document/pages/*'
        
        // Input: Text from each chunk
        inputs: [
          {
            name: 'text'
            source: '/document/pages/*/text'
          }
        ]
        
        // Output: 3072-dimensional vector embedding
        outputs: [
          {
            name: 'embedding'
            targetName: 'vector'
          }
        ]
        
        // Configuration parameters
        configuration: {
          // Azure OpenAI endpoint URL
          resourceUri: openAiEndpoint
          
          // Deployment name for text-embedding-3-large
          // This model provides state-of-the-art retrieval performance
          // with 3072-dimensional embeddings
          deploymentId: embeddingDeploymentName
          
          // Model version (optional, defaults to latest)
          // modelName: 'text-embedding-3-large'
        }
      }
    ]
    
    // Conditionally add image description skill if enabled
    // This is optional and adds cost (GPT-4o vision API calls)
    // but improves multimodal search capabilities
    #disable-next-line BCP037 // Disable warning for conditional array concatenation
    skills: union(skills, enableImageDescriptions ? [
      // ======================================================================
      // Skill 4: Image Description (Optional)
      // ======================================================================
      // Purpose: Generate text descriptions of extracted images using GPT-4o
      //          vision model for multimodal search
      //
      // Why this skill?
      // - Enables text-based search for image content
      // - Provides context for images in search results
      // - Can generate embeddings for image descriptions
      //
      // Configuration trade-offs:
      // - GPT-4o vision: High-quality descriptions but costly
      //   (alternative: GPT-4o-mini for lower cost)
      // - Prompt design affects description quality and consistency
      // - Processing time increases with image count
      //
      // Multimodal Strategy:
      // - Generate text descriptions of images
      // - Embed descriptions for semantic search
      // - Link images to relevant text chunks via page numbers
      // - Return images alongside text in search results
      // ======================================================================
      {
        '@odata.type': '#Microsoft.Skills.Vision.ImageAnalysisSkill'
        name: 'describe-images'
        description: 'Generate text descriptions of extracted images using GPT-4o vision'
        // Context: Process each extracted image independently
        context: '/document/normalized_images/*'
        
        // Input: Image data from DocumentExtractionSkill
        inputs: [
          {
            name: 'image'
            source: '/document/normalized_images/*'
          }
        ]
        
        // Output: Text description of image
        outputs: [
          {
            name: 'description'
            targetName: 'description'
          }
        ]
        
        // Configuration parameters
        configuration: {
          // Azure OpenAI endpoint for vision model
          resourceUri: openAiEndpoint
          
          // GPT-4o deployment for vision capabilities
          deploymentId: visionDeploymentName
          
          // Prompt for generating image descriptions
          // Customize this for driving manual-specific context
          prompt: 'Describe this image from a driving manual in detail, focusing on road signs, traffic situations, vehicle components, and safety information.'
          
          // Visual features to extract (description, tags, objects, etc.)
          visualFeatures: ['description']
        }
      }
      
      // Generate embeddings for image descriptions
      {
        '@odata.type': '#Microsoft.Skills.Text.AzureOpenAIEmbeddingSkill'
        name: 'generate-image-embeddings'
        description: 'Generate vector embeddings for image descriptions'
        context: '/document/normalized_images/*'
        
        inputs: [
          {
            name: 'text'
            source: '/document/normalized_images/*/description'
          }
        ]
        
        outputs: [
          {
            name: 'embedding'
            targetName: 'image_vector'
          }
        ]
        
        configuration: {
          resourceUri: openAiEndpoint
          deploymentId: embeddingDeploymentName
        }
      }
    ] : [])
    
    // Knowledge Store configuration (optional)
    // Stores enriched data (images, metadata) in blob storage
    // Useful for debugging, auditing, and alternative access patterns
    // Comment out if not using knowledge store
    // knowledgeStore: knowledgeStoreConfig
    
    // Cognitive Services connection
    // Uses managed identity for authentication (no keys required)
    cognitiveServices: {
      '@odata.type': '#Microsoft.Azure.Search.CognitiveServicesByKey'
      // In production, use managed identity via AI Foundry project
      // This is a placeholder - actual connection configured via portal/API
    }
  }
}

// Outputs
// ----------------------------------------------------------------------------

@description('Resource ID of the created skillset')
output skillsetId string = skillset.id

@description('Name of the created skillset')
output skillsetName string = skillset.name
