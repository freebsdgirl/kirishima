# Memory System: Current State, Revised Direction, and Phased Plan

## Purpose

This document captures two things:

1. how the current memory/topic/summary system actually works today
2. the revised direction we want to take it

This version reflects the current decision points:

- no semantic retrieval
- no semantic deduplication
- no automated background thread creating memories
- memories will be created only by the conversational agent itself
- summaries will become more important
- topics will move toward timeline-based storage
- history retrieval will become a dedicated tool path instead of being improvised inside the main conversational loop

The goal here is not to pretend the current model is clean. It is not. The goal is to define a version of it that is understandable, implementable, and reviewable in phases.

## Status Snapshot

Current practical status:

- automated background memory creation is no longer the intended path
- memory creation has already been tightened to require explicit keywords
- the existing memory store has already gone through a substantial manual cleanup and curation pass
- the remaining major retrieval work is now mostly about summaries, history search, and context layering
- `history_search` and deeper search changes should be treated as waiting on sub-agent architecture

---

## Executive Summary

The current system mixes together several different layers:

- raw conversation in `user_messages`
- time-based summaries
- topics assigned later as metadata
- memory records with keywords and categories
- keyword heatmap scoring for contextual retrieval

The revised direction is to separate the roles more clearly.

### Revised Model

- `user_messages` remains the raw conversation log
- `summaries` remains the primary passive continuity layer, still mostly time-based
- `memories` become explicitly intentional records created by the conversational agent
- `topics` become timeline-based conversation structure, useful for provenance and grouping
- `history_search` becomes the explicit mechanism for retrieving older summaries and, in deep mode, old conversation logs

### Core Policy Changes

- remove automated background memory creation
- require explicit keyword arrays for memory creation
- rely more on summaries for continuity
- later prune old raw conversation from the active context window after the latest summary boundary
- use a dedicated retrieval sub-agent for deeper history access
- manually clean and consolidate the current memory store before building new retrieval behavior on top of it

This direction is simpler than the current system. It reduces duplication, makes memory creation intentional again, and puts summaries and retrieval in the roles they are better suited for.

---

## Current System

## Current Data Model

### Raw Conversation

Raw conversation is stored in `user_messages`.

Current relevant columns:

| Table | Columns |
| --- | --- |
| `user_messages` | `id`, `user_id`, `platform`, `platform_msg_id`, `role`, `content`, `model`, `tool_calls`, `function_call`, `topic_id`, `created_at`, `updated_at` |

Important notes:

- `topic_id` is nullable
- conversation rows are initially just rows, not necessarily topicized
- this table is the source of truth for the transcript

### Topics

Topics are stored in `topics`.

Current relevant columns:

| Table | Columns |
| --- | --- |
| `topics` | `id`, `name`, `description`, `created_at` |

Current behavior:

- topics are created separately from normal message ingestion
- conversation rows are assigned a `topic_id` later by a timeframe-based pass

### Memories

Memories are stored in `memories`, with related tables for tags, categories, and topic links.

Current relevant columns:

| Table | Columns |
| --- | --- |
| `memories` | `id`, `memory`, `created_at`, `access_count`, `last_accessed`, `reviewed` |
| `memory_tags` | `memory_id`, `tag` |
| `memory_category` | `memory_id`, `category` |
| `memory_topics` | `memory_id`, `topic_id` |

Important notes:

- memory text lives in `memories`
- keywords are stored in `memory_tags`
- categories are stored in `memory_category`
- memory-topic links are stored separately in `memory_topics`

### Summaries

Summaries already exist and are currently time-based.

This is important because the revised plan does not replace them. It leans on them more heavily.

### Heatmap

Heatmap data is stored in:

| Table | Columns |
| --- | --- |
| `heatmap_score` | `keyword`, `score`, `last_updated` |
| `heatmap_memories` | `memory_id`, `score`, `last_updated` |

This is a ranking layer over keyword-tagged memories. It is not itself a memory store.

---

## Current Behavior

## 1. Message Ingestion

Conversation rows are added to `user_messages`.

At this point:

- the transcript exists
- the rows may not yet have a topic
- the rows may later be included in summary generation
- the rows may later be included in topic assignment and automated memory extraction

## 2. Automated Topic And Memory Scan

The current `POST /memories/_scan` path does too much.

It currently:

1. fetches untagged conversation rows
2. optionally reuses and reprocesses the most recent topic window
3. sends the conversation batch to an LLM
4. gets back topics and memories
5. creates topics
6. assigns topics to message rows by timeframe
7. creates memory rows
8. links memories to those topics

That means the current system still has a background mechanism that creates memories independently of the conversational agent.

This is the piece we explicitly moved away from as the intended model.

At this point, this path should be treated as legacy behavior rather than the future of the memory system.

## 3. Memory Creation Today

The intended active creation path is the conversational agent using the memory tool.

The create contract is now intentionally stricter:

- memory text is required
- explicit keywords are required
- category remains optional
- the brain-facing shape still includes `topic_id`
- topic association is deferred for later design work

This is no longer hypothetical. It is already the shape we want to keep.

## 4. Retrieval Today

There are currently two practical retrieval modes:

### Direct Search

`/memories/_search` can search by:

- keywords
- category
- topic
- time
- direct memory ID

### Conversational Context Injection

The brain’s live conversational retrieval path currently:

1. extracts weighted keywords from current conversation
2. updates the heatmap
3. asks ledger for the highest-ranked memories

This makes keyword quality on memories highly important.

---

## What Is Wrong With The Current Arrangement

## 1. Automated Memory Creation Was Duplicative

There are two competing ways a memory can come into existence:

- the conversational agent creates one deliberately
- the background scan later creates one from past conversation

This created obvious duplication risk, especially when both were looking at the same conversation material from different angles.

That is why the system direction now treats agent-created memory as the canonical path.

## 2. The Current Memory Store Needed Cleanup

The existing memory database needed cleanup.

Problems include:

- outdated memories
- duplicates
- overly granular entries
- keyword bloat
- inconsistent usefulness as direct agent context

The current store contained a mix of things that were not all the same kind of object.

A substantial review and cleanup pass has already happened, so future work should assume a more curated baseline than when this document was first drafted.

## 3. "Memory" Is Doing Multiple Jobs

Right now a memory is trying to be all of these:

- a durable fact
- a retrieval index record
- an agent-facing context fragment
- a dedup unit
- a topic-linked artifact

That is too much.

The revised direction does not require renaming the table immediately, but conceptually many current memories behave more like curated facts than like raw conversational context.

## 4. Topics Are Useful, But Their Storage Model Is Awkward

Topics are useful for:

- grouping related conversation spans
- later relating memories to parts of the transcript
- helping dedup or organize review work

But storing topic membership directly on message rows is not the cleanest long-term model if the real concept is "this topic was active during this span of time."

## 5. Context Needs Better Layering

The active context window, summaries, memories, and deeper history are currently not separated cleanly enough.

The revised model needs these layers to become more explicit:

- active conversation
- latest summary boundary
- curated memories
- archived summaries
- deep transcript history

---

## Revised Direction

This is the current intended direction.

## 1. Memories Are Created Only By The Conversational Agent

This is now the intended steady state.

From this point forward, the intended model is:

- the conversational agent decides whether to create a memory
- the memory tool requires explicit keywords
- memory creation becomes intentional and sparse again

This has several benefits:

- fewer duplicates
- clearer provenance
- better trust in the memory store
- simpler system behavior

## 2. Summaries Become More Important

Summaries already exist and are currently time-based.

That remains the correct backbone.

The revised direction is not to replace time-based summaries with topic-based summaries. It is to rely on time-based summaries more heavily and make them more robust.

The summary layer should serve as:

- passive continuity
- a compressed record of recent interaction
- a future context-window boundary

## 3. Topics Move Toward Timeline Storage

Instead of treating topics mainly as a direct foreign key on message rows, the revised plan is to introduce a timeline model.

### Proposed Topic Timeline Table

Recommended new table:

| Table | Columns |
| --- | --- |
| `topic_timeline` | `id`, `topic_id`, `start_time`, `end_time`, `created_at`, `updated_at` |

Optional later fields:

| Table | Columns |
| --- | --- |
| `topic_timeline` | `source`, `notes`, `created_by` |

The intended meaning is:

- `topics` defines the topic identity
- `topic_timeline` defines when that topic was active

This lets us later infer:

- which transcript rows belong to a topic
- which memories likely belong to a topic, based on memory creation time

This is cleaner than forcing topic assignment to be stored only as a per-row property forever.

Important caveat:

- timestamp-based inference will be useful, not magically perfect
- overlapping topic windows need a policy
- some memories may still need explicit topic linking later

But this is still a better structural direction than the current muddle.

## 4. Memories Are For Durable Curated Knowledge, Not Raw Agent Prompt Text

The memory store should not be exposed raw to the conversational agent in all cases.

The revised idea is:

- memory rows remain durable curated records
- they can still contain longer paragraph-style entries for important systems
- they do not have to all be tiny atomized facts

This means memory cleanup is not just deduplication. It is curation.

That curation work has already had a substantial pass and should now be treated as part of the current baseline.

Examples of what should survive well:

- stable user preferences
- important long-lived personal facts
- system-level knowledge about Kirishima itself
- durable constraints or standing facts that matter repeatedly

## 5. History Retrieval Gets Its Own Tool Path

We will add a new tool: `history_search`.

This tool is not intended to be executed directly by the conversational agent in an unbounded way.

Instead:

- the conversational agent invokes a sub-agent
- the sub-agent uses `history_search`
- the sub-agent returns only the specific relevant result or excerpt

### Intended History Search Behavior

Default mode:

- search previous summaries

Deep mode:

- search previous summaries
- and also search the conversation log itself

The main conversational agent should get back:

- the answer or relevant excerpt
- enough context to use it
- not a giant dump of raw history

## 6. Active Context Window Will Be Rebalanced Later

Longer term, we will likely:

1. prune raw conversation context before the most recent summary boundary
2. include the most recent summary in the system prompt or equivalent context layer
3. allow the active live context window to be a bit longer

The point is not to shrink context blindly. The point is to trade old raw transcript for a summary-backed boundary while keeping more active conversation in view.

Token-wise, this should roughly even out if done carefully.

This should happen after summary quality improves, not before.

---

## Revised Table Model

## Keep

These remain core:

| Table | Role |
| --- | --- |
| `user_messages` | raw transcript |
| `topics` | topic identity catalog |
| `summaries` | time-based continuity layer |
| `memories` | curated durable memory records |
| `memory_tags` | explicit keywords |
| `memory_category` | explicit categories |
| `heatmap_score` | keyword weight state |
| `heatmap_memories` | cached ranked memory scores |

## Add

Recommended new table:

| Table | Role |
| --- | --- |
| `topic_timeline` | maps topics to active time spans |

### Proposed Topic Timeline Schema

| Column | Purpose |
| --- | --- |
| `id` | unique row ID |
| `topic_id` | foreign key to `topics` |
| `start_time` | beginning of active topic window |
| `end_time` | end of active topic window |
| `created_at` | audit metadata |
| `updated_at` | audit metadata |

## Reevaluate Later

These current pieces should not be ripped out immediately, but may become less central:

| Table | Comment |
| --- | --- |
| `memory_topics` | may remain as an explicit override or legacy compatibility layer |
| `user_messages.topic_id` | may become legacy or derived rather than the primary topic model |

The right move is to add `topic_timeline` first, then decide what should become derived versus primary.

---

## Revised Tooling Direction

## Memory Tool

Memory creation is already stricter.

### Required Inputs

- memory text
- array of keywords

Current constraints and direction:

- minimum keyword count
- maximum keyword count
- keyword normalization to lowercase
- duplicate keyword collapse

We can keep category optional.

We are still not solving topic association in this first step. That comes later through the topic timeline model.

## History Search Tool

New tool to add:

- `history_search`

Suggested inputs:

| Field | Purpose |
| --- | --- |
| `query` | what the caller is looking for |
| `deep` | whether to search transcript as well as summaries |
| `time_range` | optional bound if needed later |
| `limit` | optional result control |

Suggested output:

- concise answer or relevant excerpt
- source type: summary or transcript
- source references sufficient for debugging or follow-up

The important design rule is:

- the main conversational agent should not receive a huge blob of history
- the sub-agent should do the retrieval and narrowing first

Current status:

- this is still outstanding
- this is one of the clearest pieces of work that depends on sub-agent architecture
- it should not be implemented as a broad direct-use tool for the top-level conversational model

---

## Cleanup Strategy For Existing Memories

This is a real part of the plan, not an afterthought.

Before we depend more heavily on the memory store, it needed a manual cleanup pass.

That work should include:

- deleting stale memories
- merging duplicates
- rewriting overly fragmented memories into better consolidated entries
- turning some clusters of tiny facts into more useful paragraph-length records
- trimming keyword lists so they stay tight and intentional

This is especially important for system-level knowledge such as Kirishima itself.

The goal is not for every memory to become a tiny atomic fact.

The goal is for every memory to be useful, durable, and worth keeping.

Current status:

- this work has already had a substantial pass
- future cleanup should be treated as ongoing maintenance and occasional curation, not as the big blocked prerequisite it was earlier

---

## Phased Plan

## Completed Work

### Completed Or Mostly Completed

- move the system direction away from automated background memory creation
- tighten memory creation so explicit keywords are required
- perform a substantial manual review and cleanup of the memory store

These items were previously described as:

- Phase 1: Remove Automated Background Memory Creation
- Phase 2: Tighten Memory Creation
- Phase 3: Manual Memory Store Cleanup

They should no longer be read as the next implementation steps.

## Remaining Work

## Phase 4: Introduce Topic Timeline Storage

Goal:

- shift topics toward a span-based model

Changes:

1. add `topic_timeline`
2. write topic windows there
3. begin using time spans as the primary way to understand what topic was active when
4. later infer memory/topic and transcript/topic relationships from timestamps when appropriate

Expected outcome:

- cleaner topic provenance
- easier grouping of transcript and memories
- less dependence on direct per-row topic assignment as the only model

Open design questions for this phase:

- can topic windows overlap
- how should ambiguous timestamps be handled
- should `memory_topics` remain as an override layer

## Phase 5: Strengthen Summary Generation

Goal:

- make summaries robust enough to carry more of the continuity burden

Changes:

1. improve summary prompts
2. review summary granularity and scope
3. verify summaries are useful enough to be included as a core context layer later

Expected outcome:

- summaries become a more reliable continuity substrate

Important note:

- summaries remain time-based by default
- this phase is not about replacing them with topic summaries

Dependency note:

- this phase matters on its own
- it also feeds directly into later `history_search` and context-window work

## Phase 6: Add History Search

Goal:

- provide explicit access to older summaries and transcript history without dumping it directly into the main conversational context

Changes:

1. add `history_search`
2. implement normal summary search mode
3. implement deep mode that also searches the transcript
4. route it through a sub-agent that returns only the relevant slice

Expected outcome:

- better long-range recall
- less pressure to keep huge raw context windows

Dependency:

- this phase should be treated as waiting on sub-agent architecture
- without sub-agents, `history_search` is too likely to become a direct context-bloating tool in the main conversational loop

## Phase 7: Rebalance The Active Context Window

Goal:

- make the live context window more efficient without losing continuity

Changes:

1. prune raw conversation before the most recent summary boundary
2. include the most recent summary as context
3. allow somewhat more active recent conversation to remain in-window

Expected outcome:

- better balance between recency and continuity
- less token waste on old raw conversation

Dependency:

- do not do this until summary quality is good enough
- do not do this until sub-agent-backed retrieval exists, or the system will lose recall while shrinking live context

---

## Recommended Implementation Order

This is the order that currently makes the most sense from here.

1. Phase 4: add `topic_timeline`
2. Phase 5: strengthen summaries
3. Phase 6: add `history_search`
4. Phase 7: rebalance the active context window

Reasoning:

- the cleanup and input-tightening groundwork is already mostly done
- structure and summary quality come next
- retrieval should follow once sub-agents exist
- context pruning should happen last

Updated practical reading of that order:

- Phases 1 through 3 are already substantially done
- Phase 4 and Phase 5 are the next direct memory-system work
- Phase 6 is waiting on sub-agent architecture
- Phase 7 is waiting on both stronger summaries and Phase 6

---

## Risk Management

## Database Safety Principles

When touching schema:

1. additive changes first
2. new tables before destructive rewrites
3. backfill or migration logic only after new paths are working
4. do not remove legacy fields until replacement behavior is proven

## Specific Cautions

### Topic Timeline

This is the right structural direction, but it needs careful policy decisions:

- overlapping windows
- boundary precision
- whether inferred topic membership is authoritative or just convenient

### Summary-Backed Context Pruning

This will materially affect live behavior.

Do not ship it before summary quality is trusted.

Also do not ship it before sub-agent-backed history retrieval exists.

### Memory Cleanup

Manual cleanup should be treated as curation work, not just mechanical dedup.

Most of the urgent initial cleanup work is already behind us, but the standard should remain the same for future maintenance.

---

## Open Questions

These questions are still unresolved and should be reviewed as we implement phases.

1. Should memories remain named "memories," or are they conceptually closer to curated facts?
2. Should category stay optional, or should it be encouraged more strongly for manual review and organization?
3. Should `memory_topics` survive long term as an explicit override, even after `topic_timeline` exists?
4. How should overlapping topic windows behave?
5. What exact output contract should `history_search` return to the calling sub-agent?
6. At what summary quality threshold do we feel safe pruning old raw transcript before the latest summary boundary?

---

## Immediate Next Steps

The next implementation steps should be:

- Phase 4: introduce `topic_timeline`
- Phase 5: strengthen summaries

Those are the next pieces of memory-system work that can move directly without waiting on sub-agents.

After that, assuming the sub-agent architecture lands:

- Phase 6: add `history_search`
- Phase 7: rebalance the active context window

That is the point where deeper search and context pruning become sane instead of reckless.
