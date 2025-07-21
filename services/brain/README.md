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
    "memories": [],  # Legacy, being phased out
    "messages": message.messages,
    "username": username,
    "summaries": summaries,
    "platform": platform,
    "tools": tools,  # Loaded from tools.json
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
- **Function Execution**: Execute registered tools with parameter validation
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

Comprehensive function calling system for external service integration and system control.

### Tool Definition (`tools.json`)

Tools follow OpenAI function calling specification:

```json
{
    "type": "function",
    "function": {
        "name": "manage_prompt",
        "description": "Manage the agent's prompt (add or delete a line, or list all lines and ids)",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform: 'add', 'delete', or 'list'",
                    "enum": ["add", "delete", "list"]
                },
                "prompt_id": {"type": "string"},
                "prompt_text": {"type": "string"},
                "reasoning": {"type": "string"}
            },
            "required": ["action"]
        }
    }
}
```

### Tool Registration

Tools are registered in `app/tools/__init__.py`:

```python
TOOL_FUNCTIONS = {
    "manage_prompt": manage_prompt,
    "memory": memory,
    "tts": tts,
    "update_divoom": update_divoom,
    "github_issue": github_issue,
    "smarthome": smarthome,
    "stickynotes": stickynotes
}
```

### Tool Execution Flow

1. **LLM Tool Call**: Assistant response contains tool_calls array
2. **Function Resolution**: Look up function in TOOL_FUNCTIONS registry
3. **Parameter Parsing**: JSON decode function arguments
4. **Async/Sync Handling**: Automatically detect and handle coroutine functions
5. **Error Wrapping**: Catch exceptions and return structured error responses
6. **Response Formatting**: Convert results to OpenAI tool message format

### Built-in Tools

**manage_prompt**:

- CRUD operations for agent-managed prompts
- SQLite storage in brainlets database
- **Self-modification capability**: Agent can rewrite its own system prompt
- User-specific prompt management via scripts/manage_prompt.py

**memory**:

- Legacy memory operations (being phased out)
- Add, delete, list, search memory entries
- Integration with memory service APIs

**github_issue**:

- GitHub repository integration
- Create issues, add comments in agent voice
- **Autonomous development**: All project issues are agent-created
- Automated project management workflows with @kirishima-ai account

**smarthome**:

- Home Assistant integration
- Natural language device control
- Entity discovery and state management

**tts**:

- Text-to-speech control
- Enable/disable TTS for conversation
- Integration with STT/TTS service

**update_divoom**:

- Bluetooth display control
- Emoji and pixel art updates
- Hardware status indication

**stickynotes**:

- Context-aware reminders
- Persistent note storage
- Automatic injection into conversations

### Tool Implementation Pattern

```python
async def tool_function(**kwargs):
    """
    Standard tool function signature.
    
    Args:
        **kwargs: Parameters from LLM tool call
        
    Returns:
        Union[dict, str]: Result data for LLM consumption
    """
    try:
        # Validate parameters
        # Execute tool logic
        # Return structured result
        return {"status": "success", "result": data}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

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

1. **Create Tool Function**: Implement in `app/tools/new_tool.py`
2. **Register Function**: Add to `TOOL_FUNCTIONS` in `__init__.py`
3. **Define Schema**: Add OpenAI function spec to `tools.json`
4. **Test Integration**: Verify parameter parsing and error handling

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
