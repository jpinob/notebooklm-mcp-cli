#!/usr/bin/env python3
"""Tests for ConversationMixin."""

from notebooklm_tools.core.base import BaseClient
from notebooklm_tools.core.conversation import ConversationMixin


class TestConversationMixinImport:
    """Test that ConversationMixin can be imported correctly."""

    def test_conversation_mixin_import(self):
        """Test that ConversationMixin can be imported."""
        assert ConversationMixin is not None

    def test_conversation_mixin_inherits_base(self):
        """Test that ConversationMixin inherits from BaseClient."""
        assert issubclass(ConversationMixin, BaseClient)

    def test_conversation_mixin_has_methods(self):
        """Test that ConversationMixin has expected methods."""
        expected_methods = [
            "query",
            "clear_conversation",
            "get_conversation_history",
            "_build_conversation_history",
            "_cache_conversation_turn",
            "_parse_query_response",
            "_parse_inner_from_chunk",
            "_extract_text_from_inner",
            "_extract_citations",
            "_extract_citation_mappings",
            "_extract_suggested_questions",
            "_extract_source_citation",
            "_extract_passage_text",
            "_collect_passage_texts",
            "_extract_source_ids_from_notebook",
        ]
        for method in expected_methods:
            assert hasattr(ConversationMixin, method), f"Missing method: {method}"


class TestConversationMixinMethods:
    """Test ConversationMixin method behavior."""

    def test_clear_conversation_removes_from_cache(self):
        """Test that clear_conversation removes conversation from cache."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")
        
        # Add a conversation to cache
        mixin._conversation_cache["test-conv-id"] = []
        
        # Clear it
        result = mixin.clear_conversation("test-conv-id")
        
        assert result is True
        assert "test-conv-id" not in mixin._conversation_cache

    def test_clear_conversation_returns_false_if_not_found(self):
        """Test that clear_conversation returns False if conversation not in cache."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")
        
        result = mixin.clear_conversation("nonexistent-id")
        
        assert result is False

    def test_get_conversation_history_returns_none_if_not_found(self):
        """Test that get_conversation_history returns None if conversation not in cache."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")
        
        result = mixin.get_conversation_history("nonexistent-id")
        
        assert result is None

    def test_parse_query_response_handles_empty(self):
        """Test that _parse_query_response handles empty input and returns defaults."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")

        result = mixin._parse_query_response("")

        assert result["answer"] == ""
        assert result["sources_cited"] == []
        assert result["citation_mappings"] == []
        assert result["suggested_questions"] == []

    def test_parse_inner_from_chunk_handles_invalid_json(self):
        """Test that _parse_inner_from_chunk handles invalid JSON."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")

        result = mixin._parse_inner_from_chunk("not valid json")

        assert result is None

    def test_extract_source_ids_from_notebook_handles_none(self):
        """Test that _extract_source_ids_from_notebook handles None input."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")
        
        result = mixin._extract_source_ids_from_notebook(None)
        
        assert result == []

    def test_extract_source_ids_from_notebook_handles_empty_list(self):
        """Test that _extract_source_ids_from_notebook handles empty list."""
        mixin = ConversationMixin(cookies={"test": "cookie"}, csrf_token="test")
        
        result = mixin._extract_source_ids_from_notebook([])
        
        assert result == []
