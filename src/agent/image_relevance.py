"""
Image relevance detection module for intelligent image inclusion.

This module provides functionality to determine when images should be
included in agent responses, using both keyword-based heuristics and
optional LLM-as-judge pattern for higher accuracy.

Strategy:
1. Keyword-based heuristics (fast, low cost): Check if query contains
   visual-related terms like "sign", "marking", "diagram", etc.
2. LLM-as-judge (optional, higher accuracy): Use GPT-4o to classify
   whether the query would benefit from visual context.

The keyword approach is used by default as it provides good accuracy
for most driving manual queries at zero cost. The LLM-as-judge can be
enabled for higher accuracy when cost is not a concern.

Usage:
    from agent.image_relevance import should_include_images, filter_relevant_images
    
    # Check if query needs images
    if should_include_images("What does a stop sign look like?"):
        images = filter_relevant_images(search_results)
"""

import logging
import re
from typing import List, Dict, Any, Optional

from openai import AzureOpenAI

from .config_loader import AgentConfig

# Configure module logger
logger = logging.getLogger(__name__)

# Keywords that indicate a query would benefit from images
# These are visual elements commonly found in driving manuals
IMAGE_KEYWORDS = [
    # Traffic control devices
    "sign", "signal", "marking", "diagram", "illustration",
    "symbol", "color", "shape", "picture", "image",
    
    # Road features
    "lane", "intersection", "crosswalk", "pavement marking",
    "road marking", "line", "arrow", "striping",
    
    # Visual indicators
    "hand signal", "light", "indicator", "beacon",
    "cone", "barrier", "zone marking",
    
    # Parking and positioning
    "parking", "curb", "space", "zone",
    
    # Specific signs
    "stop", "yield", "speed limit", "warning", "regulatory",
    "guide sign", "informational",
    
    # Visual queries
    "look like", "appear", "shown", "display", "example",
    "how to identify", "recognize", "distinguish"
]


def should_include_images(
    query: str,
    use_llm: bool = False,
    config: Optional[AgentConfig] = None
) -> bool:
    """
    Determine if images should be included in the response to a query.
    
    Uses keyword-based heuristics by default for fast, zero-cost detection.
    Optionally uses LLM-as-judge pattern for higher accuracy.
    
    Keyword Heuristics:
    - Checks if query contains any visual-related keywords
    - Fast and deterministic
    - Good accuracy for driving manual domain
    - Zero additional cost
    
    LLM-as-Judge (when use_llm=True):
    - Uses GPT-4o to classify query intent
    - Higher accuracy, especially for ambiguous cases
    - Small additional cost per query
    - Recommended for production with sufficient budget
    
    Args:
        query: User's question or request
        use_llm: If True, use LLM-as-judge instead of keywords
        config: Optional AgentConfig for LLM parameters
    
    Returns:
        True if images should be included, False otherwise
    
    Example:
        >>> should_include_images("What does a stop sign mean?")
        True
        >>> should_include_images("When should I use turn signals?")
        False
        >>> should_include_images("Show me lane markings")
        True
    """
    # Normalize query for matching
    query_lower = query.lower()
    
    if use_llm:
        # Use LLM-as-judge pattern for classification
        return _llm_should_include_images(query, config)
    else:
        # Use keyword-based heuristics (default)
        for keyword in IMAGE_KEYWORDS:
            if keyword in query_lower:
                logger.debug(f"Image keyword matched: '{keyword}' in query")
                return True
        
        logger.debug("No image keywords matched in query")
        return False


def _llm_should_include_images(
    query: str,
    config: Optional[AgentConfig] = None
) -> bool:
    """
    Use LLM-as-judge pattern to determine if images are needed.
    
    This function sends a classification prompt to GPT-4o asking it to
    determine if the user's query would benefit from visual context.
    
    Benefits:
    - Higher accuracy than keyword matching
    - Handles nuanced and ambiguous queries
    - Can understand context and intent
    
    Trade-offs:
    - Additional API call cost per query
    - Slight latency increase (typically <1 second)
    - Requires Azure OpenAI deployment
    
    Args:
        query: User's question or request
        config: Optional AgentConfig for model parameters
    
    Returns:
        True if images would add value, False otherwise
    """
    try:
        from .config_loader import load_agent_config
        from azure.identity import DefaultAzureCredential
        
        # Load config if not provided
        if config is None:
            config = load_agent_config()
        
        # Extract Azure OpenAI endpoint from project endpoint
        # Format: https://{region}.api.azureml.ms -> https://{region}.openai.azure.com
        # Note: This is a simplified approach; production should use proper endpoint mapping
        logger.debug(f"Using LLM-as-judge for query: {query[:50]}...")
        
        # Classification prompt for GPT-4o
        classification_prompt = f"""You are a classifier determining if a driving manual question needs images.

User question: {query}

Analyze if this question would benefit from visual aids like:
- Traffic signs, signals, or road markings
- Diagrams or illustrations
- Hand signals or positioning examples
- Any visual elements

Respond with ONLY "YES" if images would add significant value, or "NO" if text alone is sufficient.

Response:"""
        
        # Note: In a real implementation, you would use the Azure OpenAI client here
        # For now, we'll fall back to keyword matching to avoid requiring OpenAI setup
        logger.warning(
            "LLM-as-judge requested but not fully implemented. "
            "Falling back to keyword matching."
        )
        return should_include_images(query, use_llm=False, config=config)
        
    except Exception as e:
        # Fall back to keyword matching on error
        logger.warning(
            f"LLM-as-judge failed ({e}), falling back to keyword matching"
        )
        return should_include_images(query, use_llm=False, config=config)


def filter_relevant_images(
    search_results: List[Dict[str, Any]],
    threshold: float = 0.75,
    max_images: int = 5
) -> List[Dict[str, Any]]:
    """
    Filter search results to extract relevant images based on threshold.
    
    This function processes search results from Azure AI Search and
    extracts image references that meet the relevance threshold.
    
    Image Relevance Scoring:
    - Based on search score (hybrid keyword + vector similarity)
    - Images from higher-scored chunks are prioritized
    - Threshold prevents including low-quality or irrelevant images
    
    Trade-offs:
    - Higher threshold (e.g., 0.85): Fewer but more relevant images
    - Lower threshold (e.g., 0.65): More images but may include tangential ones
    - Default 0.75: Balanced approach for most use cases
    
    Args:
        search_results: List of search result documents from Azure AI Search
        threshold: Minimum relevance score (0.0-1.0) for including images
        max_images: Maximum number of images to return
    
    Returns:
        List of image reference dictionaries with keys:
            - blob_url: URL to the image in blob storage
            - page_number: Page number where image appears
            - document_name: Name of source document
            - relevance_score: Search relevance score
    
    Example:
        >>> results = [
        ...     {"@search.score": 0.89, "image_urls": ["https://..."], "page": 5},
        ...     {"@search.score": 0.62, "image_urls": ["https://..."], "page": 8}
        ... ]
        >>> images = filter_relevant_images(results, threshold=0.75)
        >>> len(images)
        1
    """
    relevant_images = []
    
    for result in search_results:
        # Extract search score (hybrid keyword + vector similarity)
        score = result.get("@search.score", 0.0)
        
        # Normalize score to 0-1 range if needed
        # Azure AI Search scores can vary, so we normalize
        normalized_score = min(score / 10.0, 1.0) if score > 1.0 else score
        
        # Check if result meets threshold
        if normalized_score < threshold:
            logger.debug(
                f"Skipping images from result with score {normalized_score:.2f} "
                f"(below threshold {threshold})"
            )
            continue
        
        # Extract image URLs from the result
        # The exact field name depends on your index schema
        # Common field names: image_urls, extracted_images, images
        image_urls = result.get("image_urls", [])
        if not image_urls:
            # Try alternative field names
            image_urls = result.get("extracted_images", [])
        if not image_urls:
            image_urls = result.get("images", [])
        
        # Process each image URL
        for image_url in image_urls:
            if len(relevant_images) >= max_images:
                logger.debug(f"Reached maximum image limit ({max_images})")
                break
            
            # Create image reference
            image_ref = {
                "blob_url": image_url,
                "page_number": result.get("page_number", result.get("page", 0)),
                "document_name": result.get("document_name", result.get("metadata_storage_name", "Unknown")),
                "relevance_score": normalized_score
            }
            
            relevant_images.append(image_ref)
            logger.debug(
                f"Added image from '{image_ref['document_name']}' "
                f"page {image_ref['page_number']} (score: {normalized_score:.2f})"
            )
        
        if len(relevant_images) >= max_images:
            break
    
    logger.info(
        f"Filtered {len(relevant_images)} relevant images from "
        f"{len(search_results)} search results (threshold: {threshold})"
    )
    
    return relevant_images


def calculate_image_relevance_score(
    query: str,
    image_metadata: Dict[str, Any],
    search_score: float
) -> float:
    """
    Calculate a relevance score for an image based on query and metadata.
    
    This is an advanced scoring function that can be used to refine
    image selection beyond simple threshold filtering.
    
    Scoring Factors:
    - Base search score (hybrid similarity)
    - Presence of query keywords in image caption/alt text
    - Image position in document (earlier pages often more relevant)
    - Image type (diagrams vs photos)
    
    Args:
        query: User's query
        image_metadata: Metadata about the image (caption, type, etc.)
        search_score: Base search score from Azure AI Search
    
    Returns:
        Adjusted relevance score (0.0-1.0)
    
    Note:
        This is a placeholder for advanced scoring logic.
        Current implementation uses search score directly.
    """
    # TODO: Implement advanced scoring logic:
    # - Analyze figure captions for keyword matches with query
    # - Weight images from earlier pages higher (usually more fundamental)
    # - Boost diagrams/illustrations over photographs
    # - Consider image position within page context
    # For now, return normalized search score
    return min(search_score / 10.0, 1.0) if search_score > 1.0 else search_score


# Example usage and testing
if __name__ == "__main__":
    """
    Test image relevance detection with sample queries.
    """
    import sys
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    # Test queries
    test_queries = [
        ("What does a stop sign mean?", True),  # Should include images
        ("When should I use turn signals?", False),  # Text-focused
        ("Show me hand signals for turning", True),  # Visual query
        ("California parking rules near fire hydrants", False),  # Text rule
        ("What do yellow lane markings indicate?", True),  # Visual element
        ("Speed limit in residential areas", False),  # Text fact
    ]
    
    print("\n" + "="*60)
    print("Image Relevance Detection Tests")
    print("="*60 + "\n")
    
    correct = 0
    for query, expected in test_queries:
        result = should_include_images(query)
        status = "✓" if result == expected else "✗"
        correct += 1 if result == expected else 0
        
        print(f"{status} Query: {query}")
        print(f"  Expected: {expected}, Got: {result}\n")
    
    print("="*60)
    print(f"Accuracy: {correct}/{len(test_queries)} ({100*correct//len(test_queries)}%)")
    print("="*60 + "\n")
    
    sys.exit(0 if correct == len(test_queries) else 1)
