"""Tests for MCP download_artifact tool."""

import pytest
from unittest.mock import patch, AsyncMock

from notebooklm_tools.services.errors import ServiceError


@pytest.mark.asyncio
class TestDownloadArtifact:
    """Tests for the download_artifact MCP tool."""

    async def test_success(self, mock_client):
        """Test successful download returns success status and result."""
        mock_result = {
            "file_path": "/tmp/podcast.mp3",
            "artifact_type": "audio",
            "size_bytes": 1024000,
        }
        with patch(
            "notebooklm_tools.mcp.tools.downloads.downloads_service"
        ) as mock_svc:
            mock_svc.download_async = AsyncMock(return_value=mock_result)
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact(
                notebook_id="nb-123",
                artifact_type="audio",
                output_path="/tmp/podcast.mp3",
            )

        assert result["status"] == "success"
        assert result["file_path"] == "/tmp/podcast.mp3"
        assert result["artifact_type"] == "audio"
        assert result["size_bytes"] == 1024000
        mock_svc.download_async.assert_awaited_once_with(
            mock_client,
            "nb-123",
            "audio",
            "/tmp/podcast.mp3",
            artifact_id=None,
            output_format="json",
        )

    async def test_with_artifact_id(self, mock_client):
        """Test download with explicit artifact_id passes it through."""
        mock_result = {
            "file_path": "/tmp/quiz.html",
            "artifact_type": "quiz",
        }
        with patch(
            "notebooklm_tools.mcp.tools.downloads.downloads_service"
        ) as mock_svc:
            mock_svc.download_async = AsyncMock(return_value=mock_result)
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact(
                notebook_id="nb-456",
                artifact_type="quiz",
                output_path="/tmp/quiz.html",
                artifact_id="art-789",
                output_format="html",
            )

        assert result["status"] == "success"
        assert result["file_path"] == "/tmp/quiz.html"
        mock_svc.download_async.assert_awaited_once_with(
            mock_client,
            "nb-456",
            "quiz",
            "/tmp/quiz.html",
            artifact_id="art-789",
            output_format="html",
        )

    async def test_service_error(self, mock_client):
        """Test ServiceError is caught and returns error status with user message."""
        with patch(
            "notebooklm_tools.mcp.tools.downloads.downloads_service"
        ) as mock_svc:
            mock_svc.download_async = AsyncMock(
                side_effect=ServiceError("internal details", user_message="Notebook not found")
            )
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact(
                notebook_id="nb-missing",
                artifact_type="audio",
                output_path="/tmp/out.mp3",
            )

        assert result["status"] == "error"
        assert result["error"] == "Notebook not found"

    async def test_unexpected_error(self, mock_client):
        """Test unexpected exceptions are caught and returned as error."""
        with patch(
            "notebooklm_tools.mcp.tools.downloads.downloads_service"
        ) as mock_svc:
            mock_svc.download_async = AsyncMock(side_effect=OSError("disk full"))
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact(
                notebook_id="nb-123",
                artifact_type="audio",
                output_path="/tmp/out.mp3",
            )

        assert result["status"] == "error"
        assert "disk full" in result["error"]
