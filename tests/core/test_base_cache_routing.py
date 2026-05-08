"""Regression tests for _update_cached_tokens cache-store routing.

_update_cached_tokens originally always wrote refreshed tokens to auth.json
(legacy single-profile cache). When a multi-profile installation was active,
load_cached_tokens ignored auth.json and read profiles/<name>/, so refreshed
tokens vanished into a file no consumer read — a silent split-brain.
"""

from unittest.mock import MagicMock, patch

from notebooklm_tools.core.base import BaseClient


def _make_client():
    """Construct a BaseClient skipping the real refresh in __init__."""
    with patch.object(BaseClient, "_refresh_auth_tokens"):
        client = BaseClient(
            cookies={"SID": "x"},
            csrf_token="csrf-NEW",
            session_id="sid-NEW",
        )
    return client


def test_update_cached_tokens_writes_to_profile_when_present():
    """When a profile is active, refresh must update profiles/<name>/ — not auth.json."""
    client = _make_client()

    fake_manager = MagicMock()
    fake_manager.profile_exists.return_value = True
    fake_profile = MagicMock(cookies={"SID": "x"}, email="test@example.com")
    fake_manager.load_profile.return_value = fake_profile

    with patch(
        "notebooklm_tools.core.auth.get_auth_manager", return_value=fake_manager
    ), patch(
        "notebooklm_tools.core.auth.save_tokens_to_cache"
    ) as legacy_writer:
        client._update_cached_tokens()

    fake_manager.save_profile.assert_called_once()
    kwargs = fake_manager.save_profile.call_args.kwargs
    assert kwargs["csrf_token"] == "csrf-NEW"
    assert kwargs["session_id"] == "sid-NEW"
    assert kwargs["email"] == "test@example.com"
    legacy_writer.assert_not_called()  # split-brain regression guard


def test_update_cached_tokens_falls_back_to_legacy_when_no_profile():
    """When no profile exists, refresh must still write to auth.json (back-compat)."""
    client = _make_client()

    fake_manager = MagicMock()
    fake_manager.profile_exists.return_value = False

    with patch(
        "notebooklm_tools.core.auth.get_auth_manager", return_value=fake_manager
    ), patch(
        "notebooklm_tools.core.auth.save_tokens_to_cache"
    ) as legacy_writer, patch(
        "notebooklm_tools.core.auth.load_cached_tokens", return_value=None
    ):
        client._update_cached_tokens()

    legacy_writer.assert_called_once()
    fake_manager.save_profile.assert_not_called()
