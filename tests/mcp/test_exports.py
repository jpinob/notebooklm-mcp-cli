"""Tests for MCP export tools."""

from unittest.mock import patch

import pytest

from notebooklm_tools.services.errors import ServiceError


class TestExportArtifact:
    """Tests for export_artifact tool."""

    def test_success(self, mock_client):
        """Happy path: exports artifact and returns result directly."""
        mock_result = {
            "status": "success",
            "export_type": "docs",
            "url": "https://docs.google.com/document/d/abc123",
            "message": "Exported to Google Docs",
        }
        with patch(
            "notebooklm_tools.mcp.tools.exports.export_service"
        ) as mock_svc:
            mock_svc.export_artifact.return_value = mock_result
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact(
                notebook_id="nb-1",
                artifact_id="art-1",
                export_type="docs",
            )

        assert result["status"] == "success"
        assert result["export_type"] == "docs"
        assert result["url"] == "https://docs.google.com/document/d/abc123"
        mock_svc.export_artifact.assert_called_once_with(
            client=mock_client,
            notebook_id="nb-1",
            artifact_id="art-1",
            export_type="docs",
            title=None,
        )

    def test_success_with_title(self, mock_client):
        """Happy path with custom title parameter."""
        mock_result = {
            "status": "success",
            "export_type": "sheets",
            "title": "My Custom Export",
            "url": "https://docs.google.com/spreadsheets/d/xyz789",
            "message": "Exported to Google Sheets",
        }
        with patch(
            "notebooklm_tools.mcp.tools.exports.export_service"
        ) as mock_svc:
            mock_svc.export_artifact.return_value = mock_result
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact(
                notebook_id="nb-2",
                artifact_id="art-2",
                export_type="sheets",
                title="My Custom Export",
            )

        assert result["status"] == "success"
        assert result["export_type"] == "sheets"
        assert result["title"] == "My Custom Export"
        assert result["url"] == "https://docs.google.com/spreadsheets/d/xyz789"
        mock_svc.export_artifact.assert_called_once_with(
            client=mock_client,
            notebook_id="nb-2",
            artifact_id="art-2",
            export_type="sheets",
            title="My Custom Export",
        )

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.exports.export_service"
        ) as mock_svc:
            mock_svc.export_artifact.side_effect = ServiceError(
                "Export failed", user_message="Could not export artifact"
            )
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact(
                notebook_id="nb-1",
                artifact_id="art-bad",
                export_type="docs",
            )

        assert result["status"] == "error"
        assert result["error"] == "Could not export artifact"

    def test_unexpected_error(self, mock_client):
        """Unexpected RuntimeError is caught by the generic except handler."""
        with patch(
            "notebooklm_tools.mcp.tools.exports.export_service"
        ) as mock_svc:
            mock_svc.export_artifact.side_effect = RuntimeError(
                "Unexpected internal error"
            )
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact(
                notebook_id="nb-1",
                artifact_id="art-crash",
                export_type="docs",
            )

        assert result["status"] == "error"
        assert "Unexpected internal error" in result["error"]
