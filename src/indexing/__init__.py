"""
Azure AI Search Indexer Pipeline Module

This module provides tools for managing and validating the Azure AI Search
indexer pipeline for processing PDF driving manuals.

Components:
- validate_indexer.py: Validation script for skillset and indexer health
- generate_test_pdfs.py: Generate sample PDF driving manuals for testing

Usage:
    from src.indexing.validate_indexer import IndexerValidator
    
    validator = IndexerValidator(
        search_endpoint="https://your-search.search.windows.net",
        index_name="driving-manual-index"
    )
    results = validator.run_full_validation(
        skillset_name="driving-manual-skillset",
        indexer_name="driving-manual-indexer"
    )
"""

__version__ = "1.0.0"
__all__ = ["IndexerValidator"]

try:
    from .validate_indexer import IndexerValidator
except ImportError:
    # Allow module to load even if dependencies not installed
    IndexerValidator = None
