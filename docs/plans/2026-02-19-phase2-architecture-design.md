# Phase 2 Design: Code Exploration & ARCHITECTURE.md

**Date:** 2026-02-19
**Status:** Approved

## Goal

Create `docs/ARCHITECTURE.md` — an exhaustive technical reference for the notebooklm-mcp-cli codebase covering architecture, all MCP tools, data flows, RPC mappings, and gap analysis.

## Deliverable

A single `docs/ARCHITECTURE.md` with these sections:

1. **Overview** — purpose, tech stack, codebase stats
2. **Component Diagram** (Mermaid) — all 5 modules with file/line counts
3. **MCP Tools Map** — table of all 29+ tools: name, RPC ID, service function, params
4. **Data Flow Diagrams** (Mermaid) — auth, query, studio, source addition
5. **RPC ID Reference** — complete table of batchexecute RPC IDs
6. **Gap Analysis & Improvements** — bugs, inconsistencies, LLM-optimization ideas, testing gaps

## Execution Strategy

5 parallel Explore agents, each analyzing one module:

| Agent | Module | Focus |
|-------|--------|-------|
| core-analyst | `core/` (21 files, 7190 LOC) | Mixins, RPC IDs, auth, batchexecute protocol |
| services-analyst | `services/` (11 files, 2321 LOC) | Business logic, TypedDicts, error handling |
| mcp-analyst | `mcp/` (15 files, 1631 LOC) | Tools, server config, tool-to-service mapping |
| cli-analyst | `cli/` (22 files, 7171 LOC) | Commands, formatters, UX patterns |
| tests-analyst | `tests/` | Coverage, patterns, gaps |

Each agent produces a structured report. Main agent consolidates into ARCHITECTURE.md with Mermaid diagrams.

## Non-Goals

- No code changes in this phase
- No new tests (that's Phase 3)
- No refactoring (identified improvements go into gap analysis)
