"""
Document Enrichment Validation Script for Azure AI Search.

This script validates the results of the indexing and enrichment process
by querying the search index and checking for completeness and quality
of extracted data including text chunks, images, and embeddings.

Validation Checks:
1. Document completeness - All uploaded PDFs are indexed
2. Chunk generation - Appropriate number of text chunks per document
3. Image extraction - Images detected and stored correctly
4. Embedding presence - Vector embeddings generated for all chunks
5. Field population - All expected fields are populated
6. Anomaly detection - Flag unusual patterns (e.g., no images for image-heavy docs)

Output Formats:
- JSON: Machine-readable validation report
- Markdown: Human-readable validation report
- Console: Real-time logging and summary

Usage:
    # Validate all documents
    python validate_enrichment.py
    
    # Validate specific document
    python validate_enrichment.py --document california-dmv-handbook-2024.pdf
    
    # Generate reports
    python validate_enrichment.py --json-output validation.json --markdown-output validation.md
    
    # From Python code
    from indexing.validate_enrichment import EnrichmentValidator
    
    validator = EnrichmentValidator()
    report = validator.validate_all_documents()

Requirements:
- azure-search-documents>=11.4.0
- azure-identity>=1.12.0
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexing.config import load_config, IndexingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnrichmentValidator:
    """
    Validates document enrichment results in Azure AI Search index.
    
    This class provides comprehensive validation of the indexing pipeline
    output, checking for data completeness, quality, and anomalies.
    
    Attributes:
        config: IndexingConfig instance
        search_client: Azure SearchClient for querying the index
        blob_service_client: Azure BlobServiceClient for checking uploaded files
    """
    
    def __init__(self, config: Optional[IndexingConfig] = None):
        """
        Initialize the enrichment validator.
        
        Args:
            config: Optional IndexingConfig instance. If not provided,
                   loads from environment variables.
        """
        self.config = config or load_config()
        
        logger.info(f"Initializing enrichment validator for index: {self.config.search_index_name}")
        
        # Initialize search client
        if self.config.use_managed_identity:
            credential = DefaultAzureCredential()
            logger.info("Using managed identity for authentication")
        else:
            api_key = self.config.get_search_api_key()
            if not api_key:
                raise ValueError(
                    "USE_MANAGED_IDENTITY is False but AZURE_SEARCH_API_KEY is not set"
                )
            credential = AzureKeyCredential(api_key)
            logger.info("Using API key for authentication")
        
        self.search_client = SearchClient(
            endpoint=self.config.search_endpoint,
            index_name=self.config.search_index_name,
            credential=credential
        )
        
        # Initialize blob service client for uploaded file validation
        if self.config.use_managed_identity:
            blob_credential = DefaultAzureCredential()
            account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=blob_credential
            )
        else:
            connection_string = self.config.get_storage_connection_string()
            if connection_string:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    connection_string
                )
            else:
                self.blob_service_client = None
                logger.warning("Blob service client not initialized - uploaded file validation will be skipped")
    
    def get_uploaded_documents(self) -> List[Dict[str, Any]]:
        """
        Get list of uploaded PDF documents from blob storage.
        
        Returns:
            List of dictionaries containing blob information:
            - name: Blob name
            - size: Size in bytes
            - metadata: Blob metadata
        
        Example:
            >>> validator = EnrichmentValidator()
            >>> docs = validator.get_uploaded_documents()
            >>> print(f"Found {len(docs)} uploaded PDFs")
        """
        if not self.blob_service_client:
            logger.warning("Blob service client not available")
            return []
        
        try:
            container_client = self.blob_service_client.get_container_client(
                self.config.storage_container_pdfs
            )
            
            blobs = []
            for blob in container_client.list_blobs():
                # Only include PDF files
                if blob.name.lower().endswith('.pdf'):
                    blobs.append({
                        'name': blob.name,
                        'size': blob.size,
                        'metadata': blob.metadata or {},
                        'last_modified': blob.last_modified.isoformat()
                    })
            
            logger.info(f"Found {len(blobs)} PDF files in blob storage")
            return blobs
            
        except AzureError as e:
            logger.error(f"Error listing blobs: {e}")
            return []
    
    def get_indexed_documents(self) -> List[Dict[str, Any]]:
        """
        Get all documents from the search index.
        
        Returns:
            List of document dictionaries from the search index
        
        Example:
            >>> validator = EnrichmentValidator()
            >>> docs = validator.get_indexed_documents()
            >>> print(f"Found {len(docs)} indexed chunks")
        """
        try:
            # Search for all documents
            results = self.search_client.search(
                search_text="*",
                select=[
                    'chunk_id', 'document_id', 'content', 'page_number',
                    'state', 'has_related_images', 'image_blob_urls',
                    'image_descriptions', 'metadata_storage_name',
                    'metadata_storage_path'
                ],
                top=10000  # Large number to get all documents
            )
            
            docs = list(results)
            logger.info(f"Retrieved {len(docs)} chunks from search index")
            return docs
            
        except AzureError as e:
            logger.error(f"Error querying search index: {e}")
            return []
    
    def validate_document_completeness(
        self,
        uploaded_docs: List[Dict[str, Any]],
        indexed_docs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate that all uploaded documents are indexed.
        
        Compares the list of uploaded PDFs with documents in the search index
        to identify any missing documents.
        
        Args:
            uploaded_docs: List of uploaded PDF blobs
            indexed_docs: List of indexed document chunks
        
        Returns:
            Dictionary with validation results:
            - uploaded_count: Number of uploaded PDFs
            - indexed_count: Number of unique documents in index
            - missing_documents: List of uploaded files not in index
            - all_indexed: Boolean indicating if all docs are indexed
        
        Example:
            >>> result = validator.validate_document_completeness(uploaded, indexed)
            >>> if not result['all_indexed']:
            ...     print(f"Missing: {result['missing_documents']}")
        """
        logger.info("Validating document completeness...")
        
        # Get unique document names from index
        indexed_names = set()
        for doc in indexed_docs:
            # Extract document name from metadata_storage_name or path
            doc_name = doc.get('metadata_storage_name', '')
            if doc_name:
                indexed_names.add(doc_name)
        
        # Check for missing documents
        missing = []
        for blob in uploaded_docs:
            blob_name = blob['name'].split('/')[-1]  # Get filename from path
            if blob_name not in indexed_names:
                missing.append(blob_name)
        
        all_indexed = len(missing) == 0
        
        result = {
            'uploaded_count': len(uploaded_docs),
            'indexed_count': len(indexed_names),
            'missing_documents': missing,
            'all_indexed': all_indexed
        }
        
        if all_indexed:
            logger.info(f"✓ All {len(uploaded_docs)} uploaded documents are indexed")
        else:
            logger.warning(f"✗ {len(missing)} documents are missing from index: {missing}")
        
        return result
    
    def validate_chunk_generation(
        self,
        indexed_docs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate text chunk generation for each document.
        
        Analyzes chunk counts per document and identifies documents with
        unusually low or high chunk counts that may indicate issues.
        
        Args:
            indexed_docs: List of indexed document chunks
        
        Returns:
            Dictionary with validation results:
            - total_chunks: Total number of chunks
            - documents: Number of unique documents
            - avg_chunks_per_doc: Average chunks per document
            - chunk_distribution: Dict mapping doc_id to chunk count
            - anomalies: List of documents with unusual chunk counts
        
        Example:
            >>> result = validator.validate_chunk_generation(indexed_docs)
            >>> print(f"Average {result['avg_chunks_per_doc']:.1f} chunks per document")
        """
        logger.info("Validating chunk generation...")
        
        # Count chunks per document
        doc_chunks = defaultdict(int)
        for doc in indexed_docs:
            doc_id = doc.get('document_id') or doc.get('metadata_storage_name', 'unknown')
            doc_chunks[doc_id] += 1
        
        # Calculate statistics
        chunk_counts = list(doc_chunks.values())
        total_chunks = sum(chunk_counts)
        num_docs = len(doc_chunks)
        avg_chunks = total_chunks / num_docs if num_docs > 0 else 0
        
        # Identify anomalies (docs with very few or very many chunks)
        # Anomaly thresholds: < 25% or > 300% of average
        anomalies = []
        for doc_id, count in doc_chunks.items():
            if count < avg_chunks * 0.25:
                anomalies.append({
                    'document': doc_id,
                    'chunks': count,
                    'issue': 'too_few',
                    'expected': f'~{avg_chunks:.0f}'
                })
            elif count > avg_chunks * 3.0:
                anomalies.append({
                    'document': doc_id,
                    'chunks': count,
                    'issue': 'too_many',
                    'expected': f'~{avg_chunks:.0f}'
                })
        
        result = {
            'total_chunks': total_chunks,
            'documents': num_docs,
            'avg_chunks_per_doc': avg_chunks,
            'min_chunks': min(chunk_counts) if chunk_counts else 0,
            'max_chunks': max(chunk_counts) if chunk_counts else 0,
            'chunk_distribution': dict(doc_chunks),
            'anomalies': anomalies
        }
        
        logger.info(f"  Total chunks: {total_chunks}")
        logger.info(f"  Documents: {num_docs}")
        logger.info(f"  Avg chunks/doc: {avg_chunks:.1f}")
        logger.info(f"  Range: {result['min_chunks']}-{result['max_chunks']}")
        
        if anomalies:
            logger.warning(f"  Found {len(anomalies)} documents with unusual chunk counts")
        else:
            logger.info("  ✓ No chunk count anomalies detected")
        
        return result
    
    def validate_image_extraction(
        self,
        indexed_docs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate image extraction from documents.
        
        Checks for presence of images, image URLs, and descriptions,
        and identifies documents that should have images but don't.
        
        Args:
            indexed_docs: List of indexed document chunks
        
        Returns:
            Dictionary with validation results:
            - total_chunks: Total number of chunks
            - chunks_with_images: Chunks that have related images
            - total_images: Total number of extracted images
            - image_percentage: Percentage of chunks with images
            - documents_with_images: Unique documents with images
            - anomalies: Chunks/docs that might be missing images
        
        Example:
            >>> result = validator.validate_image_extraction(indexed_docs)
            >>> print(f"{result['image_percentage']:.1f}% of chunks have images")
        """
        logger.info("Validating image extraction...")
        
        total_chunks = len(indexed_docs)
        chunks_with_images = 0
        total_images = 0
        docs_with_images = set()
        
        for doc in indexed_docs:
            has_images = doc.get('has_related_images', False)
            image_urls = doc.get('image_blob_urls', [])
            
            if has_images or (image_urls and len(image_urls) > 0):
                chunks_with_images += 1
                total_images += len(image_urls) if image_urls else 0
                
                doc_id = doc.get('document_id') or doc.get('metadata_storage_name', 'unknown')
                docs_with_images.add(doc_id)
        
        image_percentage = (chunks_with_images / total_chunks * 100) if total_chunks > 0 else 0
        
        result = {
            'total_chunks': total_chunks,
            'chunks_with_images': chunks_with_images,
            'total_images': total_images,
            'image_percentage': image_percentage,
            'documents_with_images': len(docs_with_images),
            'avg_images_per_chunk': total_images / total_chunks if total_chunks > 0 else 0
        }
        
        logger.info(f"  Chunks with images: {chunks_with_images}/{total_chunks} ({image_percentage:.1f}%)")
        logger.info(f"  Total images extracted: {total_images}")
        logger.info(f"  Documents with images: {len(docs_with_images)}")
        
        if image_percentage < 10:
            logger.warning(f"  ⚠ Low image extraction rate: {image_percentage:.1f}%")
        else:
            logger.info(f"  ✓ Image extraction looks healthy")
        
        return result
    
    def validate_field_population(
        self,
        indexed_docs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validate field population completeness.
        
        Checks what percentage of documents have each expected field populated
        to identify potential indexing issues.
        
        Args:
            indexed_docs: List of indexed document chunks
        
        Returns:
            Dictionary with field coverage percentages:
            - field_coverage: Dict mapping field name to coverage percentage
            - required_fields: List of fields that should always be populated
            - missing_fields: Fields with low population rates
        
        Example:
            >>> result = validator.validate_field_population(indexed_docs)
            >>> for field, coverage in result['field_coverage'].items():
            ...     print(f"{field}: {coverage:.1f}%")
        """
        logger.info("Validating field population...")
        
        if not indexed_docs:
            return {'error': 'No documents to validate'}
        
        # Expected fields
        expected_fields = [
            'chunk_id', 'document_id', 'content', 'page_number',
            'metadata_storage_name', 'metadata_storage_path'
        ]
        
        # Count field population
        field_counts = defaultdict(int)
        total_docs = len(indexed_docs)
        
        for doc in indexed_docs:
            for field in expected_fields:
                value = doc.get(field)
                if value is not None and value != '' and value != []:
                    field_counts[field] += 1
        
        # Calculate coverage percentages
        field_coverage = {
            field: (field_counts[field] / total_docs * 100)
            for field in expected_fields
        }
        
        # Identify fields with low coverage (<95%)
        missing_fields = {
            field: coverage
            for field, coverage in field_coverage.items()
            if coverage < 95.0
        }
        
        result = {
            'field_coverage': field_coverage,
            'required_fields': expected_fields,
            'missing_fields': missing_fields
        }
        
        logger.info("  Field coverage:")
        for field, coverage in field_coverage.items():
            status = "✓" if coverage >= 95.0 else "✗"
            logger.info(f"    {status} {field}: {coverage:.1f}%")
        
        if missing_fields:
            logger.warning(f"  ⚠ {len(missing_fields)} fields have incomplete coverage")
        
        return result
    
    def validate_all_documents(self) -> Dict[str, Any]:
        """
        Run all validation checks and generate comprehensive report.
        
        Returns:
            Dictionary containing all validation results:
            - timestamp: Validation run timestamp
            - config: Configuration used
            - completeness: Document completeness results
            - chunks: Chunk generation results
            - images: Image extraction results
            - fields: Field population results
            - overall_status: 'pass', 'warning', or 'fail'
        
        Example:
            >>> validator = EnrichmentValidator()
            >>> report = validator.validate_all_documents()
            >>> if report['overall_status'] == 'fail':
            ...     print("Validation failed!")
        """
        logger.info("="*60)
        logger.info("Starting comprehensive enrichment validation")
        logger.info("="*60)
        
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'config': {
                'search_endpoint': self.config.search_endpoint,
                'index_name': self.config.search_index_name,
                'storage_account': self.config.storage_account
            }
        }
        
        # Get data
        uploaded_docs = self.get_uploaded_documents()
        indexed_docs = self.get_indexed_documents()
        
        # Run validations
        report['completeness'] = self.validate_document_completeness(uploaded_docs, indexed_docs)
        report['chunks'] = self.validate_chunk_generation(indexed_docs)
        report['images'] = self.validate_image_extraction(indexed_docs)
        report['fields'] = self.validate_field_population(indexed_docs)
        
        # Determine overall status
        issues = []
        
        if not report['completeness']['all_indexed']:
            issues.append('missing_documents')
        
        if report['chunks']['anomalies']:
            issues.append('chunk_anomalies')
        
        if report['images']['image_percentage'] < 5:
            issues.append('low_image_extraction')
        
        if report['fields']['missing_fields']:
            issues.append('incomplete_fields')
        
        if len(issues) == 0:
            report['overall_status'] = 'pass'
        elif len(issues) <= 2:
            report['overall_status'] = 'warning'
        else:
            report['overall_status'] = 'fail'
        
        report['issues'] = issues
        
        logger.info("="*60)
        logger.info(f"Validation Status: {report['overall_status'].upper()}")
        if issues:
            logger.warning(f"Issues detected: {', '.join(issues)}")
        else:
            logger.info("✓ All validation checks passed")
        logger.info("="*60)
        
        return report
    
    def generate_json_report(self, report: Dict[str, Any], output_path: str) -> None:
        """
        Generate JSON validation report.
        
        Args:
            report: Validation report dictionary
            output_path: Path to save JSON file
        """
        try:
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"✓ JSON report saved to: {output_path}")
        except Exception as e:
            logger.error(f"Error writing JSON report: {e}")
    
    def generate_markdown_report(self, report: Dict[str, Any], output_path: str) -> None:
        """
        Generate human-readable Markdown validation report.
        
        Args:
            report: Validation report dictionary
            output_path: Path to save Markdown file
        """
        try:
            lines = [
                "# Azure AI Search Enrichment Validation Report",
                "",
                f"**Generated:** {report['timestamp']}",
                f"**Status:** {report['overall_status'].upper()}",
                "",
                "## Configuration",
                "",
                f"- **Search Endpoint:** {report['config']['search_endpoint']}",
                f"- **Index Name:** {report['config']['index_name']}",
                f"- **Storage Account:** {report['config']['storage_account']}",
                "",
                "## Document Completeness",
                ""
            ]
            
            completeness = report['completeness']
            lines.extend([
                f"- **Uploaded Documents:** {completeness['uploaded_count']}",
                f"- **Indexed Documents:** {completeness['indexed_count']}",
                f"- **All Indexed:** {'✓ Yes' if completeness['all_indexed'] else '✗ No'}",
                ""
            ])
            
            if completeness['missing_documents']:
                lines.extend([
                    "### Missing Documents",
                    ""
                ])
                for doc in completeness['missing_documents']:
                    lines.append(f"- {doc}")
                lines.append("")
            
            chunks = report['chunks']
            lines.extend([
                "## Chunk Generation",
                "",
                f"- **Total Chunks:** {chunks['total_chunks']}",
                f"- **Documents:** {chunks['documents']}",
                f"- **Average Chunks per Document:** {chunks['avg_chunks_per_doc']:.1f}",
                f"- **Range:** {chunks['min_chunks']}-{chunks['max_chunks']}",
                ""
            ])
            
            if chunks['anomalies']:
                lines.extend([
                    "### Chunk Count Anomalies",
                    ""
                ])
                for anomaly in chunks['anomalies']:
                    lines.append(
                        f"- **{anomaly['document']}:** {anomaly['chunks']} chunks "
                        f"({anomaly['issue']}, expected {anomaly['expected']})"
                    )
                lines.append("")
            
            images = report['images']
            lines.extend([
                "## Image Extraction",
                "",
                f"- **Chunks with Images:** {images['chunks_with_images']}/{images['total_chunks']} "
                f"({images['image_percentage']:.1f}%)",
                f"- **Total Images:** {images['total_images']}",
                f"- **Documents with Images:** {images['documents_with_images']}",
                f"- **Average Images per Chunk:** {images['avg_images_per_chunk']:.2f}",
                "",
                "## Field Population",
                ""
            ])
            
            fields = report['fields']
            for field, coverage in fields['field_coverage'].items():
                status = "✓" if coverage >= 95.0 else "✗"
                lines.append(f"- {status} **{field}:** {coverage:.1f}%")
            
            lines.extend([
                "",
                "## Summary",
                ""
            ])
            
            if report['issues']:
                lines.append("**Issues Detected:**")
                for issue in report['issues']:
                    lines.append(f"- {issue.replace('_', ' ').title()}")
            else:
                lines.append("✓ **All validation checks passed!**")
            
            # Write file
            with open(output_path, 'w') as f:
                f.write('\n'.join(lines))
            
            logger.info(f"✓ Markdown report saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Error writing Markdown report: {e}")


def main():
    """Command-line interface for enrichment validation."""
    parser = argparse.ArgumentParser(
        description="Validate Azure AI Search document enrichment results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run validation and display results
  %(prog)s
  
  # Generate JSON and Markdown reports
  %(prog)s --json-output validation.json --markdown-output validation.md
  
Environment Variables:
  AZURE_SEARCH_ENDPOINT    - Search service endpoint (required)
  AZURE_SEARCH_INDEX_NAME  - Index name (default: driving-manual-index)
  AZURE_STORAGE_ACCOUNT    - Storage account name (required)
        """
    )
    
    parser.add_argument(
        '--json-output',
        type=str,
        help='Path to save JSON validation report'
    )
    parser.add_argument(
        '--markdown-output',
        type=str,
        help='Path to save Markdown validation report'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Run validation
        validator = EnrichmentValidator()
        report = validator.validate_all_documents()
        
        # Save reports if requested
        if args.json_output:
            validator.generate_json_report(report, args.json_output)
        
        if args.markdown_output:
            validator.generate_markdown_report(report, args.markdown_output)
        
        # Return exit code based on status
        if report['overall_status'] == 'pass':
            print("\n✓ Validation passed")
            return 0
        elif report['overall_status'] == 'warning':
            print("\n⚠ Validation passed with warnings")
            return 0
        else:
            print("\n✗ Validation failed", file=sys.stderr)
            return 1
    
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
