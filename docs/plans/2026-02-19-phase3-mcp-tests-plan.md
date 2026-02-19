# Phase 3: MCP Tool Unit Tests + GitHub Actions CI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add unit tests for all 29 MCP tools (0% → 100% coverage) and configure GitHub Actions CI.

**Architecture:** Each MCP tool is a thin wrapper: `get_client()` → service call → `{"status": "success/error", ...}`. Tests mock `get_client()` via monkeypatch on the global `_client` in `_utils.py`, then mock service functions to control return values. One test file per MCP tool module, matching existing `tests/services/` structure.

**Tech Stack:** pytest, unittest.mock (MagicMock, patch), pytest-asyncio (for download_artifact), GitHub Actions with astral-sh/setup-uv

---

### Task 1: Test Infrastructure — conftest.py + __init__.py

**Files:**
- Create: `tests/mcp/__init__.py`
- Create: `tests/mcp/conftest.py`

**Step 1: Create the test package and conftest**

`tests/mcp/__init__.py` — empty file.

`tests/mcp/conftest.py`:

```python
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
    # Reset after test
    monkeypatch.setattr("notebooklm_tools.mcp.tools._utils._client", None)
```

**Step 2: Verify conftest loads**

Run: `uv run pytest tests/mcp/ --co -q`
Expected: `no tests ran` (0 tests collected, no errors)

**Step 3: Commit**

```bash
git add tests/mcp/__init__.py tests/mcp/conftest.py
git commit -m "test: add MCP test infrastructure with mock_client fixture"
```

---

### Task 2: Notebook Tools Tests (6 tools)

**Files:**
- Create: `tests/mcp/test_notebooks.py`
- Reference: `src/notebooklm_tools/mcp/tools/notebooks.py`

**Step 1: Write tests**

```python
"""Tests for MCP notebook tools."""

import pytest
from unittest.mock import patch, MagicMock
from notebooklm_tools.services.errors import ServiceError, NotFoundError


class TestNotebookList:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.list_notebooks.return_value = {
                "notebooks": [{"id": "nb-1", "title": "Test"}],
                "count": 1,
                "owned_count": 1,
                "shared_count": 0,
            }
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            result = notebook_list()

            assert result["status"] == "success"
            assert result["count"] == 1
            assert len(result["notebooks"]) == 1
            svc.list_notebooks.assert_called_once_with(mock_client, 100)

    def test_custom_max_results(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.list_notebooks.return_value = {"notebooks": [], "count": 0}
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            notebook_list(max_results=5)
            svc.list_notebooks.assert_called_once_with(mock_client, 5)

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.list_notebooks.side_effect = ServiceError("API unavailable")
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            result = notebook_list()

            assert result["status"] == "error"
            assert "API unavailable" in result["error"]

    def test_unexpected_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.list_notebooks.side_effect = RuntimeError("connection lost")
            from notebooklm_tools.mcp.tools.notebooks import notebook_list

            result = notebook_list()

            assert result["status"] == "error"
            assert "connection lost" in result["error"]


class TestNotebookGet:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.get_notebook.return_value = {
                "notebook_id": "nb-1",
                "title": "My Notebook",
                "source_count": 3,
                "url": "https://notebooklm.google.com/notebook/nb-1",
                "sources": [{"id": "s-1", "title": "Source 1"}],
            }
            from notebooklm_tools.mcp.tools.notebooks import notebook_get

            result = notebook_get("nb-1")

            assert result["status"] == "success"
            assert result["notebook"]["id"] == "nb-1"
            assert result["notebook"]["title"] == "My Notebook"
            assert len(result["sources"]) == 1

    def test_not_found(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.get_notebook.side_effect = ServiceError("Notebook not found")
            from notebooklm_tools.mcp.tools.notebooks import notebook_get

            result = notebook_get("bad-id")
            assert result["status"] == "error"


class TestNotebookDescribe:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.describe_notebook.return_value = {
                "summary": "A notebook about AI",
                "suggested_topics": ["topic1", "topic2"],
            }
            from notebooklm_tools.mcp.tools.notebooks import notebook_describe

            result = notebook_describe("nb-1")

            assert result["status"] == "success"
            assert result["summary"] == "A notebook about AI"
            assert len(result["suggested_topics"]) == 2

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.describe_notebook.side_effect = ServiceError("Failed")
            from notebooklm_tools.mcp.tools.notebooks import notebook_describe

            result = notebook_describe("nb-1")
            assert result["status"] == "error"


class TestNotebookCreate:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.create_notebook.return_value = {
                "notebook_id": "nb-new",
                "title": "New Notebook",
                "url": "https://notebooklm.google.com/notebook/nb-new",
                "message": "Created",
            }
            from notebooklm_tools.mcp.tools.notebooks import notebook_create

            result = notebook_create(title="New Notebook")

            assert result["status"] == "success"
            assert result["notebook"]["id"] == "nb-new"
            assert result["message"] == "Created"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.create_notebook.side_effect = ServiceError("Quota exceeded")
            from notebooklm_tools.mcp.tools.notebooks import notebook_create

            result = notebook_create()
            assert result["status"] == "error"
            assert "Quota exceeded" in result["error"]


class TestNotebookRename:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.rename_notebook.return_value = {"message": "Renamed to 'New Title'"}
            from notebooklm_tools.mcp.tools.notebooks import notebook_rename

            result = notebook_rename("nb-1", "New Title")

            assert result["status"] == "success"
            svc.rename_notebook.assert_called_once_with(mock_client, "nb-1", "New Title")

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.rename_notebook.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.notebooks import notebook_rename

            result = notebook_rename("bad", "Title")
            assert result["status"] == "error"


class TestNotebookDelete:
    def test_confirm_false_returns_warning(self, mock_client):
        from notebooklm_tools.mcp.tools.notebooks import notebook_delete

        result = notebook_delete("nb-1", confirm=False)

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "warning" in result

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.delete_notebook.return_value = {"message": "Deleted"}
            from notebooklm_tools.mcp.tools.notebooks import notebook_delete

            result = notebook_delete("nb-1", confirm=True)

            assert result["status"] == "success"
            svc.delete_notebook.assert_called_once_with(mock_client, "nb-1")

    def test_confirm_true_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notebooks.notebooks_service") as svc:
            svc.delete_notebook.side_effect = ServiceError("Cannot delete shared notebook")
            from notebooklm_tools.mcp.tools.notebooks import notebook_delete

            result = notebook_delete("nb-1", confirm=True)
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_notebooks.py -v`
Expected: 14 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_notebooks.py
git commit -m "test: add MCP notebook tool tests (6 tools, 14 tests)"
```

---

### Task 3: Source Tools Tests (6 tools)

**Files:**
- Create: `tests/mcp/test_sources.py`
- Reference: `src/notebooklm_tools/mcp/tools/sources.py`

**Step 1: Write tests**

```python
"""Tests for MCP source tools."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestSourceAdd:
    def test_url_source_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.add_source.return_value = {
                "source_id": "src-1",
                "title": "Example",
                "source_type": "url",
            }
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add("nb-1", "url", url="https://example.com")

            assert result["status"] == "success"
            assert result["ready"] is False  # wait=False default
            assert result["source_id"] == "src-1"

    def test_text_source_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.add_source.return_value = {"source_id": "src-2", "title": "Notes"}
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add("nb-1", "text", text="Some notes", title="Notes")

            assert result["status"] == "success"
            svc.add_source.assert_called_once()
            call_kwargs = svc.add_source.call_args
            assert call_kwargs[1]["text"] == "Some notes"
            assert call_kwargs[1]["title"] == "Notes"

    def test_wait_flag(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.add_source.return_value = {"source_id": "src-3"}
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add("nb-1", "url", url="https://x.com", wait=True)
            assert result["ready"] is True

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.add_source.side_effect = ServiceError("Invalid URL")
            from notebooklm_tools.mcp.tools.sources import source_add

            result = source_add("nb-1", "url", url="bad")
            assert result["status"] == "error"
            assert "Invalid URL" in result["error"]


class TestSourceListDrive:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.list_drive_sources.return_value = {
                "sources": [{"id": "s-1", "type": "drive"}],
                "count": 1,
            }
            from notebooklm_tools.mcp.tools.sources import source_list_drive

            result = source_list_drive("nb-1")

            assert result["status"] == "success"
            assert result["notebook_id"] == "nb-1"
            assert result["count"] == 1

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.list_drive_sources.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.sources import source_list_drive

            result = source_list_drive("nb-1")
            assert result["status"] == "error"


class TestSourceSyncDrive:
    def test_confirm_false(self, mock_client):
        from notebooklm_tools.mcp.tools.sources import source_sync_drive

        result = source_sync_drive(["s-1"], confirm=False)

        assert result["status"] == "error"
        assert "not confirmed" in result["error"].lower()
        assert "hint" in result

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.sync_drive_sources.return_value = [
                {"source_id": "s-1", "synced": True},
                {"source_id": "s-2", "synced": False},
            ]
            from notebooklm_tools.mcp.tools.sources import source_sync_drive

            result = source_sync_drive(["s-1", "s-2"], confirm=True)

            assert result["status"] == "success"
            assert result["synced_count"] == 1
            assert result["total_count"] == 2

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.sync_drive_sources.side_effect = ServiceError("Sync failed")
            from notebooklm_tools.mcp.tools.sources import source_sync_drive

            result = source_sync_drive(["s-1"], confirm=True)
            assert result["status"] == "error"


class TestSourceDelete:
    def test_confirm_false(self, mock_client):
        from notebooklm_tools.mcp.tools.sources import source_delete

        result = source_delete("s-1", confirm=False)

        assert result["status"] == "error"
        assert "warning" in result

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            from notebooklm_tools.mcp.tools.sources import source_delete

            result = source_delete("s-1", confirm=True)

            assert result["status"] == "success"
            assert "s-1" in result["message"]

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.delete_source.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.sources import source_delete

            result = source_delete("s-1", confirm=True)
            assert result["status"] == "error"


class TestSourceDescribe:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.describe_source.return_value = {
                "summary": "About **AI**",
                "keywords": ["AI", "ML"],
            }
            from notebooklm_tools.mcp.tools.sources import source_describe

            result = source_describe("s-1")

            assert result["status"] == "success"
            assert result["summary"] == "About **AI**"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.describe_source.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.sources import source_describe

            result = source_describe("s-1")
            assert result["status"] == "error"


class TestSourceGetContent:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.get_source_content.return_value = {
                "content": "Full text here",
                "title": "Doc",
                "source_type": "url",
                "char_count": 14,
            }
            from notebooklm_tools.mcp.tools.sources import source_get_content

            result = source_get_content("s-1")

            assert result["status"] == "success"
            assert result["content"] == "Full text here"
            assert result["char_count"] == 14

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sources.sources_service") as svc:
            svc.get_source_content.side_effect = ServiceError("Source not indexed")
            from notebooklm_tools.mcp.tools.sources import source_get_content

            result = source_get_content("s-1")
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_sources.py -v`
Expected: 18 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_sources.py
git commit -m "test: add MCP source tool tests (6 tools, 18 tests)"
```

---

### Task 4: Chat Tools Tests (2 tools)

**Files:**
- Create: `tests/mcp/test_chat.py`
- Reference: `src/notebooklm_tools/mcp/tools/chat.py`

**Step 1: Write tests**

```python
"""Tests for MCP chat tools."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestNotebookQuery:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.query.return_value = {
                "answer": "The answer is 42.",
                "conversation_id": "conv-1",
                "sources_used": ["s-1"],
            }
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query("nb-1", "What is the answer?")

            assert result["status"] == "success"
            assert result["answer"] == "The answer is 42."

    def test_with_source_ids(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.query.return_value = {"answer": "Filtered answer"}
            from notebooklm_tools.mcp.tools.chat import notebook_query

            notebook_query("nb-1", "Q?", source_ids=["s-1", "s-2"])

            call_kwargs = svc.query.call_args[1]
            assert call_kwargs["source_ids"] == ["s-1", "s-2"]

    def test_with_conversation_id(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.query.return_value = {"answer": "Follow-up"}
            from notebooklm_tools.mcp.tools.chat import notebook_query

            notebook_query("nb-1", "Follow up?", conversation_id="conv-1")

            call_kwargs = svc.query.call_args[1]
            assert call_kwargs["conversation_id"] == "conv-1"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.query.side_effect = ServiceError("Query failed")
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query("nb-1", "Q?")
            assert result["status"] == "error"

    def test_unexpected_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.query.side_effect = TimeoutError("timed out")
            from notebooklm_tools.mcp.tools.chat import notebook_query

            result = notebook_query("nb-1", "Q?")
            assert result["status"] == "error"
            assert "timed out" in result["error"]


class TestChatConfigure:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.configure_chat.return_value = {
                "message": "Chat configured",
                "goal": "learning_guide",
            }
            from notebooklm_tools.mcp.tools.chat import chat_configure

            result = chat_configure("nb-1", goal="learning_guide")

            assert result["status"] == "success"
            assert result["goal"] == "learning_guide"

    def test_custom_prompt(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.configure_chat.return_value = {"message": "Configured"}
            from notebooklm_tools.mcp.tools.chat import chat_configure

            chat_configure("nb-1", goal="custom", custom_prompt="Be concise")

            call_kwargs = svc.configure_chat.call_args[1]
            assert call_kwargs["custom_prompt"] == "Be concise"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.chat.chat_service") as svc:
            svc.configure_chat.side_effect = ServiceError("Invalid goal")
            from notebooklm_tools.mcp.tools.chat import chat_configure

            result = chat_configure("nb-1", goal="bad")
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_chat.py -v`
Expected: 8 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_chat.py
git commit -m "test: add MCP chat tool tests (2 tools, 8 tests)"
```

---

### Task 5: Studio Tools Tests (3 tools)

**Files:**
- Create: `tests/mcp/test_studio.py`
- Reference: `src/notebooklm_tools/mcp/tools/studio.py`

**Step 1: Write tests**

```python
"""Tests for MCP studio tools."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError, ValidationError


class TestStudioCreate:
    def test_invalid_type_returns_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.validate_artifact_type.side_effect = ValidationError("Invalid type: bad")
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create("nb-1", "bad", confirm=True)

            assert result["status"] == "error"
            assert "Invalid type" in result["error"]

    def test_confirm_false_returns_pending(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.validate_artifact_type.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create("nb-1", "audio", confirm=False)

            assert result["status"] == "pending_confirmation"
            assert "settings" in result
            assert result["settings"]["artifact_type"] == "audio"

    def test_confirm_false_audio_settings(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.validate_artifact_type.return_value = None
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create(
                "nb-1", "audio", confirm=False,
                audio_format="debate", audio_length="short",
            )

            assert result["settings"]["format"] == "debate"
            assert result["settings"]["length"] == "short"

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.validate_artifact_type.return_value = None
            svc.create_artifact.return_value = {
                "artifact_id": "art-1",
                "message": "Audio creation started",
            }
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create("nb-1", "audio", confirm=True)

            assert result["status"] == "success"
            assert result["artifact_id"] == "art-1"
            assert "notebook_url" in result

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.validate_artifact_type.return_value = None
            svc.create_artifact.side_effect = ServiceError("Creation failed")
            from notebooklm_tools.mcp.tools.studio import studio_create

            result = studio_create("nb-1", "audio", confirm=True)
            assert result["status"] == "error"


class TestStudioStatus:
    def test_status_action(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.get_studio_status.return_value = {
                "total": 2,
                "completed": 1,
                "in_progress": 1,
                "artifacts": [
                    {"id": "art-1", "type": "audio", "status": "completed"},
                    {"id": "art-2", "type": "video", "status": "in_progress"},
                ],
            }
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status("nb-1")

            assert result["status"] == "success"
            assert result["summary"]["total"] == 2
            assert result["summary"]["completed"] == 1
            assert len(result["artifacts"]) == 2

    def test_rename_action(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.rename_artifact.return_value = {"new_title": "Renamed"}
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status(
                "nb-1", action="rename",
                artifact_id="art-1", new_title="Renamed",
            )

            assert result["status"] == "success"
            assert result["action"] == "rename"
            assert "Renamed" in result["message"]

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.get_studio_status.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.studio import studio_status

            result = studio_status("nb-1")
            assert result["status"] == "error"


class TestStudioDelete:
    def test_confirm_false(self, mock_client):
        from notebooklm_tools.mcp.tools.studio import studio_delete

        result = studio_delete("nb-1", "art-1", confirm=False)

        assert result["status"] == "error"
        assert "warning" in result
        assert "hint" in result

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            from notebooklm_tools.mcp.tools.studio import studio_delete

            result = studio_delete("nb-1", "art-1", confirm=True)

            assert result["status"] == "success"
            assert "art-1" in result["message"]
            svc.delete_artifact.assert_called_once_with(mock_client, "art-1", "nb-1")

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.studio.studio_service") as svc:
            svc.delete_artifact.side_effect = ServiceError("Artifact busy")
            from notebooklm_tools.mcp.tools.studio import studio_delete

            result = studio_delete("nb-1", "art-1", confirm=True)
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_studio.py -v`
Expected: 11 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_studio.py
git commit -m "test: add MCP studio tool tests (3 tools, 11 tests)"
```

---

### Task 6: Research Tools Tests (3 tools)

**Files:**
- Create: `tests/mcp/test_research.py`
- Reference: `src/notebooklm_tools/mcp/tools/research.py`

**Note:** `research_status` returns `result` directly (not `{"status": "success", **result}`) — this is a known inconsistency documented in ARCHITECTURE.md gap analysis.

**Step 1: Write tests**

```python
"""Tests for MCP research tools."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestResearchStart:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.start_research.return_value = {
                "task_id": "task-1",
                "notebook_id": "nb-1",
                "message": "Research started",
            }
            from notebooklm_tools.mcp.tools.research import research_start

            result = research_start("quantum computing")

            assert result["status"] == "success"
            assert result["task_id"] == "task-1"

    def test_with_options(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.start_research.return_value = {"task_id": "task-2"}
            from notebooklm_tools.mcp.tools.research import research_start

            research_start(
                "AI agents", source="drive", mode="deep",
                notebook_id="nb-1", title="AI Research",
            )

            svc.start_research.assert_called_once_with(
                mock_client, "nb-1", "AI agents",
                source="drive", mode="deep",
            )

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.start_research.side_effect = ServiceError("Research unavailable")
            from notebooklm_tools.mcp.tools.research import research_start

            result = research_start("test")
            assert result["status"] == "error"


class TestResearchStatus:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.poll_research.return_value = {
                "status": "completed",
                "sources_found": 10,
                "report": "Summary...",
            }
            from notebooklm_tools.mcp.tools.research import research_status

            result = research_status("nb-1")

            # Note: research_status returns result directly (known inconsistency)
            assert result["status"] == "completed"
            assert result["sources_found"] == 10

    def test_with_task_id(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.poll_research.return_value = {"status": "in_progress"}
            from notebooklm_tools.mcp.tools.research import research_status

            research_status("nb-1", task_id="task-1", query="AI")

            svc.poll_research.assert_called_once_with(
                mock_client, "nb-1",
                task_id="task-1", query="AI", compact=True,
            )

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.poll_research.side_effect = ServiceError("Polling failed")
            from notebooklm_tools.mcp.tools.research import research_status

            result = research_status("nb-1")
            assert result["status"] == "error"


class TestResearchImport:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.import_research.return_value = {
                "imported_count": 5,
                "sources": [{"id": "s-1"}],
            }
            from notebooklm_tools.mcp.tools.research import research_import

            result = research_import("nb-1", "task-1")

            assert result["status"] == "success"
            assert result["imported_count"] == 5

    def test_with_indices(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.import_research.return_value = {"imported_count": 2}
            from notebooklm_tools.mcp.tools.research import research_import

            research_import("nb-1", "task-1", source_indices=[0, 2, 4])

            svc.import_research.assert_called_once_with(
                mock_client, "nb-1", "task-1",
                source_indices=[0, 2, 4],
            )

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.research.research_service") as svc:
            svc.import_research.side_effect = ServiceError("Task not found")
            from notebooklm_tools.mcp.tools.research import research_import

            result = research_import("nb-1", "bad-task")
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_research.py -v`
Expected: 9 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_research.py
git commit -m "test: add MCP research tool tests (3 tools, 9 tests)"
```

---

### Task 7: Notes Tool Tests (1 unified tool, 4 actions)

**Files:**
- Create: `tests/mcp/test_notes.py`
- Reference: `src/notebooklm_tools/mcp/tools/notes.py`

**Step 1: Write tests**

```python
"""Tests for MCP notes tool (unified with action parameter)."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestNoteCreate:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as svc:
            svc.create_note.return_value = {
                "note_id": "note-1",
                "message": "Note created",
            }
            from notebooklm_tools.mcp.tools.notes import note

            result = note("nb-1", "create", content="My note", title="Title")

            assert result["status"] == "success"
            assert result["action"] == "create"
            assert result["note_id"] == "note-1"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as svc:
            svc.create_note.side_effect = ServiceError("Failed")
            from notebooklm_tools.mcp.tools.notes import note

            result = note("nb-1", "create", content="text")
            assert result["status"] == "error"


class TestNoteList:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as svc:
            svc.list_notes.return_value = {
                "notes": [{"id": "n-1", "title": "Note 1"}],
                "count": 1,
            }
            from notebooklm_tools.mcp.tools.notes import note

            result = note("nb-1", "list")

            assert result["status"] == "success"
            assert result["action"] == "list"
            assert result["count"] == 1


class TestNoteUpdate:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as svc:
            svc.update_note.return_value = {"message": "Updated"}
            from notebooklm_tools.mcp.tools.notes import note

            result = note("nb-1", "update", note_id="n-1", content="New content")

            assert result["status"] == "success"
            assert result["action"] == "update"

    def test_missing_note_id(self, mock_client):
        from notebooklm_tools.mcp.tools.notes import note

        result = note("nb-1", "update", content="text")

        assert result["status"] == "error"
        assert "note_id is required" in result["error"]


class TestNoteDelete:
    def test_confirm_false(self, mock_client):
        from notebooklm_tools.mcp.tools.notes import note

        result = note("nb-1", "delete", note_id="n-1", confirm=False)

        assert result["status"] == "error"
        assert "warning" in result

    def test_missing_note_id(self, mock_client):
        from notebooklm_tools.mcp.tools.notes import note

        result = note("nb-1", "delete", confirm=True)

        assert result["status"] == "error"
        assert "note_id is required" in result["error"]

    def test_confirm_true_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.notes.notes_service") as svc:
            svc.delete_note.return_value = {"message": "Deleted"}
            from notebooklm_tools.mcp.tools.notes import note

            result = note("nb-1", "delete", note_id="n-1", confirm=True)

            assert result["status"] == "success"
            assert result["action"] == "delete"


class TestNoteInvalidAction:
    def test_invalid_action(self, mock_client):
        from notebooklm_tools.mcp.tools.notes import note

        result = note("nb-1", "invalid_action")

        assert result["status"] == "error"
        assert "Unknown action" in result["error"]
        assert "invalid_action" in result["error"]
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_notes.py -v`
Expected: 9 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_notes.py
git commit -m "test: add MCP notes tool tests (4 actions, 9 tests)"
```

---

### Task 8: Sharing Tools Tests (3 tools)

**Files:**
- Create: `tests/mcp/test_sharing.py`
- Reference: `src/notebooklm_tools/mcp/tools/sharing.py`

**Step 1: Write tests**

```python
"""Tests for MCP sharing tools."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestNotebookShareStatus:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.get_share_status.return_value = {
                "is_public": False,
                "collaborators": [],
            }
            from notebooklm_tools.mcp.tools.sharing import notebook_share_status

            result = notebook_share_status("nb-1")

            assert result["status"] == "success"
            assert result["is_public"] is False

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.get_share_status.side_effect = ServiceError("Not found")
            from notebooklm_tools.mcp.tools.sharing import notebook_share_status

            result = notebook_share_status("nb-1")
            assert result["status"] == "error"


class TestNotebookSharePublic:
    def test_enable(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.set_public_access.return_value = {
                "public_link": "https://notebooklm.google.com/share/nb-1",
            }
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public("nb-1", is_public=True)

            assert result["status"] == "success"
            assert "public_link" in result

    def test_disable(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.set_public_access.return_value = {"public_link": None}
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public("nb-1", is_public=False)

            assert result["status"] == "success"

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.set_public_access.side_effect = ServiceError("Permission denied")
            from notebooklm_tools.mcp.tools.sharing import notebook_share_public

            result = notebook_share_public("nb-1")
            assert result["status"] == "error"


class TestNotebookShareInvite:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.invite_collaborator.return_value = {"message": "Invited"}
            from notebooklm_tools.mcp.tools.sharing import notebook_share_invite

            result = notebook_share_invite("nb-1", "user@example.com", role="editor")

            assert result["status"] == "success"
            svc.invite_collaborator.assert_called_once_with(
                mock_client, "nb-1", "user@example.com", "editor",
            )

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.sharing.sharing_service") as svc:
            svc.invite_collaborator.side_effect = ServiceError("Invalid email")
            from notebooklm_tools.mcp.tools.sharing import notebook_share_invite

            result = notebook_share_invite("nb-1", "bad-email")
            assert result["status"] == "error"
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_sharing.py -v`
Expected: 7 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_sharing.py
git commit -m "test: add MCP sharing tool tests (3 tools, 7 tests)"
```

---

### Task 9: Download Tool Tests (1 async tool)

**Files:**
- Create: `tests/mcp/test_downloads.py`
- Reference: `src/notebooklm_tools/mcp/tools/downloads.py`

**Note:** `download_artifact` is `async def` — needs `@pytest.mark.asyncio`.

**Step 1: Write tests**

```python
"""Tests for MCP download tool (async)."""

import pytest
from unittest.mock import patch, AsyncMock
from notebooklm_tools.services.errors import ServiceError


@pytest.mark.asyncio
class TestDownloadArtifact:
    async def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.downloads.downloads_service") as svc:
            svc.download_async = AsyncMock(return_value={
                "file_path": "/tmp/podcast.mp3",
                "size_bytes": 1024000,
            })
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact("nb-1", "audio", "/tmp/podcast.mp3")

            assert result["status"] == "success"
            assert result["file_path"] == "/tmp/podcast.mp3"

    async def test_with_artifact_id(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.downloads.downloads_service") as svc:
            svc.download_async = AsyncMock(return_value={"file_path": "/tmp/out.pdf"})
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            await download_artifact(
                "nb-1", "slide_deck", "/tmp/out.pdf", artifact_id="art-1",
            )

            svc.download_async.assert_called_once_with(
                mock_client, "nb-1", "slide_deck", "/tmp/out.pdf",
                artifact_id="art-1", output_format="json",
            )

    async def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.downloads.downloads_service") as svc:
            svc.download_async = AsyncMock(
                side_effect=ServiceError("Artifact not ready"),
            )
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact("nb-1", "audio", "/tmp/out.mp3")
            assert result["status"] == "error"
            assert "not ready" in result["error"]

    async def test_unexpected_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.downloads.downloads_service") as svc:
            svc.download_async = AsyncMock(side_effect=OSError("disk full"))
            from notebooklm_tools.mcp.tools.downloads import download_artifact

            result = await download_artifact("nb-1", "audio", "/tmp/out.mp3")
            assert result["status"] == "error"
            assert "disk full" in result["error"]
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_downloads.py -v`
Expected: 4 tests PASS (requires `pytest-asyncio` — should already be installed; if not: `uv add --dev pytest-asyncio`)

**Step 3: Commit**

```bash
git add tests/mcp/test_downloads.py
git commit -m "test: add MCP download tool tests (1 async tool, 4 tests)"
```

---

### Task 10: Export Tool Tests (1 tool)

**Files:**
- Create: `tests/mcp/test_exports.py`
- Reference: `src/notebooklm_tools/mcp/tools/exports.py`

**Note:** `export_artifact` returns `result` directly from the service (not `{"status": "success", **result}`) — tests verify actual behavior.

**Step 1: Write tests**

```python
"""Tests for MCP export tool."""

import pytest
from unittest.mock import patch
from notebooklm_tools.services.errors import ServiceError


class TestExportArtifact:
    def test_success(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.exports.export_service") as svc:
            svc.export_artifact.return_value = {
                "status": "success",
                "url": "https://docs.google.com/document/d/abc",
                "export_type": "docs",
            }
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact("nb-1", "art-1", "docs")

            # Note: export_artifact returns service result directly
            assert result["status"] == "success"
            assert "url" in result

    def test_with_title(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.exports.export_service") as svc:
            svc.export_artifact.return_value = {"status": "success", "url": "..."}
            from notebooklm_tools.mcp.tools.exports import export_artifact

            export_artifact("nb-1", "art-1", "sheets", title="My Export")

            svc.export_artifact.assert_called_once_with(
                client=mock_client,
                notebook_id="nb-1",
                artifact_id="art-1",
                export_type="sheets",
                title="My Export",
            )

    def test_service_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.exports.export_service") as svc:
            svc.export_artifact.side_effect = ServiceError("Export failed")
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact("nb-1", "art-1", "docs")
            assert result["status"] == "error"

    def test_unexpected_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.exports.export_service") as svc:
            svc.export_artifact.side_effect = RuntimeError("timeout")
            from notebooklm_tools.mcp.tools.exports import export_artifact

            result = export_artifact("nb-1", "art-1", "docs")
            assert result["status"] == "error"
            assert "timeout" in result["error"]
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_exports.py -v`
Expected: 4 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_exports.py
git commit -m "test: add MCP export tool tests (1 tool, 4 tests)"
```

---

### Task 11: Auth Tools Tests (2 tools)

**Files:**
- Create: `tests/mcp/test_auth.py`
- Reference: `src/notebooklm_tools/mcp/tools/auth.py`

**Step 1: Write tests**

```python
"""Tests for MCP auth tools."""

import pytest
from unittest.mock import patch, MagicMock


class TestRefreshAuth:
    def test_success_from_cache(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.auth.load_cached_tokens") as load, \
             patch("notebooklm_tools.mcp.tools.auth.reset_client") as reset, \
             patch("notebooklm_tools.mcp.tools.auth.get_client") as get:
            load.return_value = MagicMock()
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()

            assert result["status"] == "success"
            assert "reloaded" in result["message"].lower()
            reset.assert_called_once()

    def test_no_cached_tokens(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.auth.load_cached_tokens") as load:
            load.return_value = None
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()

            assert result["status"] == "error"
            assert "nlm login" in result["error"]

    def test_unexpected_error(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.auth.load_cached_tokens") as load:
            load.side_effect = RuntimeError("disk error")
            from notebooklm_tools.mcp.tools.auth import refresh_auth

            result = refresh_auth()
            assert result["status"] == "error"


class TestSaveAuthTokens:
    def test_success_with_valid_cookies(self, mock_client):
        with patch("notebooklm_tools.mcp.tools.auth.reset_client"), \
             patch("notebooklm_tools.mcp.tools.auth.get_client"):
            # Need to mock the auth module imports inside save_auth_tokens
            mock_tokens_cls = MagicMock()
            mock_save = MagicMock()
            mock_cache_path = MagicMock(return_value="/tmp/cache")
            with patch.dict("sys.modules", {}):
                from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            # Build a valid cookie string with all required cookies
            cookies = "; ".join([
                "SID=sid_val", "HSID=hsid_val", "SSID=ssid_val",
                "APISID=api_val", "SAPISID=sapi_val",
                "__Secure-1PSID=sec1", "__Secure-3PSID=sec3",
            ])

            with patch("notebooklm_tools.mcp.tools.auth.AuthTokens") as tok_cls, \
                 patch("notebooklm_tools.mcp.tools.auth.save_tokens_to_cache") as save, \
                 patch("notebooklm_tools.mcp.tools.auth.get_cache_path", return_value="/tmp/c"), \
                 patch("notebooklm_tools.mcp.tools.auth.reset_client"):
                result = save_auth_tokens(cookies)

            assert result["status"] == "success"
            assert "cookies" in result["message"].lower()

    def test_missing_required_cookies(self, mock_client):
        from notebooklm_tools.mcp.tools.auth import save_auth_tokens

        result = save_auth_tokens("foo=bar; baz=qux")

        assert result["status"] == "error"
        assert "Missing required cookies" in result["error"]

    def test_csrf_extraction_from_body(self, mock_client):
        cookies = "; ".join([
            "SID=s", "HSID=h", "SSID=ss", "APISID=a", "SAPISID=sa",
        ])
        with patch("notebooklm_tools.mcp.tools.auth.AuthTokens") as tok_cls, \
             patch("notebooklm_tools.mcp.tools.auth.save_tokens_to_cache"), \
             patch("notebooklm_tools.mcp.tools.auth.get_cache_path", return_value="/tmp/c"), \
             patch("notebooklm_tools.mcp.tools.auth.reset_client"):
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(
                cookies, request_body="f.req=data&at=MY_CSRF_TOKEN&other=1",
            )

            assert result["status"] == "success"
            assert result["extracted_csrf"] is True

    def test_session_id_extraction_from_url(self, mock_client):
        cookies = "; ".join([
            "SID=s", "HSID=h", "SSID=ss", "APISID=a", "SAPISID=sa",
        ])
        with patch("notebooklm_tools.mcp.tools.auth.AuthTokens") as tok_cls, \
             patch("notebooklm_tools.mcp.tools.auth.save_tokens_to_cache"), \
             patch("notebooklm_tools.mcp.tools.auth.get_cache_path", return_value="/tmp/c"), \
             patch("notebooklm_tools.mcp.tools.auth.reset_client"):
            from notebooklm_tools.mcp.tools.auth import save_auth_tokens

            result = save_auth_tokens(
                cookies, request_url="https://example.com?f.sid=MY_SESSION&other=1",
            )

            assert result["status"] == "success"
            assert result["extracted_session_id"] is True
```

**Step 2: Run tests**

Run: `uv run pytest tests/mcp/test_auth.py -v`
Expected: 7 tests PASS

**Step 3: Commit**

```bash
git add tests/mcp/test_auth.py
git commit -m "test: add MCP auth tool tests (2 tools, 7 tests)"
```

---

### Task 12: GitHub Actions CI Workflow

**Files:**
- Create: `.github/workflows/tests.yml`

**Step 1: Write workflow**

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --dev

      - name: Run tests
        run: uv run pytest -x --tb=short -q

      - name: Lint check
        run: uv run ruff check src/
```

**Step 2: Validate YAML**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))"`
Expected: No error (requires PyYAML; alternatively just validate visually)

**Step 3: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: add GitHub Actions workflow for pytest + ruff on Python 3.11/3.12"
```

---

### Task 13: Final Verification + Commit

**Step 1: Run the full test suite**

Run: `uv run pytest -x --tb=short -q`
Expected: ~490+ tests pass (409 existing + ~80 new MCP tests), 0 failures

**Step 2: Run just MCP tests to verify count**

Run: `uv run pytest tests/mcp/ -v --tb=short`
Expected: ~80+ tests all PASS

**Step 3: Verify no regressions**

Run: `uv run pytest tests/services/ tests/core/ -q`
Expected: All existing tests pass unchanged

**Step 4: Final commit (if any remaining changes)**

Only if there are fixups needed from test failures.

---

## Summary

| Task | Module | Tools | Tests |
|------|--------|-------|-------|
| 1 | Infrastructure | — | conftest.py |
| 2 | notebooks | 6 | ~14 |
| 3 | sources | 6 | ~18 |
| 4 | chat | 2 | ~8 |
| 5 | studio | 3 | ~11 |
| 6 | research | 3 | ~9 |
| 7 | notes | 1 (4 actions) | ~9 |
| 8 | sharing | 3 | ~7 |
| 9 | downloads | 1 (async) | ~4 |
| 10 | exports | 1 | ~4 |
| 11 | auth | 2 | ~7 |
| 12 | CI | — | GitHub Actions |
| 13 | Verification | — | Full suite run |
| **Total** | | **28 functions** | **~91 tests** |
