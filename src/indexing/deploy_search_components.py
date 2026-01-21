"""
Azure AI Search Components Deployment using Python SDK.

This script uses the Azure AI Search SDK to create and manage:
- Search Index with vector search configuration
- Skillset with document extraction, chunking, and embedding generation
- Data Source connected to Azure Blob Storage
- Indexer to orchestrate the enrichment pipeline

Advantages over REST API:
- Type-safe operations with IntelliSense support
- Better error handling and validation
- Automatic retry logic
- Easier to test and maintain

Usage:
    # Deploy all components
    python deploy_search_components.py --deploy-all
    
    # Reset and run indexer
    python deploy_search_components.py --reset-indexer --run-indexer
    
    # Update only the indexer configuration
    python deploy_search_components.py --update-indexer

Requirements:
    azure-search-documents>=11.6.0
    azure-identity>=1.12.0
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from azure.core.exceptions import ResourceNotFoundError, ResourceExistsError
from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.search.documents.indexes.models import (
    # Index models
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    HnswParameters,
    VectorSearchAlgorithmMetric,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
    
    # Skillset models
    SearchIndexerSkillset,
    DocumentExtractionSkill,
    ShaperSkill,
    SplitSkill,
    AzureOpenAIEmbeddingSkill,
    InputFieldMappingEntry,
    OutputFieldMappingEntry,
    TextSplitMode,
    DefaultCognitiveServicesAccount,
    SearchIndexerDataUserAssignedIdentity,  # For system-assigned managed identity auth
    
    # Data source models
    SearchIndexerDataSourceConnection,
    SearchIndexerDataContainer,
    
    # Indexer models
    SearchIndexer,
    FieldMapping,
    FieldMappingFunction,
    IndexingParameters,
    IndexingParametersConfiguration,
    HighWaterMarkChangeDetectionPolicy,
    SoftDeleteColumnDeletionDetectionPolicy,
    
    # Projections
    SearchIndexerIndexProjection,
    SearchIndexerIndexProjectionSelector,
    SearchIndexerIndexProjectionsParameters,
    IndexProjectionMode,
    ImageAnalysisSkill,
    VisualFeature,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Version - Use the latest stable version with full vector search support
API_VERSION = "2025-09-01"

# Default configuration values
DEFAULT_CONFIG = {
    "subscription_id": "0367ae6b-bbd6-429d-a6e9-7019fb08ff08",
    "resource_group": "rg-drvagnt2-dev-eastus2",
    "search_service": "srch-drvagnt2-dev-7vczbz",
    "search_service_name": "srch-drvagnt2-dev-7vczbz",
    "index_name": "driving-manual-index",
    "skillset_name": "driving-manual-skillset",
    "datasource_name": "driving-manual-datasource",
    "indexer_name": "driving-manual-indexer",
    "storage_account": "stdrvagd7vczbz",
    "storage_container": "pdfs",
    "storage_resource_id": "/subscriptions/0367ae6b-bbd6-429d-a6e9-7019fb08ff08/resourceGroups/rg-drvagnt2-dev-eastus2/providers/Microsoft.Storage/storageAccounts/stdrvagd7vczbz",
    "aoai_endpoint": "https://fdry-drvagnt2-dev-7vczbz.cognitiveservices.azure.com/",
    "embedding_deployment": "text-embedding-3-large",
    "embedding_dimensions": 3072,
    "chunk_size": 512,
    "chunk_overlap": 100,
}


class SearchComponentsDeployer:
    """Deploys and manages Azure AI Search components using the Python SDK."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the deployer with configuration.
        
        Args:
            config: Optional configuration dictionary. Uses DEFAULT_CONFIG if not provided.
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.search_endpoint = f"https://{self.config['search_service_name']}.search.windows.net"
        
        # Initialize credential (uses DefaultAzureCredential for managed identity)
        self.credential = DefaultAzureCredential()
        
        # Initialize clients with specified API version
        self.index_client = SearchIndexClient(
            endpoint=self.search_endpoint,
            credential=self.credential,
            api_version=API_VERSION
        )
        
        self.indexer_client = SearchIndexerClient(
            endpoint=self.search_endpoint,
            credential=self.credential,
            api_version=API_VERSION
        )
        
        logger.info(f"Initialized deployer for search service: {self.config['search_service_name']}")
        logger.info(f"Using API version: {API_VERSION}")
    
    def create_or_update_index(self) -> SearchIndex:
        """
        Create or update the search index with vector search configuration.
        
        Returns:
            The created or updated SearchIndex object.
        """
        logger.info(f"Creating/updating index: {self.config['index_name']}")
        
        # Delete existing index when schema changes require it
        try:
            self.index_client.delete_index(self.config['index_name'])
            logger.info("Deleted existing index to apply schema changes")
        except ResourceNotFoundError:
            pass
        except Exception as exc:
            logger.warning(f"Could not delete index (may not exist): {exc}")

        # Define index fields
        fields = [
            SearchField(
                name="chunk_id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
                retrievable=True
            ),
            SearchField(
                name="parent_id",
                type=SearchFieldDataType.String,
                filterable=True,
                retrievable=True
            ),
            SearchField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
                retrievable=True,
                filterable=False,  # keep search-only to avoid large single-term indexing
                sortable=False,
                facetable=False,
                analyzer_name="standard.lucene"
            ),
            SearchField(
                name="chunk_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.config['embedding_dimensions'],
                vector_search_profile_name="default-vector-profile"
            ),
            SearchField(
                name="document_id",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            SearchField(
                name="state",
                type=SearchFieldDataType.String,
                filterable=True,
                sortable=True,
                facetable=True,
                retrievable=True
            ),
            SearchField(
                name="page_number",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
                retrievable=True
            ),
            SearchField(
                name="metadata_storage_name",
                type=SearchFieldDataType.String,
                searchable=True,
                filterable=True,
                sortable=True,
                retrievable=True
            ),
            SearchField(
                name="source_type",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
                retrievable=True
            ),
        ]
        
        # Configure vector search with HNSW algorithm
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="hnsw-config",
                    parameters=HnswParameters(
                        m=4,
                        ef_construction=400,
                        metric=VectorSearchAlgorithmMetric.COSINE
                    )
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="default-vector-profile",
                    algorithm_configuration_name="hnsw-config"
                )
            ]
        )
        
        # Configure semantic search (optional but recommended)
        semantic_config = SemanticConfiguration(
            name="default-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                content_fields=[SemanticField(field_name="content")],
                keywords_fields=[SemanticField(field_name="document_id")]
            )
        )
        
        semantic_search = SemanticSearch(
            configurations=[semantic_config]
        )
        
        # Create the index
        index = SearchIndex(
            name=self.config['index_name'],
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        try:
            result = self.index_client.create_or_update_index(index)
            logger.info(f"✓ Index '{self.config['index_name']}' created/updated successfully")
            return result
        except Exception as e:
            logger.error(f"✗ Failed to create/update index: {e}")
            raise
    
    def create_or_update_skillset(self) -> SearchIndexerSkillset:
        """
        Create or update the skillset with text splitting, embedding, and index projections.
        
        Returns:
            The created or updated SearchIndexerSkillset object.
        """
        logger.info(f"Creating/updating skillset: {self.config['skillset_name']}")
        
        # Skill 1: Text Split - Split content into chunks
        # We process /document/content directly (standard PDF extraction)
        text_split_skill = SplitSkill(
            name="split-text",
            description="Split extracted text into page chunks optimized for embedding generation",
            context="/document",
            text_split_mode=TextSplitMode.PAGES,
            maximum_page_length=self.config['chunk_size'],
            page_overlap_length=self.config['chunk_overlap'],
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/content")
            ],
            outputs=[
                OutputFieldMappingEntry(name="textItems", target_name="pages")
            ]
        )
        
        # Skill 3.1: Embedding - Text Chunks
        embedding_skill_text = AzureOpenAIEmbeddingSkill(
            name="embed-text-chunks",
            description="Generate embeddings for text chunks",
            context="/document/pages/*",
            resource_url=self.config['aoai_endpoint'],
            deployment_name=self.config['embedding_deployment'],
            model_name=self.config['embedding_deployment'],
            dimensions=self.config['embedding_dimensions'],
            inputs=[
                InputFieldMappingEntry(name="text", source="/document/pages/*")
            ],
            outputs=[
                OutputFieldMappingEntry(name="embedding", target_name="vector")
            ]
        )
        
        # Skill 1.5: Shaper (Best Practice for RAG)
        # Creates a structured object for each chunk to be projected
        shaper_skill = ShaperSkill(
            name="chunk-shaper",
            description="Shape text chunks into structured objects",
            context="/document/pages/*",
            inputs=[
                InputFieldMappingEntry(name="content", source="/document/pages/*"),
                InputFieldMappingEntry(name="chunk_vector", source="/document/pages/*/vector"),
                InputFieldMappingEntry(name="document_id", source="/document/metadata_storage_name"),
                InputFieldMappingEntry(name="source_type", source="='text_chunk'")
            ],
            outputs=[
                OutputFieldMappingEntry(name="output", target_name="chunk_projection")
            ]
        )
        
        # Index Projections: Map chunks and images to the search index
        index_projections = SearchIndexerIndexProjection(
            selectors=[
                # Selector for Text Chunks
                SearchIndexerIndexProjectionSelector(
                    target_index_name=self.config['index_name'],
                    parent_key_field_name="parent_id",
                    source_context="/document/pages/*/chunk_projection",
                    mappings=[
                        InputFieldMappingEntry(name="content", source="content"),
                        InputFieldMappingEntry(name="chunk_vector", source="chunk_vector"),
                        InputFieldMappingEntry(name="document_id", source="document_id"),
                        InputFieldMappingEntry(name="metadata_storage_name", source="document_id"),
                        InputFieldMappingEntry(name="source_type", source="source_type"),
                    ]
                ),
                # Selector for Images - COMMENTED OUT
                # ...
            ],
            parameters=SearchIndexerIndexProjectionsParameters(
                projection_mode=IndexProjectionMode.SKIP_INDEXING_PARENT_DOCUMENTS
            )
        )
        
        # Create skillset with all skills and projections
        skillset = SearchIndexerSkillset(
            name=self.config['skillset_name'],
            description="Skillset for extracting, verbalizing images, and enriching content from PDF driving manuals",
            skills=[text_split_skill, embedding_skill_text, shaper_skill], # Added Shaper
            index_projections=index_projections,
            cognitive_services_account=DefaultCognitiveServicesAccount()
        )
        
        try:
            result = self.indexer_client.create_or_update_skillset(skillset)
            logger.info(f"✓ Skillset '{self.config['skillset_name']}' created/updated successfully")
            return result
        except Exception as e:
            logger.error(f"✗ Failed to create/update skillset: {e}")
            raise
    
    def create_or_update_datasource(self) -> SearchIndexerDataSourceConnection:
        """
        Create or update the data source connection to Azure Blob Storage.
        
        Returns:
            The created or updated SearchIndexerDataSourceConnection object.
        """
        logger.info(f"Creating/updating data source: {self.config['datasource_name']}")
        
        # Use managed identity authentication (more secure than connection strings)
        connection_string = f"ResourceId={self.config['storage_resource_id']};Authentication=ManagedIdentity;"
        
        # Configure change detection to track modified files
        # This enables incremental indexing (only process new/changed files)
        change_detection_policy = HighWaterMarkChangeDetectionPolicy(
            high_water_mark_column_name="metadata_storage_last_modified"
        )
        
        # Configure soft delete detection (optional)
        deletion_detection_policy = SoftDeleteColumnDeletionDetectionPolicy(
            soft_delete_column_name="isDeleted",
            soft_delete_marker_value="true"
        )
        
        # Create data source
        datasource = SearchIndexerDataSourceConnection(
            name=self.config['datasource_name'],
            type="azureblob",
            connection_string=connection_string,
            container=SearchIndexerDataContainer(name=self.config['storage_container']),
            description="Blob storage data source for PDF driving manuals",
            data_change_detection_policy=change_detection_policy,
            data_deletion_detection_policy=deletion_detection_policy
        )
        
        try:
            result = self.indexer_client.create_or_update_data_source_connection(datasource)
            logger.info(f"✓ Data source '{self.config['datasource_name']}' created/updated successfully")
            return result
        except Exception as e:
            logger.error(f"✗ Failed to create/update data source: {e}")
            raise
    
    def create_or_update_indexer(self) -> SearchIndexer:
        """
        Create or update the indexer with proper configuration.
        
        FIXES APPLIED:
        1. Using index projections instead of output field mappings
        2. Removed unnecessary DocumentExtraction configuration
        3. Force delete and recreate to ensure field mappings are applied
        
        Returns:
            The created or updated SearchIndexer object.
        """
        logger.info(f"Creating/updating indexer: {self.config['indexer_name']}")
        
        # Force delete to ensure clean configuration (fixes stubborn field mappings)
        try:
            self.indexer_client.delete_indexer(self.config['indexer_name'])
            logger.info("Deleted existing indexer to ensure clean update")
        except ResourceNotFoundError:
            pass
        except Exception as e:
            logger.warning(f"Could not delete indexer (might not exist): {e}")

        # Indexer parameters configuration
        indexing_config = {
            "dataToExtract": "contentAndMetadata",
            "parsingMode": "default",
            # "imageAction": "generateNormalizedImages", # Disabled to save costs and simplify debugging
            "indexedFileNameExtensions": ".pdf",
            "allowSkillsetToReadFileData": True
        }
        
        indexing_parameters = IndexingParameters(
            batch_size=1,  # Process one document at a time for detailed error tracking
            max_failed_items=-1,  # Allow all items to fail before stopping
            max_failed_items_per_batch=-1,
            configuration=indexing_config
        )
        
        # Field mappings
        # Explicitly map the key field with base64 encoding to prevent invalid character errors
        field_mappings = [
            FieldMapping(
                source_field_name="metadata_storage_path",
                target_field_name="chunk_id",
                mapping_function=FieldMappingFunction(name="base64Encode")
            )
        ]
        
        # Create indexer
        # Note: We use IndexProjections in the skillset, but the field_mappings
        # help ensure the parent document key is valid during processing.
        indexer = SearchIndexer(
            name=self.config['indexer_name'],
            description="Indexer for processing PDF driving manuals with text extraction, chunking, and embedding generation",
            data_source_name=self.config['datasource_name'],
            target_index_name=self.config['index_name'],
            skillset_name=self.config['skillset_name'],
            parameters=indexing_parameters,
            field_mappings=field_mappings
        )
        
        try:
            result = self.indexer_client.create_or_update_indexer(indexer)
            logger.info(f"✓ Indexer '{self.config['indexer_name']}' created/updated successfully")
            return result
        except Exception as e:
            logger.error(f"✗ Failed to create/update indexer: {e}")
            raise
    

    def deploy_all(self) -> bool:
        """
        Deploy all search components in the correct order.
        
        Order is important:
        1. Index (must exist before indexer can reference it)
        2. Skillset (must exist before indexer can reference it)
        3. Data Source (must exist before indexer can reference it)
        4. Indexer (references all above components)
        
        Returns:
            True if all components deployed successfully
        """
        logger.info("=" * 60)
        logger.info("Starting deployment of all search components")
        logger.info("=" * 60)
        
        try:
            # Step 1: Create/update index
            self.create_or_update_index()
            
            # Step 2: Create/update skillset
            self.create_or_update_skillset()
            
            # Step 3: Create/update data source
            self.create_or_update_datasource()
            
            # Step 4: Create/update indexer
            self.create_or_update_indexer()
            
            logger.info("=" * 60)
            logger.info("✓ All components deployed successfully!")
            logger.info("=" * 60)
            logger.info("\nNext steps:")
            logger.info("  1. Ensure PDF files are uploaded to blob storage:")
            logger.info("     Container: pdfs")
            logger.info("     Storage: stdrvagd7vczbz")
            logger.info("")
            logger.info("  2. Run the indexer pipeline:")
            logger.info("     python src/indexing/run_indexer_pipeline.py --reset")
            
            return True
            
        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Deploy and manage Azure AI Search components using Python SDK"
    )
    
    # Deployment options
    parser.add_argument(
        "--deploy-all",
        action="store_true",
        help="Deploy all search components (index, skillset, datasource, indexer)"
    )
    parser.add_argument(
        "--update-index",
        action="store_true",
        help="Update only the search index"
    )
    parser.add_argument(
        "--update-skillset",
        action="store_true",
        help="Update only the skillset"
    )
    parser.add_argument(
        "--update-datasource",
        action="store_true",
        help="Update only the data source"
    )
    parser.add_argument(
        "--update-indexer",
        action="store_true",
        help="Update only the indexer"
    )
    

    
    # Configuration overrides
    parser.add_argument(
        "--search-service",
        help=f"Search service name (default: {DEFAULT_CONFIG['search_service_name']})"
    )
    
    args = parser.parse_args()
    
    # Build configuration
    config = DEFAULT_CONFIG.copy()
    if args.search_service:
        config['search_service_name'] = args.search_service
    
    # Initialize deployer
    deployer = SearchComponentsDeployer(config)
    
    try:
        # Handle deployment operations
        if args.deploy_all:
            success = deployer.deploy_all()
            sys.exit(0 if success else 1)
        
        if args.update_index:
            deployer.create_or_update_index()
        
        if args.update_skillset:
            deployer.create_or_update_skillset()
        
        if args.update_datasource:
            deployer.create_or_update_datasource()
        
        if args.update_indexer:
            deployer.create_or_update_indexer()

        # If no arguments provided, show help
        if not any(vars(args).values()):
            parser.print_help()
    
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
