

# MCP Server Integration & Tool Exposure – Kirishima

## Overview
This document explains how Kirishima will manage MCP (Model Context Protocol) servers and expose tools to the LLM. No ADR jargon, just the plan.

## MCP Server Config Structure
You’ll add an `mcp` section to `.kirishima/config.json`:

```json
"mcp": [
	{
		"url": "https://mcp.example.com",
		"short_name": "googlesuite",
		"description": "Google Calendar, Mail, and Contacts via MCP",
		"always_exposed": false,
		"gated": true
	},
	{
		"url": "http://localhost:8080",
		"short_name": "localbrain",
		"description": "Local Kirishima tools (memory, manage_prompt, etc)",
		"always_exposed": true,
		"gated": false
	}
]
```

## Tool Exposure Logic
- For each MCP server, if `always_exposed` is true, its tools are always listed to the LLM.
- If `gated` is true, only the menu tool (e.g., `googlesuite`) is shown; the LLM must call it to get the full list of tools for that server.
- This keeps the tool list manageable and avoids overwhelming the LLM with every possible tool from every MCP server.
- Locally written tools (like `manage_prompt`, `memory`) are always exposed and not gated—they’re available directly.

## Why This Approach?
- Less maintenance: You don’t have to hand-wire every integration or keep custom code for commodity features.
- Config-driven: Add/remove MCP servers by editing config, not code.
- Smarter tool exposure: Only show what’s relevant, keep the LLM’s context clean.

## Implementation Notes
- No fallback to old code—once a feature is migrated to MCP/SDK, the custom code is removed.
- Commit logs and config changes are your migration history; no need for ADRs or addenda.
- “Capability registry” just means the config section above—tracks what’s available, how it’s exposed, and its status.
- “Circuit breakers” (if you want them) would temporarily disable a server/tool after repeated failures, but that’s optional.
- “Normalize streaming LLM responses” means making sure your code can handle both chunked and full responses from different providers, so the LLM interface stays consistent.

## Next Steps
1. Finalize this doc.
2. Update `.kirishima/config.json` with the new `mcp` section when ready to implement.
3. Refactor tool exposure logic in orchestrator/brain to use this config.
