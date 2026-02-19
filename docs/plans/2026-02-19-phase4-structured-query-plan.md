# Phase 4: Structured Query Responses — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich `notebook_query` responses with source citations, citation mappings, suggested questions, and conversation metadata extracted from the raw batchexecute streaming response.

**Architecture:** Modify core response parsing (`_parse_query_response`) to return a dict with all extracted data instead of just the answer string. Service layer passes new fields through. MCP layer needs no changes.

**Tech Stack:** Python 3.11+, pytest, unittest.mock

---

### Task 1: Core — Add citation extraction helpers

**Files:**
- Modify: `src/notebooklm_tools/core/conversation.py:295-353`
- Test: `tests/core/test_query_parsing.py` (create)

**Step 1: Write failing tests for citation extraction**

Create `tests/core/test_query_parsing.py`:

```python
"""Tests for query response parsing with citation extraction."""

import json
import pytest
from unittest.mock import MagicMock, patch

from notebooklm_tools.core.conversation import ConversationMixin


@pytest.fixture
def mixin():
    """Create a ConversationMixin with mocked base class dependencies."""
    with patch.object(ConversationMixin, "__init__", lambda self: None):
        m = ConversationMixin.__new__(ConversationMixin)
        return m


# ---- Realistic mock data based on real API response structure ----

def _make_citation(source_id: str, confidence: float, passage: str) -> list:
    """Build a citation in the real API format."""
    passage_len = len(passage)
    return [
        None,
        None,
        confidence,
        [[None, 0, passage_len]],
        [[[0, passage_len, [[[0, passage_len, [passage]]]]]]],
        [[[source_id], "version-hash-123"]],
    ]


def _make_citation_mapping(start: int, end: int, indices: list[int]) -> list:
    """Build a citation mapping in the real API format."""
    return [[None, start, end], indices]


def _make_final_chunk(
    answer: str,
    citations: list | None = None,
    mappings: list | None = None,
    questions: list[str] | None = None,
) -> str:
    """Build a complete streaming response with one final chunk."""
    inner = [
        [answer, None, ["conv-id", "session-id", 12345], None, []],
        citations or [],
        mappings or [],
        [questions] if questions else None,
        True,  # is_final
    ]
    if questions:
        inner.append([[q, 9] for q in questions])

    inner_json = json.dumps(inner, separators=(",", ":"))
    wrb = [["wrb.fr", None, inner_json, None, None, None, "generic"]]
    chunk_json = json.dumps(wrb, separators=(",", ":"))
    byte_count = len(chunk_json.encode("utf-8"))
    return f")]}'\n{byte_count}\n{chunk_json}\n"


class TestExtractSourceCitation:
    """Tests for _extract_source_citation helper."""

    def test_extracts_source_id_and_confidence(self, mixin):
        citation = _make_citation("src-abc-123", 0.95, "Some passage text here.")
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["source_id"] == "src-abc-123"
        assert result["confidence"] == 0.95

    def test_extracts_passage_text(self, mixin):
        citation = _make_citation("src-1", 0.8, "The document discusses AI safety measures.")
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert "AI safety" in result["passage"]

    def test_returns_none_for_missing_source_id(self, mixin):
        citation = [None, None, 0.5, [], [], []]
        result = mixin._extract_source_citation(citation)

        assert result is None

    def test_returns_none_for_malformed_citation(self, mixin):
        result = mixin._extract_source_citation([])
        assert result is None

    def test_handles_zero_confidence(self, mixin):
        citation = _make_citation("src-1", 0.0, "Low confidence passage.")
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["confidence"] == 0.0

    def test_handles_multi_segment_passage(self, mixin):
        """Test passage with multiple text segments."""
        citation = [
            None, None, 0.9,
            [[None, 100, 300]],
            [
                [100, 200, [[[100, 200, ["First segment of text."]]]]],
                [200, 300, [[[200, 300, ["Second segment of text."]]]]],
            ],
            [[["src-multi"], "v1"]],
        ]
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["source_id"] == "src-multi"
        assert "First segment" in result["passage"]
        assert "Second segment" in result["passage"]


class TestExtractPassageText:
    """Tests for _extract_passage_text helper."""

    def test_single_segment(self, mixin):
        data = [[[0, 50, [[[0, 50, ["Hello world passage text here."    ]]]]]]]
        result = mixin._extract_passage_text(data)
        assert "Hello world" in result

    def test_empty_data(self, mixin):
        assert mixin._extract_passage_text([]) == ""
        assert mixin._extract_passage_text(None) == ""

    def test_multiple_segments(self, mixin):
        data = [
            [0, 20, [[[0, 20, ["First part of text."]]]]],
            [20, 50, [[[20, 50, ["Second part of the passage."]]]]],
        ]
        result = mixin._extract_passage_text(data)
        assert "First part" in result
        assert "Second part" in result


class TestParseQueryResponseFull:
    """Tests for the enriched _parse_query_response returning a dict."""

    def test_extracts_answer_text(self, mixin):
        response = _make_final_chunk("The answer is about quantum physics and relativity.")
        result = mixin._parse_query_response(response)

        assert result["answer"] == "The answer is about quantum physics and relativity."

    def test_extracts_citations(self, mixin):
        citations = [
            _make_citation("src-aaa", 0.95, "Quantum mechanics is fundamental."),
            _make_citation("src-bbb", 0.80, "Relativity changed physics forever."),
        ]
        response = _make_final_chunk(
            "The answer discusses quantum mechanics and relativity.",
            citations=citations,
        )
        result = mixin._parse_query_response(response)

        assert len(result["sources_cited"]) == 2
        assert result["sources_cited"][0]["source_id"] == "src-aaa"
        assert result["sources_cited"][0]["confidence"] == 0.95
        assert result["sources_cited"][1]["source_id"] == "src-bbb"

    def test_extracts_citation_mappings(self, mixin):
        mappings = [
            _make_citation_mapping(10, 50, [0, 1]),
            _make_citation_mapping(60, 100, [1, 2]),
        ]
        response = _make_final_chunk(
            "The answer with citations mapped to specific ranges.",
            mappings=mappings,
        )
        result = mixin._parse_query_response(response)

        assert len(result["citation_mappings"]) == 2
        assert result["citation_mappings"][0] == {
            "answer_start": 10, "answer_end": 50, "citation_indices": [0, 1]
        }

    def test_extracts_suggested_questions(self, mixin):
        questions = ["What about X?", "How does Y work?", "Why is Z important?"]
        response = _make_final_chunk(
            "The answer to the question about physics.",
            questions=questions,
        )
        result = mixin._parse_query_response(response)

        assert result["suggested_questions"] == questions

    def test_empty_response_returns_defaults(self, mixin):
        result = mixin._parse_query_response("")

        assert result["answer"] == ""
        assert result["sources_cited"] == []
        assert result["citation_mappings"] == []
        assert result["suggested_questions"] == []

    def test_thinking_only_response_falls_back(self, mixin):
        """When no final answer chunk exists, fall back to longest thinking chunk."""
        # Build a thinking-only response (is_final=False, no citations)
        inner = [
            ["Thinking about the question step by step...", None, ["c", "s", 1], None, []],
            [],
            [],
            None,
            False,
        ]
        inner_json = json.dumps(inner, separators=(",", ":"))
        wrb = [["wrb.fr", None, inner_json, None, None, None, "generic"]]
        chunk_json = json.dumps(wrb, separators=(",", ":"))
        response = f")]}'\n{len(chunk_json)}\n{chunk_json}\n"

        result = mixin._parse_query_response(response)

        assert "Thinking about" in result["answer"]
        assert result["sources_cited"] == []

    def test_multiple_chunks_uses_final(self, mixin):
        """When response has thinking + final chunks, use final for citations."""
        # Thinking chunk
        inner1 = [["Analyzing sources...", None, ["c", "s", 1], None, []], [], [], None, False]
        inner1_json = json.dumps(inner1, separators=(",", ":"))
        wrb1 = [["wrb.fr", None, inner1_json, None, None, None, "generic"]]
        chunk1 = json.dumps(wrb1, separators=(",", ":"))

        # Final chunk with citations
        citations = [_make_citation("src-final", 0.99, "Key finding from the source.")]
        inner2 = [
            ["The comprehensive answer with all details explained clearly.", None, ["c", "s", 1], None, []],
            citations,
            [_make_citation_mapping(0, 50, [0])],
            [["Follow-up question?"]],
            True,
        ]
        inner2_json = json.dumps(inner2, separators=(",", ":"))
        wrb2 = [["wrb.fr", None, inner2_json, None, None, None, "generic"]]
        chunk2 = json.dumps(wrb2, separators=(",", ":"))

        response = f")]}'\n{len(chunk1)}\n{chunk1}\n{len(chunk2)}\n{chunk2}\n"

        result = mixin._parse_query_response(response)

        assert "comprehensive answer" in result["answer"]
        assert len(result["sources_cited"]) == 1
        assert result["sources_cited"][0]["source_id"] == "src-final"
        assert result["suggested_questions"] == ["Follow-up question?"]
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_query_parsing.py -v`
Expected: FAIL — `_extract_source_citation` and enriched `_parse_query_response` don't exist yet

**Step 3: Implement citation extraction helpers**

Add to `src/notebooklm_tools/core/conversation.py` after line 353 (after `_extract_answer_from_chunk`):

```python
    def _extract_source_citation(self, citation: list) -> dict | None:
        """Extract source citation data from a single citation array.

        Citation structure (from batchexecute streaming response):
        [None, None, confidence, [[None, start, end]], [passage_segments], [[source_info]]]

        Args:
            citation: A single citation array from inner[1]

        Returns:
            Dict with source_id, confidence, passage or None if extraction fails
        """
        try:
            if not isinstance(citation, list) or len(citation) < 6:
                return None

            # Confidence score at position 2
            confidence = citation[2] if isinstance(citation[2], (int, float)) else 0.0

            # Source ID at position 5: [[["source-uuid"], "version-id"]]
            source_id = None
            if isinstance(citation[5], list) and len(citation[5]) > 0:
                source_info = citation[5][0]
                if isinstance(source_info, list) and len(source_info) > 0:
                    sid_wrapper = source_info[0]
                    if isinstance(sid_wrapper, list) and len(sid_wrapper) > 0:
                        source_id = sid_wrapper[0]

            if not source_id or not isinstance(source_id, str):
                return None

            # Extract passage text from position 4
            passage = self._extract_passage_text(citation[4]) if len(citation) > 4 else ""

            return {
                "source_id": source_id,
                "confidence": round(confidence, 4),
                "passage": passage,
            }
        except (IndexError, TypeError):
            return None

    def _extract_passage_text(self, passage_data) -> str:
        """Extract concatenated text from deeply nested passage structure.

        The passage data contains text segments in a deeply nested format:
        [[[start, end, [[[start, end, ["text content"]]]]]], ...]

        Strategy: Recursively collect all strings > 20 chars.

        Args:
            passage_data: Nested list structure containing passage text

        Returns:
            Concatenated passage text, or empty string
        """
        if not isinstance(passage_data, list):
            return ""

        texts: list[str] = []
        self._collect_passage_texts(passage_data, texts)
        return " ".join(texts) if texts else ""

    def _collect_passage_texts(self, data, texts: list[str]) -> None:
        """Recursively collect passage text strings from nested structure."""
        if isinstance(data, str) and len(data) > 20:
            texts.append(data)
        elif isinstance(data, list):
            for item in data:
                self._collect_passage_texts(item, texts)
```

**Step 4: Modify `_parse_query_response` to return enriched dict**

Replace the current `_parse_query_response` method (lines 232-293) with:

```python
    def _parse_query_response(self, response_text: str) -> dict:
        """Parse the streaming query response and extract answer with citations.

        The query endpoint returns a streaming response with multiple chunks.
        Each chunk contains progressively more complete data. The final chunk
        (inner[4] == True) contains the complete answer plus source citations.

        Response structure per chunk:
        inner[0][0] = answer text (grows with each chunk)
        inner[1]    = source citations (list of citation objects)
        inner[2]    = citation-to-answer mappings (char ranges)
        inner[3]    = suggested follow-up questions
        inner[4]    = is_final flag (True only on last chunk)

        Args:
            response_text: Raw response text from the query endpoint

        Returns:
            Dict with keys: answer, sources_cited, citation_mappings, suggested_questions
        """
        default_result = {
            "answer": "",
            "sources_cited": [],
            "citation_mappings": [],
            "suggested_questions": [],
        }

        if not response_text:
            return default_result

        # Remove anti-XSSI prefix
        if response_text.startswith(")]}'"):
            response_text = response_text[4:]

        lines = response_text.strip().split("\n")

        # Track best answer and final chunk data
        best_answer = ""
        best_thinking = ""
        final_inner = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Try to parse as byte count (indicates next line is JSON)
            try:
                int(line)
                i += 1
                if i < len(lines):
                    inner = self._parse_inner_from_chunk(lines[i])
                    if inner:
                        answer, is_final = self._extract_text_from_inner(inner)
                        if answer:
                            if is_final:
                                best_answer = answer
                                final_inner = inner
                            elif len(answer) > len(best_answer):
                                best_answer = answer
                            elif len(answer) > len(best_thinking):
                                best_thinking = answer
                i += 1
            except ValueError:
                # Not a byte count, try to parse as JSON directly
                inner = self._parse_inner_from_chunk(line)
                if inner:
                    answer, is_final = self._extract_text_from_inner(inner)
                    if answer:
                        if is_final:
                            best_answer = answer
                            final_inner = inner
                        elif len(answer) > len(best_answer):
                            best_answer = answer
                        elif len(answer) > len(best_thinking):
                            best_thinking = answer
                i += 1

        result = dict(default_result)
        result["answer"] = best_answer if best_answer else best_thinking

        # Extract citations from the final chunk
        if final_inner:
            result["sources_cited"] = self._extract_citations(final_inner)
            result["citation_mappings"] = self._extract_citation_mappings(final_inner)
            result["suggested_questions"] = self._extract_suggested_questions(final_inner)

        return result

    def _parse_inner_from_chunk(self, json_str: str) -> list | None:
        """Parse a JSON chunk and extract the inner data array.

        Chunk format: [["wrb.fr", null, "<inner_json>", ...]]
        Returns the parsed inner array, or None.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, list):
            return None

        for item in data:
            if not isinstance(item, list) or len(item) < 3:
                continue
            if item[0] != "wrb.fr":
                continue

            inner_json_str = item[2]
            if not isinstance(inner_json_str, str):
                continue

            try:
                return json.loads(inner_json_str)
            except json.JSONDecodeError:
                continue

        return None

    def _extract_text_from_inner(self, inner: list) -> tuple[str, bool]:
        """Extract answer text and is_final flag from inner data.

        Args:
            inner: Parsed inner data array

        Returns:
            Tuple of (answer_text, is_final)
        """
        if not isinstance(inner, list) or len(inner) == 0:
            return "", False

        is_final = len(inner) > 4 and inner[4] is True

        first = inner[0]
        if isinstance(first, list) and len(first) > 0:
            text = first[0]
            if isinstance(text, str) and len(text) > 20:
                return text, is_final
        elif isinstance(first, str) and len(first) > 20:
            return first, is_final

        return "", is_final

    def _extract_citations(self, inner: list) -> list[dict]:
        """Extract source citations from inner[1]."""
        if len(inner) < 2 or not isinstance(inner[1], list):
            return []

        citations = []
        for citation_data in inner[1]:
            citation = self._extract_source_citation(citation_data)
            if citation:
                citations.append(citation)

        return citations

    def _extract_citation_mappings(self, inner: list) -> list[dict]:
        """Extract citation-to-answer mappings from inner[2].

        Format: [[None, start, end], [citation_indices]]
        """
        if len(inner) < 3 or not isinstance(inner[2], list):
            return []

        mappings = []
        for mapping_data in inner[2]:
            if not isinstance(mapping_data, list) or len(mapping_data) < 2:
                continue

            range_info = mapping_data[0]
            indices = mapping_data[1]

            if (isinstance(range_info, list) and len(range_info) >= 3
                    and isinstance(indices, list)):
                mappings.append({
                    "answer_start": range_info[1] if isinstance(range_info[1], int) else 0,
                    "answer_end": range_info[2] if isinstance(range_info[2], int) else 0,
                    "citation_indices": [i for i in indices if isinstance(i, int)],
                })

        return mappings

    def _extract_suggested_questions(self, inner: list) -> list[str]:
        """Extract suggested follow-up questions from inner[3]."""
        if len(inner) < 4 or not isinstance(inner[3], list):
            return []

        # inner[3] = [["question1", "question2", ...]]
        if len(inner[3]) > 0 and isinstance(inner[3][0], list):
            return [q for q in inner[3][0] if isinstance(q, str)]

        return []
```

**Step 5: Remove old `_extract_answer_from_chunk` method**

Delete lines 295-353 (the old `_extract_answer_from_chunk` method). It is replaced by the new `_parse_inner_from_chunk` + `_extract_text_from_inner` combination.

**Step 6: Update `query()` method to use enriched response**

Replace lines 182-199 in the `query()` method:

```python
        # Parse streaming response (returns enriched dict)
        parsed = self._parse_query_response(response.text)
        answer_text = parsed["answer"]

        # Cache this turn for future follow-ups (only if we got an answer)
        if answer_text:
            self._cache_conversation_turn(conversation_id, query_text, answer_text)

        # Calculate turn number
        turns = self._conversation_cache.get(conversation_id, [])
        turn_number = len(turns)

        return {
            "answer": answer_text,
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "is_follow_up": not is_new_conversation,
            "sources_cited": parsed["sources_cited"],
            "citation_mappings": parsed["citation_mappings"],
            "suggested_questions": parsed["suggested_questions"],
        }
```

**Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_query_parsing.py -v`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add tests/core/test_query_parsing.py src/notebooklm_tools/core/conversation.py
git commit -m "feat: extract source citations from query response

Parse the full batchexecute streaming response to extract:
- Source citations with source_id, confidence, passage text
- Citation-to-answer mappings (which chars in answer cite which sources)
- Suggested follow-up questions
- is_final flag for identifying complete response chunks"
```

---

### Task 2: Service — Update QueryResult TypedDict and query function

**Files:**
- Modify: `src/notebooklm_tools/services/chat.py:1-80`
- Test: `tests/services/test_chat.py`

**Step 1: Write failing tests for enriched QueryResult**

Add to `tests/services/test_chat.py` inside `class TestQuery`:

```python
    def test_passes_through_sources_cited(self, mock_client):
        mock_client.query.return_value = {
            "answer": "The answer.",
            "conversation_id": "conv-1",
            "sources_cited": [
                {"source_id": "src-1", "confidence": 0.95, "passage": "Key finding."}
            ],
            "citation_mappings": [
                {"answer_start": 0, "answer_end": 11, "citation_indices": [0]}
            ],
            "suggested_questions": ["What about X?"],
            "turn_number": 1,
            "is_follow_up": False,
        }

        result = query(mock_client, "nb-123", "Question?")

        assert len(result["sources_cited"]) == 1
        assert result["sources_cited"][0]["source_id"] == "src-1"
        assert result["sources_cited"][0]["confidence"] == 0.95

    def test_passes_through_citation_mappings(self, mock_client):
        mock_client.query.return_value = {
            "answer": "The answer with citations.",
            "conversation_id": "conv-1",
            "citation_mappings": [
                {"answer_start": 0, "answer_end": 25, "citation_indices": [0, 1]}
            ],
        }

        result = query(mock_client, "nb-123", "Question?")

        assert len(result["citation_mappings"]) == 1
        assert result["citation_mappings"][0]["answer_start"] == 0

    def test_passes_through_suggested_questions(self, mock_client):
        mock_client.query.return_value = {
            "answer": "The answer.",
            "conversation_id": "conv-1",
            "suggested_questions": ["Follow-up 1?", "Follow-up 2?"],
        }

        result = query(mock_client, "nb-123", "Question?")

        assert result["suggested_questions"] == ["Follow-up 1?", "Follow-up 2?"]

    def test_passes_through_turn_metadata(self, mock_client):
        mock_client.query.return_value = {
            "answer": "Follow-up answer.",
            "conversation_id": "conv-1",
            "turn_number": 3,
            "is_follow_up": True,
        }

        result = query(mock_client, "nb-123", "More?")

        assert result["turn_number"] == 3
        assert result["is_follow_up"] is True

    def test_defaults_for_missing_fields(self, mock_client):
        """Old-format core response (pre-Phase 4) still works."""
        mock_client.query.return_value = {
            "answer": "Legacy answer.",
            "conversation_id": "conv-old",
        }

        result = query(mock_client, "nb-123", "Question?")

        assert result["answer"] == "Legacy answer."
        assert result["sources_cited"] == []
        assert result["citation_mappings"] == []
        assert result["suggested_questions"] == []
        assert result["turn_number"] == 0
        assert result["is_follow_up"] is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/services/test_chat.py::TestQuery -v`
Expected: FAIL — `sources_cited`, `citation_mappings`, etc. not in QueryResult

**Step 3: Update service layer**

Replace `QueryResult` and `query()` in `src/notebooklm_tools/services/chat.py`:

```python
class SourceCitation(TypedDict):
    """A source citation from a query response."""
    source_id: str
    confidence: float
    passage: str


class CitationMapping(TypedDict):
    """Maps a range in the answer text to source citation indices."""
    answer_start: int
    answer_end: int
    citation_indices: list[int]


class QueryResult(TypedDict):
    """Result of a notebook query."""
    answer: str
    conversation_id: Optional[str]
    sources_cited: list[SourceCitation]
    citation_mappings: list[CitationMapping]
    suggested_questions: list[str]
    turn_number: int
    is_follow_up: bool
```

Update the `query()` function return block (lines 70-75):

```python
    if result:
        return {
            "answer": result.get("answer", ""),
            "conversation_id": result.get("conversation_id"),
            "sources_cited": result.get("sources_cited", []),
            "citation_mappings": result.get("citation_mappings", []),
            "suggested_questions": result.get("suggested_questions", []),
            "turn_number": result.get("turn_number", 0),
            "is_follow_up": result.get("is_follow_up", False),
        }
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/services/test_chat.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add src/notebooklm_tools/services/chat.py tests/services/test_chat.py
git commit -m "feat: enrich QueryResult with citations, mappings, suggestions

Add SourceCitation and CitationMapping TypedDicts. QueryResult now
includes sources_cited, citation_mappings, suggested_questions,
turn_number, and is_follow_up. Backward-compatible defaults for all."
```

---

### Task 3: Update MCP tests for new response fields

**Files:**
- Modify: `tests/mcp/test_chat.py`

**Step 1: Update mock data in existing MCP tests**

In `tests/mcp/test_chat.py`, update the `test_success` mock to include new fields:

```python
    def test_success(self, mock_client):
        """Test successful query returns status success with enriched result data."""
        mock_result = {
            "answer": "The document discusses AI safety.",
            "conversation_id": "conv-123",
            "sources_cited": [
                {"source_id": "src-1", "confidence": 0.95, "passage": "AI safety is critical."}
            ],
            "citation_mappings": [
                {"answer_start": 0, "answer_end": 33, "citation_indices": [0]}
            ],
            "suggested_questions": ["What about alignment?"],
            "turn_number": 1,
            "is_follow_up": False,
        }
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="What is this about?",
            )

        assert result["status"] == "success"
        assert result["answer"] == "The document discusses AI safety."
        assert result["conversation_id"] == "conv-123"
        assert len(result["sources_cited"]) == 1
        assert result["sources_cited"][0]["source_id"] == "src-1"
        assert result["citation_mappings"][0]["answer_start"] == 0
        assert result["suggested_questions"] == ["What about alignment?"]
        assert result["turn_number"] == 1
        assert result["is_follow_up"] is False
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/mcp/test_chat.py -v`
Expected: ALL PASS (the MCP layer just spreads `**result`, so new fields flow through)

**Step 3: Commit**

```bash
git add tests/mcp/test_chat.py
git commit -m "test: update MCP chat tests for enriched query response"
```

---

### Task 4: Run full test suite and verify no regressions

**Step 1: Run all tests**

Run: `uv run pytest -x --tb=short -q`
Expected: All tests pass (should be ~460+ passed)

**Step 2: Run linter**

Run: `uv run ruff check src/notebooklm_tools/core/conversation.py src/notebooklm_tools/services/chat.py`
Expected: No errors

**Step 3: Fix any issues found**

Address any lint errors or test failures.

**Step 4: Final commit with all fixes**

```bash
git add -A
git commit -m "fix: address lint and test issues from Phase 4"
```

(Skip this step if no fixes needed.)

---

### Task 5: Update API documentation

**Files:**
- Modify: `docs/API_REFERENCE.md` (Query Response section, ~lines 419-425)

**Step 1: Update the Query Response section**

Add after line 425 in `docs/API_REFERENCE.md`:

```markdown
### Query Response Structure (Parsed)

The streaming response contains multiple chunks. The final chunk (`inner[4] == True`) contains:

| Field | Position | Content |
|-------|----------|---------|
| Answer text | `inner[0][0]` | Markdown-formatted answer |
| Conversation IDs | `inner[0][2]` | `[conversation_id, session_id, counter]` |
| Source citations | `inner[1]` | List of citation objects (see below) |
| Citation mappings | `inner[2]` | Answer char ranges → citation indices |
| Suggested questions | `inner[3]` | `[["question1", "question2", ...]]` |
| Is final | `inner[4]` | `True` on last chunk only |

#### Citation Object Structure
```python
citation = [
    None,                                    # [0]
    None,                                    # [1]
    0.98,                                    # [2] confidence score (float)
    [[None, 15213, 16213]],                  # [3] char positions in source
    [passage_segments],                      # [4] passage text (nested)
    [[["source-uuid"], "version-hash"]],     # [5] source identification
]
```

#### Citation Mapping Structure
```python
# Answer chars 128-333 cite sources at citation indices 0, 1, 2
[[None, 128, 333], [0, 1, 2]]
```
```

**Step 2: Commit**

```bash
git add docs/API_REFERENCE.md docs/plans/2026-02-19-phase4-structured-query-design.md
git commit -m "docs: document query response citation structure"
```

---

### Task 6: Final integration commit

**Step 1: Run full test suite one more time**

Run: `uv run pytest -x --tb=short -q`
Expected: All pass

**Step 2: Push**

```bash
git push origin main
```
