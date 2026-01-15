"""
Document Upload Script for Azure AI Search Indexing Pipeline.

This script uploads PDF driving manuals to Azure Blob Storage with metadata
for automatic indexing by Azure AI Search. It supports batch uploads,
directory structure preservation, and progress tracking.

Key Features:
- Upload PDFs to blob storage with custom metadata
- Preserve directory structure (e.g., state/California/manual-2026.pdf)
- Add metadata: state, year, version, upload_timestamp
- Batch upload with progress tracking
- Managed identity authentication (no keys)
- Error handling and retry logic

Metadata Schema:
- state: US state name (e.g., "California", "Texas")
- year: Document year (e.g., "2024", "2025")
- version: Document version (e.g., "1.0", "2.0")
- upload_timestamp: ISO 8601 timestamp of upload
- document_type: Always "driving_manual"

Usage:
    # Upload single file
    python upload_documents.py --file data/manuals/california-dmv-handbook-2024.pdf --state California --year 2024
    
    # Upload directory (batch)
    python upload_documents.py --directory data/manuals --recursive
    
    # From Python code
    from indexing.upload_documents import upload_pdf_to_blob
    
    upload_pdf_to_blob(
        file_path="path/to/manual.pdf",
        blob_name="state/California/manual-2024.pdf",
        metadata={"state": "California", "year": "2024"}
    )

Requirements:
- azure-storage-blob>=12.19.0
- azure-identity>=1.12.0
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from azure.core.exceptions import ResourceExistsError, AzureError
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, BlobClient, ContentSettings

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from indexing.config import load_config, IndexingConfig

# Configure logging with detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DocumentUploader:
    """
    Handles uploading PDF documents to Azure Blob Storage.
    
    This class provides methods to upload individual PDFs or batch upload
    directories of PDFs to Azure Blob Storage with custom metadata for
    Azure AI Search indexing.
    
    Attributes:
        config: IndexingConfig instance with storage settings
        blob_service_client: Azure BlobServiceClient for storage operations
        container_name: Name of the blob container for PDFs
    """
    
    def __init__(self, config: Optional[IndexingConfig] = None):
        """
        Initialize the document uploader.
        
        Args:
            config: Optional IndexingConfig instance. If not provided,
                   configuration will be loaded from environment variables.
        
        Raises:
            ValueError: If configuration is invalid
            AzureError: If Azure authentication fails
        """
        self.config = config or load_config()
        self.container_name = self.config.storage_container_pdfs
        
        # Initialize blob service client with managed identity or connection string
        logger.info(f"Initializing blob service client for account: {self.config.storage_account}")
        
        if self.config.use_managed_identity:
            # Use managed identity (recommended for production)
            credential = DefaultAzureCredential()
            account_url = f"https://{self.config.storage_account}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=credential
            )
            logger.info("Using managed identity for authentication")
        else:
            # Use connection string (development only)
            connection_string = self.config.get_storage_connection_string()
            if not connection_string:
                raise ValueError(
                    "USE_MANAGED_IDENTITY is False but AZURE_STORAGE_CONNECTION_STRING is not set"
                )
            self.blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            logger.info("Using connection string for authentication")
    
    def upload_pdf(
        self,
        file_path: str,
        blob_name: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
        overwrite: bool = False
    ) -> Tuple[bool, str]:
        """
        Upload a single PDF file to blob storage with metadata.
        
        This method uploads a PDF file to Azure Blob Storage, adding custom
        metadata for indexing and preserving directory structure if blob_name
        contains path separators.
        
        Args:
            file_path: Local path to the PDF file to upload
            blob_name: Optional blob name in container. If not provided,
                      uses the filename from file_path
            metadata: Optional dictionary of metadata key-value pairs.
                     Common keys: state, year, version
            overwrite: Whether to overwrite existing blobs (default: False)
        
        Returns:
            Tuple of (success: bool, message: str)
            - success: True if upload succeeded, False otherwise
            - message: Success message or error description
        
        Raises:
            FileNotFoundError: If file_path does not exist
            ValueError: If file is not a PDF
        
        Example:
            >>> uploader = DocumentUploader()
            >>> success, msg = uploader.upload_pdf(
            ...     file_path="data/manuals/ca-manual.pdf",
            ...     blob_name="California/2024/manual.pdf",
            ...     metadata={"state": "California", "year": "2024"}
            ... )
            >>> print(msg)
            'Successfully uploaded California/2024/manual.pdf'
        """
        # Validate file exists
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file is a PDF
        if file_path_obj.suffix.lower() != '.pdf':
            raise ValueError(f"File must be a PDF: {file_path}")
        
        # Determine blob name
        if blob_name is None:
            blob_name = file_path_obj.name
        
        # Prepare metadata with defaults
        upload_metadata = {
            "upload_timestamp": datetime.now(timezone.utc).isoformat(),
            "document_type": "driving_manual",
            "original_filename": file_path_obj.name
        }
        
        # Add user-provided metadata
        if metadata:
            upload_metadata.update(metadata)
        
        # Ensure all metadata values are strings
        upload_metadata = {k: str(v) for k, v in upload_metadata.items()}
        
        try:
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Check if blob exists
            if not overwrite and blob_client.exists():
                logger.warning(f"Blob already exists: {blob_name} (use --overwrite to replace)")
                return False, f"Blob already exists: {blob_name}"
            
            # Upload file with metadata
            logger.info(f"Uploading {file_path} -> {blob_name}")
            logger.debug(f"Metadata: {upload_metadata}")
            
            with open(file_path, "rb") as data:
                blob_client.upload_blob(
                    data,
                    overwrite=overwrite,
                    metadata=upload_metadata,
                    content_settings=ContentSettings(
                        content_type="application/pdf"
                    )
                )
            
            # Get blob properties to confirm upload
            properties = blob_client.get_blob_properties()
            size_mb = properties.size / (1024 * 1024)
            
            success_msg = (
                f"Successfully uploaded {blob_name} "
                f"({size_mb:.2f} MB, {len(upload_metadata)} metadata fields)"
            )
            logger.info(success_msg)
            
            return True, success_msg
            
        except ResourceExistsError:
            error_msg = f"Blob already exists: {blob_name}"
            logger.error(error_msg)
            return False, error_msg
        
        except AzureError as e:
            error_msg = f"Azure error uploading {blob_name}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error uploading {blob_name}: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def upload_directory(
        self,
        directory_path: str,
        recursive: bool = False,
        preserve_structure: bool = True,
        base_path: Optional[str] = None,
        overwrite: bool = False
    ) -> Tuple[int, int, List[str]]:
        """
        Upload all PDFs in a directory to blob storage.
        
        This method scans a directory for PDF files and uploads them to
        blob storage, optionally preserving the directory structure and
        recursively processing subdirectories.
        
        Args:
            directory_path: Local directory path to scan for PDFs
            recursive: Whether to recursively scan subdirectories (default: False)
            preserve_structure: Whether to preserve directory structure in blob names
                              (default: True). If True, "data/manuals/CA/doc.pdf"
                              uploads as "CA/doc.pdf" (relative to directory_path)
            base_path: Optional base path to strip from blob names. If not provided,
                      uses directory_path when preserve_structure is True
            overwrite: Whether to overwrite existing blobs (default: False)
        
        Returns:
            Tuple of (success_count, failure_count, error_messages)
            - success_count: Number of successfully uploaded files
            - failure_count: Number of failed uploads
            - error_messages: List of error messages for failed uploads
        
        Example:
            >>> uploader = DocumentUploader()
            >>> success, failed, errors = uploader.upload_directory(
            ...     directory_path="data/manuals",
            ...     recursive=True,
            ...     preserve_structure=True
            ... )
            >>> print(f"Uploaded {success} files, {failed} failures")
        """
        directory = Path(directory_path)
        
        # Validate directory exists
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not directory.is_dir():
            raise ValueError(f"Not a directory: {directory_path}")
        
        # Set base path for structure preservation
        if base_path is None and preserve_structure:
            base_path = str(directory)
        
        # Find all PDF files
        if recursive:
            pdf_files = list(directory.rglob("*.pdf"))
        else:
            pdf_files = list(directory.glob("*.pdf"))
        
        logger.info(f"Found {len(pdf_files)} PDF files in {directory_path}")
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {directory_path}")
            return 0, 0, []
        
        # Upload each file
        success_count = 0
        failure_count = 0
        error_messages = []
        
        for i, pdf_file in enumerate(pdf_files, 1):
            # Determine blob name
            if preserve_structure and base_path:
                # Get relative path from base_path
                try:
                    relative_path = pdf_file.relative_to(base_path)
                    blob_name = str(relative_path)
                except ValueError:
                    # File is not relative to base_path, use filename only
                    blob_name = pdf_file.name
            else:
                blob_name = pdf_file.name
            
            # Extract metadata from directory structure
            # Example: "data/manuals/California/2024/manual.pdf" -> state=California, year=2024
            metadata = self._extract_metadata_from_path(pdf_file)
            
            # Upload file
            logger.info(f"[{i}/{len(pdf_files)}] Processing {pdf_file.name}")
            success, message = self.upload_pdf(
                file_path=str(pdf_file),
                blob_name=blob_name,
                metadata=metadata,
                overwrite=overwrite
            )
            
            if success:
                success_count += 1
            else:
                failure_count += 1
                error_messages.append(f"{pdf_file.name}: {message}")
        
        # Log summary
        logger.info("="*60)
        logger.info("Upload Summary")
        logger.info("="*60)
        logger.info(f"Total files:  {len(pdf_files)}")
        logger.info(f"Successful:   {success_count}")
        logger.info(f"Failed:       {failure_count}")
        logger.info("="*60)
        
        if error_messages:
            logger.warning("Failed uploads:")
            for error in error_messages:
                logger.warning(f"  - {error}")
        
        return success_count, failure_count, error_messages
    
    def _extract_metadata_from_path(self, file_path: Path) -> Dict[str, str]:
        """
        Extract metadata from file path and filename.
        
        This method attempts to extract state, year, and version information
        from the file path structure and filename patterns.
        
        Expected patterns:
        - Path: state/California/manual-2024.pdf -> state=California
        - Path: California/2024/manual.pdf -> state=California, year=2024
        - Filename: california-dmv-handbook-2024.pdf -> year=2024
        - Filename: manual-v2.pdf -> version=2
        
        Args:
            file_path: Path object for the PDF file
        
        Returns:
            Dictionary of extracted metadata
        """
        metadata = {}
        
        # Extract from path parts
        parts = file_path.parts
        
        # Look for US state names in path
        # Common US states (can be expanded)
        us_states = [
            "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
            "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
            "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
            "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
            "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
            "New Hampshire", "New Jersey", "New Mexico", "New York",
            "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
            "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
            "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
            "West Virginia", "Wisconsin", "Wyoming"
        ]
        
        for part in parts:
            # Check for state name (case-insensitive)
            for state in us_states:
                if part.lower() == state.lower():
                    metadata["state"] = state
                    break
            
            # Check for year (4-digit number 20xx or 19xx)
            if part.isdigit() and len(part) == 4 and part.startswith(('19', '20')):
                metadata["year"] = part
        
        # Extract from filename
        filename = file_path.stem  # filename without extension
        
        # Look for year in filename (e.g., "manual-2024", "handbook-2024")
        import re
        year_match = re.search(r'(19|20)\d{2}', filename)
        if year_match and "year" not in metadata:
            metadata["year"] = year_match.group(0)
        
        # Look for version in filename (e.g., "v1", "v2.0", "version-2")
        version_match = re.search(r'v(?:ersion)?[-_]?(\d+(?:\.\d+)?)', filename, re.IGNORECASE)
        if version_match:
            metadata["version"] = version_match.group(1)
        
        return metadata
    
    def list_uploaded_documents(self, prefix: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List all uploaded PDF documents in the container.
        
        Args:
            prefix: Optional blob name prefix to filter results
                   (e.g., "California/" to list only California documents)
        
        Returns:
            List of dictionaries containing blob information:
            - name: Blob name
            - size: Blob size in bytes
            - last_modified: Last modification timestamp
            - metadata: Dictionary of blob metadata
        
        Example:
            >>> uploader = DocumentUploader()
            >>> docs = uploader.list_uploaded_documents(prefix="California/")
            >>> for doc in docs:
            ...     print(f"{doc['name']}: {doc['size']} bytes")
        """
        container_client = self.blob_service_client.get_container_client(
            self.container_name
        )
        
        blobs_list = []
        
        try:
            blobs = container_client.list_blobs(name_starts_with=prefix)
            
            for blob in blobs:
                blobs_list.append({
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified.isoformat(),
                    "metadata": blob.metadata or {}
                })
            
            logger.info(f"Found {len(blobs_list)} blobs" + (f" with prefix '{prefix}'" if prefix else ""))
            
        except AzureError as e:
            logger.error(f"Error listing blobs: {e}")
        
        return blobs_list


def main():
    """
    Command-line interface for document upload script.
    
    Provides CLI for uploading individual files or directories of PDFs
    to Azure Blob Storage with metadata extraction and progress tracking.
    """
    parser = argparse.ArgumentParser(
        description="Upload PDF driving manuals to Azure Blob Storage for indexing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Upload single file with metadata
  %(prog)s --file data/manuals/ca-manual.pdf --state California --year 2024
  
  # Upload directory recursively
  %(prog)s --directory data/manuals --recursive --overwrite
  
  # List uploaded documents
  %(prog)s --list --prefix California/
  
Environment Variables:
  AZURE_STORAGE_ACCOUNT       - Storage account name (required)
  AZURE_STORAGE_CONTAINER_PDFS - PDFs container name (default: pdfs)
  AZURE_SEARCH_ENDPOINT       - Search endpoint (required for validation)
        """
    )
    
    # Upload options
    upload_group = parser.add_mutually_exclusive_group(required=True)
    upload_group.add_argument(
        '--file',
        type=str,
        help='Path to single PDF file to upload'
    )
    upload_group.add_argument(
        '--directory',
        type=str,
        help='Path to directory containing PDFs to upload'
    )
    upload_group.add_argument(
        '--list',
        action='store_true',
        help='List uploaded documents'
    )
    
    # Metadata options
    parser.add_argument(
        '--state',
        type=str,
        help='State name for metadata (e.g., California, Texas)'
    )
    parser.add_argument(
        '--year',
        type=str,
        help='Document year for metadata (e.g., 2024)'
    )
    parser.add_argument(
        '--version',
        type=str,
        help='Document version for metadata (e.g., 1.0, 2.0)'
    )
    parser.add_argument(
        '--blob-name',
        type=str,
        help='Custom blob name (default: uses filename)'
    )
    
    # Directory options
    parser.add_argument(
        '--recursive',
        action='store_true',
        help='Recursively scan subdirectories'
    )
    parser.add_argument(
        '--no-preserve-structure',
        action='store_true',
        help='Do not preserve directory structure in blob names'
    )
    
    # List options
    parser.add_argument(
        '--prefix',
        type=str,
        help='Blob name prefix for filtering (used with --list)'
    )
    
    # General options
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing blobs'
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
        # Initialize uploader
        uploader = DocumentUploader()
        
        # Handle list command
        if args.list:
            docs = uploader.list_uploaded_documents(prefix=args.prefix)
            
            if not docs:
                print("No documents found")
                return 0
            
            print(f"\nFound {len(docs)} documents:\n")
            for doc in docs:
                size_mb = doc['size'] / (1024 * 1024)
                print(f"  {doc['name']}")
                print(f"    Size: {size_mb:.2f} MB")
                print(f"    Modified: {doc['last_modified']}")
                if doc['metadata']:
                    print(f"    Metadata: {doc['metadata']}")
                print()
            
            return 0
        
        # Handle file upload
        if args.file:
            # Prepare metadata
            metadata = {}
            if args.state:
                metadata['state'] = args.state
            if args.year:
                metadata['year'] = args.year
            if args.version:
                metadata['version'] = args.version
            
            # Upload file
            success, message = uploader.upload_pdf(
                file_path=args.file,
                blob_name=args.blob_name,
                metadata=metadata if metadata else None,
                overwrite=args.overwrite
            )
            
            if success:
                print(f"\n✓ {message}")
                return 0
            else:
                print(f"\n✗ {message}", file=sys.stderr)
                return 1
        
        # Handle directory upload
        if args.directory:
            success_count, failure_count, errors = uploader.upload_directory(
                directory_path=args.directory,
                recursive=args.recursive,
                preserve_structure=not args.no_preserve_structure,
                overwrite=args.overwrite
            )
            
            if failure_count == 0:
                print(f"\n✓ Successfully uploaded {success_count} files")
                return 0
            else:
                print(f"\n⚠ Uploaded {success_count} files, {failure_count} failures", file=sys.stderr)
                return 1
    
    except Exception as e:
        logger.exception("Unexpected error")
        print(f"\n✗ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
