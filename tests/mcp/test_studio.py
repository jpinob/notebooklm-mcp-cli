"""Unit tests for MCP studio tools (studio_create, studio_status, studio_delete)."""

import pytest
from unittest.mock import patch, MagicMock

from notebooklm_tools.services.errors import ServiceError, ValidationError


class TestStudioCreate:
    """Tests for the studio_create MCP tool."""

    def test_invalid_artifact_type(self, mock_client):
        """Test that an invalid artifact_type returns error from ValidationError."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.side_effect = ValidationError(
                "Unknown artifact type 'bad'. Valid types: audio, flashcards, quiz, report, video"
            )
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="bad",
            )

        assert result["status"] == "error"
        assert "Unknown artifact type" in result["error"]
        # create_artifact should NOT have been called
        mock_service.create_artifact.assert_not_called()

    def test_confirm_false_pending_confirmation(self, mock_client):
        """Test confirm=False returns pending_confirmation with settings preview."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="report",
                confirm=False,
            )

        assert result["status"] == "pending_confirmation"
        assert "settings" in result
        assert result["settings"]["artifact_type"] == "report"
        assert result["settings"]["notebook_id"] == "nb-abc"
        assert result["settings"]["source_ids"] == "all sources"
        assert "note" in result
        # Service create should NOT have been called
        mock_service.create_artifact.assert_not_called()

    def test_confirm_false_audio_settings(self, mock_client):
        """Test confirm=False for audio type includes audio-specific settings."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="audio",
                audio_format="debate",
                audio_length="short",
                language="es",
                confirm=False,
            )

        assert result["status"] == "pending_confirmation"
        settings = result["settings"]
        assert settings["artifact_type"] == "audio"
        assert settings["format"] == "debate"
        assert settings["length"] == "short"
        assert settings["language"] == "es"

    def test_confirm_false_with_focus_prompt(self, mock_client):
        """Test confirm=False includes focus_prompt in settings when provided."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="video",
                focus_prompt="Focus on chapter 3",
                confirm=False,
            )

        assert result["status"] == "pending_confirmation"
        assert result["settings"]["focus_prompt"] == "Focus on chapter 3"

    def test_confirm_true_success(self, mock_client):
        """Test confirm=True calls create_artifact and returns success."""
        mock_result = {
            "artifact_id": "art-123",
            "artifact_type": "audio",
            "message": "Audio generation started.",
        }
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            mock_service.create_artifact.return_value = mock_result
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="audio",
                confirm=True,
            )

        assert result["status"] == "success"
        assert result["artifact_id"] == "art-123"
        assert result["notebook_url"] == "https://notebooklm.google.com/notebook/nb-abc"
        mock_service.create_artifact.assert_called_once()
        call_kwargs = mock_service.create_artifact.call_args
        assert call_kwargs[0][0] is mock_client
        assert call_kwargs[0][1] == "nb-abc"
        assert call_kwargs[0][2] == "audio"

    def test_confirm_true_service_error(self, mock_client):
        """Test ServiceError during creation returns error status."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            mock_service.create_artifact.side_effect = ServiceError(
                "API failure", user_message="Failed to create artifact. Try again later."
            )
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="audio",
                confirm=True,
            )

        assert result["status"] == "error"
        assert result["error"] == "Failed to create artifact. Try again later."

    def test_confirm_true_with_source_ids(self, mock_client):
        """Test confirm=True passes source_ids to service."""
        mock_result = {"artifact_id": "art-456", "artifact_type": "quiz"}
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.validate_artifact_type.return_value = None
            mock_service.create_artifact.return_value = mock_result
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                notebook_id="nb-abc",
                artifact_type="quiz",
                source_ids=["src-1", "src-2"],
                question_count=5,
                difficulty="hard",
                confirm=True,
            )

        assert result["status"] == "success"
        call_kwargs = mock_service.create_artifact.call_args
        assert call_kwargs[1]["source_ids"] == ["src-1", "src-2"]
        assert call_kwargs[1]["question_count"] == 5
        assert call_kwargs[1]["difficulty"] == "hard"


class TestStudioStatus:
    """Tests for the studio_status MCP tool."""

    def test_status_action(self, mock_client):
        """Test action='status' returns summary and artifacts list."""
        mock_result = {
            "total": 3,
            "completed": 2,
            "in_progress": 1,
            "artifacts": [
                {
                    "artifact_id": "art-1",
                    "title": "Audio Overview",
                    "type": "audio",
                    "status": "completed",
                    "url": "https://example.com/audio",
                },
                {
                    "artifact_id": "art-2",
                    "title": "Study Guide",
                    "type": "report",
                    "status": "completed",
                    "url": None,
                },
                {
                    "artifact_id": "art-3",
                    "title": "Video Overview",
                    "type": "video",
                    "status": "in_progress",
                    "url": None,
                },
            ],
        }
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.get_studio_status.return_value = mock_result
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status(notebook_id="nb-abc", action="status")

        assert result["status"] == "success"
        assert result["notebook_id"] == "nb-abc"
        assert result["summary"]["total"] == 3
        assert result["summary"]["completed"] == 2
        assert result["summary"]["in_progress"] == 1
        assert len(result["artifacts"]) == 3
        assert result["artifacts"][0]["artifact_id"] == "art-1"
        assert result["notebook_url"] == "https://notebooklm.google.com/notebook/nb-abc"
        mock_service.get_studio_status.assert_called_once_with(mock_client, "nb-abc")

    def test_rename_action(self, mock_client):
        """Test action='rename' calls rename_artifact and returns success."""
        mock_result = {"artifact_id": "art-1", "new_title": "My New Title"}
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.rename_artifact.return_value = mock_result
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status(
                notebook_id="nb-abc",
                action="rename",
                artifact_id="art-1",
                new_title="My New Title",
            )

        assert result["status"] == "success"
        assert result["action"] == "rename"
        assert "My New Title" in result["message"]
        assert result["artifact_id"] == "art-1"
        assert result["new_title"] == "My New Title"
        mock_service.rename_artifact.assert_called_once_with(
            mock_client, "art-1", "My New Title"
        )

    def test_service_error(self, mock_client):
        """Test ServiceError during status check returns error."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.get_studio_status.side_effect = ServiceError(
                "API error", user_message="Could not retrieve studio status."
            )
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status(notebook_id="nb-abc")

        assert result["status"] == "error"
        assert result["error"] == "Could not retrieve studio status."


class TestStudioDelete:
    """Tests for the studio_delete MCP tool."""

    def test_confirm_false_returns_error(self, mock_client):
        """Test confirm=False returns error with warning and hint."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service"):
            from notebooklm_tools.mcp.tools.studio import studio_delete

            result = studio_delete(
                notebook_id="nb-abc",
                artifact_id="art-1",
                confirm=False,
            )

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "warning" in result
        assert "IRREVERSIBLE" in result["warning"]
        assert "hint" in result

    def test_confirm_true_success(self, mock_client):
        """Test confirm=True calls delete_artifact and returns success."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.delete_artifact.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_delete

            result = studio_delete(
                notebook_id="nb-abc",
                artifact_id="art-1",
                confirm=True,
            )

        assert result["status"] == "success"
        assert "art-1" in result["message"]
        assert "permanently deleted" in result["message"]
        assert result["notebook_id"] == "nb-abc"
        mock_service.delete_artifact.assert_called_once_with(
            mock_client, "art-1", "nb-abc"
        )

    def test_confirm_true_service_error(self, mock_client):
        """Test ServiceError during deletion returns error status."""
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as mock_service:
            mock_service.delete_artifact.side_effect = ServiceError(
                "Deletion failed", user_message="Artifact not found or already deleted."
            )
            from notebooklm_tools.mcp.tools.studio import studio_delete

            result = studio_delete(
                notebook_id="nb-abc",
                artifact_id="art-999",
                confirm=True,
            )

        assert result["status"] == "error"
        assert result["error"] == "Artifact not found or already deleted."
