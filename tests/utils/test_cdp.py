"""Regression tests for has_chrome_profile() Chrome cookie path detection.

has_chrome_profile() originally only checked Default/Cookies, missing modern
Chrome (>= v98) which moved cookies to Default/Network/Cookies. That made
Layer 3 (headless auth recovery) silently dead for any user with a recent
Chrome, so cookie expiry always required a manual `nlm login`.
"""

from unittest.mock import patch

from notebooklm_tools.utils.cdp import has_chrome_profile


def _make_profile(tmp_path, *, cookie_subpath: str | None):
    """Create a fake Chrome profile dir, optionally with a Cookies stub."""
    if cookie_subpath:
        cookies = tmp_path / cookie_subpath
        cookies.parent.mkdir(parents=True, exist_ok=True)
        # Empty file is enough; has_chrome_profile only checks existence.
        cookies.write_bytes(b"")
    return tmp_path


def test_has_chrome_profile_modern_chrome(tmp_path):
    """Chrome >= v98 stores cookies at Default/Network/Cookies."""
    profile_dir = _make_profile(tmp_path, cookie_subpath="Default/Network/Cookies")
    with patch(
        "notebooklm_tools.utils.cdp.get_chrome_profile_dir",
        return_value=profile_dir,
    ):
        assert has_chrome_profile() is True


def test_has_chrome_profile_legacy_chrome(tmp_path):
    """Older Chrome stored cookies at Default/Cookies."""
    profile_dir = _make_profile(tmp_path, cookie_subpath="Default/Cookies")
    with patch(
        "notebooklm_tools.utils.cdp.get_chrome_profile_dir",
        return_value=profile_dir,
    ):
        assert has_chrome_profile() is True


def test_has_chrome_profile_empty_returns_false(tmp_path):
    """A profile dir with no cookies file at any known location is unusable."""
    profile_dir = _make_profile(tmp_path, cookie_subpath=None)
    with patch(
        "notebooklm_tools.utils.cdp.get_chrome_profile_dir",
        return_value=profile_dir,
    ):
        assert has_chrome_profile() is False
