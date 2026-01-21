"""
Azure AI Agent Framework v2 Implementation

This module provides a complete implementation of the DrivingRules expert agent
using Azure AI Agent Framework v2, integrated with Azure AI Search for RAG.

## Structure

- `client.py` - AIProjectClient initialization with managed identity
- `config_loader.py` - Type-safe configuration management
- `agent_factory.py` - Agent creation with comprehensive instructions
- `search_tool.py` - Azure AI Search tool configuration (hybrid search)
- `conversation.py` - Thread and conversation management
- `streaming.py` - Custom event handler for streaming responses
- `image_relevance.py` - Intelligent image inclusion detection
- `response_formatter.py` - Multimodal response assembly
- `telemetry.py` - OpenTelemetry integration for observability
- `app.py` - Main CLI application

## Quick Start

### Single Query
```python
from agent.app import run_agent_query

response = run_agent_query("What does a stop sign mean?")
print(response)
```

### Interactive Mode
```python
from agent.app import interactive_mode

interactive_mode()
```

### Custom Agent Creation
```python
from agent.agent_factory import create_driving_rules_agent
from agent.conversation import create_thread, add_message

# Create agent
agent = create_driving_rules_agent()

# Create conversation thread
thread = create_thread()

# Add message and run agent
add_message(thread.id, "What does a yield sign mean?")
# ... run agent logic ...
```

## Environment Variables

Required:
- `AZURE_AI_PROJECT_ENDPOINT` - Azure AI Foundry project endpoint
- `AZURE_SEARCH_ENDPOINT` - Azure AI Search service endpoint

Optional:
- `AZURE_SEARCH_INDEX_NAME` - Search index name (default: driving-rules-hybrid)
- `AGENT_MODEL_DEPLOYMENT` - Model deployment (default: gpt-4o)
- `AGENT_TEMPERATURE` - Response temperature (default: 0.7)
- `SEARCH_TOP_K` - Number of search results (default: 5)
- `IMAGE_RELEVANCE_THRESHOLD` - Image inclusion threshold (default: 0.75)
- `ENABLE_TELEMETRY` - Enable OpenTelemetry (default: true)

See `.env.example` for complete configuration options.

## Features

- ✅ Agent Framework v2 with GPT-4o
- ✅ Hybrid search (keyword + vector) with Azure AI Search
- ✅ Intelligent image inclusion based on query analysis
- ✅ Streaming responses with real-time display
- ✅ Multi-turn conversations with context retention
- ✅ State-specific filtering for queries
- ✅ Comprehensive citations with document and page references
- ✅ Multimodal responses (text + images)
- ✅ OpenTelemetry integration for observability
- ✅ Structured logging with trace correlation
- ✅ Error handling with graceful degradation

## Architecture

The agent follows a modular RAG (Retrieval-Augmented Generation) architecture:

1. **Query Processing**: User query is analyzed for intent and state context
2. **Image Detection**: Heuristics determine if visual aids would help
3. **Search**: Hybrid search retrieves relevant chunks from indexed manuals
4. **Generation**: GPT-4o generates response with citations
5. **Assembly**: Response is assembled with text, citations, and images
6. **Streaming**: Response is streamed to user in real-time

## Testing

Run unit tests:
```powershell
pytest tests/agent/
```

Run integration tests:
```powershell
pytest tests/agent/test_integration.py
```

Test CLI:
```powershell
python -m agent.app "What does a stop sign mean?"
```

## Security

- Managed identity authentication (no keys in code)
- RBAC-based access control
- Secure credential handling via Azure SDKs
- No secrets in source code or logs
"""

# Public API exports
from .client import get_project_client, close_project_client
from .config_loader import load_agent_config, AgentConfig
from .agent_factory import create_driving_rules_agent, delete_agent
from .conversation import (
    create_thread,
    add_message,
    get_conversation_history,
    delete_thread
)
from .streaming import AgentEventHandler, create_simple_handler
from .image_relevance import should_include_images, filter_relevant_images
from .response_formatter import assemble_multimodal_response
from .telemetry import init_telemetry, trace_operation

__all__ = [
    # Client
    "get_project_client",
    "close_project_client",
    # Configuration
    "load_agent_config",
    "AgentConfig",
    # Agent
    "create_driving_rules_agent",
    "delete_agent",
    # Conversation
    "create_thread",
    "add_message",
    "get_conversation_history",
    "delete_thread",
    # Streaming
    "AgentEventHandler",
    "create_simple_handler",
    # Image handling
    "should_include_images",
    "filter_relevant_images",
    # Response formatting
    "assemble_multimodal_response",
    # Telemetry
    "init_telemetry",
    "trace_operation",
]
