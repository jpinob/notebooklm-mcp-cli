# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**NotebookLM MCP Server & CLI** — Programmatic access to Google NotebookLM via a Model Context Protocol server and CLI. Uses undocumented internal APIs (batchexecute protocol). Tested with personal/free tier accounts.

**Executables:** `nlm` (CLI) and `notebooklm-mcp` (MCP server)
**Python:** >=3.11 | **Build:** hatchling | **Package:** `notebooklm-mcp-cli`

## Development Commands

```bash
# Install as tool (creates nlm + notebooklm-mcp executables)
uv tool install .

# Reinstall after code changes (ALWAYS clean cache first)
uv cache clean && uv tool install --force .

# Run tests
uv run pytest
uv run pytest tests/test_file.py::test_function -v

# Lint and type check
uv run ruff check src/
uv run ruff check --fix src/
uv run mypy src/

# Run MCP server
notebooklm-mcp                                    # stdio (default)
notebooklm-mcp --debug                            # with debug logging
notebooklm-mcp --transport http --port 8000        # HTTP mode
```

**Ruff config:** line-length=100, target py311, rules: E/F/I/UP/B/SIM (E501 ignored).

## Architecture

### Layer Diagram

```
┌─────────────┐  ┌─────────────┐
│  cli/       │  │  mcp/       │   ← Thin wrappers (UX only)
│  commands/  │  │  tools/     │
└──────┬──────┘  └──────┬──────┘
       │                │
       ▼                ▼
┌──────────────────────────────┐
│         services/            │   ← Business logic, validation, TypedDict returns
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│           core/              │   ← Low-level API (batchexecute, auth, constants)
└──────────────────────────────┘
```

### Layering Rules (CRITICAL)

- `cli/` and `mcp/` are **thin wrappers**: they handle UX concerns (prompts, spinners, JSON responses) and delegate ALL logic to `services/`
- `cli/` and `mcp/` must **NEVER import from `core/`** directly — always go through `services/`
- `services/` contains all business logic, validation, and error handling. Returns `TypedDict` objects.
- `services/` raises `ServiceError`/`ValidationError` — never raw exceptions

### Key Patterns

**1. Service Layer — TypedDict Returns**

All service functions accept a `NotebookLMClient` as first argument and return TypedDict objects:

```python
# services/notebooks.py
class NotebookInfo(TypedDict):
    id: str
    title: str
    source_count: int
    url: str
    # ...

def list_notebooks(client: NotebookLMClient, max_results: int = 100) -> NotebookListResult:
    raw = client.list_notebooks()
    # Parse nested lists → typed dict
    return {"notebooks": [...], "count": len(notebooks)}
```

**2. Error Hierarchy**

```python
# services/errors.py
ServiceError          # Base — has user_message (user-facing) + debug_code (technical)
├── ValidationError   # Invalid inputs
├── NotFoundError     # Resource doesn't exist
├── CreationError     # Creation failed
└── ExportError       # Export failed
```

MCP tools and CLI commands catch `ServiceError` and convert to their response format. Users see `e.user_message`.

**3. MCP Tools — logged_tool Decorator**

```python
# mcp/tools/notebooks.py
@logged_tool()  # Registers with FastMCP + adds logging
def notebook_list(max_results: int = 100) -> dict[str, Any]:
    try:
        client = get_client()
        result = notebooks_service.list_notebooks(client, max_results)
        return {"status": "success", **result}
    except ServiceError as e:
        return {"status": "error", "error": e.user_message}
```

MCP tools always return `{"status": "success"|"error", ...}`. `get_client()` from `mcp/tools/_utils.py` creates a client from env vars or cached tokens.

**4. CLI Commands — Typer + Rich**

```python
# cli/commands/notebook.py
@app.command("list")
def list_notebooks(profile: Optional[str] = None):
    with get_client(profile) as client:
        result = notebooks_service.list_notebooks(client)
    formatter.format_notebooks(result["notebooks"])
```

**5. Core Client — Mixin Architecture**

`NotebookLMClient` inherits from multiple mixins, each adding domain-specific RPC methods:

```python
# core/client.py composes:
NotebookLMClient → ExportMixin, DownloadMixin, StudioMixin, ResearchMixin,
                   ConversationMixin, SourceMixin, SharingMixin, NotebookMixin, NotesMixin
                   → BaseClient
```

Each mixin calls `self._call_rpc(rpc_id, params)` from `BaseClient`.

**6. Batchexecute Protocol**

All API calls use Google's internal batchexecute protocol:

```
POST /_/LabsTailwindUi/data/batchexecute?rpcids=RPC_ID&...
Body: f.req=[[[RPC_ID, JSON_PARAMS, null, "generic"]]]&at=CSRF_TOKEN

Response: )]}' followed by nested JSON lists (no stable schema)
```

RPC IDs are string constants like `"wXbhsf"` (list notebooks), `"izAoDd"` (add source). See `core/base.py` for all IDs.

**7. CodeMapper — Bidirectional Constants**

```python
# core/constants.py
STUDIO_TYPES = CodeMapper({"audio": 1, "report": 2, "video": 3, ...})
STUDIO_TYPES.get_code("audio")  # → 1
STUDIO_TYPES.get_name(1)        # → "audio"
STUDIO_TYPES.options_str         # → "audio, report, video, ..."
```

Used for: `CHAT_GOALS`, `STUDIO_TYPES`, `AUDIO_FORMATS`, `VIDEO_STYLES`, `SOURCE_TYPES`, etc.

**8. Authentication**

Multi-profile auth managed by `AuthManager` in `core/auth.py`:

```
~/.notebooklm-mcp-cli/profiles/<name>/
├── cookies.json      # Browser cookies
└── metadata.json     # {csrf_token, session_id, email, last_validated}
```

- **Cookies** — Required, stable for weeks. Set via `nlm login` or `NOTEBOOKLM_COOKIES` env var.
- **CSRF token & session ID** — Auto-extracted on first API call; no manual setup needed.
- Three-layer retry on auth failure: refresh CSRF → reload cookies from disk → headless Chrome re-auth.

### Data Flow Example

```
User: "list my notebooks"
  → MCP tool (mcp/tools/notebooks.py::notebook_list)
    → Service (services/notebooks.py::list_notebooks)
      → Client (core/notebooks.py mixin::list_notebooks)
        → BaseClient._call_rpc("wXbhsf", params)
          → HTTP POST to batchexecute endpoint
        ← Nested list response parsed
      ← Raw data normalized to TypedDict
    ← {"status": "success", "notebooks": [...]}
  ← JSON response to MCP client
```

## Testing

Tests live in `tests/` mirroring the source structure:

```
tests/
├── services/       # Service layer tests (mock the client)
├── core/           # Low-level API tests (mock httpx)
└── cli/            # CLI formatting tests
```

**Pattern:** Service tests mock `NotebookLMClient`, then assert TypedDict returns and `ServiceError` raises.

**Markers:** `@pytest.mark.e2e` (requires live auth), `@pytest.mark.integration` (CLI tests).

## Documentation

- **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** — RPC IDs, parameter structures, response formats. Read when debugging API issues or adding new features.
- **[docs/MCP_CLI_TEST_PLAN.md](./docs/MCP_CLI_TEST_PLAN.md)** — Step-by-step test cases for all 29 MCP tools. Use when validating after code changes.
- **[docs/CLI_GUIDE.md](./docs/CLI_GUIDE.md)** — Complete CLI command reference.
- **[docs/MCP_GUIDE.md](./docs/MCP_GUIDE.md)** — MCP server configuration and tool documentation.

## Adding New Features

1. Capture the network request (Chrome DevTools) and document the RPC ID in `docs/API_REFERENCE.md`
2. Add the low-level RPC method as a mixin in `core/` (e.g., `core/notebooks.py`)
3. Add business logic in the appropriate `services/*.py` module — validate inputs, return TypedDict, raise ServiceError
4. Add thin wrapper in `mcp/tools/*.py` (catch ServiceError → return status dict) and `cli/commands/*.py` (catch ServiceError → print + exit)
5. Write unit tests in `tests/services/` (mock client, test happy path + error cases)
6. Add test case to `docs/MCP_CLI_TEST_PLAN.md`
