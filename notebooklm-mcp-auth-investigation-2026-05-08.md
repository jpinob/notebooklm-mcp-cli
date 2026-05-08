# NotebookLM MCP CLI — Auth investigation post-mortem

**Date:** 2026-05-08
**Affected version:** notebooklm-mcp-cli v0.3.3 (fork jpinob/notebooklm-mcp-cli)
**Platform:** Windows 11 (native, no WSL), Chrome 143, Python 3.11
**Status:** Fixed locally, pending upstream PR

## TL;DR

The "auto-refresh" promised by the README was silently broken on any installation with Chrome ≥ v98. Two independent bugs combined to make every cookie expiry require a manual `nlm login`: the headless recovery layer never ran (looked for cookies at the wrong filesystem path), and any partial refresh that did succeed wrote to a legacy cache file that the loader had stopped reading. Two small patches restore the documented behaviour.

## Real auth model (not what the README says)

Storage layout under `~/.notebooklm-mcp-cli/`:

| Path | Role | Updated by |
|---|---|---|
| `profiles/<name>/cookies.json` | **Canonical** Google session cookies (live store) | `nlm login`, `nlm login --check` |
| `profiles/<name>/metadata.json` | CSRF token, session id, email, last_validated | `nlm login`, `nlm login --check`, `_update_cached_tokens` (after fix) |
| `auth.json` | Legacy single-profile cache, **fallback only** | Pre-multi-profile installs, `_update_cached_tokens` (before fix) |
| `chrome-profiles/<name>/Default/Network/Cookies` | Chrome profile sqlite with persistent Google session — feeds Layer 3 headless recovery | `nlm login` (via Chrome itself) |

Loader behaviour (`core/auth.py:73-118 load_cached_tokens`):

1. If `profiles/<active>/` exists → read it, ignore `auth.json` entirely
2. Else → fall back to `auth.json`

This is a "preferred + fallback" pattern. Anything writing to `auth.json` while a profile exists is writing to a dead path.

Recovery pipeline (`core/base.py:583-604 _call_rpc`, fires on RPC error 16 or HTTP 401/403):

| Layer | Function | What it does |
|---|---|---|
| 1 | `_refresh_auth_tokens` | Fetches notebooklm.google.com homepage with stored cookies; extracts new CSRF (`SNlM0e`) and session id (`FdrFJe`) from the HTML. Fails with `ValueError` if the request redirects to `accounts.google.com` (cookies dead). |
| 2 | `_try_reload_or_headless_auth` (reload branch) | Re-reads `cookies.json` from disk, blanks the in-memory CSRF/session, retries Layer 1. Useful if another terminal ran `nlm login` between attempts. |
| 3 | `_try_reload_or_headless_auth` → `run_headless_auth` | Launches Chrome headless against the saved profile, lets Google auto-issue fresh cookies via the persistent session, extracts them via CDP `Network.getAllCookies`. |

The README implies these are transparent. They aren't, on Windows or anywhere with Chrome ≥ v98.

## The two bugs

### 🔴 Bug 1 — Layer 3 dead because of the wrong cookie path

`utils/cdp.py:675-684` (before fix):

```python
def has_chrome_profile(profile_name: str = "default") -> bool:
    profile_dir = get_chrome_profile_dir(profile_name)
    cookies_file = profile_dir / "Default" / "Cookies"
    return cookies_file.exists()
```

Chrome moved its cookie store from `Default/Cookies` to `Default/Network/Cookies` around v98 (2022). Verified on this system:

- `chrome-profiles/default/Default/Cookies` → ABSENT
- `chrome-profiles/default/Default/Network/Cookies` → 61 KB, modified the same day as the last login
- `chrome-profiles/default/Default/Network/NetworkDataMigrated` → present since first profile creation

`run_headless_auth` (`utils/cdp.py:754`) gates on `has_chrome_profile()`. With the legacy path it always returned `False`, so headless recovery returned `None` immediately, every time. Layer 3 had been a no-op for the lifetime of every profile created on a modern Chrome.

### 🟡 Bug 2 — Split-brain between the legacy and profile cache

`core/base.py:666-694 _update_cached_tokens` and `utils/cdp.py:817` (before fix) both wrote refreshed tokens to `auth.json` via `save_tokens_to_cache`. But `load_cached_tokens` ignores `auth.json` whenever a profile exists. Net effect with a profile active: refreshed tokens vanished into a file no consumer read. The next client init read the stale `metadata.json`.

Evidence: `auth.json` on this system was last modified 78 days before the investigation, despite the user running NotebookLM commands constantly.

## Symptom and reconstruction

What the user saw:

```
$ nlm login --check
RPC Error 16: Authentication expired
[traceback]

$ nlm login --check     # minutes later
✓ Authentication valid! Notebooks found: 48
```

`auth.json` did not change between the two runs. The user *thought* they had not run anything else in between, but `profiles/default/cookies.json` had a fresh timestamp matching exactly the gap. The reconstruction:

1. Cookies in `cookies.json` had aged out
2. Layer 1 redirected to `accounts.google.com` → `ValueError`
3. Layer 2 reloaded the same stale `cookies.json` → same fail
4. Layer 3 returned `None` immediately (Bug 1) — never tried headless
5. `AuthenticationError` bubbled up
6. User ran `nlm login` (interactive Chrome window), didn't register it as "running something" because the prompt felt routine
7. Login wrote a fresh `cookies.json`
8. Second `--check` worked

If Layer 3 had been functional, Chrome's persistent Google session in `Default/Network/Cookies` would have re-issued fresh cookies headless and the user would never have seen step 1.

## Fix applied

Three edits, all in the local repo at `E:\DEV\projects\notebooklm-mcp-cli\`:

### Edit 1 — `src/notebooklm_tools/utils/cdp.py` (`has_chrome_profile`)

Detect both legacy and modern cookie paths:

```python
def has_chrome_profile(profile_name: str = "default") -> bool:
    profile_dir = get_chrome_profile_dir(profile_name)
    legacy = profile_dir / "Default" / "Cookies"
    modern = profile_dir / "Default" / "Network" / "Cookies"
    return legacy.exists() or modern.exists()
```

### Edit 2 — `src/notebooklm_tools/utils/cdp.py` (`run_headless_auth` persistence)

After a successful headless extraction, persist to the active profile (canonical store) when one exists; fall back to legacy `auth.json` only when no profile has been created yet:

```python
try:
    from notebooklm_tools.core.auth import get_auth_manager
    manager = get_auth_manager(profile_name)
    if manager.profile_exists():
        prev_email = ""
        try:
            prev_email = manager.load_profile().email or ""
        except Exception:
            pass
        manager.save_profile(
            cookies=cookies,
            csrf_token=csrf_token or "",
            session_id=session_id or "",
            email=prev_email,
        )
    else:
        save_tokens_to_cache(tokens)
except Exception:
    save_tokens_to_cache(tokens)
```

### Edit 3 — `src/notebooklm_tools/core/base.py` (`_update_cached_tokens`)

Same routing logic for the CSRF refresh path. Profile gets `metadata.json` updates; legacy cache only used when no profile exists:

```python
manager = get_auth_manager()
if manager.profile_exists():
    profile = manager.load_profile()
    manager.save_profile(
        cookies=profile.cookies,
        csrf_token=self.csrf_token,
        session_id=self._session_id,
        email=profile.email,
    )
    return
# else: existing legacy path unchanged
```

### Reinstall

```powershell
Stop-Process -Id <notebooklm-mcp.exe PID> -Force   # release directory lock
uv cache clean
uv tool uninstall notebooklm-mcp-cli
cd E:\DEV\projects\notebooklm-mcp-cli
uv tool install --force --reinstall .
```

## Validation

Immediate:

```
$ nlm --version
nlm version 0.3.3

$ nlm login --check
✓ Authentication valid! Notebooks found: 48

# Bug 1 fix:
$ python -c "from notebooklm_tools.utils.cdp import has_chrome_profile; print(has_chrome_profile())"
True            # before fix: False

# Bug 2 fix — force CSRF refresh, observe which file gets updated:
auth.json       19/02/2026 22:11:21      ← unchanged (correct: ignored when profile exists)
metadata.json   08/05/2026 16:44:39      ← updated (correct: canonical store)

# Smoke tests:
$ pytest tests/test_auth_migration.py tests/mcp/test_auth.py -v
18 passed (2 unrelated failures from a fastmcp/mcp.types env issue, pre-existing)
```

End-to-end behaviour the user wanted:

- Cookies expire over days/weeks — Layer 1 still extracts fresh CSRF until cookies fully die
- When cookies finally do die, Layer 3 now actually runs: Chrome headless re-issues a session via the persistent Google login in `Default/Network/Cookies`, fresh cookies land in `cookies.json`, the user never sees a prompt
- Only when the underlying Google session in the Chrome profile expires (months, typically only when password is changed or 2FA is rotated) does the user need a real `nlm login`

## Lessons reusable for other MCPs

These are bugs the *kind*, not bugs the project. Any MCP server with cookie-based auth and a recovery path can hit them.

1. **Treat "auto-refresh" claims as untested until you've forced a refresh and watched a file change.** Both bugs survived because the recovery path looked plausible from the README and the unit tests only checked imports.

2. **A "preferred location with legacy fallback" loader needs a corresponding writer.** `load_cached_tokens` was forked into multi-profile but the writers stayed pointed at the legacy file. Whenever a loader has a priority order, every writer needs the same routing or you get split-brain. Audit pattern: grep for the legacy path's writer and confirm every call site.

3. **Vendor file paths drift.** Chrome's cookie move from `Default/Cookies` to `Default/Network/Cookies` was a 4-year-old change at the time of this bug. Any code that probes a vendor's filesystem layout should accept multiple locations or compute it from the vendor's own state files. The presence of `NetworkDataMigrated` is a stronger signal than the absence of `Cookies`.

4. **Silent `try/except: pass` is where bugs hide.** `_update_cached_tokens` wraps the cache write in a bare `except`. If the legacy path had been deleted instead of left orphaned, the bug would have been obvious. Bare excepts mask both intended (caching is best-effort) and unintended (writer is talking to nobody) failures. At minimum, log the swallowed exception at DEBUG.

5. **Test the recovery path, not just the import.** `test_auth_migration.py` only asserts `callable(has_chrome_profile)`. A single test that constructs a temp profile dir with `Network/Cookies` and asserts `has_chrome_profile() is True` would have failed loudly on the day the constant was wrong.

6. **Multi-profile migrations need an end-to-end smoke run.** When auth is rebuilt from `auth.json` to `profiles/<name>/`, somebody should manually expire cookies and verify the recovery layers actually use the new store. This was probably skipped because the happy path (login + read) worked fine.

## Pending follow-ups

- Open PR upstream to `jacob-bd/notebooklm-mcp-cli` from `jpinob/notebooklm-mcp-cli`. The fix is mechanical, additive, and version-agnostic. Other Chrome ≥ v98 users (most users) are silently affected.
- Verify whether v0.6.6 already includes either fix; if so, this patch can fold into a clean upgrade rather than a fork-only patch.
- Consider replacing the bare `except` in `_update_cached_tokens` with a `logger.debug("token cache update failed: %s", exc)` to make future regressions of this class observable.

## Appendix — Real Claude ↔ NotebookLM alternatives (parking lot)

Not investigated in depth, just noting for future:

- **NotebookLM API has no official public surface.** All access is via the same internal `batchexecute` protocol this fork reverse-engineers. No Workspace API, no OAuth scope, no Cloud product offers it. Every alternative is some flavour of the same approach.
- **Google AI Studio + Gemini API + custom RAG** offers most of what NotebookLM does (source-grounded chat, audio overview, summaries) via supported APIs, at the cost of building the pipeline yourself. Probably the only sustainable long-term path if `batchexecute` semantics drift.
- **Browser automation (Playwright/Selenium) instead of CDP** is structurally similar to what this fork does and carries the same risk surface; not an improvement.
- **NotebookLM Plus / Workspace tier** does not expose new APIs at the time of writing — it just changes quotas and Workspace integration. Useful operationally, doesn't help architecturally.

Bottom line: this fork is the realistic option until Google ships a real API. Worth keeping the auth recovery healthy.
