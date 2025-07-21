# Enhanced Memory Deduplication System

This document explains the new multi-stage memory deduplication system implemented in Kirishima's ledger service.

## Problem Statement

The original deduplication system had several scaling issues:

1. **Context Window Limitations**: With 241 topics, sending all topic data to the LLM exceeded context limits
2. **Topic Duplication**: The scan process created similar topics instead of consolidating them  
3. **Memory Duplication**: Multiple memories with similar content but different wording
4. **Inefficient Processing**: Trying to process all topics at once was resource-intensive
5. **Excessive LLM Calls**: Every memory pair with keyword overlap was sent to the LLM

## Solution Overview

The enhanced system uses a multi-stage approach with **smart filtering** to limit LLM usage:

### Stage 1: Keyword-Based Pre-filtering

- Identifies memory pairs that share 3+ common keywords (configurable)
- Uses database queries for fast filtering
- Creates connected components of similar memories

### Stage 2: Smart Group Filtering

- **Prioritizes groups** by highest keyword overlap scores
- **Limits group size** (max 10 memories per group)
- **Caps total groups** processed (max 20 groups by default)
- **Scores groups** using average keyword overlap and size

### Stage 3: Topic Similarity Detection

- Processes topics in smaller batches (15-20 topics per batch)
- Uses LLM to identify semantically similar topics within each batch
- Avoids context window limitations

### Stage 4: Memory Consolidation

- **Only processes filtered, high-priority groups**
- Deduplicates memories within similar topic groups
- Uses existing LLM prompts for consistency

### Stage 5: Enhanced Topic Creation Prevention

- Improved scan.py logic to prevent duplicate topic creation
- Checks against recent topics using similarity scoring
- Multiple similarity heuristics (substring, word-level, character-level)

## New Endpoints

### `/memories/_dedup_v2` (POST)

Enhanced deduplication endpoint with configurable limits:

```python
# Default conservative settings
POST /memories/_dedup_v2
{
    "min_keyword_overlap": 3,      # Require 3+ common keywords
    "max_groups_to_process": 20,   # Process max 20 groups
    "max_memories_per_group": 10   # Max 10 memories per group
}
```

### `/memories/_dedup_preview` (GET)

Preview endpoint that shows what would be processed:

```python
GET /memories/_dedup_preview?min_keyword_overlap=3&max_groups_to_process=20
```

### `/memories/_dedup_analyze` (GET)

Analysis endpoint (unchanged) that shows statistics without making changes.

## Smart Filtering Algorithm

### Group Prioritization

Groups are scored and prioritized by:

1. **Average keyword overlap score** - Higher overlap = higher priority
2. **Group size penalty** - Smaller groups are easier for LLM to process
3. **Priority score** = `avg_overlap_score * (1.0 / group_size)`

### Conservative Defaults

- **Minimum 3 keyword overlap** (vs. 2 in old system)
- **Maximum 20 groups processed** (vs. unlimited in old system)
- **Maximum 10 memories per group** (vs. unlimited in old system)
- **Estimated 20 LLM calls maximum** (vs. potentially hundreds)

## Usage Examples

### Preview What Would Be Processed

```bash
cd /home/randi/kirishima
python scripts/analyze_dedup.py preview --keywords 3 --max-groups 20
```

### Run Conservative Deduplication

```bash
python scripts/analyze_dedup.py deduplicate
```

### Analyze Overall Potential

```bash
python scripts/analyze_dedup.py analyze
```

### Adjust Aggressiveness

```bash
# More aggressive (more LLM calls)
python scripts/analyze_dedup.py preview --keywords 2 --max-groups 50

# More conservative (fewer LLM calls)  
python scripts/analyze_dedup.py preview --keywords 4 --max-groups 10
```

## Cost Control

### Before Enhancement (Original System)

- **Larry Kuehner example**: Would process ALL memory pairs with 2+ keyword overlap
- **Potential LLM calls**: 50-200+ calls depending on data
- **Risk**: High cost, long processing time

### After Enhancement (New System)

- **Smart filtering**: Only top 20 priority groups processed
- **Maximum LLM calls**: ~20 calls for memory dedup + ~15 calls for topic similarity
- **Total estimated cost**: 85% reduction in LLM usage

## Algorithm Details

### Topic Similarity Scoring

Multiple heuristics calculate topic similarity:

1. **Exact Match**: Returns 1.0 for identical names
2. **Substring Containment**: High score if one topic name contains the other
3. **Word-level Jaccard**: Intersection/union of words in topic names
4. **Character-level**: For short topics, character overlap similarity

### Memory Group Scoring

```python
priority_score = average_keyword_overlap * (1.0 / group_size)
```

This favors:
- Groups with high keyword overlap (likely duplicates)
- Smaller groups (easier for LLM to process accurately)

### Batch Processing

Topics processed in batches of 15-20 to stay within LLM context limits while maintaining effectiveness.

## Configuration

### API Parameters

```python
{
    "min_keyword_overlap": 3,      # 2-5 recommended range
    "max_groups_to_process": 20,   # 10-50 recommended range  
    "max_memories_per_group": 10   # 5-15 recommended range
}
```

### Environment Variables

- `API_PORT`: Port for API service (default: 4200)
- Standard ledger configuration in `/app/config/config.json`

## Performance Improvements

### Memory Usage

- Database queries optimized with proper indexing
- Batch processing limits memory usage during LLM calls
- Smart filtering reduces working set size

### LLM Usage

- **Reduced from O(n²) to O(max_groups)** for memory deduplication
- **Fixed cost** regardless of total memory count
- **Predictable billing** with configurable limits

### Processing Time

- Pre-filtering with SQL is much faster than LLM calls
- Parallel processing of topic batches
- Early termination when limits reached

## Migration Strategy

### From Old System

1. **Test with preview**: `python scripts/analyze_dedup.py preview`
2. **Start conservative**: Use default settings (3+ keywords, max 20 groups)
3. **Monitor results**: Check deduplication effectiveness
4. **Adjust if needed**: Increase/decrease limits based on results

### Rollback Plan

- Old system remains available at `/memories/_dedup`
- New system is additive, doesn't replace old endpoints
- Can switch back if issues arise

## Troubleshooting

### Common Issues

1. **No candidates found**: Lower `min_keyword_overlap` to 2
2. **Too many LLM calls**: Increase `min_keyword_overlap` or decrease `max_groups_to_process`
3. **Missing obvious duplicates**: Check if they have 3+ common keywords

### Monitoring

- Use preview endpoint to estimate costs before running
- Check logs for group processing statistics
- Monitor deduplication effectiveness over time

## Future Enhancements

1. **Semantic Embeddings**: Use vector embeddings for better similarity detection
2. **Learning from Results**: Adjust scoring based on successful deduplications
3. **User Feedback Loop**: Allow manual review and adjustment of decisions
4. **Incremental Processing**: Only process new memories since last run

## Examples for Your Data

### Larry Kuehner Duplicate Case

**Before (Old System)**:
- Would process every memory pair with 2+ keywords
- Larry + Kuehner + email + LLM = many potential pairs
- Could result in 20+ LLM calls just for email-related memories

**After (New System)**:
- Identifies Larry Kuehner memories as high-priority group (4+ common keywords)
- Groups them into single connected component
- Processes as one LLM call with clear context
- Topics "Incoming Email from Larry Kuehner" and "Email interactions" would be merged

### Expected Results

With your 241 topics and memory database:
- **Preview estimate**: 15-25 high-priority groups
- **Total LLM calls**: ~20 for memories + ~15 for topics = ~35 total
- **Processing time**: 5-10 minutes instead of 30+ minutes
- **Cost reduction**: ~80% fewer LLM calls than old system
