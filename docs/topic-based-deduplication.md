# Topic-Based Memory Deduplication System

## Overview

The topic-based memory deduplication system provides a **predictable, cost-controlled** approach to cleaning up memory duplicates by using topic similarity and keyword overlap analysis. This system is designed to be more reliable and transparent than pure semantic clustering.

## Architecture

### 1. Current System Components

After implementing the topic-based system, we now have:

**Topic Assignment:**
- **Original scan** (`scan.py`) - assigns topics to messages (time-based, reliable)

**Memory Deduplication:**
- **Topic-based dedup** (`dedup_topic_based.py`) - **NEW! Predictable keyword-based deduplication**
- **Semantic dedup** (`dedup_semantic.py`) - semantic clustering (complex, documented separately)

**Topic Management:**
- **Topic semantic dedup** (`topic/dedup_semantic.py`) - merges similar topics

### 2. Topic-Based Deduplication Process

```
1. Find Similar Topics
   ├── Use semantic similarity on topic names
   ├── Group topics with similarity > threshold
   └── Create topic consolidation plan

2. Consolidate Topics
   ├── Send topic groups to LLM for merge decisions
   ├── Merge approved topic groups
   └── Update memory-topic associations

3. Group Memories by Keyword Overlap
   ├── Within consolidated topics
   ├── Start with highest keyword overlap (10→2)
   ├── Create memory groups based on shared keywords
   └── Estimate token costs

4. Deduplicate Memory Groups
   ├── Send keyword-overlapping groups to LLM
   ├── Apply memory updates/deletions
   └── Track costs and results
```

## API Endpoints

### 1. Topic-Based Memory Deduplication

**POST** `/memories/_dedup_topic_based`

**Parameters:**
- `topic_similarity_threshold: float = 0.8` - Semantic similarity for topic grouping (0.7-0.9)
- `min_keyword_overlap: int = 2` - Minimum shared keywords for memory grouping (1-5)
- `max_keyword_overlap: int = 10` - Maximum overlap to consider (5-15)
- `max_topic_groups: int = 20` - Maximum topic groups to consolidate (10-50)
- `max_memory_groups: int = 50` - Maximum memory groups to deduplicate (20-100)
- `max_total_tokens: int = 100000` - Maximum total tokens to process (50k-200k)
- `dry_run: bool = False` - Preview without making changes

**Example:**
```bash
curl -X POST "http://localhost:4203/memories/_dedup_topic_based" \
  -d "topic_similarity_threshold=0.8&min_keyword_overlap=3&dry_run=true"
```

### 2. Topic Consolidation Analysis

**POST** `/topics/_consolidate_all`

**Parameters:**
- `dry_run: bool = True` - Preview without making changes
- `max_topics_per_request: int = 20` - Topics per LLM request (10-30)

**Example:**
```bash
curl -X POST "http://localhost:4203/topics/_consolidate_all" \
  -d "dry_run=true&max_topics_per_request=15"
```

## CLI Usage

### 1. Preview Topic-Based Deduplication (Recommended First Step)

```bash
python scripts/analyze_dedup.py preview-topic-based --similarity 0.8 --keywords 3
```

**Output:**
```
📊 TOPIC-BASED DEDUPLICATION PLAN
==================================================
Total topics: 45
Topic groups to consolidate: 8
Memory groups to deduplicate: 12
Estimated LLM requests: 20
Estimated total tokens: 45,230

🏷️  TOPIC CONSOLIDATIONS:
  1. AI Development + [Machine Learning, Deep Learning]
      (23 memories, similarity: 0.85)
  2. Personal Projects + [Side Projects, Hobby Code]
      (17 memories, similarity: 0.82)

🧠 MEMORY GROUPS:
  1. 5 memories from: AI Development, Machine Learning
      (keyword overlap: 4, tokens: 1,250)
  2. 3 memories from: Personal Projects, Side Projects
      (keyword overlap: 3, tokens: 890)

💰 ESTIMATED COST:
   Total LLM requests: 20
   Total tokens: 45,230
```

### 2. Execute Topic-Based Deduplication

```bash
python scripts/analyze_dedup.py dedup-topic-based --similarity 0.8 --keywords 3
```

### 3. Analyze All Topics for Consolidation

```bash
python scripts/analyze_dedup.py consolidate-topics
```

**Output:**
```
📊 TOPIC CONSOLIDATION ANALYSIS
============================================
Total topics: 45
Estimated LLM requests: 3
Estimated tokens: 2,150
Topics per request: 20

🏷️  TOPIC PREVIEW (Top 20 by memory count):
  1. AI and Machine Learning                        (23 memories)
  2. Personal Development                           (18 memories)
  3. Work Projects                                  (15 memories)

💰 ESTIMATED COST:
   LLM requests: 3
   Tokens: 2,150
```

## Configuration Guidelines

### Topic Similarity Threshold
- **0.7-0.75**: More aggressive grouping, may merge unrelated topics
- **0.8-0.85**: **Recommended** - good balance
- **0.9+**: Very conservative, only obvious matches

### Keyword Overlap
- **min_keyword_overlap: 2-3**: **Recommended starting point**
- **max_keyword_overlap: 8-12**: Covers most meaningful overlaps

### Cost Controls
- **max_topic_groups: 10-20**: Start small, increase if needed
- **max_memory_groups: 20-50**: Controls LLM usage directly
- **max_total_tokens: 50k-100k**: Prevents runaway costs

## Workflow Recommendations

### 1. Initial Analysis (Free)
```bash
# Get overview of data
python scripts/analyze_dedup.py stats

# Preview topic-based deduplication
python scripts/analyze_dedup.py preview-topic-based --similarity 0.8 --keywords 3

# Analyze topic consolidation opportunities
python scripts/analyze_dedup.py consolidate-topics
```

### 2. Conservative First Run
```bash
# Start with high overlap to catch obvious duplicates
python scripts/analyze_dedup.py dedup-topic-based --similarity 0.8 --keywords 4
```

### 3. Incremental Cleanup
```bash
# Lower overlap threshold gradually
python scripts/analyze_dedup.py preview-topic-based --similarity 0.8 --keywords 3
python scripts/analyze_dedup.py dedup-topic-based --similarity 0.8 --keywords 3

python scripts/analyze_dedup.py preview-topic-based --similarity 0.8 --keywords 2
python scripts/analyze_dedup.py dedup-topic-based --similarity 0.8 --keywords 2
```

## Cost Estimation

### Typical Costs (Example Dataset)
- **50 topics, 500 memories**: ~15-25 LLM requests, ~30k-60k tokens
- **100 topics, 1000 memories**: ~25-40 LLM requests, ~60k-120k tokens

### Cost per Stage
- **Topic consolidation**: 1 token per topic name (~50-200 tokens per request)
- **Memory deduplication**: 10-50 tokens per memory (~500-2000 tokens per request)

## Comparison with Other Methods

| Method | Predictability | Cost Control | Reliability | Use Case |
|--------|---------------|--------------|-------------|----------|
| **Topic-based** | ✅ Excellent | ✅ Excellent | ✅ High | **Primary deduplication** |
| Semantic clustering | ❌ Poor | ❌ Poor | ⚠️ Medium | Complex cases only |
| Original keyword | ✅ Good | ✅ Good | ⚠️ Medium | Simple overlaps |

## Troubleshooting

### "No topic groups found"
- Lower `topic_similarity_threshold` (try 0.7)
- Check if you have enough topics with memories

### "No memory groups found"
- Lower `min_keyword_overlap` (try 2 or 1)
- Check if memories within topics share keywords

### "Too many LLM requests"
- Reduce `max_topic_groups` and `max_memory_groups`
- Increase `min_keyword_overlap`
- Lower `max_total_tokens`

### "JSON parse errors"
- Usually temporary LLM issues, retry the operation
- Check logs for specific error details

## Future Enhancements

1. **Topic Merging Implementation**: Complete the topic consolidation workflow
2. **Memory Migration**: Move memories between consolidated topics
3. **Category-based Grouping**: Additional grouping by memory category
4. **Batch Processing**: Process large datasets in smaller chunks
5. **Cost Analytics**: Detailed cost tracking and optimization suggestions

## Related Documentation

- **Semantic Deduplication**: See `dedup_semantic.py` documentation
- **Original Scan**: See `scan.py` for topic assignment logic
- **Topic Management**: See `topic/` directory for topic operations
- **CLI Tools**: See `scripts/analyze_dedup.py` for all deduplication commands
