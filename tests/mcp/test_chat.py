"""Unit tests for MCP chat tools (notebook_query, chat_configure)."""

import pytest
from unittest.mock import patch, MagicMock

from notebooklm_tools.services.errors import ServiceError


class TestNotebookQuery:
    """Tests for the notebook_query MCP tool."""

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
        mock_service.query.assert_called_once()

    def test_with_source_ids(self, mock_client):
        """Test query with specific source_ids passes them through."""
        mock_result = {"answer": "Filtered answer.", "conversation_id": "conv-456"}
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="Summarize source 1",
                source_ids=["src-1"],
            )

        assert result["status"] == "success"
        assert result["answer"] == "Filtered answer."
        call_kwargs = mock_service.query.call_args
        assert call_kwargs[1]["source_ids"] == ["src-1"]

    def test_with_conversation_id(self, mock_client):
        """Test follow-up query with conversation_id passes it through."""
        mock_result = {"answer": "Follow-up answer.", "conversation_id": "conv-123"}
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="Tell me more",
                conversation_id="conv-123",
            )

        assert result["status"] == "success"
        call_kwargs = mock_service.query.call_args
        assert call_kwargs[1]["conversation_id"] == "conv-123"

    def test_service_error(self, mock_client):
        """Test ServiceError is caught and returns error status with user_message."""
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.side_effect = ServiceError(
                "Internal detail", user_message="Notebook not found"
            )
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-invalid",
                query="Hello?",
            )

        assert result["status"] == "error"
        assert result["error"] == "Notebook not found"

    def test_unexpected_error_timeout(self, mock_client):
        """Test unexpected TimeoutError is caught and returns error status."""
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.side_effect = TimeoutError("Request timed out after 120s")
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="Long query",
            )

        assert result["status"] == "error"
        assert "timed out" in result["error"]

    def test_custom_timeout_passed_through(self, mock_client):
        """Test that custom timeout parameter is forwarded to the service."""
        mock_result = {"answer": "Quick answer.", "conversation_id": "conv-789"}
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.query.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="Fast question",
                timeout=30.0,
            )

        assert result["status"] == "success"
        call_kwargs = mock_service.query.call_args
        assert call_kwargs[1]["timeout"] == 30.0

    def test_default_timeout_uses_get_query_timeout(self, mock_client):
        """Test that when no timeout is provided, get_query_timeout() is used."""
        mock_result = {"answer": "Default timeout answer.", "conversation_id": "conv-000"}
        with (
            patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service,
            patch("notebooklm_tools.mcp.tools.chat.get_query_timeout", return_value=60.0),
        ):
            mock_service.query.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query(
                notebook_id="nb-abc",
                query="Use default timeout",
            )

        assert result["status"] == "success"
        call_kwargs = mock_service.query.call_args
        assert call_kwargs[1]["timeout"] == 60.0


class TestChatConfigure:
    """Tests for the chat_configure MCP tool."""

    def test_success_default_settings(self, mock_client):
        """Test successful configuration with default settings."""
        mock_result = {
            "notebook_id": "nb-abc",
            "goal": "default",
            "response_length": "default",
            "message": "Chat settings updated successfully.",
        }
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.configure_chat.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import chat_configure

            result = chat_configure(notebook_id="nb-abc")

        assert result["status"] == "success"
        assert result["goal"] == "default"
        assert result["message"] == "Chat settings updated successfully."
        mock_service.configure_chat.assert_called_once_with(
            mock_client,
            "nb-abc",
            goal="default",
            custom_prompt=None,
            response_length="default",
        )

    def test_with_custom_prompt(self, mock_client):
        """Test configuration with custom goal and prompt."""
        mock_result = {
            "notebook_id": "nb-abc",
            "goal": "custom",
            "custom_prompt": "Be a concise teacher",
            "response_length": "shorter",
            "message": "Chat settings updated successfully.",
        }
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.configure_chat.return_value = mock_result
            from notebooklm_tools.mcp.tools.chat import chat_configure

            result = chat_configure(
                notebook_id="nb-abc",
                goal="custom",
                custom_prompt="Be a concise teacher",
                response_length="shorter",
            )

        assert result["status"] == "success"
        assert result["custom_prompt"] == "Be a concise teacher"
        assert result["response_length"] == "shorter"
        mock_service.configure_chat.assert_called_once_with(
            mock_client,
            "nb-abc",
            goal="custom",
            custom_prompt="Be a concise teacher",
            response_length="shorter",
        )

    def test_service_error(self, mock_client):
        """Test ServiceError is caught and returns error status."""
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as mock_service:
            mock_service.configure_chat.side_effect = ServiceError(
                "Invalid goal", user_message="Invalid goal 'bad'. Use: default, learning_guide, custom"
            )
            from notebooklm_tools.mcp.tools.chat import chat_configure

            result = chat_configure(
                notebook_id="nb-abc",
                goal="bad",
            )

        assert result["status"] == "error"
        assert "Invalid goal" in result["error"]
