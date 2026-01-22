"""
Azure AI Search tool configuration for Agent Framework v2.

This module provides configuration and helper functions for integrating
Azure AI Search with the Agent Framework v2 using the AzureAISearchTool.

The search tool enables hybrid search (keyword + vector) over the
driving manual index with support for state-specific filtering.

Key Features:
- Hybrid search (BM25 keyword + vector similarity)
- Semantic ranking for improved relevance
- State-specific filtering using OData filters
- Configurable top-k retrieval
- Result formatting for LLM context

Usage:
    from agent.search_tool import create_search_tool, format_search_results
    
    # Create search tool for agent
    search_tool = create_search_tool()
    
    # Format results for LLM context
    formatted = format_search_results(results)
"""

import logging
from typing import List, Dict, Any, Optional

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

from .config_loader import AgentConfig, load_agent_config

# Configure module logger
logger = logging.getLogger(__name__)


def create_search_tool(config: Optional[AgentConfig] = None) -> Dict[str, Any]:
    """
    Create AzureAISearchTool configuration for Agent Framework v2.
    
    This function creates a configuration dictionary for the AzureAISearchTool
    that will be attached to the agent. The tool enables hybrid search over
    the driving manual index.
    
    Hybrid Search Benefits:
    - Keyword search (BM25): Good for exact term matching (e.g., "stop sign")
    - Vector search: Good for semantic similarity (e.g., "red octagonal traffic control")
    - Semantic ranking: Re-ranks results using deep learning for better relevance
    
    The hybrid approach combines strengths of both methods, providing
    better results than either alone for driving manual queries.
    
    Args:
        config: Optional AgentConfig instance. If not provided, loads from environment.
    
    Returns:
        Dictionary with search tool configuration containing:
            - connection_id: Azure AI Search connection identifier
            - index_name: Name of the search index
            - query_type: "hybrid" for keyword + vector search
            - top_k: Number of results to retrieve
            - semantic_configuration: Name of semantic configuration (if enabled)
    
    Example:
        >>> tool = create_search_tool()
        >>> tool['index_name']
        'driving-rules-hybrid'
        >>> tool['query_type']
        'hybrid'
    """
    # Load configuration if not provided
    if config is None:
        config = load_agent_config()
    
    logger.info(
        f"Creating search tool for index '{config.search_index_name}' "
        f"with top_k={config.search_top_k}"
    )
    
    # In Agent Framework v2, the AzureAISearchTool is configured via
    # the agent's tools parameter. The exact format depends on the SDK version.
    # This configuration dictionary will be used when creating the agent.
    # 
    # Index contains character-based chunks (1000 chars, 200 overlap)
    # extracted via Azure AI Search native text extraction
    search_tool_config = {
        "type": "azure_ai_search",
        "endpoint": config.search_endpoint,
        "index_name": config.search_index_name,
        "query_type": "hybrid",  # Combines keyword (BM25) + vector search
        "top_k": config.search_top_k,
        "semantic_configuration": "default",  # Enable semantic ranking
        "use_managed_identity": config.use_managed_identity
    }
    
    logger.debug(f"Search tool configuration: {search_tool_config}")
    return search_tool_config


def get_search_client(config: Optional[AgentConfig] = None) -> SearchClient:
    """
    Get Azure AI Search client for direct search operations.
    
    This client can be used for operations outside of the agent,
    such as index validation, manual searches, or testing.
    
    Args:
        config: Optional AgentConfig instance
    
    Returns:
        SearchClient instance configured with managed identity
    
    Example:
        >>> client = get_search_client()
        >>> results = client.search("stop sign", top=5)
    """
    # Load configuration if not provided
    if config is None:
        config = load_agent_config()
    
    # Use managed identity for authentication
    credential = DefaultAzureCredential()
    
    # Create search client
    client = SearchClient(
        endpoint=config.search_endpoint,
        index_name=config.search_index_name,
        credential=credential
    )
    
    logger.info(f"Created search client for index '{config.search_index_name}'")
    return client


def build_state_filter(state: str) -> str:
    """
    Build OData filter for state-specific queries.
    
    Azure AI Search supports OData filters to narrow results to specific
    documents. This is useful for state-specific driving law queries.
    
    Filter Format:
    - Uses OData v4 syntax
    - Supports equality, comparison, and logical operators
    - Can filter on any filterable field in the index
    
    Args:
        state: State name or abbreviation (e.g., "California", "CA")
    
    Returns:
        OData filter string
    
    Example:
        >>> filter_str = build_state_filter("California")
        >>> filter_str
        "state eq 'California' or state eq 'CA'"
    """
    # Normalize state name
    state_lower = state.lower().strip()
    
    # Common state abbreviations mapping
    state_abbrev = {
        "california": "CA", "texas": "TX", "florida": "FL",
        "new york": "NY", "pennsylvania": "PA", "illinois": "IL",
        "ohio": "OH", "georgia": "GA", "north carolina": "NC",
        "michigan": "MI"
    }
    
    # Build filter for both full name and abbreviation
    if state_lower in state_abbrev:
        abbrev = state_abbrev[state_lower]
        filter_str = f"state eq '{state.title()}' or state eq '{abbrev}'"
    elif len(state) == 2 and state.isupper():
        # Already an abbreviation
        filter_str = f"state eq '{state}'"
    else:
        # Use as-is
        filter_str = f"state eq '{state}'"
    
    logger.debug(f"Built state filter: {filter_str}")
    return filter_str


def format_search_results(
    results: List[Dict[str, Any]],
    include_images: bool = False
) -> str:
    """
    Format search results for inclusion in LLM context.
    
    This function converts raw Azure AI Search results into a formatted
    string that can be included in the agent's context. The format is
    designed to provide clear citations and relevant information.
    
    Format:
    - Each result is numbered
    - Includes document name, page number, and content
    - Optionally includes image references
    - Clear separation between results
    
    Args:
        results: List of search result documents
        include_images: Whether to include image URLs in output
    
    Returns:
        Formatted string with all search results
    
    Example:
        >>> results = [{"content": "Stop signs...", "document": "CA-DMV.pdf", "page": 5}]
        >>> formatted = format_search_results(results)
        >>> print(formatted)
        [1] Source: CA-DMV.pdf (Page 5)
        Content: Stop signs...
    """
    if not results:
        return "No relevant information found in the driving manuals."
    
    formatted_parts = []
    
    for i, result in enumerate(results, 1):
        # Extract result fields (field names may vary based on index schema)
        content = result.get("content", result.get("chunk", ""))
        document = result.get("document_name", result.get("metadata_storage_name", "Unknown"))
        page = result.get("page_number", result.get("page", "N/A"))
        score = result.get("@search.score", 0.0)
        
        # Format result
        result_text = f"[{i}] Source: {document} (Page {page})\n"
        result_text += f"Content: {content}\n"
        
        # Include images if requested
        if include_images:
            image_urls = result.get("image_urls", [])
            if image_urls:
                result_text += f"Images: {', '.join(image_urls[:3])}\n"
        
        formatted_parts.append(result_text)
    
    # Join all results with separator
    formatted = "\n---\n\n".join(formatted_parts)
    
    logger.debug(f"Formatted {len(results)} search results")
    return formatted


def search_with_filter(
    query: str,
    state: Optional[str] = None,
    top_k: int = 5,
    config: Optional[AgentConfig] = None
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search with optional state filtering.
    
    This is a helper function for direct search operations outside
    of the agent framework. It combines query, filtering, and result
    retrieval in a single call.
    
    Args:
        query: Search query text
        state: Optional state name for filtering
        top_k: Number of results to retrieve
        config: Optional AgentConfig instance
    
    Returns:
        List of search result documents
    
    Example:
        >>> results = search_with_filter(
        ...     query="parking near fire hydrant",
        ...     state="California",
        ...     top_k=3
        ... )
        >>> len(results)
        3
    """
    # Get search client
    client = get_search_client(config)
    
    # Build filter if state specified
    filter_str = build_state_filter(state) if state else None
    
    # Perform search
    logger.info(
        f"Searching for '{query}' "
        f"{'with filter: ' + filter_str if filter_str else ''}"
    )
    
    # Execute hybrid search
    # Note: This is a simplified example. Production code should handle
    # vector search and semantic ranking properly.
    search_results = client.search(
        search_text=query,
        filter=filter_str,
        top=top_k,
        include_total_count=True
    )
    
    # Convert to list
    results = list(search_results)
    
    logger.info(f"Found {len(results)} results")
    return results


# Example usage and testing
if __name__ == "__main__":
    """
    Test search tool configuration and formatting.
    """
    import sys
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    try:
        # Try to load .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("Loaded .env file\n")
        except ImportError:
            print("python-dotenv not installed, using environment variables only\n")
        
        # Create search tool configuration
        print("Creating search tool configuration...")
        tool_config = create_search_tool()
        
        print("\n" + "="*60)
        print("Search Tool Configuration")
        print("="*60)
        print(f"Index name:  {tool_config['index_name']}")
        print(f"Query type:  {tool_config['query_type']}")
        print(f"Top K:       {tool_config['top_k']}")
        print(f"Endpoint:    {tool_config['endpoint']}")
        print("="*60 + "\n")
        
        # Test state filter
        print("Testing state filter...")
        filter_ca = build_state_filter("California")
        filter_tx = build_state_filter("TX")
        print(f"California filter: {filter_ca}")
        print(f"Texas filter:      {filter_tx}\n")
        
        # Test result formatting
        print("Testing result formatting...")
        sample_results = [
            {
                "content": "A stop sign is an octagonal red sign with white letters.",
                "document_name": "california-dmv-handbook.pdf",
                "page_number": 5,
                "@search.score": 0.89
            },
            {
                "content": "You must come to a complete stop at stop signs.",
                "document_name": "california-dmv-handbook.pdf",
                "page_number": 12,
                "@search.score": 0.76
            }
        ]
        
        formatted = format_search_results(sample_results)
        print("\nFormatted Results:")
        print(formatted)
        
        print("\n✓ All tests passed!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}\n", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
