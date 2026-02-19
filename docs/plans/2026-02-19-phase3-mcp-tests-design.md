# Phase 3 Design: MCP Tool Unit Tests + GitHub Actions CI

**Date:** 2026-02-19
**Status:** Approved

## Goal

Add unit tests for all 29 MCP tools (currently 0% coverage) and configure GitHub Actions CI.

## Approach

**Conftest + per-module tests** — same structure as `tests/services/`. Shared fixtures in `conftest.py`, one test file per MCP tool module.

## Test Structure

```
tests/mcp/
├── __init__.py
├── conftest.py           # mock_client fixture, reset_client helper
├── test_notebooks.py     # 6 tools: list, get, describe, create, rename, delete
├── test_sources.py       # 5 tools: list, add, delete, describe, get_content
├── test_chat.py          # 2 tools: query, configure_chat
├── test_studio.py        # 3 tools: create, status, delete
├── test_research.py      # 3 tools: start, status, import
├── test_notes.py         # 4 tools: create, list, update, delete
├── test_sharing.py       # 3 tools: status, public, invite
├── test_downloads.py     # 1 tool: download_artifact
├── test_exports.py       # 1 tool: export_artifact
└── test_auth.py          # 1 tool: save_auth_tokens
```

## Test Pattern

Each tool gets minimum 2 tests:

1. **Happy path** — mock service function return, verify `{"status": "success", ...}` with correct fields
2. **Error path** — service raises `ServiceError`, verify `{"status": "error", "error": "message"}`

Tools with special logic get additional tests:
- `notebook_delete` — confirm=False returns warning
- `source_add` — different source types (url, text, file)
- `studio_create` — type validation
- `save_auth_tokens` — token extraction and caching

## Conftest Design

```python
@pytest.fixture
def mock_client(monkeypatch):
    """Patch get_client() to return a MagicMock instead of creating a real client."""
    client = MagicMock()
    monkeypatch.setattr("notebooklm_tools.mcp.tools._utils._client", client)
    yield client
    monkeypatch.setattr("notebooklm_tools.mcp.tools._utils._client", None)
```

## GitHub Actions CI

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv run pytest -x --tb=short
```

No credentials, no e2e — unit tests with mocks only.

## Success Criteria

- All 29 MCP tools have at least happy path + error path tests
- ~80-90 new tests
- All existing tests (409) continue to pass
- CI green on Python 3.11 and 3.12

## Non-Goals

- No CLI command tests (Phase 3+)
- No modification to existing tests
- No e2e tests in CI
