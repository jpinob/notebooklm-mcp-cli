"""Tests for MCP sharing tools."""

from unittest.mock import patch

import pytest

from notebooklm_tools.services.errors import ServiceError


class TestNotebookShareStatus:
    """Tests for notebook_share_status tool."""

    def test_success(self, mock_client):
        """Happy path: returns success with sharing status."""
        mock_result = {
            "is_public": True,
            "access_level": "viewer",
            "collaborators": [
                {"email": "alice@example.com", "role": "editor"},
            ],
            "public_link": "https://notebooklm.google.com/notebook/nb-1/share",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.get_share_status.return_value = mock_result
            from notebooklm_tools.mcp.tools.sharing import notebook_share_status

            result = notebook_share_status(notebook_id="nb-1")

        assert result["status"] == "success"
        assert result["is_public"] is True
        assert result["access_level"] == "viewer"
        assert len(result["collaborators"]) == 1
        assert result["collaborators"][0]["email"] == "alice@example.com"
        assert result["public_link"] == "https://notebooklm.google.com/notebook/nb-1/share"
        mock_svc.get_share_status.assert_called_once_with(mock_client, "nb-1")

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.get_share_status.side_effect = ServiceError(
                "API failure", user_message="Could not get sharing status"
            )
            from notebooklm_tools.mcp.tools.sharing import notebook_share_status

            result = notebook_share_status(notebook_id="nb-1")

        assert result["status"] == "error"
        assert result["error"] == "Could not get sharing status"


class TestNotebookSharePublic:
    """Tests for notebook_share_public tool."""

    def test_enable_public(self, mock_client):
        """Happy path: enables public access and returns link."""
        mock_result = {
            "is_public": True,
            "public_link": "https://notebooklm.google.com/notebook/nb-1/share",
            "message": "Public access enabled",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.set_public_access.return_value = mock_result
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public(notebook_id="nb-1", is_public=True)

        assert result["status"] == "success"
        assert result["is_public"] is True
        assert result["public_link"] == "https://notebooklm.google.com/notebook/nb-1/share"
        mock_svc.set_public_access.assert_called_once_with(mock_client, "nb-1", True)

    def test_disable_public(self, mock_client):
        """Disabling public access returns no link."""
        mock_result = {
            "is_public": False,
            "message": "Public access disabled",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.set_public_access.return_value = mock_result
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public(notebook_id="nb-1", is_public=False)

        assert result["status"] == "success"
        assert result["is_public"] is False
        assert "public_link" not in result
        mock_svc.set_public_access.assert_called_once_with(mock_client, "nb-1", False)

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.set_public_access.side_effect = ServiceError(
                "API failure", user_message="Could not update public access"
            )
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public(notebook_id="nb-1", is_public=True)

        assert result["status"] == "error"
        assert result["error"] == "Could not update public access"


class TestNotebookShareInvite:
    """Tests for notebook_share_invite tool."""

    def test_success_with_editor_role(self, mock_client):
        """Happy path: invites collaborator with editor role."""
        mock_result = {
            "email": "bob@example.com",
            "role": "editor",
            "message": "Invitation sent successfully",
        }
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.invite_collaborator.return_value = mock_result
            from notebooklm_tools.mcp.tools.sharing import notebook_share_invite

            result = notebook_share_invite(
                notebook_id="nb-1", email="bob@example.com", role="editor"
            )

        assert result["status"] == "success"
        assert result["email"] == "bob@example.com"
        assert result["role"] == "editor"
        assert result["message"] == "Invitation sent successfully"
        mock_svc.invite_collaborator.assert_called_once_with(
            mock_client, "nb-1", "bob@example.com", "editor"
        )

    def test_service_error(self, mock_client):
        """ServiceError is caught and returned as error status."""
        with patch(
            "notebooklm_tools.mcp.tools.sharing.sharing_service"
        ) as mock_svc:
            mock_svc.invite_collaborator.side_effect = ServiceError(
                "Invite failed", user_message="Could not invite collaborator"
            )
            from notebooklm_tools.mcp.tools.sharing import notebook_share_invite

            result = notebook_share_invite(
                notebook_id="nb-1", email="bad@example.com", role="viewer"
            )

        assert result["status"] == "error"
        assert result["error"] == "Could not invite collaborator"
