"""Tests for MCP source tools."""

from unittest.mock import patch, MagicMock

import pytest

from notebooklm_tools.services.errors import ServiceError


class TestSourceAdd:
    """Tests for source_add tool."""

    def test_add_url_source(self, mock_client):
        """Happy path: adds a URL source."""
        mock_result = {
            "source_id": "src-1",
            "title": "Example Page",
            "source_type": "url",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.add_source.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add(
                notebook_id="nb-1",
                source_type="url",
                url="https://example.com",
            )

        assert result["status"] == "success"
        assert result["ready"] is False
        assert result["source_id"] == "src-1"
        assert result["source_type"] == "url"
        mock_svc.add_source.assert_called_once_with(
            mock_client, "nb-1", "url",
            url="https://example.com", text=None, title=None,
            file_path=None, document_id=None,
            doc_type="doc", wait=False, wait_timeout=120.0,
        )

    def test_add_text_source(self, mock_client):
        """Happy path: adds a text source with title."""
        mock_result = {
            "source_id": "src-2",
            "title": "My Notes",
            "source_type": "text",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.add_source.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add(
                notebook_id="nb-1",
                source_type="text",
                text="Some pasted content here.",
                title="My Notes",
            )

        assert result["status"] == "success"
        assert result["ready"] is False
        assert result["source_id"] == "src-2"
        mock_svc.add_source.assert_called_once_with(
            mock_client, "nb-1", "text",
            url=None, text="Some pasted content here.", title="My Notes",
            file_path=None, document_id=None,
            doc_type="doc", wait=False, wait_timeout=120.0,
        )

    def test_add_source_with_wait(self, mock_client):
        """When wait=True, ready flag is True in response."""
        mock_result = {
            "source_id": "src-3",
            "title": "Waited Source",
            "source_type": "url",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.add_source.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add(
                notebook_id="nb-1",
                source_type="url",
                url="https://example.com/article",
                wait=True,
                wait_timeout=60.0,
            )

        assert result["status"] == "success"
        assert result["ready"] is True
        mock_svc.add_source.assert_called_once_with(
            mock_client, "nb-1", "url",
            url="https://example.com/article", text=None, title=None,
            file_path=None, document_id=None,
            doc_type="doc", wait=True, wait_timeout=60.0,
        )

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.add_source.side_effect = ServiceError(
                "Bad source", user_message="Invalid source type"
            )
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add(
                notebook_id="nb-1",
                source_type="invalid",
            )

        assert result["status"] == "error"
        assert result["error"] == "Invalid source type"


class TestSourceListDrive:
    """Tests for source_list_drive tool."""

    def test_success(self, mock_client):
        """Happy path: lists drive sources for a notebook."""
        mock_result = {
            "sources": [
                {"id": "src-1", "title": "Doc 1", "stale": False},
                {"id": "src-2", "title": "Doc 2", "stale": True},
            ],
            "count": 2,
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.list_drive_sources.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_list_drive

            result = source_list_drive(notebook_id="nb-1")

        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-1"
        assert result["count"] == 2
        assert len(result["sources"]) == 2
        mock_svc.list_drive_sources.assert_called_once_with(mock_client, "nb-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.list_drive_sources.side_effect = ServiceError(
                "API error", user_message="Could not list drive sources"
            )
            from notebooklm_tools.mcp.tools.sources import source_list_drive

            result = source_list_drive(notebook_id="nb-1")

        assert result["status"] == "error"
        assert result["error"] == "Could not list drive sources"


class TestSourceSyncDrive:
    """Tests for source_sync_drive tool."""

    def test_confirm_false_returns_error(self, mock_client):
        """When confirm=False, returns error with hint."""
        from notebooklm_tools.mcp.tools.sources import source_sync_drive

        result = source_sync_drive(source_ids=["src-1", "src-2"], confirm=False)

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "hint" in result

    def test_confirm_true_success(self, mock_client):
        """Happy path with confirm=True: syncs sources and counts."""
        mock_results = [
            {"source_id": "src-1", "synced": True},
            {"source_id": "src-2", "synced": True},
            {"source_id": "src-3", "synced": False},
        ]
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.sync_drive_sources.return_value = mock_results
            from notebooklm_tools.mcp.tools.sources import source_sync_drive

            result = source_sync_drive(
                source_ids=["src-1", "src-2", "src-3"], confirm=True
            )

        assert result["status"] == "success"
        assert result["synced_count"] == 2
        assert result["total_count"] == 3
        assert len(result["results"]) == 3
        mock_svc.sync_drive_sources.assert_called_once_with(
            mock_client, ["src-1", "src-2", "src-3"]
        )

    def test_confirm_true_service_error(self, mock_client):
        """ServiceError with confirm=True is caught and returned."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.sync_drive_sources.side_effect = ServiceError(
                "Sync failed", user_message="Could not sync sources"
            )
            from notebooklm_tools.mcp.tools.sources import source_sync_drive

            result = source_sync_drive(source_ids=["src-1"], confirm=True)

        assert result["status"] == "error"
        assert result["error"] == "Could not sync sources"


class TestSourceDelete:
    """Tests for source_delete tool."""

    def test_confirm_false_returns_error(self, mock_client):
        """When confirm=False, returns error with warning."""
        from notebooklm_tools.mcp.tools.sources import source_delete

        result = source_delete(source_id="src-1", confirm=False)

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "warning" in result

    def test_confirm_true_success(self, mock_client):
        """Happy path with confirm=True: deletes source."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.delete_source.return_value = None
            from notebooklm_tools.mcp.tools.sources import source_delete

            result = source_delete(source_id="src-1", confirm=True)

        assert result["status"] == "success"
        assert "src-1" in result["message"]
        assert "permanently deleted" in result["message"].lower()
        mock_svc.delete_source.assert_called_once_with(mock_client, "src-1")

    def test_confirm_true_service_error(self, mock_client):
        """ServiceError with confirm=True is caught and returned."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.delete_source.side_effect = ServiceError(
                "Delete failed", user_message="Could not delete source"
            )
            from notebooklm_tools.mcp.tools.sources import source_delete

            result = source_delete(source_id="src-1", confirm=True)

        assert result["status"] == "error"
        assert result["error"] == "Could not delete source"


class TestSourceDescribe:
    """Tests for source_describe tool."""

    def test_success(self, mock_client):
        """Happy path: returns source summary and keywords."""
        mock_result = {
            "summary": "This source covers **API design** patterns.",
            "keywords": ["REST", "GraphQL", "authentication"],
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.describe_source.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_describe

            result = source_describe(source_id="src-1")

        assert result["status"] == "success"
        assert "API design" in result["summary"]
        assert len(result["keywords"]) == 3
        mock_svc.describe_source.assert_called_once_with(mock_client, "src-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.describe_source.side_effect = ServiceError(
                "Describe failed", user_message="Could not describe source"
            )
            from notebooklm_tools.mcp.tools.sources import source_describe

            result = source_describe(source_id="src-1")

        assert result["status"] == "error"
        assert result["error"] == "Could not describe source"


class TestSourceGetContent:
    """Tests for source_get_content tool."""

    def test_success(self, mock_client):
        """Happy path: returns raw source content."""
        mock_result = {
            "content": "Full text content of the source document...",
            "title": "API Design Guide",
            "source_type": "url",
            "char_count": 42,
        }
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.get_source_content.return_value = mock_result
            from notebooklm_tools.mcp.tools.sources import source_get_content

            result = source_get_content(source_id="src-1")

        assert result["status"] == "success"
        assert result["content"] == "Full text content of the source document..."
        assert result["title"] == "API Design Guide"
        assert result["source_type"] == "url"
        assert result["char_count"] == 42
        mock_svc.get_source_content.assert_called_once_with(mock_client, "src-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sources.sources_service"
        ) as mock_svc:
            mock_svc.get_source_content.side_effect = ServiceError(
                "Content failed", user_message="Could not get source content"
            )
            from notebooklm_tools.mcp.tools.sources import source_get_content

            result = source_get_content(source_id="src-1")

        assert result["status"] == "error"
        assert result["error"] == "Could not get source content"
