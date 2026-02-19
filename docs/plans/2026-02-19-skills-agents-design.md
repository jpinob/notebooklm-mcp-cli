# Design: Skills & Agents for NotebookLM MCP+CLI Development

**Date:** 2026-02-19
**Status:** Implemented

## Context

The project needed project-specific development tooling to accelerate feature development, enforce architectural patterns, and maintain security standards. Based on a full security audit and codebase analysis, 4 skills and 4 agents were designed and created.

## Skills Created

### nlm-add-feature
**Purpose:** Step-by-step workflow for adding new RPC endpoints across all layers.
**Triggers:** "add a new tool", "implement X feature", "new RPC endpoint"
**Location:** `.claude/skills/nlm-add-feature/SKILL.md`

Covers the full 7-step process: document RPC → core mixin → service layer → MCP tool → CLI command → tests → documentation. Enforces layering rules at each step.

### nlm-security-check
**Purpose:** Project-specific security checklist before commits.
**Triggers:** "security check", "safe to commit?", "review auth changes"
**Location:** `.claude/skills/nlm-security-check/SKILL.md`

Quick scan (6 checks) + deep scan (3 checks) for credential exposure, logging leaks, file permissions, .gitignore coverage, MCP response safety, and test credential hygiene.

### nlm-test-patterns
**Purpose:** Testing patterns and templates for all project layers.
**Triggers:** "write tests", "add tests for X", "how to test this?"
**Location:** `.claude/skills/nlm-test-patterns/SKILL.md`

4 test patterns: service tests (mock client), core/mixin tests (mock RPC), validation tests, and confirm=True tests. Includes fixture patterns and minimum test requirements.

### nlm-debug-protocol
**Purpose:** Troubleshooting guide for batchexecute protocol issues.
**Triggers:** "error 401", "API not responding", "empty response", "CSRF expired"
**Location:** `.claude/skills/nlm-debug-protocol/SKILL.md`

Covers auth failures (3-layer recovery), empty responses, parsing errors, rate limiting, and the BL string update process.

## Agents Created

### nlm-test-runner (haiku)
**Purpose:** Fast test execution and result analysis.
**Color:** green
**Location:** `.claude/agents/nlm-test-runner.md`

Runs pytest with appropriate flags, reports pass/fail/skip counts, and analyzes failures with root cause identification.

### nlm-service-reviewer (sonnet)
**Purpose:** Architecture compliance review.
**Color:** yellow
**Location:** `.claude/agents/nlm-service-reviewer.md`

Enforces layering rules: no cross-layer imports, TypedDict returns in services, ServiceError usage, logged_tool decorator in MCP, and proper delegation patterns.

### nlm-auth-scanner (sonnet)
**Purpose:** Security scanning for credential leaks.
**Color:** red
**Location:** `.claude/agents/nlm-auth-scanner.md`

Scans for credential exposure in logs, missing file permissions, hardcoded values, debug logging leaks, and git safety (staged files with cookie/token patterns).

### nlm-rpc-analyst (sonnet)
**Purpose:** Protocol analysis and endpoint documentation.
**Color:** blue
**Location:** `.claude/agents/nlm-rpc-analyst.md`

Helps reverse-engineer new RPC endpoints from Chrome DevTools captures, map parameter structures, parse response formats, and produce documentation.

## Architecture Decision

All skills and agents are **project-local** (in `.claude/` within the repo) rather than global (in `~/.claude/`), so they:
1. Travel with the repo (available to all contributors)
2. Don't pollute the global Claude Code config
3. Can be version-controlled alongside the code
4. Are specific to this project's patterns and conventions
