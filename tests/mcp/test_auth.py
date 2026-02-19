"""Tests for MCP auth tools (refresh_auth, save_auth_tokens)."""

import pytest
from unittest.mock import patch, MagicMock


class TestRefreshAuth:
    """Tests for the refresh_auth MCP tool."""

    def test_success_from_cache(self, mock_client):
        """Test refresh_auth succeeds when cached tokens are found on disk."""
        mock_tokens = MagicMock()
        with patch(
            "notebooklm_tools.core.auth.load_cached_tokens",
            return_value=mock_tokens,
        ), patch(
            "notebooklm_tools.mcp.tools.auth.reset_client"
        ) as mock_reset, patch(
            "notebooklm_tools.mcp.tools.auth.get_client"
        ) as mock_get:
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()

        assert result["status"] == "success"
        assert "reloaded" in result["message"].lower() or "disk" in result["message"].lower()
        mock_reset.assert_called_once()
        mock_get.assert_called_once()

    def test_no_cached_tokens(self, mock_client):
        """Test refresh_auth returns error when no cached tokens and headless fails."""
        with patch(
            "notebooklm_tools.core.auth.load_cached_tokens",
            return_value=None,
        ), patch(
            "notebooklm_tools.mcp.tools.auth.reset_client"
        ), patch(
            "notebooklm_tools.mcp.tools.auth.get_client"
        ):
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()

        assert result["status"] == "error"
        assert "nlm login" in result["error"].lower() or "no cached tokens" in result["error"].lower()

    def test_unexpected_error(self, mock_client):
        """Test refresh_auth catches unexpected exceptions."""
        with patch(
            "notebooklm_tools.core.auth.load_cached_tokens",
            side_effect=RuntimeError("corrupt token file"),
        ):
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()

        assert result["status"] == "error"
        assert "corrupt token file" in result["error"]


class TestSaveAuthTokens:
    """Tests for the save_auth_tokens MCP tool."""

    def test_missing_required_cookies(self, mock_client):
        """Test returns error when required cookies are missing."""
        with patch(
            "notebooklm_tools.core.auth.AuthTokens"
        ), patch(
            "notebooklm_tools.core.auth.save_tokens_to_cache"
        ), patch(
            "notebooklm_tools.core.auth.get_cache_path"
        ):
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(cookies="foo=bar; baz=qux")

        assert result["status"] == "error"
        assert "Missing required cookies" in result["error"]
        # All 5 required cookies should be listed as missing
        for cookie_name in ["SID", "HSID", "SSID", "APISID", "SAPISID"]:
            assert cookie_name in result["error"]

    def test_success_with_valid_cookies(self, mock_client):
        """Test successful save with all required cookies."""
        mock_tokens_instance = MagicMock()
        mock_cache_path = MagicMock()
        mock_cache_path.__str__ = lambda self: "/tmp/test-tokens"

        cookie_str = (
            "SID=s1; HSID=h1; SSID=ss1; "
            "APISID=a1; SAPISID=sa1; OTHER=o1"
        )

        with patch(
            "notebooklm_tools.core.auth.AuthTokens",
            return_value=mock_tokens_instance,
        ) as mock_auth_cls, patch(
            "notebooklm_tools.core.auth.save_tokens_to_cache"
        ) as mock_save, patch(
            "notebooklm_tools.core.auth.get_cache_path",
            return_value=mock_cache_path,
        ), patch(
            "notebooklm_tools.mcp.tools.auth.reset_client"
        ) as mock_reset:
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(cookies=cookie_str)

        assert result["status"] == "success"
        assert "essential cookies" in result["message"].lower() or "saved" in result["message"].lower()
        assert result["extracted_csrf"] is False
        assert result["extracted_session_id"] is False
        mock_save.assert_called_once_with(mock_tokens_instance)
        mock_reset.assert_called_once()

    def test_csrf_extraction_from_request_body(self, mock_client):
        """Test CSRF token is extracted from request_body containing at=TOKEN&."""
        mock_tokens_instance = MagicMock()
        mock_cache_path = MagicMock()
        mock_cache_path.__str__ = lambda self: "/tmp/test-tokens"

        cookie_str = (
            "SID=s1; HSID=h1; SSID=ss1; "
            "APISID=a1; SAPISID=sa1"
        )
        request_body = "f.req=some_data&at=MY_TOKEN&other=stuff"

        with patch(
            "notebooklm_tools.core.auth.AuthTokens",
            return_value=mock_tokens_instance,
        ) as mock_auth_cls, patch(
            "notebooklm_tools.core.auth.save_tokens_to_cache"
        ), patch(
            "notebooklm_tools.core.auth.get_cache_path",
            return_value=mock_cache_path,
        ), patch(
            "notebooklm_tools.mcp.tools.auth.reset_client"
        ):
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(cookies=cookie_str, request_body=request_body)

        assert result["status"] == "success"
        assert result["extracted_csrf"] is True
        # Verify AuthTokens was called with the extracted CSRF token
        call_kwargs = mock_auth_cls.call_args
        assert call_kwargs[1]["csrf_token"] == "MY_TOKEN" or call_kwargs.kwargs["csrf_token"] == "MY_TOKEN"

    def test_session_id_extraction_from_request_url(self, mock_client):
        """Test session_id is extracted from request_url containing f.sid=SID&."""
        mock_tokens_instance = MagicMock()
        mock_cache_path = MagicMock()
        mock_cache_path.__str__ = lambda self: "/tmp/test-tokens"

        cookie_str = (
            "SID=s1; HSID=h1; SSID=ss1; "
            "APISID=a1; SAPISID=sa1"
        )
        request_url = "https://notebooklm.google.com/_/LabsTailwindUi/data/batchexecute?rpcids=foo&f.sid=MY_SID&bl=boq"

        with patch(
            "notebooklm_tools.core.auth.AuthTokens",
            return_value=mock_tokens_instance,
        ) as mock_auth_cls, patch(
            "notebooklm_tools.core.auth.save_tokens_to_cache"
        ), patch(
            "notebooklm_tools.core.auth.get_cache_path",
            return_value=mock_cache_path,
        ), patch(
            "notebooklm_tools.mcp.tools.auth.reset_client"
        ):
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(cookies=cookie_str, request_url=request_url)

        assert result["status"] == "success"
        assert result["extracted_session_id"] is True
        # Verify AuthTokens was called with the extracted session ID
        call_kwargs = mock_auth_cls.call_args
        assert call_kwargs[1]["session_id"] == "MY_SID" or call_kwargs.kwargs["session_id"] == "MY_SID"
