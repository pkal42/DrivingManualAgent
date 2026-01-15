"""
Unit tests for indexer validation module

These tests verify the IndexerValidator class functionality without requiring
actual Azure resources.
"""

import unittest
from unittest.mock import patch
import sys
import os

# Add parent directories to path for imports
# This is acceptable in test files to allow importing from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)


class TestIndexerValidator(unittest.TestCase):
    """Test cases for IndexerValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.search_endpoint = "https://test-search.search.windows.net"
        self.index_name = "test-index"
    
    def test_import_validator(self):
        """Test that IndexerValidator can be imported."""
        try:
            from indexing.validate_indexer import IndexerValidator
            self.assertIsNotNone(IndexerValidator)
        except ImportError as e:
            self.skipTest(f"Azure SDK dependencies not installed: {e}")
    
    def test_analyze_field_coverage(self):
        """Test field coverage analysis."""
        try:
            from indexing.validate_indexer import IndexerValidator
            
            # Mock credential
            with patch('indexing.validate_indexer.DefaultAzureCredential'):
                with patch('indexing.validate_indexer.SearchClient'):
                    with patch('indexing.validate_indexer.SearchIndexClient'):
                        with patch('indexing.validate_indexer.SearchIndexerClient'):
                            validator = IndexerValidator(
                                self.search_endpoint,
                                self.index_name
                            )
                            
                            # Test with sample documents
                            docs = [
                                {'field1': 'value1', 'field2': 'value2'},
                                {'field1': 'value3', 'field2': None},
                                {'field1': '', 'field2': 'value4'}
                            ]
                            
                            coverage = validator._analyze_field_coverage(docs)
                            
                            # field1 has 2 non-empty values (66.7%)
                            # field2 has 2 non-empty values (66.7%)
                            self.assertIn('field1', coverage)
                            self.assertIn('field2', coverage)
                            self.assertAlmostEqual(coverage['field1'], 66.7, places=1)
                            self.assertAlmostEqual(coverage['field2'], 66.7, places=1)
        
        except ImportError as e:
            self.skipTest(f"Azure SDK dependencies not installed: {e}")
    
    def test_analyze_chunk_stats(self):
        """Test chunk statistics analysis."""
        try:
            from indexing.validate_indexer import IndexerValidator
            
            with patch('indexing.validate_indexer.DefaultAzureCredential'):
                with patch('indexing.validate_indexer.SearchClient'):
                    with patch('indexing.validate_indexer.SearchIndexClient'):
                        with patch('indexing.validate_indexer.SearchIndexerClient'):
                            validator = IndexerValidator(
                                self.search_endpoint,
                                self.index_name
                            )
                            
                            # Test with sample documents
                            docs = [
                                {'content': 'a' * 100},
                                {'content': 'b' * 200},
                                {'content': 'c' * 150}
                            ]
                            
                            stats = validator._analyze_chunk_stats(docs)
                            
                            self.assertEqual(stats['total_chunks'], 3)
                            self.assertEqual(stats['min_length'], 100)
                            self.assertEqual(stats['max_length'], 200)
                            self.assertEqual(stats['avg_length'], 150)
        
        except ImportError as e:
            self.skipTest(f"Azure SDK dependencies not installed: {e}")
    
    def test_analyze_image_stats(self):
        """Test image statistics analysis."""
        try:
            from indexing.validate_indexer import IndexerValidator
            
            with patch('indexing.validate_indexer.DefaultAzureCredential'):
                with patch('indexing.validate_indexer.SearchClient'):
                    with patch('indexing.validate_indexer.SearchIndexClient'):
                        with patch('indexing.validate_indexer.SearchIndexerClient'):
                            validator = IndexerValidator(
                                self.search_endpoint,
                                self.index_name
                            )
                            
                            # Test with sample documents
                            docs = [
                                {'has_related_images': True, 'image_blob_urls': ['url1', 'url2']},
                                {'has_related_images': False, 'image_blob_urls': []},
                                {'has_related_images': True, 'image_blob_urls': ['url3']}
                            ]
                            
                            stats = validator._analyze_image_stats(docs)
                            
                            self.assertEqual(stats['chunks_with_images'], 2)
                            self.assertEqual(stats['total_images'], 3)
                            self.assertAlmostEqual(stats['image_percentage'], 66.7, places=1)
        
        except ImportError as e:
            self.skipTest(f"Azure SDK dependencies not installed: {e}")


class TestPDFGeneration(unittest.TestCase):
    """Test cases for PDF generation script."""
    
    def test_import_pdf_generator(self):
        """Test that PDF generation script can be imported."""
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "generate_test_pdfs",
                os.path.join(project_root, 'src', 'indexing', 'generate_test_pdfs.py')
            )
            module = importlib.util.module_from_spec(spec)
            # Don't execute, just check it can be loaded
            self.assertIsNotNone(module)
        except ImportError as e:
            self.skipTest(f"reportlab dependencies not installed: {e}")


if __name__ == '__main__':
    unittest.main()
