# Ledger Microservice

A comprehensive persistent data store for the Kirishima system, managing message buffers, memories, topics, and summaries across platforms using SQLite. The ledger serves as the central repository for all conversational data and associated metadata.

## Architecture

The ledger service operates as the persistent storage layer for:

- **Message Buffers**: Complete conversation history with advanced synchronization
- **Memory System**: Long-term knowledge storage with semantic organization
- **Topic Management**: Conversation threading and categorization
- **Summary Storage**: Temporal summary data with metadata

## Core Features

### Message Management

- Stores all user, assistant, system, and tool messages with full metadata
- Advanced deduplication and conflict resolution for message synchronization
- Handles consecutive user messages (e.g., after server errors)
- In-place editing of assistant messages when content changes
- Platform-agnostic storage (API, Discord, iMessage, etc.)
- Ensures message buffers always start with a user message
- Configurable message history limits via `ledger.turns` in config

### Memory System

- Persistent storage of extracted memories with keywords and categories
- Full-text search capabilities with multiple filter combinations
- Topic association linking memories to conversation threads
- Access tracking and usage analytics
- Memory deduplication and management tools
- Automated memory extraction from conversation scanning

### Topic Management

- UUID-based topic identification and storage
- Topic-to-message and topic-to-memory relationships
- Temporal topic assignment to message ranges
- Recent topics discovery and analytics

### Summary Management

- Temporal summaries with typed periods (morning, afternoon, evening, night, daily, weekly, monthly)
- Summary metadata including timestamps and classification
- Summary creation, retrieval, and deletion endpoints

## Summary System Details

### Summary Types and Periods

The summary system supports multiple temporal classifications:

#### Time-Based Periods

- **`morning`**: 06:00 - 11:59 (6 hours)
- **`afternoon`**: 12:00 - 17:59 (6 hours)
- **`evening`**: 18:00 - 23:59 (6 hours)
- **`night`**: 00:00 - 05:59 (6 hours)

#### Aggregate Periods

- **`daily`**: Full 24-hour day summaries
- **`weekly`**: 7-day period summaries
- **`monthly`**: Calendar month summaries
- **`periodic`**: Custom time range summaries

### Summary Metadata Structure

Each summary includes comprehensive metadata:

```json
{
  "id": "uuid-summary-123",
  "content": "Summary text content...",
  "metadata": {
    "timestamp_begin": "2025-07-18T06:00:00Z",
    "timestamp_end": "2025-07-18T11:59:59Z", 
    "summary_type": "morning"
  }
}
```

#### Metadata Fields

- **`timestamp_begin`**: ISO timestamp marking summary period start
- **`timestamp_end`**: ISO timestamp marking summary period end
- **`summary_type`**: Enum value from supported period types
- **Automatic Validation**: Ensures timestamp consistency and type validity

### Summary Operations

#### Creation (`POST /summaries/create`)

- **Message-Based Generation**: Creates summaries from user message history
- **Time Range Specification**: Flexible start/end timestamp configuration
- **Content Analysis**: Extracts key themes, decisions, and important events
- **Automatic Categorization**: Assigns appropriate summary type based on time range
- **Duplicate Prevention**: Prevents overlapping summaries for same period

#### Retrieval (`GET /summaries`)

- **Filtered Queries**: Search by summary type, time range, or content
- **Temporal Ordering**: Results sorted by timestamp for chronological analysis
- **Metadata Inclusion**: Returns complete summary objects with all metadata
- **Pagination Support**: Handles large summary collections efficiently

#### Management

- **Update Operations**: Modify summary content while preserving metadata
- **Deletion (`DELETE /summaries/{id}`)**: Remove summaries with cascade handling
- **Bulk Operations**: Process multiple summaries simultaneously

### Summary Use Cases

#### Contextual Memory

- **Conversation Context**: Provides historical context for ongoing discussions
- **Temporal Awareness**: Helps maintain awareness of when events occurred
- **Pattern Recognition**: Identifies recurring themes across time periods

#### Analytics and Insights

- **Activity Patterns**: Analyzes communication patterns across different time periods
- **Content Evolution**: Tracks how topics and interests change over time
- **Productivity Metrics**: Measures engagement and activity levels

#### Data Management

- **Storage Optimization**: Compressed representation of large message volumes
- **Quick Access**: Rapid retrieval of historical information without full message parsing
- **Backup and Recovery**: Structured data for system recovery and migration

## API Endpoints

### Message Operations

- `GET /user/{user_id}/messages` - Retrieve messages with time period filtering
- `GET /active` - List all active user IDs in the database
- `DELETE /user/{user_id}` - Delete user messages with period/date filtering
- `POST /user/{user_id}/sync` - Advanced message buffer synchronization

### Memory Operations

- `POST /memories` - Create new memory entries
- `GET /memories/{memory_id}` - Retrieve specific memory with full details
- `GET /memories` - List memories with pagination and filtering
- `PATCH /memories` - Update existing memory content
- `DELETE /memories/{memory_id}` - Delete memory and associated data
- `GET /memories/search` - Advanced multi-parameter memory search
- `POST /memories/scan` - Automated memory extraction from messages
- `PATCH /memories/topic` - Assign topics to memories
- `GET /memories/topic/{topic_id}` - Retrieve memories by topic
- `POST /memories/dedup` - Memory deduplication utilities

### Topic Operations

- `POST /topics` - Create new topics (with duplicate prevention)
- `GET /topics` - Retrieve recent topics from message history
- `GET /topics/{topic_id}` - Get specific topic details
- `DELETE /topics/{topic_id}` - Delete topic and cascade relationships
- `PATCH /topics/{topic_id}` - Assign topic to message timeframes
- `GET /topics/{topic_id}/messages` - Retrieve messages associated with topic
- `POST /topics/timeframe` - Get topic IDs within time ranges

### Summary Operation

- `POST /summaries` - Create new summaries with metadata
- `GET /summaries` - Retrieve summaries with filtering
- `DELETE /summaries/{summary_id}` - Delete specific summaries
- `POST /summaries/create` - Generate summaries from message data

## Database Schema

### Core Tables

- **`user_messages`**: Message storage with platform metadata, tool calls, and topic associations
- **`memories`**: Core memory storage with access tracking and review status
- **`memory_tags`**: Many-to-many keyword associations for memories
- **`memory_category`**: One-to-one category assignments for memories
- **`memory_topics`**: Many-to-many memory-to-topic relationships
- **`topics`**: Topic definitions with names and creation timestamps
- **`summaries`**: Temporal summary storage with metadata

### Key Features

- WAL journal mode for concurrent access
- Foreign key constraints with proper cascading
- Optimized indexes for common query patterns
- Automatic timestamp management
- UUID-based primary keys for distributed compatibility

## Advanced Synchronization Logic

The `/user/{user_id}/sync` endpoint implements sophisticated message synchronization:

### Deduplication Rules

1. **User Message Deduplication**: Identical consecutive user messages are deduplicated
2. **Assistant Message Editing**: In-place updates when assistant content changes
3. **Consecutive User Handling**: Resolves server error scenarios with multiple user messages
4. **Platform-Specific Logic**: Different handling for API vs. external platform messages

### Edge Case Handling

- Server error recovery with message rollback
- Tool call and function call preservation
- Platform message ID tracking for external services
- Content-based change detection for assistant edits

## Memory Search, Scan, and Deduplication

### Advanced Memory Search

The memory search system (`GET /memories/search`) supports sophisticated multi-parameter queries using AND logic:

#### Search Parameters

- **Keywords**: Multi-keyword search with configurable minimum matches
  - Supports progressive fallback (reduces minimum requirements if no matches found)
  - Case-insensitive matching against memory tags
  - Example: `["meeting", "project"]` with `min_keywords: 2`
- **Category**: Single category filtering for organizational structure
  - Exact match against memory category assignments
  - Example: `"Work"`, `"Personal"`, `"Technical"`
- **Topic Association**: Topic-based memory filtering
  - Links memories to specific conversation threads
  - Searches memories associated with a given topic UUID
- **Time Ranges**: Temporal filtering with ISO timestamp support
  - `created_after`: Return memories created after specified time
  - `created_before`: Return memories created before specified time
- **Memory ID**: Direct memory lookup (bypasses all other filters)
  - Exact UUID match for specific memory retrieval

#### Search Algorithm

- **Intersection Logic**: All specified parameters must match (AND operation)
- **Progressive Keyword Matching**: Automatically reduces minimum keyword requirements if no results
- **Efficient Indexing**: Optimized SQL queries with proper database indexes
- **Complete Data Return**: Returns full `MemoryEntry` objects with all associated data

#### Example Search Request

```json
{
  "keywords": ["meeting", "project", "deadline"],
  "category": "Work", 
  "min_keywords": 2,
  "created_after": "2025-07-01T00:00:00",
  "topic_id": "uuid-topic-123"
}
```

### Memory Scanning (`POST /memories/scan`)

Automated memory extraction from conversation messages:

#### Functionality

- **Message Analysis**: Scans user message history for extractable knowledge
- **Context-Aware Extraction**: Identifies facts, preferences, and important information
- **Keyword Generation**: Automatically generates relevant tags for discovered memories
- **Category Assignment**: Intelligently categorizes extracted memories
- **Deduplication**: Prevents creation of duplicate memories during scanning

#### Scan Parameters

- **User ID**: Target user for message scanning
- **Time Range**: Optional date range for message analysis
- **Memory Threshold**: Minimum importance score for memory creation
- **Category Hints**: Suggested categories for discovered memories

### Memory Deduplication (`POST /memories/dedup`)

Comprehensive deduplication system for memory management:

#### Deduplication Types

- **Content-Based**: Identifies memories with similar or identical text content
- **Keyword-Based**: Finds memories sharing significant keyword overlap
- **Topic-Based**: Groups memories associated with the same conversation topics
- **Temporal**: Identifies memories created in close time proximity with similar content

#### Deduplication Process

1. **Similarity Analysis**: Compares memory content using text similarity algorithms
2. **Keyword Intersection**: Calculates shared keyword percentages between memories
3. **Confidence Scoring**: Assigns confidence scores to potential duplicates
4. **Merge Suggestions**: Provides recommendations for memory consolidation
5. **Safe Deletion**: Removes clear duplicates while preserving unique information

#### Deduplication Options

- **Automatic Mode**: Removes high-confidence duplicates automatically
- **Interactive Mode**: Returns suggestions for manual review and approval
- **Dry Run**: Analysis only, no actual deletions performed
- **Threshold Configuration**: Adjustable similarity thresholds for duplicate detection

## Deduplication System

The ledger service provides comprehensive deduplication capabilities for both memories and topics, supporting multiple strategies and approaches.

### Memory Deduplication

#### Global Memory Deduplication (`/memories/_dedup_semantic`)

**Method**: `GET` (with `dry_run` parameter)  
**Purpose**: Global memory deduplication using timeframe or keyword grouping strategies.

**Key Features**:
- **Grouping Strategies**: 
  - `timeframe`: Groups memories created within specified days (default: 7)
  - `keyword`: Groups memories sharing minimum keyword matches (default: 2)
- **LLM Integration**: Uses existing `dedup_memories.j2` prompt template for intelligent deduplication
- **Dry Run Support**: `dry_run=true` shows groups without making changes
- **Live Mode**: `dry_run=false` applies LLM recommendations with updates and deletions

**Parameters**:
- `dry_run` (bool): Preview mode vs. actual execution (default: true)
- `grouping_strategy` (str): "timeframe" or "keyword" (default: "timeframe")
- `min_keyword_matches` (int): Minimum shared keywords for grouping (default: 2)
- `timeframe_days` (int): Days for timeframe grouping (default: 7)

**Example**:
```bash
# Preview grouping
curl "http://localhost:4203/memories/_dedup_semantic?dry_run=true&grouping_strategy=keyword&min_keyword_matches=3"

# Execute deduplication
curl "http://localhost:4203/memories/_dedup_semantic?dry_run=false&grouping_strategy=timeframe&timeframe_days=5"
```

**Response Structure**:
```json
{
  "strategy": "timeframe",
  "groups_processed": 15,
  "memory_count": 245,
  "operations": {
    "update": {"mem_id": {"memory": "consolidated text", "keywords": [...]}},
    "delete": ["mem_id_1", "mem_id_2"]
  },
  "results": {
    "updated": 8,
    "deleted": 12,
    "errors": []
  },
  "group_details": [...]
}
```

#### Topic-Based Memory Deduplication (`/memories/_dedup_topic_based`)

**Method**: `POST`  
**Purpose**: Comprehensive two-phase deduplication: topic consolidation followed by memory deduplication within consolidated topics.

**Process Flow**:
1. **Topic Similarity Analysis**: Uses sentence-transformers to find semantically similar topics
2. **Topic Consolidation**: LLM determines which topics should be merged and optimal naming
3. **Memory Chunking**: Groups memories by timeframe within consolidated topics  
4. **Memory Deduplication**: LLM processes each memory chunk for deduplication

**Key Features**:
- **Semantic Topic Clustering**: Uses DBSCAN clustering with cosine similarity on topic names
- **LLM Topic Merging**: Intelligent topic consolidation with naming optimization
- **Timeframe Chunking**: Prevents token overflow by processing memories in temporal chunks
- **Comprehensive Dry Run**: Complete cost analysis and planning without execution
- **Token Management**: Configurable limits to control LLM usage and costs

**Parameters**:
- `topic_similarity_threshold` (float): Cosine similarity threshold for topic clustering (0.7-0.9, default: 0.8)
- `max_topic_groups` (int): Maximum topic groups to consolidate (10-50, default: 20)
- `max_memory_chunks` (int): Maximum memory chunks to process (20-100, default: 50)
- `max_memories_per_chunk` (int): Maximum memories per LLM request (10-20, default: 15)
- `chunk_days` (int): Days per timeframe chunk (3-14, default: 7)
- `max_total_tokens` (int): Total token budget (50k-200k, default: 100k)
- `dry_run` (bool): Analysis-only mode (default: false)

**Example**:
```bash
# Dry run analysis
curl -X POST "http://localhost:4203/memories/_dedup_topic_based?dry_run=true&max_topic_groups=10"

# Execute full deduplication
curl -X POST "http://localhost:4203/memories/_dedup_topic_based?topic_similarity_threshold=0.75&max_memory_chunks=30"
```

**Dry Run Response**:
```json
{
  "status": "dry_run_complete",
  "plan": {
    "total_topics": 192,
    "topic_groups_to_consolidate": 5,
    "memory_chunks_to_deduplicate": 9,
    "estimated_llm_requests": 14,
    "estimated_total_tokens": 3735,
    "cost_breakdown": {...}
  },
  "topic_consolidations": [...],
  "memory_chunks": [...]
}
```

### Topic Deduplication

#### Semantic Topic Deduplication (`/topics/_dedup_semantic`)

**Method**: `POST` (execution), `GET /topics/_dedup_semantic/preview` (preview)  
**Purpose**: Standalone topic deduplication using semantic similarity and LLM decision-making.

**Key Features**:
- **Sentence-Transformers**: Uses all-MiniLM-L6-v2 model for topic name embeddings
- **DBSCAN Clustering**: Groups semantically similar topics with configurable similarity thresholds
- **LLM Merge Decisions**: GPT-4.1 analyzes topic clusters and determines optimal consolidation
- **Memory Preservation**: Moves all memories from deleted topics to primary topics
- **Topic Ranking**: Prioritizes topics with more memories for primary selection

**Parameters**:
- `semantic_similarity_threshold` (float): Cosine similarity threshold (0.6-0.85, default: 0.7)
- `min_cluster_size` (int): Minimum topics per cluster (2-4, default: 2)
- `max_clusters_to_process` (int): Processing limit (5-15, default: 10)
- `min_memory_count` (int): Minimum memories per topic to consider (1-5, default: 1)
- `max_topics` (int): Maximum topics to analyze (50-200, default: 100)

**Example**:
```bash
# Preview what would be processed
curl "http://localhost:4203/topics/_dedup_semantic/preview?max_topics=200&semantic_similarity_threshold=0.75"

# Execute topic deduplication
curl -X POST "http://localhost:4203/topics/_dedup_semantic?max_topics=200&max_clusters_to_process=15"
```

**Execution Response**:
```json
{
  "status": "completed",
  "topic_dedup_results": {
    "processed_clusters": 10,
    "results": [
      {
        "cluster_index": 0,
        "cluster_size": 3,
        "semantic_density": 0.908,
        "avg_similarity": 0.908,
        "merge_decision": {
          "primary_topic_id": "uuid-1",
          "primary_topic_name": "Consolidated Topic Name",
          "merge_topic_ids": ["uuid-2", "uuid-3"],
          "reasoning": "LLM explanation"
        },
        "merge_result": {
          "primary_topic_id": "uuid-1",
          "primary_topic_name": "Consolidated Topic Name", 
          "deleted_topics": ["uuid-2", "uuid-3"],
          "moved_memories": 6
        }
      }
    ]
  },
  "stats": {
    "topics_analyzed": 204,
    "semantic_clusters_found": 24,
    "clusters_processed": 10,
    "topics_merged": 12,
    "memories_moved": 17
  }
}
```

### Deduplication Dependencies

**Required Packages**:
- `sentence-transformers`: Semantic similarity analysis
- `scikit-learn`: Clustering algorithms (DBSCAN)
- `numpy`: Numerical operations for embeddings

**LLM Integration**:
- Uses existing prompt templates in `/home/randi/.kirishima/prompts/ledger/`
- Integrates with proxy service for OpenAI API calls
- Supports configurable model selection (default: gpt-4.1)

**Safety Features**:
- Transaction-based operations with rollback on errors
- Comprehensive error logging and reporting
- Dry run modes for cost estimation and planning
- Configurable limits to prevent runaway operations
- Graceful degradation when dependencies unavailable

## Configuration

```json
{
  "db": {
    "ledger": "/path/to/ledger.db"
  },
  "ledger": {
    "turns": 15  // Default message history limit
  },
  "tracing_enabled": false
}
```

## Technical Notes

### Performance Considerations

- SQLite WAL mode enables concurrent read/write operations
- Prepared statements and connection pooling for efficiency
- Indexed queries for common access patterns
- Background task support for expensive operations

### Data Integrity

- Foreign key constraints prevent orphaned data
- Transaction-based operations ensure consistency
- Validation at API and database levels
- Graceful degradation for missing optional data

### Platform Integration

- Platform-agnostic message storage with metadata preservation
- Cross-platform user ID normalization
- Tool call and function call serialization support
- Extensible message schema for future platform additions

## Dependencies

- FastAPI for REST API framework
- SQLite3 for persistent storage
- Pydantic for data validation and serialization
- Shared middleware for tracing and logging
