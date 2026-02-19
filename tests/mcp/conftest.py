"""Shared fixtures for MCP tool tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_client(monkeypatch):
    """Patch the global _client so get_client() returns our mock.

    This avoids needing real auth tokens. The MCP tools call get_client()
    which checks the global _client in _utils.py — if it's not None,
    it returns it directly without trying to load cookies.
    """
    client = MagicMock()
    monkeypatch.setattr("notebooklm_tools.mcp.tools._utils._client", client)
    yield client
    monkeypatch.setattr("notebooklm_tools.mcp.tools._utils._client", None)
