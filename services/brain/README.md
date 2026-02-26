# Brain Service - Core Orchestrator

The brain service is the central orchestration hub of the Kirishima system, coordinating multi-turn conversations, context management, tool execution, and cross-service integration. It implements a sophisticated pipeline for processing chat requests through modular "brainlets" and comprehensive tool execution.

## Architecture Overview

Brain acts as the primary coordinator between:

- **Proxy Service**: LLM interaction via structured request/response flow
- **Ledger Service**: Message persistence and conversation history
- **Tool System**: Function calling and external service integration
- **Brainlet System**: Modular pre/post-processing pipeline
- **Platform Services**: Discord, iMessage, API endpoints

### API Endpoints

### Core Processing

- **POST /api/multiturn** — Primary conversation orchestration endpoint with full context management
- **POST /api/singleturn** — Single-turn processing for simple interactions without conversation history

### Mode Management

- **POST /mode/{mode}** — Set the active model mode for subsequent conversations
- **GET /mode** — Get the current active mode configuration

### Notification System

- **POST /notification** — Create new notifications for scheduling or reminder systems
- **GET /notification/{user_id}** — Retrieve pending notifications for a specific user
- **POST /notification/execute** — Execute callback notifications from scheduled jobs

### Embedding Generation

- **POST /embedding** — Generate text embeddings for semantic search and analysis

## Core Request Flow

```text
External Request → Brain Multiturn → Pre-Brainlets → Proxy LLM → Tool Execution Loop → 
Post-Brainlets → Ledger Sync → Response
```

## Multiturn Conversation Pipeline (`multiturn.py`)

The `/api/multiturn` endpoint implements a comprehensive conversation orchestration workflow:

### 1. **Context Preparation**

- **User Resolution**: Maps incoming user_id to system user, falls back to admin user
- **Platform Detection**: Identifies request source (api, discord, imessage)
- **Agent Prompts**: Retrieves user-specific agent prompts from brainlets database
- **Summaries**: Fetches recent conversation summaries for context injection

### 2. **Request Enrichment**

```python
updated_request = message.copy(update={
    "memories": [],
    "messages": message.messages,
    "username": username,
    "summaries": summaries,
    "platform": platform,
    "tools": tools,  # Built from always_tools + router-selected tools
    "agent_prompt": agent_prompt
})
```

### 3. **Ledger Synchronization**

- **Message Buffering**: Last 4 messages synced to ledger for persistence
- **Deduplication**: Ledger handles message ordering and duplicate prevention
- **Tool Call Preservation**: Maintains OpenAI-spec tool_calls, function_call, tool_call_id fields

### 4. **Pre-Execution Brainlets**

- **Topological Sort**: Brainlets executed in dependency order using Kahn's algorithm
- **Mode Filtering**: Only brainlets configured for the current model mode are executed
- **Output Merging**: Brainlet results merged into message stream as tool calls

### 5. **Tool Execution Loop**

- **LLM Request**: Send enriched request to proxy service
- **Tool Call Detection**: Parse assistant response for function calls
- **Function Execution**: Direct dispatch via `call_tool()` from registry (no HTTP self-call)
- **Response Formatting**: Convert tool results to OpenAI-compatible tool messages
- **Loop Control**: Maximum 10 iterations to prevent infinite loops

### 6. **Post-Execution Brainlets**

- **Context-Aware Processing**: Access to complete conversation including tool results
- **Response Modification**: Can inject additional context or trigger side effects

### 7. **Final Response Assembly**

- **Message Persistence**: All messages synced to ledger
- **Response Validation**: Ensure proper ProxyResponse structure
- **Error Handling**: Graceful degradation with detailed error logging

## Brainlets System

Modular processing units for lightweight, model-driven tasks that run before or after the main LLM interaction.

### Configuration Structure

Brainlets are configured in `config.json`:

```json
{
    "name": "memory_search",
    "description": "A brainlet that injects memories into the conversation",
    "model": "gpt-4.1",
    "provider": "openai", 
    "execution_stage": "pre",  // "pre" or "post"
    "depends_on": [],  // Dependency list for execution order
    "options": {
        "max_completion_tokens": 64,
        "stream": false,
        "temperature": 0.7
    },
    "modes": ["default", "boyfriend", "tts"]  // Model modes where this runs
}
```

### Execution Pipeline

**Dependency Resolution**:

- Uses topological sorting (Kahn's algorithm) to respect `depends_on` relationships
- Ensures prerequisite brainlets complete before dependent ones execute

**Stage-Based Processing**:

- **Pre-Execution**: Run before LLM interaction (e.g., memory injection, context enrichment)
- **Post-Execution**: Run after LLM response (e.g., side effects, logging, external API calls)

**Mode-Based Filtering**:

- Brainlets only execute for specified model modes
- Allows different processing pipelines per conversation type

### Implementation Pattern

```python
async def brainlet_function(brainlets_output: Dict[str, Any], request: MultiTurnRequest):
    """
    Standard brainlet function signature.
    
    Args:
        brainlets_output: Results from previously executed brainlets
        request: Current multiturn request with full context
        
    Returns:
        Union[dict, list, str]: Result data for injection into conversation
    """
    # Process request, call external services, etc.
    return result
```

### Built-in Brainlets

**memory_search** (Pre-execution):

- Extracts keywords from conversation using LLM
- Searches memory database for relevant context
- Injects memory results as tool calls into conversation
- Uses single-turn proxy request for keyword extraction

**divoom** (Post-execution):

- Generates emoji/pixel art based on conversation sentiment
- Updates Bluetooth Divoom display device
- Triggers external hardware side effects

## Tools System

Decorator-based, auto-discovering tool system for function calling and external service integration.

### Architecture

Tools are self-registering Python modules in `app/tools/`. Each tool file contains a single `@tool`-decorated async function that carries all metadata inline — no JSON files, no manual registry.

```
app/tools/
    __init__.py          # Auto-discovery, registry, dispatch (public API)
    base.py              # @tool decorator + ToolResponse model
    router.py            # Cheap LLM call to select relevant tools per message
    get_personality.py   # Multi-model style guidelines (always=True)
    github_issue.py      # GitHub API integration (always=False, routed)
    manage_prompt.py     # Agent self-modification (always=True)
    memory_management.py # Ledger-backed memory CRUD (always=True)
    stickynotes.py       # Persistent reminders (always=False, routed)
```

### Tool Definition Pattern

```python
from app.tools.base import tool, ToolResponse

@tool(
    name="my_tool",
    description="Does a thing",
    parameters={"type": "object", "properties": {...}, "required": [...]},
    persistent=True,     # logged to ledger
    always=True,         # always sent to LLM (vs. routed by tool router)
    clients=["internal", "copilot"],  # access control
    guidance="Optional extra context injected into system prompt",
)
async def my_tool(parameters: dict) -> ToolResponse:
    return ToolResponse(result={"status": "ok"})
```

### Registry API (`app.tools`)

| Function | Purpose |
|---|---|
| `get_tool(name)` | Return callable or None |
| `get_openai_tools(client_type)` | All tools in OpenAI format, filtered by client access |
| `get_mcp_tools(client_type)` | All tools in MCP format, filtered |
| `get_always_tools(client_type)` | Only `always=True` tools in OpenAI format |
| `get_routed_tools_catalog()` | `{name: description}` for `always=False` tools (router input) |
| `get_openai_tools_by_names(names, ct)` | OpenAI format for specific tool names |
| `call_tool(name, params)` | Execute locally → fallback to MCPClient → ToolResponse |

### Tool Execution Flow

1. **Tool Router**: Cheap LLM call (gpt-4.1-nano) selects which routed tools are relevant
2. **Tool Merge**: Always-on tools + router-selected tools sent to conversational LLM
3. **LLM Response**: Assistant response may contain `tool_calls` array
4. **Direct Dispatch**: `call_tool(name, params)` — direct function call, no HTTP round-trip
5. **External Fallback**: If tool not found locally, falls through to MCPClient for external MCP servers
6. **Ledger Sync**: Tool call and result synced to ledger for history
7. **Loop**: Repeat until LLM responds with text (max 10 iterations)

### Tool Router (`app/tools/router.py`)

Reduces token waste by only sending relevant tools to the conversational LLM:

- **Always-on tools** (`always=True`): Sent every call — `memory`, `manage_prompt`, `get_personality`
- **Routed tools** (`always=False`): Only included when the router says they're relevant — `github_issue`, future external MCP tools
- **Router model**: `router` mode in proxy config → gpt-4.1-nano (fast, cheap)
- **Graceful fallback**: If router fails, all routed tools are included (safe default)

### Built-in Tools

| Tool | Service | Actions | Persistent | Always |
|------|---------|---------|------------|--------|
| `get_personality` | Local | Return style guidelines | No | Yes |
| `manage_prompt` | Local SQLite | add, delete, list | Yes | Yes |
| `memory` | Ledger | search, create, update, delete, list, get | Yes | Yes |
| `github_issue` | GitHub API | create, view, comment, close, list, list_comments | Yes | No |
| `stickynotes` | Stickynotes | create, list, snooze, resolve | Yes | No |

### MCP Server Endpoints (`routes/mcp.py`)

- **`/mcp/`** — Internal tools (full access)
- **`/mcp/copilot/`** — Copilot tools (curated subset)
- **`/mcp/external/`** — External client tools (restricted)
- All use the same registry — client access controlled via `config/mcp_clients.json`

### Adding a New Tool

1. Create `app/tools/my_tool.py` with `@tool` decorator
2. Save. Docker auto-restarts. Tool is live.

No JSON files. No executor mapping. No routes to register. Auto-discovery handles everything.

## Service Integration Patterns

### Proxy Service Communication

**Request Structure**:

- Enriched MultiTurnRequest with context, tools, and metadata
- Provider/model resolution handled by proxy
- Streaming and non-streaming response support

**Response Handling**:

- ProxyResponse model validation
- Tool call extraction and processing
- Error propagation with detailed logging

### Ledger Service Synchronization

**Message Persistence**:

- All user, assistant, tool, and system messages logged
- Maintains conversation continuity across sessions
- Supports message retrieval and context reconstruction

**Sync Pattern**:

```python
sync_snapshot = [{
    "user_id": user_id,
    "platform": platform,
    "platform_msg_id": None,
    "role": message["role"],
    "content": message["content"],
    "model": model,
    "tool_calls": message.get("tool_calls"),
    "function_call": message.get("function_call"),
    "tool_call_id": message.get("tool_call_id")
}]
```

### Cross-Service HTTP Communication

**Service Discovery**:

- Environment variable-based port resolution
- Consul integration for service discovery
- Configurable timeout and retry policies

**Error Handling**:

- Structured error responses with HTTP status codes
- Service-specific error prefixes for debugging
- Graceful degradation on service failures

## Configuration and Extensibility

### Adding New Tools

1. Create `app/tools/my_tool.py` with `@tool` decorator
2. Save. Docker auto-restarts. Auto-discovery registers the tool.
3. No JSON, no manual registration, no route changes.

### Adding New Brainlets

1. **Implement Function**: Create in `app/brainlets/new_brainlet.py`
2. **Import Module**: Add to `app/brainlets/__init__.py`
3. **Configure Execution**: Add configuration to `config.json`
4. **Set Dependencies**: Define execution order with `depends_on`

### Database Configuration

**Brainlets Database**: SQLite database for user prompts and brainlet state
**Connection Pattern**: Context manager with WAL mode for concurrent access
**Schema**: User-specific tables for prompts, settings, and temporary state

## Error Handling and Monitoring

### Logging Strategy

- **Structured Logging**: JSON-formatted logs with service identification
- **Debug Levels**: Configurable log levels for development vs production
- **Request Tracing**: Correlation IDs for cross-service request tracking

### Error Propagation

- **Service Errors**: HTTP exceptions with detailed error context
- **Tool Errors**: Structured error responses returned to LLM
- **Brainlet Errors**: Graceful fallback with warning logs

### Monitoring Points

- **Request Latency**: Tool execution and brainlet processing times
- **Error Rates**: Service communication failures and tool exceptions
- **Loop Detection**: Tool execution iteration counts and infinite loop prevention

## Performance Considerations

### Concurrency

- **Async/Await**: Full async implementation for I/O operations
- **HTTP Connection Pooling**: Reused connections for service communication
- **Database Connections**: WAL mode SQLite for concurrent read access

### Memory Management

- **Message Buffering**: Limited message history in memory
- **Tool Result Caching**: Temporary storage of tool execution results
- **Brainlet Output Merging**: Efficient message list concatenation

### Scalability

- **Stateless Design**: No persistent state between requests
- **Service Boundaries**: Clear separation of concerns across microservices
- **Database Isolation**: Service-specific databases prevent cross-contamination
