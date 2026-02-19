"""Tests for MCP notebook tools."""

from unittest.mock import patch, MagicMock

import pytest

from notebooklm_tools.services.errors import ServiceError


class TestNotebookList:
    """Tests for notebook_list tool."""

    def test_success(self, mock_client):
        """Happy path: returns success with notebook list."""
        mock_result = {
            "notebooks": [
                {"id": "nb-1", "title": "Test Notebook", "source_count": 3, "url": "https://notebooklm.google.com/notebook/nb-1"},
            ],
            "count": 1,
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.list_notebooks.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            result = notebook_list(max_results=50)

        assert result["status"] == "success"
        assert result["count"] == 1
        assert len(result["notebooks"]) == 1
        assert result["notebooks"][0]["id"] == "nb-1"
        mock_svc.list_notebooks.assert_called_once_with(mock_client, 50)

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.list_notebooks.side_effect = ServiceError(
                "API failure", user_message="Could not list notebooks"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            result = notebook_list()

        assert result["status"] == "error"
        assert result["error"] == "Could not list notebooks"


class TestNotebookGet:
    """Tests for notebook_get tool."""

    def test_success(self, mock_client):
        """Happy path: returns reshaped notebook and sources."""
        mock_result = {
            "notebook_id": "nb-1",
            "title": "My Notebook",
            "source_count": 2,
            "url": "https://notebooklm.google.com/notebook/nb-1",
            "sources": [
                {"id": "src-1", "title": "Source 1"},
                {"id": "src-2", "title": "Source 2"},
            ],
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.get_notebook.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_get

            result = notebook_get(notebook_id="nb-1")

        assert result["status"] == "success"
        assert result["notebook"]["id"] == "nb-1"
        assert result["notebook"]["title"] == "My Notebook"
        assert result["notebook"]["source_count"] == 2
        assert result["notebook"]["url"] == "https://notebooklm.google.com/notebook/nb-1"
        assert len(result["sources"]) == 2
        mock_svc.get_notebook.assert_called_once_with(mock_client, "nb-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.get_notebook.side_effect = ServiceError(
                "Not found", user_message="Notebook not found"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_get

            result = notebook_get(notebook_id="nonexistent")

        assert result["status"] == "error"
        assert result["error"] == "Notebook not found"


class TestNotebookDescribe:
    """Tests for notebook_describe tool."""

    def test_success(self, mock_client):
        """Happy path: returns success with summary and topics."""
        mock_result = {
            "summary": "This notebook covers **machine learning** topics.",
            "suggested_topics": ["neural networks", "gradient descent"],
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.describe_notebook.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_describe

            result = notebook_describe(notebook_id="nb-1")

        assert result["status"] == "success"
        assert "machine learning" in result["summary"]
        assert len(result["suggested_topics"]) == 2
        mock_svc.describe_notebook.assert_called_once_with(mock_client, "nb-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.describe_notebook.side_effect = ServiceError(
                "Describe failed", user_message="Could not describe notebook"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_describe

            result = notebook_describe(notebook_id="nb-1")

        assert result["status"] == "error"
        assert result["error"] == "Could not describe notebook"


class TestNotebookCreate:
    """Tests for notebook_create tool."""

    def test_success(self, mock_client):
        """Happy path: creates notebook and returns reshaped result."""
        mock_result = {
            "notebook_id": "nb-new",
            "title": "New Notebook",
            "url": "https://notebooklm.google.com/notebook/nb-new",
            "message": "Notebook created successfully",
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.create_notebook.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_create

            result = notebook_create(title="New Notebook")

        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-new"
        assert result["notebook"]["id"] == "nb-new"
        assert result["notebook"]["title"] == "New Notebook"
        assert result["notebook"]["url"] == "https://notebooklm.google.com/notebook/nb-new"
        assert result["message"] == "Notebook created successfully"
        mock_svc.create_notebook.assert_called_once_with(mock_client, "New Notebook")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.create_notebook.side_effect = ServiceError(
                "Creation failed", user_message="Could not create notebook"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_create

            result = notebook_create(title="Failing Notebook")

        assert result["status"] == "error"
        assert result["error"] == "Could not create notebook"


class TestNotebookRename:
    """Tests for notebook_rename tool."""

    def test_success(self, mock_client):
        """Happy path: renames notebook and returns result."""
        mock_result = {
            "notebook_id": "nb-1",
            "title": "Renamed Notebook",
            "message": "Notebook renamed successfully",
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.rename_notebook.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_rename

            result = notebook_rename(notebook_id="nb-1", new_title="Renamed Notebook")

        assert result["status"] == "success"
        assert result["title"] == "Renamed Notebook"
        assert result["notebook_id"] == "nb-1"
        mock_svc.rename_notebook.assert_called_once_with(
            mock_client, "nb-1", "Renamed Notebook"
        )

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.rename_notebook.side_effect = ServiceError(
                "Rename failed", user_message="Could not rename notebook"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_rename

            result = notebook_rename(notebook_id="nb-1", new_title="Bad Name")

        assert result["status"] == "error"
        assert result["error"] == "Could not rename notebook"


class TestNotebookDelete:
    """Tests for notebook_delete tool."""

    def test_confirm_false_returns_error(self, mock_client):
        """When confirm=False, returns error without calling the service."""
        from notebooklm_tools.mcp.tools.notebooks import notebook_delete

        result = notebook_delete(notebook_id="nb-1", confirm=False)

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "warning" in result

    def test_confirm_true_success(self, mock_client):
        """Happy path with confirm=True: deletes notebook."""
        mock_result = {
            "notebook_id": "nb-1",
            "message": "Notebook deleted successfully",
        }
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.delete_notebook.return_value = mock_result
            from notebooklm_tools.mcp.tools.notebooks import notebook_delete

            result = notebook_delete(notebook_id="nb-1", confirm=True)

        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-1"
        mock_svc.delete_notebook.assert_called_once_with(mock_client, "nb-1")

    def test_confirm_true_service_error(self, mock_client):
        """ServiceError with confirm=True is caught and returned."""
        with patch(
            "notebooklm_tools.mcp.tools.notebooks.notebooks_service"
        ) as mock_svc:
            mock_svc.delete_notebook.side_effect = ServiceError(
                "Delete failed", user_message="Could not delete notebook"
            )
            from notebooklm_tools.mcp.tools.notebooks import notebook_delete

            result = notebook_delete(notebook_id="nb-1", confirm=True)

        assert result["status"] == "error"
        assert result["error"] == "Could not delete notebook"
