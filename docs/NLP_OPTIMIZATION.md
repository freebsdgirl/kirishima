# NLP Response Optimization

## Overview

The NLP endpoint has been optimized to reduce token usage through two main strategies:
1. **Slim responses** that filter out unnecessary metadata from API responses
2. **Human-readable format** that converts JSON to natural language for maximum token efficiency

## Usage

### Human-Readable Format (Most Token Efficient)
```bash
curl -X POST "http://localhost:4215/nlp?readable=true" \
  -H "Content-Type: application/json" \
  -d '{"query": "search my calendar for events next week"}'
```

Returns natural language format:
```
1. Axon Interview Confirmation!
   Time: Mon Jul 28, 2025 from 11:00AM to 12:00PM
   Location: https://axon.zoom.us/j/96249031868
   Details: We're excited for you to meet the Axon team! This is your scheduled interview...
```

### Slim JSON Response (Default)
```bash
curl -X POST "http://localhost:4215/nlp?slim=true" \
  -H "Content-Type: application/json" \
  -d '{"query": "search my calendar for events next week"}'
```

Returns only essential JSON fields:
- `id`, `subject`, `from`, `to`, `date`
- `body_cleaned`, `is_reply`, `thread_summary`
- `has_thread_context`, `word_count`

### Full Response (Debug Mode)
```bash
curl -X POST "http://localhost:4215/nlp?slim=false" \
  -H "Content-Type: application/json" \
  -d '{"query": "search my calendar for events next week"}'
```

Returns complete data including:
- Raw Gmail API response with all headers
- Complete email payload and MIME parts
- Full statistics object
- All metadata

## Token Savings

### Calendar Events
- **Full Response**: 1,969 bytes
- **Slim JSON**: 1,677 bytes (15% reduction)
- **Readable**: 593 bytes (70% reduction from full)

### Email Searches  
- **Full Response**: ~12,896 bytes
- **Slim JSON**: 4,615 bytes (64% reduction)
- **Readable**: 3,697 bytes (71% reduction from full)

### Single Email
- **Full Response**: ~12,896 bytes
- **Slim JSON**: 564 bytes (95.6% reduction)

## HTML Cleaning

Both slim and readable formats automatically clean HTML content:
- Removes `<https://example.com>` link formatting
- Strips HTML tags from event descriptions
- Cleans up excessive whitespace
- Preserves essential content while removing formatting noise

## Supported Actions

### Gmail Actions
- `get_email_by_id`: Returns essential email fields or readable summary
- `search_emails`: Returns simplified email list with core fields or readable list

### Calendar Actions
- `search_events`: Returns essential event fields or readable event list
- `get_upcoming`: Returns upcoming events in slim or readable format

### Future Extensions
This optimization pattern can be extended to:
- Contact information (essential fields only)
- Task lists and other Google services
- Smart home device responses

## Implementation Notes

- Default behavior is `slim=true` to maximize token efficiency
- Use `readable=true` for maximum token savings when JSON structure not needed
- Use `slim=false` only when debugging or when full metadata is required
- All cleaning and processing logic remains the same, only response format changes
- Thread summarization and context preservation are maintained in all modes
- HTML cleaning applied automatically to prevent formatting noise

## Token Budget Impact

These optimizations are crucial for the Kirishima system because:
- LLM context windows are limited (~8K-32K tokens)
- System includes: conversation history + memory injection + tool outputs
- Email responses were consuming 15-20% of available context
- Readable responses reduce this to <2% of context usage
- Allows more room for conversation history and memory context

## Parameter Combinations

- `readable=true` (ignores slim parameter): Maximum token efficiency, natural language
- `slim=true, readable=false` (default): Essential JSON fields only
- `slim=false, readable=false`: Full debug data with all metadata
