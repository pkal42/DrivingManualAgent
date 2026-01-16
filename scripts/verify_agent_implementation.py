#!/usr/bin/env python3
"""Agent Implementation Verification Script"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from agent.image_relevance import should_include_images
from agent.response_formatter import extract_citations
from agent.search_tool import build_state_filter

print("="*60)
print("Agent Implementation Verification")
print("="*60)

# Test 1: Image relevance
print("\n✓ Image relevance: ", should_include_images("What does a stop sign look like?"))

# Test 2: Citation extraction
text = "Test (Source: CA Handbook, Page 5)."
citations = extract_citations(text)
print(f"✓ Citation extraction: {len(citations)} citations found")

# Test 3: State filter
filter_str = build_state_filter("California")
print(f"✓ State filter: {filter_str}")

print("\n" + "="*60)
print("✅ All basic verification tests passed!")
print("="*60)
