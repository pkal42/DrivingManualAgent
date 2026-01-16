"""
Document indexing pipeline using Azure AI SDK.

This script downloads PDFs from Azure Blob Storage, extracts and chunks text,
generates embeddings using Azure OpenAI, and uploads to Azure AI Search.

Uses managed identity authentication throughout.
"""

import base64
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
import sys

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from openai import AzureOpenAI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentIndexer:
    """Indexes PDF documents from blob storage into Azure AI Search with embeddings."""
    
    def __init__(
        self,
        storage_account: str,
        container_name: str,
        document_intelligence_endpoint: str,
        foundry_endpoint: str,
        embedding_deployment: str,
        search_endpoint: str,
        index_name: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Initialize the document indexer.
        
        Args:
            storage_account: Storage account name (e.g., 'stdrvagdbvxlqv')
            container_name: Blob container name (e.g., 'pdfs')
            foundry_endpoint: Azure AI Foundry endpoint
            embedding_deployment: Embedding model deployment name
            search_endpoint: Azure AI Search endpoint
            index_name: Search index name
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Token overlap between chunks
        """
        self.container_name = container_name
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.index_name = index_name
        
        # Initialize credential
        self.credential = DefaultAzureCredential()
        
        # Initialize blob client
        blob_url = f"https://{storage_account}.blob.core.windows.net"
        self.blob_service = BlobServiceClient(blob_url, credential=self.credential)
        self.container_client = self.blob_service.get_container_client(container_name)
        
        # Initialize Azure OpenAI client for embeddings with managed identity
        token_provider = get_bearer_token_provider(
            self.credential, 
            "https://cognitiveservices.azure.com/.default"
        )
        self.openai_client = AzureOpenAI(
            azure_endpoint=foundry_endpoint,
            azure_ad_token_provider=token_provider,
            api_version="2024-02-01"
        )
        self.embedding_deployment = embedding_deployment
        
        # Initialize Document Intelligence client
        self.doc_intelligence_client = DocumentIntelligenceClient(
            endpoint=document_intelligence_endpoint,
            credential=self.credential
        )
        self.storage_account = storage_account
        
        # Initialize search client with stable API version
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=self.credential,
            api_version="2024-07-01"  # Stable GA version with vector search support
        )
        
        logger.info("DocumentIndexer initialized")
        logger.info(f"  Storage: {blob_url}/{container_name}")
        logger.info(f"  Document Intelligence: {document_intelligence_endpoint}")
        logger.info(f"  Foundry: {foundry_endpoint}")
        logger.info(f"  Search: {search_endpoint}/{index_name}")
    
    def list_pdfs(self) -> List[str]:
        """List all PDF files in the blob container."""
        logger.info(f"Listing PDFs in container '{self.container_name}'...")
        pdf_names = [
            blob.name for blob in self.container_client.list_blobs()
            if blob.name.lower().endswith('.pdf')
        ]
        logger.info(f"Found {len(pdf_names)} PDF(s): {pdf_names}")
        return pdf_names
    
    def download_pdf(self, blob_name: str) -> bytes:
        """Download PDF content from blob storage."""
        logger.info(f"Downloading '{blob_name}'...")
        blob_client = self.container_client.get_blob_client(blob_name)
        return blob_client.download_blob().readall()
    
    def extract_text_from_pdf(self, blob_url: str, filename: str) -> List[Dict[str, Any]]:
        """
        Extract text from PDF using Azure Document Intelligence, preserving page numbers.
        
        Args:
            blob_url: URL to the blob (Document Intelligence can access via managed identity)
            filename: Name of the file for logging
        
        Returns:
            List of dicts with 'page_number' and 'text' keys
        """
        logger.info(f"Extracting text from '{filename}' using Document Intelligence...")
        
        # Use Document Intelligence to analyze the PDF
        # Using prebuilt-layout model for text extraction including OCR from images
        poller = self.doc_intelligence_client.begin_analyze_document(
            model_id="prebuilt-layout",
            body={"urlSource": blob_url}
        )
        result: AnalyzeResult = poller.result()
        
        pages = []
        if result.pages:
            for page in result.pages:
                # Extract text from lines on each page (includes OCR'd text from images)
                page_text = "\n".join([line.content for line in page.lines]) if page.lines else ""
                if page_text.strip():
                    pages.append({
                        'page_number': page.page_number,
                        'text': page_text
                    })
        
        # Also extract text from figures/images if available
        if result.figures:
            logger.info(f"Found {len(result.figures)} figures with text")
            for figure in result.figures:
                if figure.caption and figure.caption.content:
                    # Add figure captions to the page they appear on
                    page_num = figure.bounding_regions[0].page_number if figure.bounding_regions else 1
                    for page in pages:
                        if page['page_number'] == page_num:
                            page['text'] += f"\n[Figure: {figure.caption.content}]"
                            break
        
        logger.info(f"Extracted {len(pages)} pages from '{filename}'")
        return pages
    
    def chunk_text(self, pages: List[Dict[str, Any]], document_id: str) -> List[Dict[str, Any]]:
        """
        Chunk text using character-based chunking with overlap.
        Document Intelligence handles optimal text extraction.
        
        Args:
            pages: List of page dicts with 'page_number' and 'text'
            document_id: Document identifier
            
        Returns:
            List of chunk dicts ready for indexing
        """
        logger.info(f"Chunking text (size={self.chunk_size} chars, overlap={self.chunk_overlap} chars)...")
        chunks = []
        
        for page_info in pages:
            page_number = page_info['page_number']
            text = page_info['text']
            
            # Create overlapping chunks based on character count
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                chunk_text = text[start:end]
                
                # Create chunk ID from document ID and position
                chunk_position = f"{page_number}_{start}"
                chunk_id = base64.urlsafe_b64encode(
                    f"{document_id}#{chunk_position}".encode()
                ).decode('utf-8')
                
                if chunk_text.strip():
                    chunks.append({
                        'chunk_id': chunk_id,
                        'content': chunk_text,
                    'document_id': document_id,
                    'page_number': page_number,
                    'metadata_storage_name': document_id,
                    'state': None  # Can be used for filtering by state
                })
                
                # Move to next chunk with overlap
                start += self.chunk_size - self.chunk_overlap
        
        logger.info(f"Created {len(chunks)} chunks")
        return chunks
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using Azure OpenAI with managed identity.
        
        Args:
            texts: List of text chunks to embed
            
        Returns:
            List of embedding vectors
        """
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        
        # Use Azure OpenAI embeddings API
        response = self.openai_client.embeddings.create(
            input=texts,
            model=self.embedding_deployment
        )
        
        embeddings = [item.embedding for item in response.data]
        logger.info(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")
        return embeddings
    
    def upload_to_search(self, chunks: List[Dict[str, Any]]):
        """
        Upload chunks with embeddings to Azure AI Search index.
        
        Args:
            chunks: List of chunk dicts with 'chunk_vector' field
        """
        logger.info(f"Uploading {len(chunks)} chunks to search index '{self.index_name}'...")
        
        # Use merge_or_upload to handle updates
        result = self.search_client.merge_or_upload_documents(documents=chunks)
        
        succeeded = sum(1 for r in result if r.succeeded)
        failed = sum(1 for r in result if not r.succeeded)
        
        logger.info(f"Upload complete: {succeeded} succeeded, {failed} failed")
        
        if failed > 0:
            for r in result:
                if not r.succeeded:
                    logger.error(f"Failed to upload chunk {r.key}: {r.error_message}")
    
    def index_document(self, blob_name: str):
        """
        Index a single PDF document through the full pipeline.
        
        Args:
            blob_name: Name of the PDF blob to index
        """
        logger.info(f"=== Indexing document: {blob_name} ===")
        
        # 1. Get blob URL for Document Intelligence
        blob_url = f"https://{self.storage_account}.blob.core.windows.net/{self.container_name}/{blob_name}"
        
        # 2. Extract text using Document Intelligence
        pages = self.extract_text_from_pdf(blob_url, blob_name)
        
        if not pages:
            logger.warning(f"No text extracted from '{blob_name}', skipping")
            return
        
        # 3. Chunk text
        document_id = blob_name
        chunks = self.chunk_text(pages, document_id)
        
        if not chunks:
            logger.warning(f"No chunks created from '{blob_name}', skipping")
            return
        
        # 4. Generate embeddings in batches
        batch_size = 100  # Azure OpenAI embedding batch limit
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [chunk['content'] for chunk in batch]
            
            embeddings = self.generate_embeddings(texts)
            
            # Add embeddings to chunks
            for chunk, embedding in zip(batch, embeddings):
                chunk['chunk_vector'] = embedding
            
            # 5. Upload batch to search
            self.upload_to_search(batch)
        
        logger.info(f"=== Completed indexing: {blob_name} ===")
    
    def index_all_documents(self):
        """Index all PDF documents in the blob container."""
        logger.info("=== Starting full document indexing ===")
        
        pdf_names = self.list_pdfs()
        
        if not pdf_names:
            logger.warning("No PDFs found in container")
            return
        
        for pdf_name in pdf_names:
            try:
                self.index_document(pdf_name)
            except Exception as e:
                logger.error(f"Failed to index '{pdf_name}': {e}", exc_info=True)
        
        logger.info("=== Document indexing complete ===")


def main():
    """Main entry point for the indexing pipeline."""
    # Configuration - these would typically come from environment variables or config file
    config = {
        'storage_account': 'stdrvagdbvxlqv',
        'container_name': 'pdfs',
        'document_intelligence_endpoint': 'https://di-drvagent-dev-bvxlqv.cognitiveservices.azure.com/',
        'foundry_endpoint': 'https://fdry-drvagent-dev-bvxlqv.cognitiveservices.azure.com/',
        'embedding_deployment': 'text-embedding-3-large',
        'search_endpoint': 'https://srch-drvagent-dev-bvxlqv.search.windows.net',
        'index_name': 'driving-manual-index',
        'chunk_size': 1000,  # characters (approx 250 tokens)
        'chunk_overlap': 200
    }
    
    try:
        indexer = DocumentIndexer(**config)
        indexer.index_all_documents()
        logger.info("Indexing pipeline completed successfully!")
    except Exception as e:
        logger.error(f"Indexing pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
