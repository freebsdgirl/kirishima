# Sub-Agent Architecture Overview

This document is the short version.

Read this first if the detailed design doc starts feeling like a hostage situation.

Related detailed doc:
- `docs/Subagent_Design.md`

## Why Change The Current Model

Right now, the main conversational path in `brain` still thinks in terms of exposing a growing set of tools directly to the top-level LLM.

That works for a small tool list, but it breaks down as soon as:

- the number of tools grows
- MCP servers add more tools dynamically
- some tasks are multi-step and should be done off to the side
- retrieval-heavy tasks would dump too much raw data into the main context window

The main conversational agent should not be the thing doing broad tool selection over the entire system.

It should mostly decide:

1. answer directly
2. create/update memory directly
3. delegate a bounded task to a worker

## Core Direction

For the top-level chat path, reduce the visible tool surface to one or two tools:

- `spawn_minion`
- optionally a separate explicit memory-write tool

That means the conversational agent stops managing a giant tool belt and starts managing delegation.

## What `spawn_minion` Means

`spawn_minion` is a thin delegation interface:

- input: a natural-language task from the main conversational agent
- internal runtime: structured worker orchestration
- output: a narrow result shaped for the caller

This keeps the top-level interface simple without making the backend sloppy.

## Main Pattern

The recommended pattern is:

- a supervisor agent with almost no tools
- a worker agent that first chooses tools from a menu, then executes with only those tools
- hard execution budgets
- a minimal return payload

In practice:

1. the main agent decides whether delegation is needed
2. `brain` spawns a worker context
3. the worker gets a plaintext tool menu and requests the tools it needs
4. `brain` loads only those tools into the worker context
5. the worker plans and executes inside that smaller sandbox
6. the worker returns only a minimal response to the supervisor

## Natural Language Boundary

Inside `brain`, the worker still needs:

- a tool-selection pass
- a max step budget
- a tiny supervisor-facing return shape
- a timeout

So the model is:

- natural language at the boundary
- structured control underneath

- rich execution data belongs in internal logging or ledger traces

## Recommended First Version

Phase 1 should stay shallow.

Use only one level of delegation:

- main conversational agent
- one worker

Do not start with recursive sub-sub-agents.

## Phase 1 Scope

Phase 1 uses a plaintext menu of available tools. The worker requests the tools it needs. If the menu gets too large later, it can be grouped by MCP server.

## Memory Direction

Memory writes should stay more explicit than general delegation.

This matches the existing memory direction already written elsewhere in the repo:

- broad retrieval should happen in a sub-agent
- the main conversational agent should get back only the relevant slice

## Codex And MCP

Codex integration is separate from the sub-agent runtime.

- `brain` owns the sub-agent runtime
- Codex is one external backend or capability the worker may use

If Codex is exposed through MCP, the worker can request it from the tool menu.

## What This Replaces

This direction replaces the current pattern in which `multiturn.py` assembles tools directly for the top-level model.

The top-level model gets:

- `spawn_minion`
- memory write capability
- maybe a tiny handful of other truly universal tools if experience proves they belong there

Everything else moves behind the worker boundary.

## Practical Benefits

If this is done correctly, it gives you:

- smaller top-level prompts
- fewer top-level tool definitions
- less context pollution from retrieval-heavy tasks
- cleaner handling of multi-step work
- a better place to integrate Codex or other external executors
- a path to scale tool count without making the main chat loop worse

## Main Risks

Main failure modes:

- making `spawn_minion` completely unstructured internally
- allowing unlimited recursion
- giving every worker all tools in the execution pass
- adding extra routing abstractions too early
- returning debug-heavy payloads to the supervisor instead of logging them separately
- letting workers return giant raw dumps
- mixing memory authoring too casually into generic delegation

## Bottom Line

The direction is:

- fewer top-level tools
- stronger delegation
- tighter worker scoping
- bounded outputs

That is the architecture to build toward.
