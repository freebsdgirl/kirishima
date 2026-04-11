# Heatmap Cache Removal

## 1. Motivation

`services/ledger/app/services/context/heatmap.py` maintains two derived tables:

- `heatmap_score` — authoritative `(keyword, score, last_updated)` table, updated by `update_heatmap()`.
- `heatmap_memories` — `(memory_id, score, last_updated)` cache, rebuilt from scratch on every call to `update_heatmap()` via `_recalculate_memory_scores()` at `heatmap.py:152-212`.

The cache is rebuilt by `DELETE FROM heatmap_memories` followed by a full rescan of every memory whose tags intersect any current keyword, a second per-memory tag lookup, and an insert. This happens **synchronously inside every `update_heatmap()` call**, on the request path, inside the same transaction as the keyword update.

The cache has one reader: `get_top_memories_by_heatmap()` at `heatmap.py:215-252`. That reader is a single `SELECT … JOIN heatmap_memories … ORDER BY score DESC LIMIT ?`. It can be rewritten as a join through `memory_tags` and `heatmap_score` directly, computing memory scores at query time, without the cache table.

Deleting the cache:
- Removes the synchronous O(memories × keywords) rescore from the write path.
- Removes one derived table to keep consistent.
- Reduces `update_heatmap()` latency to O(keywords).
- Has no impact on read latency at realistic memory-store sizes (Randi's personal store, bounded by one human).

## 2. Changes

### 2.1 Delete the cache table

Remove the `heatmap_memories` table definition and its index from `services/ledger/app/setup.py`. Drop the table on startup via a one-line migration: `DROP TABLE IF EXISTS heatmap_memories` executed unconditionally before the remaining `CREATE TABLE IF NOT EXISTS` calls. This is safe because the table is purely derived — losing it loses nothing not reconstructible from `heatmap_score` + `memory_tags`.

### 2.2 Delete `_recalculate_memory_scores`

Remove `_recalculate_memory_scores()` at `heatmap.py:152-212` entirely. Remove its call site at `heatmap.py:127` inside `update_heatmap()`, and remove the `affected_memories` field from both the local variable assignment at `heatmap.py:127` and the return dict at `heatmap.py:141`. Update the log message at `heatmap.py:132-134` to drop the "N memories rescored" phrase.

Callers of `update_heatmap()` receive a dict and may inspect fields. Search for consumers of `affected_memories` specifically. If any exist, drop the field from their consumption (it is an informational statistic only, not a correctness signal).

### 2.3 Rewrite `get_top_memories_by_heatmap`

Replace the body of `get_top_memories_by_heatmap()` at `heatmap.py:215-252` with a query that computes memory scores on the fly:

```sql
SELECT
    m.id,
    m.memory,
    m.created_at,
    SUM(hs.score) AS heatmap_score
FROM memories m
JOIN memory_tags mt ON m.id = mt.memory_id
JOIN heatmap_score hs ON hs.keyword = mt.tag
GROUP BY m.id, m.memory, m.created_at
ORDER BY heatmap_score DESC
LIMIT ?
```

The returned dict shape must stay the same: `{"id", "memory", "created_at", "heatmap_score", "score_updated"}`. For `score_updated`, return the current timestamp (`datetime.now().isoformat()`) — the "last updated" semantic no longer applies to a cache that does not exist, and no caller depends on this value being meaningful.

### 2.4 Verify no other consumers

Before merging, grep the ledger service for `heatmap_memories`. Current references (confirmed):

- `services/ledger/app/services/context/heatmap.py` (all go away per §2.1-§2.3)
- `services/ledger/app/setup.py` (DDL, deleted per §2.1)
- `services/ledger/README.md` (documentation, update to remove references)
- `docs/Memory_System_Current_State_And_Proposal.md` (already a planning doc, update if it proposes to keep the cache)
- `docs/Full Architecture.md`, `.github/copilot-instructions.md` (update if they describe the cache as an architectural component)

Re-grep at implementation time to catch anything added since this doc was written.

## 3. Acceptance Criteria

1. **Equivalence on read path:** Populate a test ledger with a handful of memories tagged with keywords, run `update_heatmap()` with a known weight set, then call `get_top_memories_by_heatmap(limit=10)`. The returned list must match the ordering and scores produced by the current cached implementation against the same fixture. Verified by a snapshot test comparing the two.

2. **`update_heatmap` no longer touches `heatmap_memories`:** After the change, grep the codebase for `heatmap_memories`. The only remaining reference should be the `DROP TABLE IF EXISTS` migration line in `setup.py`. No `SELECT`, `INSERT`, `DELETE`, or `UPDATE` against `heatmap_memories` in live code paths.

3. **`update_heatmap` return shape:** `update_heatmap()` returns a dict with keys `new_keywords`, `updated_keywords`, `decayed_keywords`, `removed_keywords`. The `affected_memories` key is gone. Any caller that previously inspected `affected_memories` is updated to not.

4. **Latency improvement:** Informal verification, not a hard test. Call `update_heatmap()` with a realistic keyword set against a populated ledger and confirm wall time is materially lower than the pre-change baseline. Log the timing in debug mode for manual inspection.

5. **No regression in brain memory retrieval:** Hit `GET /context/?limit=5` on the running ledger service via brain and confirm the returned memory list is still non-empty and ordered by score. End-to-end smoke test against the live containers.

## 4. Implementation Order

1. Add index on `memory_tags.tag` if not already present. Verify: `EXPLAIN QUERY PLAN` on the new join should show an index scan. Without this index, the read path would do a full table scan per query; the cache was hiding this concern.
2. Rewrite `get_top_memories_by_heatmap()` per §2.3. Leave `_recalculate_memory_scores()` in place for now so both paths coexist temporarily.
3. Add the snapshot test per acceptance criterion #1. Confirm it passes with both implementations giving identical results.
4. Remove `_recalculate_memory_scores()` and its call site per §2.2.
5. Add the `DROP TABLE IF EXISTS heatmap_memories` migration and remove the table from `setup.py` per §2.1.
6. Update documentation references per §2.4.
7. Run the end-to-end smoke test per acceptance criterion #5.
8. Commit as a single change.

## 5. Non-Goals

- Changing the `heatmap_score` table shape or update semantics. The keyword heatmap itself (boost, decay, clamp, remove) stays exactly as currently implemented at `heatmap.py:44-149`.
- Adding semantic search or vector retrieval. The memory system remains keyword-based per existing design.
- Changing the `/context/*` HTTP routes. Wire contract is unchanged.
- Changing memory tag storage. `memory_tags` stays as-is.
