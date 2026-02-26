# Kirishima: MCP Server Integration & Tool Orchestration Planning

## Summary of Discussion

- **Tool Usage & Autonomy:**
  - Copilot and similar agentic LLMs achieve high tool autonomy via strong system instructions and an orchestration layer, not just prompt engineering.
  - Kirishima's brainlets (e.g., memory_search) act as an orchestration layer, injecting context and managing tool calls, even when the LLM is passive.
  - True agentic behavior comes from combining explicit system-level enforcement with modular, API-driven tool exposure.

- **MCP Server Concept:**
  - MCP (Model Context Protocol) servers expose tools and workflows as standardized API endpoints, making them accessible to any agent (LLM, Copilot, etc.).
  - Moving Kirishima's tools/brainlets to an MCP server makes them reusable, agent-agnostic, and future-proof.
  - Brain is the natural place to implement the MCP server, as it already orchestrates all cross-service coordination.

- **Tool Categorization & Logging:**
  - Persistent tools (e.g., add_memory, create_stickynote) should write to ledger.
  - Ephemeral tools (e.g., memory_search) should not write to ledger, to avoid cluttering context/history.
  - Planning/"intents" logic can be a brainlet, an MCP tool, or both, depending on how much autonomy you want to give the agent.

- **Tool Discovery:**
  - Prefer dynamic tool discovery via MCP over static tools.json, but keep tools.json for bootstrapping if needed.

- **Single FastAPI App:**
  - All MCP and internal endpoints can be served from a single FastAPI app using APIRouter for modularity.

---

# MCP Server Integration & Tool Orchestration: Planning Guide

## 1. MCP Server Implementation in Brain
- Use FastAPI for the MCP server, leveraging APIRouter to organize endpoints (e.g., `/mcp/` for MCP tools).
- Expose each tool/brainlet as an endpoint (e.g., `/mcp/memory_search`, `/mcp/add_stickynote`, `/mcp/intents`).
- Follow MCP spec for request/response formats (JSON, with tool name, parameters, and context).
- Implement a `/mcp/tools` endpoint for dynamic tool discovery (returns available tools and schemas).

## 2. Tool Routing & Categorization
- Route each MCP endpoint to the corresponding internal function, brainlet, or service API.
- **Persistent tools:** Write to ledger (e.g., add_memory, create_stickynote).
- **Ephemeral tools:** Do not write to ledger (e.g., memory_search, get_context).
- **Planning tools:** Expose an `/mcp/intents` endpoint for tool suggestion/planning, powered by a brainlet or sub-agent.

## 3. Ledger Sync & Logging
- Only log persistent, user/system-generated content to ledger.
- Do not log ephemeral tool outputs unless needed for audit/debugging.
- Log all tool invocations for traceability.

## 4. Authentication & Access Control
- Add API key or token-based authentication for MCP endpoints if exposing externally.

## 5. Migration Path
- Start by exposing a few core tools (memory_search, add_stickynote, get_context) via MCP.
- Gradually migrate more brainlets/tools to MCP as needed.
- Keep legacy tools.json for bootstrapping, but prefer MCP for dynamic discovery.

## 6. Documentation
- Auto-generate OpenAPI docs from FastAPI routes for easy agent integration and testing.

---

## Implementation Roadmap

### Phase 1: MCP Server Foundation
- ✅ **Initial MCP router implementation** - Created `/mcp/` endpoints in brain service
- ✅ **Tool registry system** - Decorator-based auto-discovery via `app/tools/` (replaced JSON files)
- ✅ **Shared models created** - `ToolResponse` in `app/tools/base.py` (replaced `MCPToolResponse`)
- ✅ **Service layer structure** - Tools live in `app/tools/` as self-registering modules
- ✅ **Auto-discovery registry** - `@tool` decorator + `__init__.py` scanner (replaced `mcp_tools.json`)

### Phase 2: Tool Dependency Resolution
- ✅ ~~**Dependency resolver**~~ - Removed; no tools use `depends_on`. Add back if needed.

### Phase 3: URL-Based Client Authentication & Identification
- ✅ **URL-based client endpoints** - Implemented `/mcp/` (internal) and `/mcp/copilot/` (external)
- ✅ **Client registry system** - Added `mcp_clients.json` with tool filtering by client type
- ✅ **Tool access control** - Copilot gets curated safe tools, internal gets full access
- ✅ **Zero-config authentication** - No headers required, URL path determines permissions

### Phase 4: Core Tool Implementation
- ✅ **Memory tool** - Full CRUD operations (search, create, update, delete, list, get)
- ✅ **GitHub issue tool** - Issue management with create, view, comment, close, list operations
- ✅ **Manage prompt tool** - Agent system prompt management (internal only)
- ✅ **Get personality tool** - Multi-model style guidelines
- ✅ **Tool migration complete** - 4 core tools migrated to decorator pattern, old implementations deleted

### Phase 5: Input Validation & Error Handling
- ✅ **Standardize error responses** - Unified `ToolResponse` model (replaced `MCPToolResponse` and `ToolCallResponse`)
- ✅ **Add timeout handling** - HTTP client timeouts prevent hanging tool executions
- ✅ **Implement comprehensive logging** - Custom logging module integration throughout

### Phase 6: Production Integration
- ✅ **Integrate with Kirishima** - `multiturn.py` uses direct `call_tool()` dispatch (no HTTP self-call)
- ✅ **Tool router** - Cheap LLM call selects relevant tools per message (`app/tools/router.py`)
- ✅ **MCP routes rewritten** - `routes/mcp.py` uses registry directly (no importlib, no JSON files)
- ✅ **Old code deleted** - 25+ files removed (JSON configs, old implementations, legacy infrastructure)
- 🔄 **External agent testing** - Validate Copilot integration in production

### Phase 7: Intent-Based Orchestration (Future Initiative)
- 🔄 **Design intent detection system** - Replace brainlets with intent-based orchestration
- 🔄 **Create intent resolver service** - Analyze user input and determine required tools
- 🔄 **Implement pre/post execution hooks** - Maintain brainlet-like functionality
- 🔄 **Add context injection logic** - Transparent orchestration for different models
- 🔄 **Migrate existing brainlets** - Convert memory_search, divoom to intent-driven
- 🔄 **Integrate with Kirishima** - Replace tools.json usage with MCP calls
- 🔄 **Test with Copilot** - Validate external agent integration
- 🔄 **Performance optimization** - Add caching, connection pooling as needed
- 🔄 **Documentation & monitoring** - OpenAPI docs, health checks

---

## Terminology Clarification

**MCP (Model Context Protocol):** The standardized API layer that exposes tools to any agent. This is the "server" part.

**Intent-Based Orchestration:** The intelligent middleware that decides which tools to execute based on context, user input, and model behavior. This replaces the current brainlet system.

Industry terms you might see:
- "Tool orchestration" 
- "Agent workflow management"
- "Function calling orchestration"
- "Multi-agent coordination"

"Intents" is perfectly fine and descriptive. It's commonly used in conversational AI (like Google Dialogflow, Microsoft Bot Framework).
