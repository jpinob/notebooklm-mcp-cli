"""Unit tests for MCP notes tool."""

from unittest.mock import patch, MagicMock

import pytest

from notebooklm_tools.services.errors import ServiceError, ValidationError


class TestNoteInvalidAction:
    """Tests for the note tool with invalid actions."""

    def test_unknown_action(self, mock_client):
        """Test that an unknown action returns an error with valid actions listed."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            from notebooklm_tools.mcp.tools.notes import note

            result = note(notebook_id="nb-123", action="invalid_action")

        assert result["status"] == "error"
        assert "Unknown action 'invalid_action'" in result["error"]
        assert "create, list, update, delete" in result["error"]


class TestNoteCreate:
    """Tests for the note tool with action='create'."""

    def test_create_success(self, mock_client):
        """Test creating a note with content and title."""
        mock_result = {
            "note_id": "note-abc",
            "title": "My Note",
        }

        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.create_note.return_value = mock_result
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123",
                action="create",
                content="Note body text",
                title="My Note",
            )

        mock_svc.create_note.assert_called_once_with(
            mock_client, "nb-123", "Note body text", "My Note"
        )
        assert result["status"] == "success"
        assert result["action"] == "create"
        assert result["note_id"] == "note-abc"

    def test_create_without_content_uses_empty_string(self, mock_client):
        """Test that creating a note without content passes empty string."""
        mock_result = {"note_id": "note-def"}

        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.create_note.return_value = mock_result
            from notebooklm_tools.mcp.tools.notes import note

            result = note(notebook_id="nb-123", action="create")

        mock_svc.create_note.assert_called_once_with(
            mock_client, "nb-123", "", None
        )
        assert result["status"] == "success"
        assert result["action"] == "create"

    def test_create_service_error(self, mock_client):
        """Test create action with ServiceError."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.create_note.side_effect = ServiceError(
                "creation failed", user_message="Could not create note"
            )
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="create", content="test"
            )

        assert result["status"] == "error"
        assert result["error"] == "Could not create note"


class TestNoteList:
    """Tests for the note tool with action='list'."""

    def test_list_success(self, mock_client):
        """Test listing notes in a notebook."""
        mock_result = {
            "notes": [
                {"note_id": "note-1", "title": "First"},
                {"note_id": "note-2", "title": "Second"},
            ],
            "count": 2,
        }

        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.list_notes.return_value = mock_result
            from notebooklm_tools.mcp.tools.notes import note

            result = note(notebook_id="nb-123", action="list")

        mock_svc.list_notes.assert_called_once_with(mock_client, "nb-123")
        assert result["status"] == "success"
        assert result["action"] == "list"
        assert result["count"] == 2
        assert len(result["notes"]) == 2

    def test_list_service_error(self, mock_client):
        """Test list action with ServiceError."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.list_notes.side_effect = ServiceError(
                "list failed", user_message="Could not list notes"
            )
            from notebooklm_tools.mcp.tools.notes import note

            result = note(notebook_id="nb-123", action="list")

        assert result["status"] == "error"
        assert result["error"] == "Could not list notes"


class TestNoteUpdate:
    """Tests for the note tool with action='update'."""

    def test_update_without_note_id(self, mock_client):
        """Test that update without note_id returns an error."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="update", content="new content"
            )

        assert result["status"] == "error"
        assert "note_id is required" in result["error"]

    def test_update_success(self, mock_client):
        """Test updating a note with content and title."""
        mock_result = {
            "note_id": "note-abc",
            "title": "Updated Title",
        }

        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.update_note.return_value = mock_result
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123",
                action="update",
                note_id="note-abc",
                content="Updated body",
                title="Updated Title",
            )

        mock_svc.update_note.assert_called_once_with(
            mock_client, "nb-123", "note-abc", "Updated body", "Updated Title"
        )
        assert result["status"] == "success"
        assert result["action"] == "update"
        assert result["note_id"] == "note-abc"

    def test_update_service_error(self, mock_client):
        """Test update action with ServiceError."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.update_note.side_effect = ValidationError(
                "invalid note_id", user_message="Note not found"
            )
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="update",
                note_id="bad-id", content="test"
            )

        assert result["status"] == "error"
        assert result["error"] == "Note not found"


class TestNoteDelete:
    """Tests for the note tool with action='delete'."""

    def test_delete_without_note_id(self, mock_client):
        """Test that delete without note_id returns an error."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="delete", confirm=True
            )

        assert result["status"] == "error"
        assert "note_id is required" in result["error"]

    def test_delete_without_confirm(self, mock_client):
        """Test that delete without confirm=True returns error with warning."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="delete",
                note_id="note-abc", confirm=False,
            )

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower() or "confirm=True" in result["error"]
        assert "warning" in result

    def test_delete_success(self, mock_client):
        """Test successful delete with confirm=True."""
        mock_result = {
            "note_id": "note-abc",
            "deleted": True,
        }

        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.delete_note.return_value = mock_result
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123",
                action="delete",
                note_id="note-abc",
                confirm=True,
            )

        mock_svc.delete_note.assert_called_once_with(
            mock_client, "nb-123", "note-abc"
        )
        assert result["status"] == "success"
        assert result["action"] == "delete"
        assert result["deleted"] is True

    def test_delete_service_error(self, mock_client):
        """Test delete action with ServiceError."""
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as mock_svc:
            mock_svc.delete_note.side_effect = ServiceError(
                "delete failed", user_message="Failed to delete note"
            )
            from notebooklm_tools.mcp.tools.notes import note

            result = note(
                notebook_id="nb-123", action="delete",
                note_id="note-abc", confirm=True,
            )

        assert result["status"] == "error"
        assert result["error"] == "Failed to delete note"
