"""Tests for services.chat module."""

import pytest
from unittest.mock import MagicMock

from notebooklm_tools.services.chat import query, configure_chat
from notebooklm_tools.services.errors import ValidationError, ServiceError


@pytest.fixture
def mock_client():
    return MagicMock()


class TestQuery:
    """Test query service function."""

    def test_successful_query(self, mock_client):
        mock_client.query.return_value = {
            "answer": "The answer is 42.",
            "conversation_id": "conv-123",
            "sources_cited": [
                {"source_id": "src-1", "confidence": 0.9, "passage": "p1"},
                {"source_id": "src-2", "confidence": 0.8, "passage": "p2"},
            ],
        }

        result = query(mock_client, "nb-123", "What is the meaning?")

        assert result["answer"] == "The answer is 42."
        assert result["conversation_id"] == "conv-123"
        assert len(result["sources_cited"]) == 2

    def test_empty_query_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Query text is required"):
            query(mock_client, "nb-123", "")

    def test_whitespace_query_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Query text is required"):
            query(mock_client, "nb-123", "   ")

    def test_falsy_result_raises_service_error(self, mock_client):
        mock_client.query.return_value = None
        with pytest.raises(ServiceError, match="empty result"):
            query(mock_client, "nb-123", "question")

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.query.side_effect = RuntimeError("timeout")
        with pytest.raises(ServiceError, match="Query failed"):
            query(mock_client, "nb-123", "question")

    def test_source_ids_passed_through(self, mock_client):
        mock_client.query.return_value = {"answer": "ok"}
        query(mock_client, "nb-123", "question", source_ids=["src-1"])
        mock_client.query.assert_called_once_with(
            notebook_id="nb-123",
            query_text="question",
            source_ids=["src-1"],
            conversation_id=None,
            timeout=None,
        )

    def test_timeout_passed_through(self, mock_client):
        mock_client.query.return_value = {"answer": "ok"}
        query(mock_client, "nb-123", "question", timeout=30.0)
        mock_client.query.assert_called_once_with(
            notebook_id="nb-123",
            query_text="question",
            source_ids=None,
            conversation_id=None,
            timeout=30.0,
        )

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
        """Old-format core response still works with backward-compatible defaults."""
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


class TestConfigureChat:
    """Test configure_chat service function."""

    def test_successful_default_config(self, mock_client):
        mock_client.configure_chat.return_value = {"status": "ok"}

        result = configure_chat(mock_client, "nb-123")

        assert result["goal"] == "default"
        assert result["response_length"] == "default"
        assert "updated" in result["message"].lower()

    def test_invalid_goal_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Invalid goal"):
            configure_chat(mock_client, "nb-123", goal="invalid")

    def test_custom_goal_without_prompt_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Custom prompt is required"):
            configure_chat(mock_client, "nb-123", goal="custom")

    def test_custom_goal_with_prompt_works(self, mock_client):
        mock_client.configure_chat.return_value = {"status": "ok"}

        result = configure_chat(
            mock_client, "nb-123",
            goal="custom",
            custom_prompt="Be a pirate.",
        )

        assert result["goal"] == "custom"

    def test_prompt_too_long_raises_validation_error(self, mock_client):
        long_prompt = "x" * 10_001
        with pytest.raises(ValidationError, match="10000 character"):
            configure_chat(
                mock_client, "nb-123",
                goal="custom",
                custom_prompt=long_prompt,
            )

    def test_invalid_response_length_raises_validation_error(self, mock_client):
        with pytest.raises(ValidationError, match="Invalid response_length"):
            configure_chat(mock_client, "nb-123", response_length="huge")

    def test_learning_guide_goal_works(self, mock_client):
        mock_client.configure_chat.return_value = {"status": "ok"}

        result = configure_chat(mock_client, "nb-123", goal="learning_guide")

        assert result["goal"] == "learning_guide"

    def test_shorter_response_length_works(self, mock_client):
        mock_client.configure_chat.return_value = {"status": "ok"}

        result = configure_chat(mock_client, "nb-123", response_length="shorter")

        assert result["response_length"] == "shorter"

    def test_falsy_result_raises_service_error(self, mock_client):
        mock_client.configure_chat.return_value = None
        with pytest.raises(ServiceError, match="falsy result"):
            configure_chat(mock_client, "nb-123")

    def test_api_error_raises_service_error(self, mock_client):
        mock_client.configure_chat.side_effect = RuntimeError("fail")
        with pytest.raises(ServiceError, match="Failed to configure"):
            configure_chat(mock_client, "nb-123")
