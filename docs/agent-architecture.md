# Agent Architecture Documentation

## Overview

The DrivingRules Agent is built using Azure AI Agent Framework v2 and implements a Retrieval-Augmented Generation (RAG) pattern for answering questions about driving laws and regulations from state driving manuals.

## Architecture Diagram

```
┌─────────────┐
│    User     │
└──────┬──────┘
       │
       │ Query
       ▼
┌─────────────────────────────────────────────────────────┐
│                     Agent Application                    │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │   CLI/API  │─→│ Image        │─→│ Query           │ │
│  │            │  │ Relevance    │  │ Enhancement     │ │
│  └────────────┘  └──────────────┘  └─────────────────┘ │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           Azure AI Agent Framework v2                   │
│  ┌─────────────┐                                       │
│  │   Agent     │ GPT-4o with instructions              │
│  │  (GPT-4o)   │ - Role: Driving rules expert          │
│  │             │ - Citations required                  │
│  └──────┬──────┘ - Visual aids when helpful            │
│         │                                               │
│         │ Uses                                          │
│         ▼                                               │
│  ┌──────────────────┐                                  │
│  │ AzureAISearchTool │ Hybrid search                   │
│  │                   │ - Keyword (BM25)                │
│  │                   │ - Vector similarity             │
│  │                   │ - Semantic ranking              │
│  └──────┬───────────┘                                  │
└─────────┼──────────────────────────────────────────────┘
          │
          │ Search Query
          ▼
┌──────────────────────────────────────────────────────┐
│          Azure AI Search Index                       │
│  ┌────────────────────────────────────────────────┐  │
│  │  Document Chunks (1000 chars, 200 overlap)     │  │
│  │  - Chunk text (OCR-extracted via Doc Intel)   │  │
│  │  - Vector embeddings (3072-dim)                │  │
│  │  - Metadata (document, page, state)            │  │
│  │  - Figure captions from images                 │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
          │
          │ Returns chunks + image URLs
          ▼
┌──────────────────────────────────────────────────────┐
│          Response Assembly                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Extract    │→ │  Filter      │→ │  Format    │  │
│  │  Citations  │  │  Images      │  │  Output    │  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────┘
          │
          │ Multimodal Response
          ▼
┌─────────────────┐
│  User Response  │
│  - Text         │
│  - Citations    │
│  - Images       │
└─────────────────┘
```

## Components

### 1. Agent Application Layer (`app.py`)

**Purpose**: User interface and orchestration

**Responsibilities**:
- Accept user queries via CLI or API
- Determine if images should be included
- Enhance query with state context
- Stream responses to user
- Handle errors gracefully

**Key Functions**:
- `run_agent_query()` - Single query execution
- `interactive_mode()` - Multi-turn conversation

### 2. Client Management (`client.py`)

**Purpose**: Azure AI Project client initialization

**Responsibilities**:
- Initialize AIProjectClient with managed identity
- Implement singleton pattern for efficiency
- Handle authentication via DefaultAzureCredential

**Authentication Methods** (in order):
1. Managed Identity (Azure production)
2. Azure CLI credentials (local development)
3. Visual Studio Code credentials
4. Environment variables

### 3. Agent Factory (`agent_factory.py`)

**Purpose**: Create and configure agents

**Responsibilities**:
- Create agents with GPT-4o
- Define comprehensive agent instructions
- Attach Azure AI Search tool
- Configure model parameters

**Agent Instructions** (key points):
- Role: Expert on US driving rules
- Always cite sources (document + page)
- Include images for visual concepts
- Only answer from indexed manuals
- Admit when information unavailable

**Configuration Choices**:
- **Model**: GPT-4o (multimodal, strong reasoning)
- **Temperature**: 0.7 (balanced accuracy/fluency)
- **Top-p**: 0.95 (focused but natural)
- **Search Top-K**: 5 (sufficient context)

### 4. Search Tool Integration (`search_tool.py`)

**Purpose**: Configure and use Azure AI Search

**Responsibilities**:
- Configure AzureAISearchTool for hybrid search
- Build OData filters for state-specific queries
- Format search results for LLM context
- Provide helper functions for direct search

**Hybrid Search**:
- **Keyword (BM25)**: Exact term matching
- **Vector**: Semantic similarity via embeddings
- **Semantic Ranking**: Deep learning re-ranking
- **Benefits**: Better than either method alone

### 5. Conversation Management (`conversation.py`)

**Purpose**: Manage threads and messages

**Responsibilities**:
- Create conversation threads
- Add user/assistant messages
- Retrieve conversation history
- Clean up threads

**Thread Lifecycle**:
1. Create thread (with optional metadata)
2. Add user message
3. Run agent to generate response
4. Retrieve history for context
5. Continue or delete thread

### 6. Streaming Handler (`streaming.py`)

**Purpose**: Handle streaming responses

**Responsibilities**:
- Process message deltas (text chunks)
- Track run status
- Log tool calls
- Handle errors gracefully

**Event Types**:
- `on_message_delta` - Partial text chunks
- `on_thread_run` - Status updates
- `on_tool_call` - Tool invocations
- `on_error` - Error handling

### 7. Image Relevance Detection (`image_relevance.py`)

**Purpose**: Determine when to include images

**Two Strategies**:

#### A. Keyword Heuristics (Default)
- Fast and deterministic
- Zero additional cost
- Good accuracy for domain
- Keywords: sign, marking, diagram, lane, etc.

#### B. LLM-as-Judge (Optional)
- Higher accuracy
- Handles ambiguous queries
- Small additional cost
- Uses GPT-4o for classification

**Threshold**:
- Default: 0.75 (balanced)
- Higher (0.85): Fewer, more relevant images
- Lower (0.65): More images, some tangential

### 8. Response Formatter (`response_formatter.py`)

**Purpose**: Assemble multimodal responses

**Pipeline**:
1. **Extract Citations**: Parse agent text for sources
2. **Filter Images**: Apply relevance threshold
3. **Fetch URLs**: Parallel async retrieval
4. **Format Output**: Combine text, citations, images

**Citation Format**:
```
Original: (Source: CA Handbook, Page 5)
Formatted: [1]

Citations:
[1] CA Handbook, Page 5
```

**Image References**:
```
Images:
- Figure 1: Stop sign (Source: CA Handbook, Page 5)
  URL: https://...
```

### 9. Telemetry (`telemetry.py`)

**Purpose**: Observability and monitoring

**Capabilities**:
- Distributed tracing with OpenTelemetry
- Custom metrics tracking
- Azure Monitor integration
- Structured logging with trace correlation

**Metrics Tracked**:
- Query duration
- Search latency
- Token usage
- Error rates

### 10. Configuration (`config_loader.py`)

**Purpose**: Type-safe configuration management

**Configuration Sources** (precedence):
1. Environment variables (highest)
2. Default values

**Validation**:
- Required fields present
- Endpoint formats valid
- Numeric ranges valid
- Container names compliant

## Data Flow

### Single Query Flow

1. **User Input**: `"What does a stop sign mean?"`

2. **Image Detection**:
   ```python
   should_include_images("What does a stop sign mean?")
   # Returns: True (contains "sign")
   ```

3. **Agent Creation**:
   ```python
   agent = create_driving_rules_agent()
   # GPT-4o with driving rules instructions
   ```

4. **Thread Creation**:
   ```python
   thread = create_thread(metadata={"query": "..."})
   ```

5. **Message Addition**:
   ```python
   add_message(thread.id, "What does a stop sign mean?")
   ```

6. **Agent Execution**:
   - Agent receives message
   - Calls AzureAISearchTool with query
   - Hybrid search retrieves relevant chunks
   - GPT-4o generates response with citations
   - Response streamed back

7. **Search Results**:
   ```json
   [
     {
       "content": "A stop sign is an octagonal red sign...",
       "document_name": "California Driver Handbook",
       "page_number": 45,
       "@search.score": 0.89,
       "image_urls": ["https://..."]
     }
   ]
   ```

8. **Response Assembly**:
   ```python
   response = assemble_multimodal_response(
       agent_text="A stop sign is... (Source: CA Handbook, Page 45)",
       search_results=[...],
       include_images=True
   )
   ```

9. **Final Output**:
   ```
   A stop sign is an octagonal red sign with white letters. [1]
   
   Images:
   - Figure 1: Stop sign example (Source: CA Handbook, Page 45)
     URL: https://...
   
   Citations:
   [1] CA Handbook, Page 45
   ```

### Multi-Turn Conversation Flow

1. **Session Start**: Create thread once
2. **Turn 1**: Add message → Run agent → Display response
3. **Turn 2**: Add message (same thread) → Run agent → Display response
4. **Context**: Full history maintained in thread
5. **Session End**: Delete thread

## Security Model

### Authentication
- **Managed Identity**: DefaultAzureCredential
- **No Keys**: No connection strings or API keys in code
- **RBAC**: Least privilege access control

### Required Roles
- Application → AI Search: "Search Index Data Reader"
- Application → Storage: "Storage Blob Data Reader"  
- Application → AI Foundry: "Azure AI Developer"

### Secure Practices
- Credentials via Azure SDK
- No secrets in source/logs
- Managed identity in production
- Environment variables for config

## Performance Characteristics

### Latency
- **Search**: ~100-200ms (hybrid query)
- **LLM Generation**: ~1-3s (streaming)
- **Image Fetch**: ~50-100ms per image (parallel)
- **Total**: ~2-5s for typical query

### Scalability
- **Stateless**: Each query independent
- **Concurrent**: Multiple queries in parallel
- **Caching**: Search results cacheable
- **Limits**: Azure OpenAI rate limits apply

### Cost Optimization
- **Hybrid Search**: More efficient than pure vector
- **Keyword Heuristics**: Free vs LLM-as-judge
- **Top-K=5**: Balance context vs tokens
- **Streaming**: Better UX, same cost

## Error Handling

### Error Categories
1. **Authentication Errors**: Invalid credentials
2. **Resource Errors**: Missing index/agent
3. **Timeout Errors**: Long-running operations
4. **Rate Limit Errors**: Too many requests
5. **Generation Errors**: LLM failures

### Graceful Degradation
- Images unavailable → Return text only
- Search fails → Return cached/default response
- Streaming fails → Fall back to sync
- Telemetry fails → Continue without

### Retry Logic
- Exponential backoff for transient errors
- Maximum 3 retries
- Circuit breaker for persistent failures

## Testing Strategy

### Unit Tests
- Configuration validation
- Citation extraction
- Image relevance detection
- Response formatting
- Mock agent/search calls

### Integration Tests
- Live agent creation
- Thread management
- Search queries
- End-to-end flow
- Requires Azure setup

### Test Queries
- "What does a stop sign mean?" (image query)
- "When should I use turn signals?" (text query)
- "California parking rules" (state-specific)

## Deployment

### Local Development
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` from `.env.example`
4. Run: `python -m agent.app "Your question"`

### Production Deployment
1. Deploy infrastructure (Bicep templates)
2. Configure managed identity
3. Set environment variables
4. Deploy application container
5. Enable Application Insights

## Monitoring

### Key Metrics
- Query volume
- Response latency
- Error rate
- Citation accuracy
- User satisfaction

### Dashboards
- Azure Monitor workbook
- Application Insights
- Custom Grafana/Kibana

### Alerts
- High error rate (>5%)
- Slow responses (>10s)
- Low availability (<99%)

## Future Enhancements

### Planned
- [ ] Multi-modal input (image queries)
- [ ] Conversation summarization
- [ ] User feedback integration
- [ ] Advanced citation linking
- [ ] Multi-language support

### Considered
- [ ] Voice interface
- [ ] Web UI
- [ ] Mobile app
- [ ] API endpoints
- [ ] Batch processing

## References

- [Azure AI Agent Framework v2 Documentation](https://learn.microsoft.com/azure/ai-services/agents/)
- [Azure AI Search Hybrid Search](https://learn.microsoft.com/azure/search/hybrid-search-overview)
- [RAG Pattern Best Practices](https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-solution-design-and-evaluation-guide)
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/instrumentation/python/)
