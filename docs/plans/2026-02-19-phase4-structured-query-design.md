# Phase 4: Structured Query Responses — Design Document

## Problem

The `notebook_query` MCP tool currently returns minimal data:
```json
{"status": "success", "answer": "text...", "conversation_id": "uuid", "sources_used": []}
```

Three critical gaps:
1. **`sources_used` is always `[]`** — core `query()` never returns it; service defaults to `[]`
2. **Source citations exist in raw response but are discarded** — `_parse_query_response()` only extracts answer text
3. **No metadata for LLM consumers** — no turn_number, is_follow_up, or suggested questions

## Discovery: Raw Response Structure

Analysis of the streaming batchexecute response reveals rich data at `inner[0..5]`:

| Position | Content | Currently |
|----------|---------|-----------|
| `inner[0][0]` | Answer text (markdown) | Extracted |
| `inner[0][2]` | `[conversation_id, session_id, counter]` | Discarded |
| `inner[1]` | Source citations (N items, each with source_id, confidence, passage) | **Discarded** |
| `inner[2]` | Citation-to-answer mappings (char ranges → citation indices) | **Discarded** |
| `inner[3]` | Suggested follow-up questions (3 strings) | **Discarded** |
| `inner[4]` | `is_final` flag (bool) | Partially used |
| `inner[5]` | Questions with relevance scores | **Discarded** |

### Citation structure (`inner[1][n]`):
```
[None, None, 0.98, [[None, 15213, 16213]], [passage_segments], [[["source-uuid"], "version-id"]]]
     ^             ^                        ^                     ^
     confidence    char range in source     passage text          source_id
```

### Citation mapping (`inner[2]`):
```
[[None, 128, 333], [0, 1, 2, 3]]  → answer chars 128-333 cite sources at indices 0,1,2,3 in inner[1]
```

## Design

### New response format:
```json
{
  "status": "success",
  "answer": "Based on the sources...",
  "conversation_id": "uuid",
  "sources_cited": [
    {"source_id": "5beafb81-...", "confidence": 0.98, "passage": "This book focuses on..."}
  ],
  "citation_mappings": [
    {"answer_start": 128, "answer_end": 333, "citation_indices": [0, 1, 2]}
  ],
  "suggested_questions": ["Why did Peter question...?", "What role does Nous play...?"],
  "turn_number": 1,
  "is_follow_up": false
}
```

### Changes by layer:

**Core (`core/conversation.py`)**:
- `_parse_query_response()` → returns dict instead of str
- New `_extract_source_citation()` — extracts source_id, confidence, passage from one citation
- New `_extract_passage_text()` — concatenates text from nested passage structure
- `query()` → passes enriched data through

**Service (`services/chat.py`)**:
- New TypedDicts: `SourceCitation`, `CitationMapping`
- `QueryResult` updated with new optional fields
- `query()` passes new fields from core

**MCP (`mcp/tools/chat.py`)**: No changes needed (already spreads `**result`)

### Backward compatibility:
- All new fields are additive — existing consumers see extra fields but nothing breaks
- `sources_used` replaced by `sources_cited` (more accurate name, richer data)
- `turn_number` and `is_follow_up` already computed in core, just passed through now
