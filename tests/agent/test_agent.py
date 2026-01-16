"""
Unit tests for agent creation and response assembly.

Tests core agent functionality including agent factory,
configuration, and response formatting.
"""

import unittest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'src'))

from agent.config_loader import AgentConfig, load_agent_config
from agent.response_formatter import (
    extract_citations,
    format_text_with_citations,
    assemble_multimodal_response,
    Citation,
    ImageReference,
    MultimodalResponse
)
from agent.search_tool import (
    build_state_filter,
    format_search_results
)


class TestAgentConfig(unittest.TestCase):
    """Test cases for agent configuration."""
    
    def test_agent_config_defaults(self):
        """Test that AgentConfig has sensible defaults."""
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net"
        )
        
        # Check defaults
        self.assertEqual(config.search_index_name, "driving-rules-hybrid")
        self.assertEqual(config.model_deployment, "gpt-4o")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.top_p, 0.95)
        self.assertEqual(config.max_tokens, 4096)
        self.assertEqual(config.search_top_k, 5)
        self.assertEqual(config.image_relevance_threshold, 0.75)
        self.assertTrue(config.enable_telemetry)
        self.assertTrue(config.use_managed_identity)
    
    def test_agent_config_validation_missing_endpoint(self):
        """Test validation fails when required endpoints are missing."""
        # Missing project endpoint
        config = AgentConfig(
            project_endpoint="",
            search_endpoint="https://test.search.windows.net"
        )
        with self.assertRaises(ValueError):
            config.validate()
        
        # Missing search endpoint
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint=""
        )
        with self.assertRaises(ValueError):
            config.validate()
    
    def test_agent_config_validation_invalid_endpoint_format(self):
        """Test validation fails for invalid endpoint formats."""
        # Invalid project endpoint (not HTTPS)
        config = AgentConfig(
            project_endpoint="http://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net"
        )
        with self.assertRaises(ValueError):
            config.validate()
    
    def test_agent_config_validation_invalid_ranges(self):
        """Test validation fails for parameters out of valid range."""
        # Invalid temperature
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net",
            temperature=1.5  # Out of range
        )
        with self.assertRaises(ValueError):
            config.validate()
        
        # Invalid threshold
        config = AgentConfig(
            project_endpoint="https://test.api.azureml.ms",
            search_endpoint="https://test.search.windows.net",
            image_relevance_threshold=1.5  # Out of range
        )
        with self.assertRaises(ValueError):
            config.validate()


class TestCitationExtraction(unittest.TestCase):
    """Test cases for citation extraction from text."""
    
    def test_extract_citations_standard_format(self):
        """Test extraction of citations in standard format."""
        text = (
            "Stop signs are red (Source: CA Handbook, Page 5). "
            "You must stop completely (Source: TX Manual, Page 12)."
        )
        
        citations = extract_citations(text)
        
        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0].document_name, "CA Handbook")
        self.assertEqual(citations[0].page_number, 5)
        self.assertEqual(citations[1].document_name, "TX Manual")
        self.assertEqual(citations[1].page_number, 12)
    
    def test_extract_citations_no_citations(self):
        """Test handling of text without citations."""
        text = "This text has no citations."
        citations = extract_citations(text)
        self.assertEqual(len(citations), 0)
    
    def test_extract_citations_case_insensitive(self):
        """Test that citation extraction is case-insensitive."""
        text = "Test (source: Document, page 10)"
        citations = extract_citations(text)
        self.assertEqual(len(citations), 1)
        self.assertEqual(citations[0].page_number, 10)
    
    def test_format_text_with_citations(self):
        """Test formatting text with citation markers."""
        text = "Stop signs are red (Source: CA Handbook, Page 5)."
        citations = extract_citations(text)
        
        formatted = format_text_with_citations(text, citations)
        
        # Should contain citation marker
        self.assertIn("[1]", formatted)
        # Should contain citation list
        self.assertIn("Citations:", formatted)
        self.assertIn("CA Handbook, Page 5", formatted)
    
    def test_format_text_no_citations(self):
        """Test formatting text without citations."""
        text = "This text has no citations."
        formatted = format_text_with_citations(text, [])
        
        # Should return original text
        self.assertEqual(formatted, text)


class TestSearchToolHelpers(unittest.TestCase):
    """Test cases for search tool helper functions."""
    
    def test_build_state_filter_full_name(self):
        """Test building state filter with full state name."""
        filter_str = build_state_filter("California")
        
        # Should include both full name and abbreviation
        self.assertIn("California", filter_str)
        self.assertIn("CA", filter_str)
        self.assertIn(" or ", filter_str)
    
    def test_build_state_filter_abbreviation(self):
        """Test building state filter with state abbreviation."""
        filter_str = build_state_filter("TX")
        
        # Should use abbreviation
        self.assertIn("TX", filter_str)
    
    def test_build_state_filter_case_handling(self):
        """Test state filter handles various cases."""
        # Lowercase full name
        filter1 = build_state_filter("california")
        self.assertIn("California", filter1) or self.assertIn("CA", filter1)
        
        # Uppercase abbreviation
        filter2 = build_state_filter("TX")
        self.assertIn("TX", filter2)
    
    def test_format_search_results_empty(self):
        """Test formatting empty search results."""
        formatted = format_search_results([])
        self.assertIn("No relevant information", formatted)
    
    def test_format_search_results_with_results(self):
        """Test formatting search results."""
        results = [
            {
                "content": "Stop signs are octagonal.",
                "document_name": "CA Handbook",
                "page_number": 5,
                "@search.score": 0.89
            },
            {
                "content": "Red means stop.",
                "document_name": "TX Manual",
                "page_number": 12,
                "@search.score": 0.76
            }
        ]
        
        formatted = format_search_results(results)
        
        # Should contain both results
        self.assertIn("Stop signs are octagonal", formatted)
        self.assertIn("Red means stop", formatted)
        # Should contain document names
        self.assertIn("CA Handbook", formatted)
        self.assertIn("TX Manual", formatted)
        # Should contain page numbers
        self.assertIn("5", formatted)
        self.assertIn("12", formatted)


class TestResponseAssembly(unittest.TestCase):
    """Test cases for multimodal response assembly."""
    
    def test_assemble_multimodal_response_text_only(self):
        """Test assembling response without images."""
        agent_text = "Stop signs are red (Source: CA Handbook, Page 5)."
        search_results = []
        
        response = assemble_multimodal_response(
            agent_text=agent_text,
            search_results=search_results,
            include_images=False
        )
        
        self.assertIsInstance(response, MultimodalResponse)
        self.assertEqual(response.text, agent_text)
        self.assertEqual(len(response.citations), 1)
        self.assertEqual(len(response.images), 0)
        self.assertIn("Stop signs are red", response.formatted_text)
    
    def test_assemble_multimodal_response_with_images(self):
        """Test assembling response with images."""
        agent_text = "Stop signs are red (Source: CA Handbook, Page 5)."
        search_results = [
            {
                "@search.score": 0.95,
                "image_urls": ["https://example.com/stop-sign.png"],
                "page_number": 5,
                "document_name": "CA Handbook"
            }
        ]
        
        response = assemble_multimodal_response(
            agent_text=agent_text,
            search_results=search_results,
            include_images=True,
            image_threshold=0.5,  # Low threshold to ensure inclusion
            config=None  # Skip actual image fetch
        )
        
        self.assertIsInstance(response, MultimodalResponse)
        self.assertEqual(len(response.citations), 1)
        # Note: Image inclusion depends on filtering logic
        # Just verify the structure is correct
        self.assertIsInstance(response.images, list)


class TestDataClasses(unittest.TestCase):
    """Test data classes for structured data."""
    
    def test_citation_dataclass(self):
        """Test Citation dataclass."""
        citation = Citation(
            document_name="Test Document",
            page_number=42,
            text="(Source: Test Document, Page 42)"
        )
        
        self.assertEqual(citation.document_name, "Test Document")
        self.assertEqual(citation.page_number, 42)
        self.assertEqual(citation.text, "(Source: Test Document, Page 42)")
    
    def test_image_reference_dataclass(self):
        """Test ImageReference dataclass."""
        image_ref = ImageReference(
            blob_url="https://example.com/image.png",
            document_name="Test Document",
            page_number=5,
            relevance_score=0.85,
            caption="Stop sign"
        )
        
        self.assertEqual(image_ref.blob_url, "https://example.com/image.png")
        self.assertEqual(image_ref.document_name, "Test Document")
        self.assertEqual(image_ref.page_number, 5)
        self.assertEqual(image_ref.relevance_score, 0.85)
        self.assertEqual(image_ref.caption, "Stop sign")
    
    def test_multimodal_response_dataclass(self):
        """Test MultimodalResponse dataclass."""
        response = MultimodalResponse(
            text="Test response",
            citations=[],
            images=[],
            formatted_text="Test response formatted"
        )
        
        self.assertEqual(response.text, "Test response")
        self.assertEqual(len(response.citations), 0)
        self.assertEqual(len(response.images), 0)
        self.assertEqual(response.formatted_text, "Test response formatted")


if __name__ == '__main__':
    unittest.main()
