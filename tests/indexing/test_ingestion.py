"""
Unit tests for document ingestion configuration module.

Tests the IndexingConfig dataclass and configuration loading from
environment variables with validation.
"""

import os
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))


class TestIndexingConfig(unittest.TestCase):
    """Test cases for IndexingConfig dataclass."""
    
    def setUp(self):
        """Set up test environment variables."""
        # Save original environment
        self.original_env = os.environ.copy()
        
        # Set test environment variables
        os.environ['AZURE_STORAGE_ACCOUNT'] = 'teststorage'
        os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://testsearch.search.windows.net'
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_load_config_with_defaults(self):
        """Test loading configuration with default values."""
        try:
            from indexing.config import load_config
            
            config = load_config()
            
            # Check required fields
            self.assertEqual(config.storage_account, 'teststorage')
            self.assertEqual(config.search_endpoint, 'https://testsearch.search.windows.net')
            
            # Check defaults
            self.assertEqual(config.storage_container_pdfs, 'pdfs')
            self.assertEqual(config.storage_container_images, 'extracted-images')
            self.assertEqual(config.search_index_name, 'driving-manual-index')
            self.assertEqual(config.search_indexer_name, 'driving-manual-indexer')
            self.assertEqual(config.indexer_poll_interval, 10)
            self.assertEqual(config.indexer_timeout, 1800)
            self.assertTrue(config.use_managed_identity)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_load_config_with_custom_values(self):
        """Test loading configuration with custom environment variables."""
        try:
            from indexing.config import load_config
            
            # Set custom values
            os.environ['AZURE_STORAGE_CONTAINER_PDFS'] = 'custom-pdfs'
            os.environ['AZURE_SEARCH_INDEX_NAME'] = 'custom-index'
            os.environ['INDEXER_POLL_INTERVAL'] = '5'
            os.environ['INDEXER_TIMEOUT'] = '3600'
            
            config = load_config()
            
            # Check custom values were loaded
            self.assertEqual(config.storage_container_pdfs, 'custom-pdfs')
            self.assertEqual(config.search_index_name, 'custom-index')
            self.assertEqual(config.indexer_poll_interval, 5)
            self.assertEqual(config.indexer_timeout, 3600)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validation_missing_storage_account(self):
        """Test validation fails when storage account is missing."""
        try:
            from indexing.config import load_config
            
            # Remove required field
            del os.environ['AZURE_STORAGE_ACCOUNT']
            
            # Should raise ValueError during validation
            with self.assertRaises(ValueError) as context:
                load_config()
            
            self.assertIn('AZURE_STORAGE_ACCOUNT', str(context.exception))
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validation_missing_search_endpoint(self):
        """Test validation fails when search endpoint is missing."""
        try:
            from indexing.config import load_config
            
            # Remove required field
            del os.environ['AZURE_SEARCH_ENDPOINT']
            
            # Should raise ValueError during validation
            with self.assertRaises(ValueError) as context:
                load_config()
            
            self.assertIn('AZURE_SEARCH_ENDPOINT', str(context.exception))
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validation_invalid_endpoint_format(self):
        """Test validation fails for invalid endpoint format."""
        try:
            from indexing.config import load_config
            
            # Set invalid endpoint (not https://)
            os.environ['AZURE_SEARCH_ENDPOINT'] = 'http://testsearch.search.windows.net'
            
            # Should raise ValueError during validation
            with self.assertRaises(ValueError) as context:
                load_config()
            
            self.assertIn('https://', str(context.exception))
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validation_invalid_poll_interval(self):
        """Test validation fails for invalid poll interval."""
        try:
            from indexing.config import load_config
            
            # Set invalid poll interval (must be > 0)
            os.environ['INDEXER_POLL_INTERVAL'] = '0'
            
            # Should raise ValueError during validation
            with self.assertRaises(ValueError) as context:
                load_config()
            
            self.assertIn('poll interval', str(context.exception).lower())
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validation_invalid_container_name(self):
        """Test validation fails for invalid container name."""
        try:
            from indexing.config import load_config
            
            # Set invalid container name (uppercase not allowed)
            os.environ['AZURE_STORAGE_CONTAINER_PDFS'] = 'Invalid-Container-Name'
            
            # Should raise ValueError during validation
            with self.assertRaises(ValueError) as context:
                load_config()
            
            self.assertIn('container name', str(context.exception).lower())
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_skip_validation(self):
        """Test loading config without validation."""
        try:
            from indexing.config import load_config
            
            # Remove required field
            del os.environ['AZURE_STORAGE_ACCOUNT']
            
            # Should not raise error when validation is skipped
            config = load_config(validate=False)
            self.assertEqual(config.storage_account, '')
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_get_storage_connection_string(self):
        """Test retrieving storage connection string."""
        try:
            from indexing.config import load_config
            
            # Set connection string
            conn_str = 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=test'
            os.environ['AZURE_STORAGE_CONNECTION_STRING'] = conn_str
            
            config = load_config()
            
            # Should return the connection string
            self.assertEqual(config.get_storage_connection_string(), conn_str)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_get_search_api_key(self):
        """Test retrieving search API key."""
        try:
            from indexing.config import load_config
            
            # Set API key
            api_key = 'test-api-key-12345'
            os.environ['AZURE_SEARCH_API_KEY'] = api_key
            
            config = load_config()
            
            # Should return the API key
            self.assertEqual(config.get_search_api_key(), api_key)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")


class TestDocumentUploader(unittest.TestCase):
    """Test cases for DocumentUploader class."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        os.environ['AZURE_STORAGE_ACCOUNT'] = 'teststorage'
        os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://testsearch.search.windows.net'
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_extract_metadata_from_path(self):
        """Test metadata extraction from file paths."""
        try:
            from indexing.upload_documents import DocumentUploader
            from indexing.config import load_config
            
            # Mock Azure clients to avoid real connections
            with patch('indexing.upload_documents.DefaultAzureCredential'):
                with patch('indexing.upload_documents.BlobServiceClient'):
                    uploader = DocumentUploader()
                    
                    # Test state extraction
                    path1 = Path('data/manuals/California/manual-2024.pdf')
                    metadata1 = uploader._extract_metadata_from_path(path1)
                    self.assertEqual(metadata1.get('state'), 'California')
                    self.assertEqual(metadata1.get('year'), '2024')
                    
                    # Test year extraction from filename
                    path2 = Path('data/texas-handbook-2023.pdf')
                    metadata2 = uploader._extract_metadata_from_path(path2)
                    self.assertEqual(metadata2.get('year'), '2023')
                    
                    # Test version extraction
                    path3 = Path('data/manual-v2.pdf')
                    metadata3 = uploader._extract_metadata_from_path(path3)
                    self.assertEqual(metadata3.get('version'), '2')
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")


class TestIndexerRunner(unittest.TestCase):
    """Test cases for IndexerRunner class."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        os.environ['AZURE_STORAGE_ACCOUNT'] = 'teststorage'
        os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://testsearch.search.windows.net'
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_format_error(self):
        """Test error formatting."""
        try:
            from indexing.trigger_indexer import IndexerRunner
            
            with patch('indexing.trigger_indexer.DefaultAzureCredential'):
                with patch('indexing.trigger_indexer.SearchIndexerClient'):
                    runner = IndexerRunner()
                    
                    # Create mock error object
                    class MockError:
                        def __init__(self):
                            self.key = 'doc1'
                            self.error_message = 'Test error message'
                            self.status_code = 500
                            self.name = 'TestError'
                        
                        def __str__(self):
                            return self.error_message
                    
                    error = MockError()
                    formatted = runner._format_error(error)
                    
                    self.assertEqual(formatted['key'], 'doc1')
                    self.assertEqual(formatted['error_message'], 'Test error message')
                    self.assertEqual(formatted['status_code'], 500)
                    self.assertEqual(formatted['name'], 'TestError')
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")


class TestEnrichmentValidator(unittest.TestCase):
    """Test cases for EnrichmentValidator class."""
    
    def setUp(self):
        """Set up test environment."""
        self.original_env = os.environ.copy()
        os.environ['AZURE_STORAGE_ACCOUNT'] = 'teststorage'
        os.environ['AZURE_SEARCH_ENDPOINT'] = 'https://testsearch.search.windows.net'
    
    def tearDown(self):
        """Restore original environment."""
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def test_validate_document_completeness(self):
        """Test document completeness validation."""
        try:
            from indexing.validate_enrichment import EnrichmentValidator
            
            with patch('indexing.validate_enrichment.DefaultAzureCredential'):
                with patch('indexing.validate_enrichment.SearchClient'):
                    with patch('indexing.validate_enrichment.BlobServiceClient'):
                        validator = EnrichmentValidator()
                        
                        # Mock data
                        uploaded = [
                            {'name': 'california.pdf', 'size': 1024},
                            {'name': 'texas.pdf', 'size': 2048}
                        ]
                        
                        indexed = [
                            {'metadata_storage_name': 'california.pdf'},
                            {'metadata_storage_name': 'california.pdf'},
                            {'metadata_storage_name': 'texas.pdf'}
                        ]
                        
                        result = validator.validate_document_completeness(uploaded, indexed)
                        
                        self.assertEqual(result['uploaded_count'], 2)
                        self.assertEqual(result['indexed_count'], 2)
                        self.assertTrue(result['all_indexed'])
                        self.assertEqual(len(result['missing_documents']), 0)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")
    
    def test_validate_chunk_generation(self):
        """Test chunk generation validation."""
        try:
            from indexing.validate_enrichment import EnrichmentValidator
            
            with patch('indexing.validate_enrichment.DefaultAzureCredential'):
                with patch('indexing.validate_enrichment.SearchClient'):
                    with patch('indexing.validate_enrichment.BlobServiceClient'):
                        validator = EnrichmentValidator()
                        
                        # Mock indexed documents
                        indexed = [
                            {'document_id': 'doc1', 'content': 'a' * 100},
                            {'document_id': 'doc1', 'content': 'b' * 200},
                            {'document_id': 'doc2', 'content': 'c' * 150},
                        ]
                        
                        result = validator.validate_chunk_generation(indexed)
                        
                        self.assertEqual(result['total_chunks'], 3)
                        self.assertEqual(result['documents'], 2)
                        self.assertEqual(result['chunk_distribution']['doc1'], 2)
                        self.assertEqual(result['chunk_distribution']['doc2'], 1)
            
        except ImportError as e:
            self.skipTest(f"Dependencies not installed: {e}")


if __name__ == '__main__':
    unittest.main()
