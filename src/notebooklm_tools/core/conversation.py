#!/usr/bin/env python3
"""Conversation and query mixin for NotebookLM client.

This module provides the ConversationMixin class which handles all query
and conversation-related operations.
"""

import json
import os
import urllib.parse
from typing import Any

from .base import BaseClient
from .data_types import ConversationTurn


class ConversationMixin(BaseClient):
    """Mixin providing query and conversation operations.
    
    Methods:
        - query: Query the notebook with questions
        - clear_conversation: Clear conversation cache
        - get_conversation_history: Get conversation history
    """
    
    # =========================================================================
    # Conversation Cache Management
    # =========================================================================
    
    def _build_conversation_history(self, conversation_id: str) -> list | None:
        """Build the conversation history array for follow-up queries.

        Chrome expects history in format: [[answer, null, 2], [query, null, 1], ...]
        where type 1 = user message, type 2 = AI response.

        The history includes ALL previous turns, not just the most recent one.
        Turns are added in chronological order (oldest first).

        Args:
            conversation_id: The conversation ID to get history for

        Returns:
            List in Chrome's expected format, or None if no history exists
        """
        turns = self._conversation_cache.get(conversation_id, [])
        if not turns:
            return None

        history = []
        # Add turns in chronological order (oldest first)
        # Each turn adds: [answer, null, 2] then [query, null, 1]
        for turn in turns:
            history.append([turn.answer, None, 2])
            history.append([turn.query, None, 1])

        return history if history else None

    def _cache_conversation_turn(
        self, conversation_id: str, query: str, answer: str
    ) -> None:
        """Cache a conversation turn for future follow-up queries."""
        if conversation_id not in self._conversation_cache:
            self._conversation_cache[conversation_id] = []

        turn_number = len(self._conversation_cache[conversation_id]) + 1
        turn = ConversationTurn(query=query, answer=answer, turn_number=turn_number)
        self._conversation_cache[conversation_id].append(turn)

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear the conversation cache for a specific conversation."""
        if conversation_id in self._conversation_cache:
            del self._conversation_cache[conversation_id]
            return True
        return False

    def get_conversation_history(self, conversation_id: str) -> list[dict] | None:
        """Get the conversation history for a specific conversation."""
        turns = self._conversation_cache.get(conversation_id)
        if not turns:
            return None

        return [
            {"turn": t.turn_number, "query": t.query, "answer": t.answer}
            for t in turns
        ]

    # =========================================================================
    # Query Operations
    # =========================================================================

    def query(
        self,
        notebook_id: str,
        query_text: str,
        source_ids: list[str] | None = None,
        conversation_id: str | None = None,
        timeout: float = 120.0,
    ) -> dict | None:
        """Query the notebook with a question.

        Supports both new conversations and follow-up queries. For follow-ups,
        the conversation history is automatically included from the cache.

        Args:
            notebook_id: The notebook UUID
            query_text: The question to ask
            source_ids: Optional list of source IDs to query (default: all sources)
            conversation_id: Optional conversation ID for follow-up questions.
                           If None, starts a new conversation.
                           If provided and exists in cache, includes conversation history.
            timeout: Request timeout in seconds (default: 120.0)

        Returns:
            Dict with:
            - answer: The AI's response text
            - conversation_id: ID to use for follow-up questions
            - turn_number: Which turn this is in the conversation (1 = first)
            - is_follow_up: Whether this was a follow-up query
            - sources_cited: List of citation dicts (source_id, confidence, passage)
            - citation_mappings: List of mapping dicts (start, end, citation_indices)
            - suggested_questions: List of suggested follow-up question strings
        """
        import uuid

        client = self._get_client()

        # If no source_ids provided, get them from the notebook
        if source_ids is None:
            notebook_data = self.get_notebook(notebook_id)
            source_ids = self._extract_source_ids_from_notebook(notebook_data)

        # Determine if this is a new conversation or follow-up
        is_new_conversation = conversation_id is None
        if is_new_conversation:
            conversation_id = str(uuid.uuid4())
            conversation_history = None
        else:
            # Check if we have cached history for this conversation
            conversation_history = self._build_conversation_history(conversation_id)

        # Build source IDs structure: [[[sid]]] for each source (3 brackets, not 4!)
        sources_array = [[[sid]] for sid in source_ids] if source_ids else []

        # Query params structure (from network capture)
        # For new conversations: params[2] = None
        # For follow-ups: params[2] = [[answer, null, 2], [query, null, 1], ...]
        params = [
            sources_array,
            query_text,
            conversation_history,  # None for new, history array for follow-ups
            [2, None, [1]],
            conversation_id,
        ]

        # Use compact JSON format matching Chrome (no spaces)
        params_json = json.dumps(params, separators=(",", ":"))

        f_req = [None, params_json]
        f_req_json = json.dumps(f_req, separators=(",", ":"))

        # URL encode with safe='' to encode all characters including /
        body_parts = [f"f.req={urllib.parse.quote(f_req_json, safe='')}"]
        if self.csrf_token:
            body_parts.append(f"at={urllib.parse.quote(self.csrf_token, safe='')}")
        # Add trailing & to match NotebookLM's format
        body = "&".join(body_parts) + "&"

        self._reqid_counter += 100000  # Increment counter
        url_params = {
            "bl": os.environ.get("NOTEBOOKLM_BL", "boq_labs-tailwind-frontend_20260108.06_p0"),
            "hl": "en",
            "_reqid": str(self._reqid_counter),
            "rt": "c",
        }
        if self._session_id:
            url_params["f.sid"] = self._session_id

        query_string = urllib.parse.urlencode(url_params)
        url = f"{self.BASE_URL}{self.QUERY_ENDPOINT}?{query_string}"

        response = client.post(url, content=body, timeout=timeout)
        response.raise_for_status()

        # Parse streaming response (returns enriched dict with citations)
        parsed = self._parse_query_response(response.text)
        answer_text = parsed["answer"]

        # Cache this turn for future follow-ups (only if we got an answer)
        if answer_text:
            self._cache_conversation_turn(conversation_id, query_text, answer_text)

        # Calculate turn number
        turns = self._conversation_cache.get(conversation_id, [])
        turn_number = len(turns)

        return {
            "answer": answer_text,
            "conversation_id": conversation_id,
            "turn_number": turn_number,
            "is_follow_up": not is_new_conversation,
            "sources_cited": parsed["sources_cited"],
            "citation_mappings": parsed["citation_mappings"],
            "suggested_questions": parsed["suggested_questions"],
        }

    def _extract_source_ids_from_notebook(self, notebook_data: Any) -> list[str]:
        """Extract source IDs from notebook data."""
        source_ids = []
        if not notebook_data or not isinstance(notebook_data, list):
            return source_ids

        try:
            # Notebook structure: [[notebook_title, sources_array, notebook_id, ...]]
            # The outer array contains one element with all notebook info
            # Sources are at position [0][1]
            if len(notebook_data) > 0 and isinstance(notebook_data[0], list):
                notebook_info = notebook_data[0]
                if len(notebook_info) > 1 and isinstance(notebook_info[1], list):
                    sources = notebook_info[1]
                    for source in sources:
                        # Each source: [[source_id], title, metadata, [null, 2]]
                        if isinstance(source, list) and len(source) > 0:
                            source_id_wrapper = source[0]
                            if isinstance(source_id_wrapper, list) and len(source_id_wrapper) > 0:
                                source_id = source_id_wrapper[0]
                                if isinstance(source_id, str):
                                    source_ids.append(source_id)
        except (IndexError, TypeError):
            pass

        return source_ids

    # =========================================================================
    # Response Parsing
    # =========================================================================

    def _parse_query_response(self, response_text: str) -> dict[str, Any]:
        """Parse the streaming query response and extract the final answer with citations.

        The query endpoint returns a streaming response with multiple chunks.
        Each chunk wraps a "wrb.fr" item whose inner JSON contains the answer,
        citations, citation mappings, and suggested follow-up questions.

        Strategy: iterate all chunks, keep the one whose answer text is longest
        and whose ``is_final`` flag is True.  If no final chunk is found, fall
        back to the longest non-final (thinking) chunk.

        Args:
            response_text: Raw response text from the query endpoint.

        Returns:
            Dict with keys:
            - answer (str): The extracted answer text.
            - sources_cited (list[dict]): Citation dicts with source_id, confidence, passage.
            - citation_mappings (list[dict]): Mapping dicts with start, end, citation_indices.
            - suggested_questions (list[str]): Suggested follow-up questions.
        """
        defaults: dict[str, Any] = {
            "answer": "",
            "sources_cited": [],
            "citation_mappings": [],
            "suggested_questions": [],
        }

        if not response_text:
            return defaults

        # Remove anti-XSSI prefix
        if response_text.startswith(")]}'"):
            response_text = response_text[4:]

        lines = response_text.strip().split("\n")

        best_final: dict[str, Any] | None = None
        best_thinking: dict[str, Any] | None = None

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Try to parse as byte count (indicates next line is JSON)
            json_line: str | None = None
            try:
                int(line)
                i += 1
                if i < len(lines):
                    json_line = lines[i]
                i += 1
            except ValueError:
                json_line = line
                i += 1

            if json_line is None:
                continue

            inner = self._parse_inner_from_chunk(json_line)
            if inner is None:
                continue

            text, is_final = self._extract_text_from_inner(inner)
            if not text:
                continue

            parsed: dict[str, Any] = {
                "answer": text,
                "sources_cited": self._extract_citations(inner),
                "citation_mappings": self._extract_citation_mappings(inner),
                "suggested_questions": self._extract_suggested_questions(inner),
            }

            if is_final:
                if best_final is None or len(text) > len(best_final["answer"]):
                    best_final = parsed
            else:
                if best_thinking is None or len(text) > len(best_thinking["answer"]):
                    best_thinking = parsed

        if best_final is not None:
            return best_final
        if best_thinking is not None:
            return best_thinking
        return defaults

    # ------------------------------------------------------------------
    # Chunk-level helpers
    # ------------------------------------------------------------------

    def _parse_inner_from_chunk(self, json_str: str) -> list | None:
        """Parse a raw JSON chunk and return the inner array from the "wrb.fr" item.

        Args:
            json_str: A single JSON chunk string from the streaming response.

        Returns:
            The parsed inner list, or None if the chunk cannot be parsed.
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, list):
            return None

        for item in data:
            if not isinstance(item, list) or len(item) < 3:
                continue
            if item[0] != "wrb.fr":
                continue
            inner_json_str = item[2]
            if not isinstance(inner_json_str, str):
                continue
            try:
                return json.loads(inner_json_str)
            except json.JSONDecodeError:
                continue

        return None

    def _extract_text_from_inner(self, inner: list) -> tuple[str, bool]:
        """Extract (answer_text, is_final) from the parsed inner array.

        ``inner[0]`` is the answer element.  ``inner[4]`` is a boolean flag
        that is ``True`` for the final answer chunk.

        Args:
            inner: The parsed inner list from a "wrb.fr" chunk.

        Returns:
            Tuple of (answer_text, is_final).  answer_text may be empty.
        """
        if not isinstance(inner, list) or len(inner) == 0:
            return "", False

        first_elem = inner[0]
        answer_text = ""
        if isinstance(first_elem, list) and len(first_elem) > 0:
            candidate = first_elem[0]
            if isinstance(candidate, str):
                answer_text = candidate
        elif isinstance(first_elem, str):
            answer_text = first_elem

        # Reason: inner[4] is the "is_final" boolean flag set by the API
        is_final = False
        if len(inner) > 4 and inner[4] is True:
            is_final = True

        return answer_text, is_final

    # ------------------------------------------------------------------
    # Citation extraction
    # ------------------------------------------------------------------

    def _extract_citations(self, inner: list) -> list[dict]:
        """Extract citation dicts from inner[1].

        Each citation is parsed via ``_extract_source_citation`` and only
        non-None results are included.

        Args:
            inner: The parsed inner list from a "wrb.fr" chunk.

        Returns:
            List of citation dicts with source_id, confidence, passage.
        """
        if not isinstance(inner, list) or len(inner) < 2:
            return []

        raw_citations = inner[1]
        if not isinstance(raw_citations, list):
            return []

        results = []
        for citation in raw_citations:
            parsed = self._extract_source_citation(citation)
            if parsed is not None:
                results.append(parsed)
        return results

    def _extract_source_citation(self, citation: list) -> dict | None:
        """Extract source_id, confidence, and passage from a single citation.

        Citation structure (from real API):
        ``[None, None, confidence, [[None, start, end]], [passage_segments],
        [[[source_uuid], version_hash]]]``

        Args:
            citation: A single citation list from the API response.

        Returns:
            Dict with source_id, confidence, passage — or None if malformed.
        """
        if not isinstance(citation, list) or len(citation) < 6:
            return None

        # Extract source_id from citation[5][0][0][0]
        try:
            source_wrapper = citation[5]
            if not isinstance(source_wrapper, list) or len(source_wrapper) == 0:
                return None
            first_source = source_wrapper[0]
            if not isinstance(first_source, list) or len(first_source) == 0:
                return None
            source_id_list = first_source[0]
            if not isinstance(source_id_list, list) or len(source_id_list) == 0:
                return None
            source_id = source_id_list[0]
            if not isinstance(source_id, str):
                return None
        except (IndexError, TypeError):
            return None

        # Extract confidence from citation[2]
        confidence = citation[2]
        if not isinstance(confidence, int | float):
            confidence = 0.0

        # Extract passage text from citation[4]
        passage = ""
        if len(citation) > 4 and isinstance(citation[4], list):
            passage = self._extract_passage_text(citation[4])

        return {
            "source_id": source_id,
            "confidence": confidence,
            "passage": passage,
        }

    def _extract_passage_text(self, passage_data: list) -> str:
        """Extract and concatenate passage text from nested passage structure.

        The passage data is deeply nested: segments contain sub-segments that
        eventually hold plain-text strings.  This method uses a recursive
        helper to collect all strings longer than 20 characters and
        concatenates them.

        Args:
            passage_data: The passage list from a citation (citation[4]).

        Returns:
            Concatenated passage text, or empty string if none found.
        """
        texts: list[str] = []
        self._collect_passage_texts(passage_data, texts)
        return " ".join(texts) if texts else ""

    def _collect_passage_texts(self, data: Any, texts: list[str]) -> None:
        """Recursively walk nested lists to find passage text strings.

        Collects any string longer than 20 characters that is not a UUID
        or hash-like token.

        Args:
            data: Current node in the nested passage structure.
            texts: Accumulator list that found strings are appended to.
        """
        if isinstance(data, str):
            if len(data) > 20:
                texts.append(data)
            return

        if isinstance(data, list):
            for item in data:
                self._collect_passage_texts(item, texts)

    # ------------------------------------------------------------------
    # Citation mappings
    # ------------------------------------------------------------------

    def _extract_citation_mappings(self, inner: list) -> list[dict]:
        """Extract citation mapping dicts from inner[2].

        Each mapping links a character range in the answer text to one or
        more citation indices.

        Mapping structure: ``[[None, start, end], [idx0, idx1, ...]]``

        Args:
            inner: The parsed inner list from a "wrb.fr" chunk.

        Returns:
            List of mapping dicts with start, end, citation_indices.
        """
        if not isinstance(inner, list) or len(inner) < 3:
            return []

        raw_mappings = inner[2]
        if not isinstance(raw_mappings, list):
            return []

        results = []
        for mapping in raw_mappings:
            if not isinstance(mapping, list) or len(mapping) < 2:
                continue
            range_part = mapping[0]
            indices_part = mapping[1]
            if not isinstance(range_part, list) or len(range_part) < 3:
                continue
            if not isinstance(indices_part, list):
                continue

            start = range_part[1]
            end = range_part[2]
            if not isinstance(start, int) or not isinstance(end, int):
                continue

            results.append({
                "start": start,
                "end": end,
                "citation_indices": indices_part,
            })
        return results

    # ------------------------------------------------------------------
    # Suggested questions
    # ------------------------------------------------------------------

    def _extract_suggested_questions(self, inner: list) -> list[str]:
        """Extract suggested follow-up questions from inner[3].

        The structure is ``[[q1, q2, q3]]`` — a list of lists of strings.
        We flatten and return all question strings found.

        Args:
            inner: The parsed inner list from a "wrb.fr" chunk.

        Returns:
            List of suggested question strings.
        """
        if not isinstance(inner, list) or len(inner) < 4:
            return []

        raw_questions = inner[3]
        if not isinstance(raw_questions, list):
            return []

        questions: list[str] = []
        for group in raw_questions:
            if isinstance(group, list):
                for item in group:
                    if isinstance(item, str):
                        questions.append(item)
            elif isinstance(group, str):
                questions.append(group)
        return questions
