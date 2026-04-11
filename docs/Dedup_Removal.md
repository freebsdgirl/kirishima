# Memory Dedup Subsystem Removal

## 1. Motivation

The ledger service currently contains three coexisting generations of memory deduplication logic:

- `services/ledger/app/services/memory/dedup.py` (~434 lines) — keyword-overlap grouping and timeframe grouping, LLM-based merges.
- `services/ledger/app/services/memory/dedup_semantic.py` (~344 lines) — semantic grouping with optional keyword rebalancing.
- `services/ledger/app/services/memory/dedup_topic_based.py` (~853 lines) — two-phase DBSCAN topic clustering with timeframe memory chunking and LLM merges. Loads an embeddings model, runs semantic similarity, calls the LLM for merge decisions.

Combined: approximately **1631 lines**, one embeddings model load, three entry points, three route handlers.

`docs/Memory_System_Current_State_And_Proposal.md` (currently uncommitted, in-flight edits) documents the intentional direction change for the memory subsystem:

- Automated background memory creation has been removed.
- Explicit keyword requirement was added for memory writes.
- The memory store has been manually cleaned.
- The scan operation is legacy and should be deprecated or removed.
- Next phases (4-7) focus on topic timelines, stronger summaries, and sub-agent-driven history search — not on bulk memory ingestion.

Under the new policy, memories are created manually via the conversational agent calling an explicit memory-write tool (per `Subagent_Design.md` §5.2 and §14.1). The system no longer produces the duplication that dedup engines were built to manage. The dedup subsystem is **fighting a problem the system no longer creates**, and its ongoing maintenance cost (1631 lines, one embeddings model, three LLM-driven paths) earns nothing in return.

This document describes deleting the three memory-dedup service files, their three route handlers, and their model/response classes. It leaves all other ledger functionality intact.

## 2. Scope

### 2.1 In scope

- Delete three service files.
- Delete three route handlers.
- Delete unused shared models.
- Neutralize CLI references.
- Archive scripts that only existed to exercise or analyze the dedup subsystem.
- Update documentation.

### 2.2 Explicitly out of scope

- **Topic-level dedup.** `services/ledger/app/services/topic/dedup_semantic.py` is a separate file in the `topic/` subtree, not the `memory/` subtree. Topics are moving toward a `topic_timeline` table per the Memory System proposal doc Phase 4, which is its own design conversation. Leave `topic/dedup_semantic.py` alone.
- **Message deduplication in the sync path.** The comment at `services/ledger/app/services/user/sync.py:186` — "User message deduplication and assistant refresh logic" — refers to *consecutive user message collapse* during ledger sync, which is load-bearing behavior completely unrelated to memory dedup. Leave the sync path alone.
- **Memory search, memory create, memory update, memory delete routes.** Only the three `/memories/_dedup*` routes are removed.
- **Memory tags, memory topics, memory categories.** No schema changes.

## 3. Files and Routes Deleted

### 3.1 Service files to delete

- `services/ledger/app/services/memory/dedup.py`
- `services/ledger/app/services/memory/dedup_semantic.py`
- `services/ledger/app/services/memory/dedup_topic_based.py`

### 3.2 Route handlers to delete

In `services/ledger/app/routes/memory.py`:

- `GET /memories/_dedup` at `memory.py:347` (handler `deduplicate_memories_by_topic`) — remove the function, its decorator, and its imports of `_memory_deduplicate`.
- `POST /memories/_dedup_topic_based` at `memory.py:391` (handler `deduplicate_memories_topic_based`) — remove the function, its decorator, and its import of `_memory_deduplicate_topic_based`.
- `GET /memories/_dedup_semantic` at `memory.py:470` (handler `deduplicate_memories_semantic`) — remove the function, its decorator, and its import of `_memory_deduplicate_semantic`.

The three import lines at `memory.py:31-33` are all deleted.

### 3.3 Shared models to delete

`shared/models/ledger.py` defines `MemoryDedupResponse`. Grep for other consumers; if none exist outside the deleted routes and service files, delete the model class. If other consumers exist, leave the class in place and revisit separately.

### 3.4 App-level documentation in code

- `services/ledger/app/routes/memory.py:3-4` — update the module docstring to remove the "deduplicating memories" phrasing.
- `services/ledger/app/routes/memory.py:15-17` — remove the three `/_dedup*` endpoint lines from the docstring.
- `services/ledger/app/app.py:13` — update the comment "all memory management endpoints including deduplication" to drop "including deduplication".
- `services/ledger/README.md` — remove any documentation of the three deleted endpoints.

## 4. CLI Handling

`cli/tui.py` and `cli/transcript_renderer.py` contain references to the dedup endpoints. Recommended handling:

**Leave the CLI UI elements in place, but have them no-op with a user-visible message.** Concretely, find each call site that hits `/memories/_dedup*` and replace the HTTP call with a log line plus a status message along the lines of: `"Memory deduplication has been removed. See docs/Dedup_Removal.md."`. Keep any keybindings, menu entries, or status line items so that the TUI layout does not shift — the user sees the same button, it just tells them the feature is gone when pressed.

Rationale: resurrecting one of the dedup variants as a one-off manual script is plausible future work. The CLI button becoming a bridge to that script is a cheaper future migration than re-adding the UI element.

If the CLI author (Randi) disagrees at implementation time, just delete the references instead. Either is fine; the design goal is not losing TUI layout to a stray `except HTTPError`.

## 5. Scripts Handling

Three scripts exercise the dedup subsystem:

- `scripts/analyze_dedup.py`
- `scripts/test_semantic_systems.py`
- `scripts/cleanup_ledger_db.py`

Recommended handling: **move them to `scripts/archive/` rather than delete.** They are one-shot utility scripts, not production code, and may contain exploratory SQL, sample prompts, or fixture data worth keeping as historical reference. Moving them out of `scripts/` keeps the active script directory clean while preserving the content for git archaeology without requiring a `git log` dive.

`scripts/cleanup_ledger_db.py` is ambiguous — its name suggests generic cleanup, not dedup-specific cleanup. Read the file at implementation time and decide: if it is dedup-specific, archive it; if it is general-purpose ledger maintenance, leave it in place and strip any dedup-specific sections.

## 6. Documentation Updates

Grep for "dedup" and "deduplication" across the repository and update the following files to remove or mark obsolete the dedup subsystem:

- `README.md`
- `CLAUDE.md`
- `docs/Full Architecture.md`
- `docs/topic-based-deduplication.md` — rename to `docs/archive/topic-based-deduplication.md` or prepend a deprecation header. It documents a removed subsystem.
- `docs/Enhanced_Memory_Deduplication.md` — same treatment as above.
- `docs/Semantic_Memory_Systems.md` — review and remove dedup-specific content, keep any non-dedup content.
- `docs/Handoff_Summary.md` — remove dedup mentions.
- `.github/copilot-instructions.md` — remove dedup mentions from the architectural reference.
- `docs/Memory_System_Current_State_And_Proposal.md` — already in flight; the deletion of the dedup subsystem is consistent with its direction and may be referenced from there.
- `services/ledger/README.md` — remove endpoint documentation for the three deleted routes.

## 7. Acceptance Criteria

1. **Dedup service files gone:** `services/ledger/app/services/memory/dedup.py`, `dedup_semantic.py`, and `dedup_topic_based.py` do not exist on disk.
2. **Dedup routes gone:** `GET /memories/_dedup`, `POST /memories/_dedup_topic_based`, and `GET /memories/_dedup_semantic` return `404 Not Found` from a running ledger container.
3. **Ledger still starts:** `docker compose up ledger` succeeds without import errors.
4. **Other memory routes still work:** `GET /memories`, `POST /memories`, `GET /memories/_search`, `DELETE /memories/{id}`, and all other memory endpoints respond normally. Smoke-tested end-to-end.
5. **Topic dedup untouched:** `services/ledger/app/services/topic/dedup_semantic.py` is unchanged. Any topic routes that depend on it still work.
6. **Message sync untouched:** `POST /sync/user` and `GET /sync/get` behave identically to before, including the consecutive-user-message collapse at `sync.py:186`.
7. **Brain is unaffected:** Brain service sends no traffic to the removed endpoints. Verified by `grep -r 'dedup' services/brain/` returning no production-code hits.
8. **CLI does not crash:** Running `cli/tui.py` and pressing the dedup button surfaces a visible "feature removed" message rather than an HTTP error traceback.
9. **Line count dropped:** Rough verification — deleted code totals approximately 1600 lines of Python, plus the archived docs and scripts.

## 8. Implementation Order

1. **Check for hidden consumers.** Grep the full repo for `_memory_deduplicate`, `_memory_deduplicate_topic_based`, `_memory_deduplicate_semantic`, `MemoryDedupResponse`, and the three endpoint paths. Update this document if anything outside the scope identified here shows up.
2. **Archive documentation first.** Move or mark `docs/topic-based-deduplication.md`, `docs/Enhanced_Memory_Deduplication.md`, and dedup sections of `docs/Semantic_Memory_Systems.md` before touching code. This leaves a historical record in git with clean commit boundaries.
3. **Archive scripts.** `mkdir -p scripts/archive && git mv scripts/analyze_dedup.py scripts/archive/` (and the others per §5).
4. **Neutralize CLI call sites** per §4. Run the CLI once manually to confirm the buttons surface the intended message.
5. **Delete service files.** `git rm services/ledger/app/services/memory/dedup.py dedup_semantic.py dedup_topic_based.py`.
6. **Delete route handlers and imports** in `services/ledger/app/routes/memory.py` per §3.2 and §3.4.
7. **Delete `MemoryDedupResponse` model** per §3.3 if no other consumers exist.
8. **Update remaining documentation** per §6.
9. **Restart ledger** (auto-restart on code change — do not manually restart per project rules) and run the acceptance smoke tests (§7 items 2-6).
10. **Commit as a single change** titled something like "Remove memory dedup subsystem".

## 9. Non-Goals

- Replacing the dedup subsystem with anything.
- Deleting the memory store itself.
- Deleting message sync, summary generation, topic assignment, or context/heatmap logic.
- Refactoring unrelated code discovered during the grep in step 1. If something else looks broken, file it separately and keep this change scoped.
- Changing the memory schema. `memories`, `memory_tags`, `memory_category`, `memory_topics` stay as-is.
