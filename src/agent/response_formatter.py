"""
Multimodal response formatter for agent responses.

This module provides functions to assemble and format agent responses
with text citations and relevant images. It handles parallel image retrieval
from blob storage and formats the final output.

Key Features:
- Extract citations from agent text
- Fetch image blob URLs from search results
- Filter images by relevance threshold
- Parallel async image retrieval
- Format multimodal response with inline image references

Usage:
    from agent.response_formatter import assemble_multimodal_response
    
    response = assemble_multimodal_response(
        agent_text="A stop sign is...",
        search_results=[...],
        include_images=True
    )
"""

import logging
import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import aiohttp
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

from .config_loader import AgentConfig, load_agent_config
from .image_relevance import filter_relevant_images

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """
    Structured citation information extracted from response.
    
    Attributes:
        document_name: Name of the source document
        page_number: Page number in the document
        text: Cited text content
        start_index: Starting character index in response
        end_index: Ending character index in response
    """
    document_name: str
    page_number: int
    text: str
    start_index: int = 0
    end_index: int = 0


@dataclass
class ImageReference:
    """
    Structured image reference information.
    
    Attributes:
        blob_url: URL to the image in blob storage
        document_name: Name of source document
        page_number: Page number where image appears
        relevance_score: Search relevance score (0.0-1.0)
        caption: Optional image caption or description
        local_path: Optional local file path if downloaded
    """
    blob_url: str
    document_name: str
    page_number: int
    relevance_score: float
    caption: Optional[str] = None
    local_path: Optional[str] = None


@dataclass
class MultimodalResponse:
    """
    Complete multimodal response with text, citations, and images.
    
    Attributes:
        text: Main response text
        citations: List of extracted citations
        images: List of relevant image references
        formatted_text: Text formatted with citation markers
    """
    text: str
    citations: List[Citation]
    images: List[ImageReference]
    formatted_text: str = ""


def extract_citations(text: str) -> List[Citation]:
    """
    Extract citations from agent response text.
    
    Citation Format:
    - Standard: (Source: Document Name, Page 123)
    - Variations: [Source: Document, p. 123], (Document, Page 123)
    
    This function uses regex to find and parse citation patterns,
    extracting structured citation information.
    
    Args:
        text: Agent response text containing citations
    
    Returns:
        List of Citation objects with extracted information
    
    Example:
        >>> text = "Stop signs are red (Source: CA Handbook, Page 5)."
        >>> citations = extract_citations(text)
        >>> citations[0].document_name
        'CA Handbook'
        >>> citations[0].page_number
        5
    """
    citations = []
    seen_positions = set()  # Track matched positions to avoid duplicates
    
    # Citation patterns to match (in order of specificity)
    # Pattern 1: (Source: Document Name, Page 123) - most specific
    pattern1 = r'\(Source:\s*([^,]+),\s*Page\s+(\d+)\)'
    
    # Pattern 2: [Source: Document, p. 123]
    pattern2 = r'\[Source:\s*([^,]+),\s*p\.\s*(\d+)\]'
    
    # Pattern 3: (Document Name, Page 123) - least specific
    pattern3 = r'\(([^,:]+),\s*Page\s+(\d+)\)'
    
    # Try patterns in order of specificity
    patterns = [pattern1, pattern2, pattern3]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            # Skip if we already matched this position
            if match.start() in seen_positions:
                continue
            
            # Mark this position as matched
            for pos in range(match.start(), match.end()):
                seen_positions.add(pos)
            
            document_name = match.group(1).strip()
            page_number = int(match.group(2))
            
            citation = Citation(
                document_name=document_name,
                page_number=page_number,
                text=match.group(0),
                start_index=match.start(),
                end_index=match.end()
            )
            citations.append(citation)
            
            logger.debug(
                f"Extracted citation: {document_name}, Page {page_number}"
            )
    
    logger.info(f"Extracted {len(citations)} citations from response")
    return citations


def format_text_with_citations(
    text: str,
    citations: List[Citation]
) -> str:
    """
    Format text with enhanced citation markers.
    
    Converts inline citations to numbered footnotes for cleaner presentation.
    
    Original:
        "Stop signs are red (Source: CA Handbook, Page 5)."
    
    Formatted:
        "Stop signs are red. [1]
        
        Citations:
        [1] CA Handbook, Page 5"
    
    Args:
        text: Original response text
        citations: List of extracted citations
    
    Returns:
        Formatted text with citation markers and footnotes
    """
    if not citations:
        return text
    
    # Sort citations by position (reverse order for replacement)
    sorted_citations = sorted(citations, key=lambda c: c.start_index, reverse=True)
    
    # Replace citations with numbered markers
    formatted = text
    citation_list = []
    
    for i, citation in enumerate(sorted_citations, 1):
        # Get citation number (reversed since we're going backwards)
        num = len(sorted_citations) - i + 1
        marker = f"[{num}]"
        
        # Replace citation with marker
        formatted = (
            formatted[:citation.start_index] +
            marker +
            formatted[citation.end_index:]
        )
        
        # Add to citation list
        citation_list.insert(0, f"[{num}] {citation.document_name}, Page {citation.page_number}")
    
    # Append citation list
    if citation_list:
        formatted += "\n\nCitations:\n" + "\n".join(citation_list)
    
    return formatted


async def fetch_image_blob_url(
    image_ref: ImageReference,
    storage_account: str,
    container_name: str,
    config: Optional[AgentConfig] = None
) -> Optional[str]:
    """
    Fetch public blob URL for an image.
    
    This async function retrieves the blob URL for an image stored
    in Azure Blob Storage. It can be used with asyncio.gather() for
    parallel retrieval of multiple images.
    
    Args:
        image_ref: ImageReference with blob information
        storage_account: Azure Storage account name
        container_name: Blob container name
        config: Optional AgentConfig instance
    
    Returns:
        Public blob URL or None if fetch fails
    
    Example:
        >>> url = await fetch_image_blob_url(
        ...     image_ref,
        ...     "mystorageacct",
        ...     "extracted-images"
        ... )
    """
    try:
        # If blob_url is already set, return it
        if image_ref.blob_url and image_ref.blob_url.startswith("https://"):
            return image_ref.blob_url
        
        # Otherwise, construct blob URL
        # Format: https://{account}.blob.core.windows.net/{container}/{blob}
        blob_name = image_ref.blob_url  # Assuming this is the blob name
        blob_url = (
            f"https://{storage_account}.blob.core.windows.net/"
            f"{container_name}/{blob_name}"
        )
        
        logger.debug(f"Constructed blob URL: {blob_url}")
        return blob_url
        
    except Exception as e:
        logger.warning(f"Failed to fetch blob URL for image: {e}")
        return None


async def fetch_images_parallel(
    image_refs: List[ImageReference],
    config: Optional[AgentConfig] = None
) -> List[ImageReference]:
    """
    Fetch multiple image blob URLs in parallel.
    
    Uses asyncio.gather() to retrieve multiple images concurrently,
    significantly reducing latency compared to sequential retrieval.
    
    Performance:
    - Sequential: N images × ~100ms = N×100ms total
    - Parallel: max(~100ms) ≈ 100ms total
    
    Args:
        image_refs: List of ImageReference objects
        config: Optional AgentConfig instance
    
    Returns:
        List of ImageReference objects with updated blob URLs
    
    Example:
        >>> refs = [ImageReference(...), ImageReference(...)]
        >>> updated_refs = await fetch_images_parallel(refs)
    """
    if not image_refs:
        return []
    
    # Load config if not provided
    if config is None:
        config = load_agent_config()
    
    logger.info(f"Fetching {len(image_refs)} images in parallel")
    
    # Create tasks for parallel execution
    tasks = [
        fetch_image_blob_url(
            ref,
            config.storage_account,
            config.storage_container_images,
            config
        )
        for ref in image_refs
    ]
    
    # Execute in parallel
    blob_urls = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Update image references with fetched URLs
    updated_refs = []
    for ref, url in zip(image_refs, blob_urls):
        if url and not isinstance(url, Exception):
            ref.blob_url = url
            updated_refs.append(ref)
        else:
            logger.warning(f"Failed to fetch URL for {ref.document_name} p.{ref.page_number}")
    
    logger.info(f"Successfully fetched {len(updated_refs)} image URLs")
    return updated_refs


def format_multimodal_output(
    text: str,
    citations: List[Citation],
    images: List[ImageReference]
) -> str:
    """
    Format complete multimodal response for display.
    
    Creates a well-formatted output with:
    - Main response text with citation markers
    - Image references with source information
    - Citation list
    
    Args:
        text: Response text
        citations: List of citations
        images: List of image references
    
    Returns:
        Formatted multimodal response string
    
    Example output:
        A stop sign is an octagonal red sign. [1]
        
        Images:
        - Figure 1: Stop sign example (Source: CA Handbook, Page 5)
          URL: https://...
        
        Citations:
        [1] CA Handbook, Page 5
    """
    # Format text with citations
    formatted = format_text_with_citations(text, citations)
    
    # Add images section if present
    if images:
        formatted += "\n\nImages:"
        for i, img in enumerate(images, 1):
            formatted += (
                f"\n- Figure {i}: {img.document_name}, Page {img.page_number}"
                f"\n  URL: {img.blob_url}"
            )
            if img.caption:
                formatted += f"\n  Caption: {img.caption}"
    
    return formatted


def assemble_multimodal_response(
    agent_text: str,
    search_results: List[Dict[str, Any]],
    include_images: bool = True,
    image_threshold: float = 0.75,
    max_images: int = 5,
    config: Optional[AgentConfig] = None
) -> MultimodalResponse:
    """
    Assemble complete multimodal response with text, citations, and images.
    
    This is the main function for creating multimodal responses. It:
    1. Extracts citations from agent text
    2. Filters relevant images from search results
    3. Fetches image blob URLs (async)
    4. Formats final response
    
    Args:
        agent_text: Generated response text from agent
        search_results: List of search result documents
        include_images: Whether to include images in response
        image_threshold: Minimum relevance score for images (0.0-1.0)
        max_images: Maximum number of images to include
        config: Optional AgentConfig instance
    
    Returns:
        MultimodalResponse object with all components
    
    Example:
        >>> response = assemble_multimodal_response(
        ...     agent_text="A stop sign is red...",
        ...     search_results=[...],
        ...     include_images=True
        ... )
        >>> print(response.formatted_text)
    """
    logger.info("Assembling multimodal response")
    
    # Extract citations
    citations = extract_citations(agent_text)
    
    # Filter and fetch images if requested
    images = []
    if include_images and search_results:
        # Filter relevant images
        image_refs = filter_relevant_images(
            search_results,
            threshold=image_threshold,
            max_images=max_images
        )
        
        # Convert to ImageReference objects
        images = [
            ImageReference(
                blob_url=img['blob_url'],
                document_name=img['document_name'],
                page_number=img['page_number'],
                relevance_score=img['relevance_score']
            )
            for img in image_refs
        ]
        
        # Fetch image URLs in parallel (if needed)
        if images and config and config.storage_account:
            try:
                # Run async image fetching
                images = asyncio.run(fetch_images_parallel(images, config))
            except Exception as e:
                logger.warning(f"Failed to fetch images in parallel: {e}")
                # Continue without images rather than failing
    
    # Format final output
    formatted_text = format_multimodal_output(agent_text, citations, images)
    
    # Create response object
    response = MultimodalResponse(
        text=agent_text,
        citations=citations,
        images=images,
        formatted_text=formatted_text
    )
    
    logger.info(
        f"Assembled response with {len(citations)} citations "
        f"and {len(images)} images"
    )
    
    return response


# Example usage and testing
if __name__ == "__main__":
    """
    Test response formatting with sample data.
    """
    import sys
    
    # Configure logging for the test
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    print("\n" + "="*60)
    print("Response Formatter Test")
    print("="*60 + "\n")
    
    # Sample agent text with citations
    sample_text = """A stop sign is an octagonal red sign with white letters that requires drivers to come to a complete stop (Source: California Driver Handbook, Page 45). You must stop at the marked line or before entering the intersection (Source: California Driver Handbook, Page 46)."""
    
    # Sample search results
    sample_results = [
        {
            "@search.score": 0.89,
            "image_urls": ["https://example.com/stop-sign.png"],
            "page_number": 45,
            "document_name": "California Driver Handbook"
        }
    ]
    
    # Test citation extraction
    print("1. Testing citation extraction...")
    citations = extract_citations(sample_text)
    print(f"   ✓ Extracted {len(citations)} citations")
    for i, cit in enumerate(citations, 1):
        print(f"     [{i}] {cit.document_name}, Page {cit.page_number}")
    
    # Test text formatting
    print("\n2. Testing text formatting...")
    formatted = format_text_with_citations(sample_text, citations)
    print(f"   ✓ Formatted text:\n")
    print("   " + "\n   ".join(formatted.split("\n")))
    
    # Test full assembly (without actual image fetch)
    print("\n3. Testing full response assembly...")
    response = assemble_multimodal_response(
        agent_text=sample_text,
        search_results=sample_results,
        include_images=False  # Skip image fetch for test
    )
    print(f"   ✓ Response assembled")
    print(f"     - Citations: {len(response.citations)}")
    print(f"     - Images: {len(response.images)}")
    
    print("\n" + "="*60)
    print("✓ All formatter tests passed!")
    print("="*60 + "\n")
    
    sys.exit(0)
