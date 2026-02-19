"""Tests for query response parsing with citation extraction."""

import json
from unittest.mock import patch

import pytest

from notebooklm_tools.core.conversation import ConversationMixin


@pytest.fixture
def mixin():
    """Create a ConversationMixin with mocked base class dependencies."""
    with patch.object(ConversationMixin, "__init__", lambda self: None):
        m = ConversationMixin.__new__(ConversationMixin)
        return m


def _make_citation(source_id: str, confidence: float, passage: str) -> list:
    """Build a citation in the real API format.

    Args:
        source_id: UUID of the source document.
        confidence: Confidence score (0.0-1.0).
        passage: The passage text cited.

    Returns:
        A list matching the real batchexecute citation structure.
    """
    passage_len = len(passage)
    return [
        None, None, confidence,
        [[None, 0, passage_len]],
        [[[0, passage_len, [[[0, passage_len, [passage]]]]]]],
        [[[source_id], "version-hash-123"]],
    ]


def _make_citation_mapping(start: int, end: int, indices: list[int]) -> list:
    """Build a citation mapping in the real API format.

    Args:
        start: Start character offset in the answer text.
        end: End character offset in the answer text.
        indices: List of citation indices this range maps to.

    Returns:
        A list matching the real batchexecute citation mapping structure.
    """
    return [[None, start, end], indices]


def _make_final_chunk(answer, citations=None, mappings=None, questions=None):
    """Build a complete batchexecute streaming chunk with answer and metadata.

    Args:
        answer: The answer text string.
        citations: Optional list of citation structures.
        mappings: Optional list of citation mapping structures.
        questions: Optional list of suggested question strings.

    Returns:
        A string in the batchexecute streaming response format.
    """
    inner = [
        [answer, None, ["conv-id", "session-id", 12345], None, []],
        citations or [],
        mappings or [],
        [questions] if questions else None,
        True,
    ]
    if questions:
        inner.append([[q, 9] for q in questions])
    inner_json = json.dumps(inner, separators=(",", ":"))
    wrb = [["wrb.fr", None, inner_json, None, None, None, "generic"]]
    chunk_json = json.dumps(wrb, separators=(",", ":"))
    byte_count = len(chunk_json.encode("utf-8"))
    prefix = ")]}'"
    return f"{prefix}\n{byte_count}\n{chunk_json}\n"


# =========================================================================
# TestExtractSourceCitation
# =========================================================================


class TestExtractSourceCitation:
    """Tests for _extract_source_citation method."""

    def test_extracts_source_id_and_confidence(self, mixin):
        """Test that source_id and confidence are correctly extracted."""
        citation = _make_citation("src-uuid-abc", 0.85, "Some passage text here for testing.")
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["source_id"] == "src-uuid-abc"
        assert result["confidence"] == 0.85

    def test_extracts_passage_text(self, mixin):
        """Test that passage text is correctly extracted from citation."""
        passage = "This is a long passage with enough characters to be extracted properly."
        citation = _make_citation("src-uuid-xyz", 0.92, passage)
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["passage"] == passage

    def test_returns_none_for_missing_source_id(self, mixin):
        """Test that None is returned when source_id is missing."""
        # Citation with empty source list
        citation = [
            None, None, 0.5,
            [[None, 0, 10]],
            [[[0, 10, [[[0, 10, ["some text."]]]]]]],
            [[[], "version-hash"]],
        ]
        result = mixin._extract_source_citation(citation)

        assert result is None

    def test_returns_none_for_malformed_citation(self, mixin):
        """Test that None is returned for a completely malformed citation."""
        result = mixin._extract_source_citation([])

        assert result is None

    def test_handles_zero_confidence(self, mixin):
        """Test that zero confidence is correctly handled (not treated as falsy)."""
        citation = _make_citation("src-uuid-zero", 0.0, "A passage with zero confidence score here.")
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["confidence"] == 0.0
        assert result["source_id"] == "src-uuid-zero"

    def test_handles_multi_segment_passage(self, mixin):
        """Test extraction when passage has multiple text segments."""
        # Build a citation with multiple passage segments manually
        # Reason: each segment must be >20 chars to pass the _collect_passage_texts filter
        seg1 = "First segment of the passage text."
        seg2 = "Second segment of the passage text."
        total_len = len(seg1) + len(seg2)
        passage_data = [
            [[0, total_len, [
                [[0, len(seg1), [seg1]], [len(seg1), total_len, [seg2]]]
            ]]],
        ]
        citation = [
            None, None, 0.75,
            [[None, 0, total_len]],
            passage_data,
            [[["multi-src-id"], "version-hash-456"]],
        ]
        result = mixin._extract_source_citation(citation)

        assert result is not None
        assert result["source_id"] == "multi-src-id"
        # Passage should contain concatenated text from both segments
        assert seg1 in result["passage"]
        assert seg2 in result["passage"]


# =========================================================================
# TestExtractPassageText
# =========================================================================


class TestExtractPassageText:
    """Tests for _extract_passage_text method."""

    def test_single_segment(self, mixin):
        """Test extraction from a single passage segment."""
        passage_data = [
            [[0, 50, [[[0, 50, ["This is a single segment with enough characters."]]]]]]
        ]
        result = mixin._extract_passage_text(passage_data)

        assert result == "This is a single segment with enough characters."

    def test_empty_data(self, mixin):
        """Test that empty passage data returns empty string."""
        result = mixin._extract_passage_text([])

        assert result == ""

    def test_multiple_segments(self, mixin):
        """Test extraction from multiple passage segments concatenated."""
        passage_data = [
            [[0, 60, [
                [[0, 30, ["First segment of the passage."]], [30, 60, ["Second segment of the passage"]]]
            ]]]
        ]
        result = mixin._extract_passage_text(passage_data)

        assert "First segment of the passage." in result
        assert "Second segment of the passage" in result


# =========================================================================
# TestParseQueryResponseFull
# =========================================================================


class TestParseQueryResponseFull:
    """Tests for _parse_query_response with full citation extraction."""

    def test_extracts_answer_text(self, mixin):
        """Test that the answer text is correctly extracted from a full response."""
        response = _make_final_chunk(
            "This is a comprehensive answer to the user's question about the topic."
        )
        result = mixin._parse_query_response(response)

        assert result["answer"] == (
            "This is a comprehensive answer to the user's question about the topic."
        )

    def test_extracts_citations(self, mixin):
        """Test that citations are extracted from the response."""
        citations = [
            _make_citation(
                "source-id-001", 0.95,
                "Important passage from the first source document."
            ),
            _make_citation(
                "source-id-002", 0.80,
                "Another relevant passage from a second source."
            ),
        ]
        response = _make_final_chunk(
            "The answer references multiple sources for accuracy and completeness.",
            citations=citations,
        )
        result = mixin._parse_query_response(response)

        assert len(result["sources_cited"]) == 2
        assert result["sources_cited"][0]["source_id"] == "source-id-001"
        assert result["sources_cited"][0]["confidence"] == 0.95
        assert result["sources_cited"][1]["source_id"] == "source-id-002"
        assert result["sources_cited"][1]["confidence"] == 0.80

    def test_extracts_citation_mappings(self, mixin):
        """Test that citation mappings are extracted from the response."""
        citations = [
            _make_citation("src-a", 0.9, "A passage with enough text for extraction here."),
        ]
        mappings = [
            _make_citation_mapping(0, 25, [0]),
            _make_citation_mapping(26, 70, [0]),
        ]
        response = _make_final_chunk(
            "The answer text that has citation mappings applied to specific ranges.",
            citations=citations,
            mappings=mappings,
        )
        result = mixin._parse_query_response(response)

        assert len(result["citation_mappings"]) == 2
        assert result["citation_mappings"][0]["start"] == 0
        assert result["citation_mappings"][0]["end"] == 25
        assert result["citation_mappings"][0]["citation_indices"] == [0]
        assert result["citation_mappings"][1]["start"] == 26
        assert result["citation_mappings"][1]["end"] == 70

    def test_extracts_suggested_questions(self, mixin):
        """Test that suggested follow-up questions are extracted."""
        questions = [
            "What are the key findings?",
            "How does this compare to other studies?",
            "What are the practical implications?",
        ]
        response = _make_final_chunk(
            "Here is a detailed answer to the original question about the research.",
            questions=questions,
        )
        result = mixin._parse_query_response(response)

        assert len(result["suggested_questions"]) == 3
        assert "What are the key findings?" in result["suggested_questions"]
        assert "How does this compare to other studies?" in result["suggested_questions"]
        assert "What are the practical implications?" in result["suggested_questions"]

    def test_empty_response_returns_defaults(self, mixin):
        """Test that an empty response returns sensible defaults."""
        result = mixin._parse_query_response("")

        assert result["answer"] == ""
        assert result["sources_cited"] == []
        assert result["citation_mappings"] == []
        assert result["suggested_questions"] == []

    def test_thinking_only_response_falls_back(self, mixin):
        """Test that a thinking-only chunk (no final answer) falls back gracefully."""
        # Build a chunk that looks like a thinking step (no True final marker)
        inner = [
            ["This is just a thinking step, not the final answer text.", None, None, None, []],
            [],
            [],
            None,
            False,
        ]
        inner_json = json.dumps(inner, separators=(",", ":"))
        wrb = [["wrb.fr", None, inner_json, None, None, None, "generic"]]
        chunk_json = json.dumps(wrb, separators=(",", ":"))
        byte_count = len(chunk_json.encode("utf-8"))
        prefix = ")]}'"
        response = f"{prefix}\n{byte_count}\n{chunk_json}\n"

        result = mixin._parse_query_response(response)

        # Should still capture the text as fallback
        assert "thinking step" in result["answer"]

    def test_multiple_chunks_uses_final(self, mixin):
        """Test that when multiple chunks exist, the final (longest answer) is used."""
        # First chunk: short thinking step
        inner1 = [
            ["Short thinking.", None, None, None, []],
            [],
            [],
            None,
            False,
        ]
        inner1_json = json.dumps(inner1, separators=(",", ":"))
        wrb1 = [["wrb.fr", None, inner1_json, None, None, None, "generic"]]
        chunk1_json = json.dumps(wrb1, separators=(",", ":"))
        byte1 = len(chunk1_json.encode("utf-8"))

        # Second chunk: the final answer with citations
        citations = [
            _make_citation("final-src", 0.88, "The definitive passage from the source document."),
        ]
        inner2 = [
            [
                "This is the final comprehensive answer to the query with full detail.",
                None,
                ["conv-id", "session-id", 12345],
                None,
                [],
            ],
            citations,
            [_make_citation_mapping(0, 30, [0])],
            [["Follow up question one?", "Follow up question two?"]],
            True,
        ]
        inner2_json = json.dumps(inner2, separators=(",", ":"))
        wrb2 = [["wrb.fr", None, inner2_json, None, None, None, "generic"]]
        chunk2_json = json.dumps(wrb2, separators=(",", ":"))
        byte2 = len(chunk2_json.encode("utf-8"))

        prefix = ")]}'"
        response = f"{prefix}\n{byte1}\n{chunk1_json}\n{byte2}\n{chunk2_json}\n"

        result = mixin._parse_query_response(response)

        assert "final comprehensive answer" in result["answer"]
        assert len(result["sources_cited"]) == 1
        assert result["sources_cited"][0]["source_id"] == "final-src"
        assert len(result["citation_mappings"]) == 1
        assert len(result["suggested_questions"]) == 2
