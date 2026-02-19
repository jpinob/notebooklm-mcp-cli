"""Unit tests for MCP research tools."""

from unittest.mock import patch, MagicMock

import pytest

from notebooklm_tools.services.errors import ServiceError


class TestResearchStart:
    """Tests for the research_start MCP tool."""

    def test_success_defaults(self, mock_client):
        """Test research_start with default parameters returns success."""
        mock_result = {
            "notebook_id": "nb-123",
            "task_id": "task-456",
            "message": "Research started",
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.start_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_start

            result = research_start(query="quantum computing")

        mock_svc.start_research.assert_called_once_with(
            mock_client, None, "quantum computing",
            source="web", mode="fast",
        )
        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-123"
        assert result["task_id"] == "task-456"

    def test_success_with_options(self, mock_client):
        """Test research_start with custom source, mode, notebook_id, and title."""
        mock_result = {
            "notebook_id": "nb-existing",
            "task_id": "task-789",
            "message": "Deep research started",
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.start_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_start

            result = research_start(
                query="machine learning papers",
                source="drive",
                mode="deep",
                notebook_id="nb-existing",
                title="ML Research",
            )

        mock_svc.start_research.assert_called_once_with(
            mock_client, "nb-existing", "machine learning papers",
            source="drive", mode="deep",
        )
        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-existing"
        assert result["task_id"] == "task-789"

    def test_service_error(self, mock_client):
        """Test research_start returns error dict on ServiceError."""
        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.start_research.side_effect = ServiceError(
                "internal error", user_message="Research failed to start"
            )
            from notebooklm_tools.mcp.tools.research import research_start

            result = research_start(query="test query")

        assert result["status"] == "error"
        assert result["error"] == "Research failed to start"


class TestResearchStatus:
    """Tests for the research_status MCP tool."""

    def test_success_returns_result_directly(self, mock_client):
        """Test research_status returns result directly (no status wrapper)."""
        mock_result = {
            "status": "completed",
            "task_id": "task-456",
            "sources_found": 10,
            "report": "Summary of findings...",
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.poll_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_status

            result = research_status(notebook_id="nb-123")

        mock_svc.poll_research.assert_called_once_with(
            mock_client, "nb-123",
            task_id=None, query=None, compact=True,
        )
        # Known inconsistency: returns result directly, not wrapped
        assert result is mock_result
        assert result["status"] == "completed"
        assert result["task_id"] == "task-456"

    def test_success_with_task_id_and_query(self, mock_client):
        """Test research_status with task_id and query parameters."""
        mock_result = {
            "status": "in_progress",
            "task_id": "task-specific",
            "progress": 50,
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.poll_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_status

            result = research_status(
                notebook_id="nb-123",
                task_id="task-specific",
                query="fallback query",
                compact=False,
            )

        mock_svc.poll_research.assert_called_once_with(
            mock_client, "nb-123",
            task_id="task-specific", query="fallback query", compact=False,
        )
        assert result is mock_result
        assert result["status"] == "in_progress"

    def test_service_error(self, mock_client):
        """Test research_status returns error dict on ServiceError."""
        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.poll_research.side_effect = ServiceError(
                "poll failed", user_message="Could not poll research status"
            )
            from notebooklm_tools.mcp.tools.research import research_status

            result = research_status(notebook_id="nb-123")

        assert result["status"] == "error"
        assert result["error"] == "Could not poll research status"


class TestResearchImport:
    """Tests for the research_import MCP tool."""

    def test_success_import_all(self, mock_client):
        """Test research_import with default source_indices (all sources)."""
        mock_result = {
            "imported_count": 10,
            "sources": ["source1", "source2"],
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.import_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_import

            result = research_import(notebook_id="nb-123", task_id="task-456")

        mock_svc.import_research.assert_called_once_with(
            mock_client, "nb-123", "task-456",
            source_indices=None,
        )
        assert result["status"] == "success"
        assert result["imported_count"] == 10

    def test_success_with_source_indices(self, mock_client):
        """Test research_import with specific source indices."""
        mock_result = {
            "imported_count": 2,
            "sources": ["source1", "source3"],
        }

        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.import_research.return_value = mock_result
            from notebooklm_tools.mcp.tools.research import research_import

            result = research_import(
                notebook_id="nb-123",
                task_id="task-456",
                source_indices=[0, 2],
            )

        mock_svc.import_research.assert_called_once_with(
            mock_client, "nb-123", "task-456",
            source_indices=[0, 2],
        )
        assert result["status"] == "success"
        assert result["imported_count"] == 2

    def test_service_error(self, mock_client):
        """Test research_import returns error dict on ServiceError."""
        with patch("notebooklm_tools.mcp.tools.research.research_service") as mock_svc:
            mock_svc.import_research.side_effect = ServiceError(
                "import failed", user_message="Failed to import research sources"
            )
            from notebooklm_tools.mcp.tools.research import research_import

            result = research_import(notebook_id="nb-123", task_id="task-456")

        assert result["status"] == "error"
        assert result["error"] == "Failed to import research sources"
