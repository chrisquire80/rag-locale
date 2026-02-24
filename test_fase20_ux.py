"""
FASE 20 - UX Enhancements Tests
Tests citation generation, query suggestions, conversation memory, and UI formatting
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from citation_engine import (
    CitationEngine,
    Citation,
    CitationLink
)
from query_suggestions import (
    QuerySuggestionEngine,
    QuerySuggestion,
    QueryIntent
)
from chat_memory import (
    ConversationMemory,
    ConversationTurn
)
from rag_engine_ux import (
    UXEnhancedRAGEngine,
    EnhancedRAGResponse,
    UIFormattedResponse
)


class TestCitationEngine:
    """Tests for CitationEngine"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = CitationEngine()

    def test_engine_initialization(self):
        """Test citation engine initializes"""
        assert self.engine is not None
        assert len(self.engine.citations) == 0

    def test_generate_citations_empty_sources(self):
        """Test citation generation with empty sources"""
        citations = self.engine.generate_citations([])
        assert len(citations) == 0

    def test_generate_citations_single_source(self):
        """Test citation generation from single source"""
        sources = [{
            "document": "Machine learning is powerful.",
            "source": "ML Guide",
            "metadata": {"url": "http://example.com"}
        }]

        citations = self.engine.generate_citations(sources)

        assert len(citations) == 1
        assert "cite_1" in citations

    def test_generate_citations_multiple_sources(self):
        """Test citation generation from multiple sources"""
        sources = [
            {
                "document": "First document",
                "source": "Source 1",
                "metadata": {}
            },
            {
                "document": "Second document",
                "source": "Source 2",
                "metadata": {}
            }
        ]

        citations = self.engine.generate_citations(sources)

        assert len(citations) == 2
        assert "cite_1" in citations
        assert "cite_2" in citations

    def test_citation_preview_format(self):
        """Test citation preview formatting"""
        citation = Citation(
            id="cite_1",
            source_name="Python Docs",
            section="Standard Library",
            excerpt="Python is a programming language."
        )

        preview = self.engine.create_citation_preview(citation)

        assert "Python Docs" in preview
        assert "Standard Library" in preview
        assert len(preview) > 0

    def test_extract_citation_context(self):
        """Test extracting citation context"""
        source = {
            "document": "This is a long document with many words. " * 10
        }

        context = self.engine.extract_citation_context(source, context_window=50)

        assert len(context) > 0
        assert "..." in context

    def test_link_citations_to_answer(self):
        """Test linking citations to answer text"""
        answer = "Machine learning is powerful. Neural networks are effective."
        citations = {
            "cite_1": Citation(
                id="cite_1",
                source_name="ML Guide",
                excerpt="Machine learning is"
            )
        }

        links = self.engine.link_citations_to_answer(answer, citations)

        assert len(links) > 0

    def test_format_answer_inline_citations(self):
        """Test inline citation formatting"""
        answer = "Machine learning is powerful."
        citations = {
            "cite_1": Citation(
                id="cite_1",
                source_name="ML Guide",
                excerpt="Machine learning"
            )
        }

        formatted = self.engine.format_answer_with_citations(
            answer,
            citations,
            format_type="inline"
        )

        assert "References:" in formatted or "[1]" in formatted

    def test_get_citation_statistics(self):
        """Test citation statistics"""
        sources = [
            {
                "document": "Doc 1",
                "source": "Source 1",
                "metadata": {"url": "http://example.com"}
            }
        ]

        self.engine.generate_citations(sources)
        stats = self.engine.get_citation_statistics()

        assert stats["total_citations"] == 1

    def test_export_citations_json(self):
        """Test exporting citations as JSON"""
        sources = [{
            "document": "Test",
            "source": "Source",
            "metadata": {}
        }]

        self.engine.generate_citations(sources)
        export = self.engine.export_citations(format="json")

        assert isinstance(export, str)
        assert "cite_1" in export


class TestQuerySuggestionEngine:
    """Tests for QuerySuggestionEngine"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = QuerySuggestionEngine()

    def test_engine_initialization(self):
        """Test engine initializes"""
        assert self.engine is not None

    def test_generate_followup_questions_empty_input(self):
        """Test with empty inputs"""
        questions = self.engine.generate_followup_questions("", "")
        assert isinstance(questions, list)

    def test_generate_followup_questions_explanation(self):
        """Test follow-up for explanation queries"""
        query = "Why is machine learning important?"
        answer = "Machine learning enables automation."

        questions = self.engine.generate_followup_questions(query, answer)

        assert len(questions) > 0
        assert any("example" in q.lower() for q in questions)

    def test_generate_followup_questions_how_to(self):
        """Test follow-up for how-to queries"""
        query = "How do I implement machine learning?"
        answer = "First, prepare your data..."

        questions = self.engine.generate_followup_questions(query, answer)

        assert len(questions) > 0

    def test_suggest_related_queries(self):
        """Test related query suggestions"""
        query = "machine learning"

        related = self.engine.suggest_related_queries(query)

        assert isinstance(related, list)

    def test_analyze_query_intent_explanation(self):
        """Test query intent analysis for explanation"""
        intent = self.engine.analyze_query_intent("Why is machine learning important?")
        assert intent == QueryIntent.EXPLANATION

    def test_analyze_query_intent_comparison(self):
        """Test query intent analysis for comparison"""
        intent = self.engine.analyze_query_intent("Compare Python and Java")
        assert intent == QueryIntent.COMPARISON

    def test_analyze_query_intent_definition(self):
        """Test query intent analysis for definition"""
        intent = self.engine.analyze_query_intent("What is machine learning?")
        assert intent == QueryIntent.DEFINITION

    def test_rank_suggestions(self):
        """Test ranking suggestions by relevance"""
        suggestions = [
            "Tell me about neural networks",
            "What is Python?",
            "Explain machine learning"
        ]
        query = "machine learning"

        ranked = self.engine.rank_suggestions(suggestions, query)

        assert len(ranked) > 0
        # First suggestion should have higher score
        assert ranked[0][1] >= ranked[-1][1]

    def test_get_suggestion_objects(self):
        """Test getting structured suggestion objects"""
        query = "machine learning"
        answer = "ML is important."

        suggestions = self.engine.get_suggestion_objects(query, answer)

        assert isinstance(suggestions, list)
        assert all(isinstance(s, QuerySuggestion) for s in suggestions)


class TestConversationMemory:
    """Tests for ConversationMemory"""

    def setup_method(self):
        """Setup for each test"""
        self.memory = ConversationMemory()

    def test_memory_initialization(self):
        """Test memory initializes"""
        assert self.memory is not None
        assert len(self.memory.turns) == 0

    def test_add_turn_single(self):
        """Test adding single turn"""
        turn = self.memory.add_turn(
            query="What is AI?",
            response="AI is artificial intelligence."
        )

        assert turn.turn_id == 1
        assert turn.query == "What is AI?"
        assert len(self.memory.turns) == 1

    def test_add_turn_multiple(self):
        """Test adding multiple turns"""
        for i in range(5):
            self.memory.add_turn(
                query=f"Question {i}",
                response=f"Answer {i}"
            )

        assert len(self.memory.turns) == 5

    def test_add_turn_with_metadata(self):
        """Test adding turn with metadata"""
        turn = self.memory.add_turn(
            query="Test",
            response="Response",
            quality_score=0.8,
            sources=["source1", "source2"],
            metadata={"user": "test_user"}
        )

        assert turn.quality_score == 0.8
        assert len(turn.sources) == 2

    def test_get_recent_turns(self):
        """Test getting recent turns"""
        for i in range(10):
            self.memory.add_turn(f"Q{i}", f"A{i}")

        recent = self.memory.get_recent_turns(3)

        assert len(recent) == 3

    def test_get_conversation_context(self):
        """Test getting conversation context"""
        self.memory.add_turn("Q1", "A1")
        self.memory.add_turn("Q2", "A2")

        context = self.memory.get_conversation_context()

        assert isinstance(context, str)
        assert "Q1" in context or "User" in context

    def test_clear_old_turns(self):
        """Test clearing old turns"""
        self.memory.add_turn("Q1", "A1")

        # Should not clear immediately
        removed = self.memory.clear_old_turns(max_age_minutes=0)

        assert removed == 0

    def test_export_conversation(self):
        """Test exporting conversation"""
        self.memory.add_turn("Q1", "A1")
        self.memory.add_turn("Q2", "A2")

        export = self.memory.export_conversation()

        assert "conversation_id" in export
        assert "turns" in export
        assert len(export["turns"]) == 2

    def test_get_conversation_statistics(self):
        """Test conversation statistics"""
        self.memory.add_turn(
            "What is machine learning?",
            "Machine learning enables computers to learn from data.",
            quality_score=0.8
        )

        stats = self.memory.get_conversation_statistics()

        assert stats["total_turns"] == 1
        assert stats["avg_quality_score"] == 0.8

    def test_search_conversation(self):
        """Test searching conversation"""
        self.memory.add_turn("What is AI?", "AI is artificial intelligence.")
        self.memory.add_turn("Tell me about ML", "Machine learning is...")

        results = self.memory.search_conversation("machine")

        assert len(results) > 0

    def test_get_topics_discussed(self):
        """Test extracting topics"""
        self.memory.add_turn("machine learning", "Response about ML")
        self.memory.add_turn("machine learning", "More about ML")

        topics = self.memory.get_topics_discussed()

        assert "machine" in topics or "learning" in topics

    def test_to_markdown(self):
        """Test Markdown export"""
        self.memory.add_turn("Q1", "A1")

        markdown = self.memory.to_markdown()

        assert "Conversation" in markdown
        assert "Q1" in markdown
        assert "A1" in markdown


class TestUXEnhancedRAGEngine:
    """Tests for UXEnhancedRAGEngine"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = UXEnhancedRAGEngine()

    def test_engine_initialization(self):
        """Test engine initializes"""
        assert self.engine is not None
        assert self.engine.citation_engine is not None
        assert self.engine.suggestion_engine is not None
        assert self.engine.conversation_memory is not None

    def test_query_with_ux_enhancements_basic(self):
        """Test basic UX enhanced query"""
        response = self.engine.query_with_ux_enhancements(
            "test query",
            include_citations=False,
            include_suggestions=False
        )

        assert isinstance(response, EnhancedRAGResponse)
        assert hasattr(response, 'formatted_answer')
        assert hasattr(response, 'ui_metadata')

    def test_response_includes_citations(self):
        """Test response includes citations"""
        response = self.engine.query_with_ux_enhancements(
            "test query",
            include_citations=True
        )

        assert hasattr(response, 'citations')

    def test_response_includes_suggestions(self):
        """Test response includes suggestions"""
        response = self.engine.query_with_ux_enhancements(
            "test query",
            include_suggestions=True
        )

        assert hasattr(response, 'followup_suggestions')
        assert hasattr(response, 'related_queries')

    def test_get_formatted_ui_response(self):
        """Test getting UI-formatted response"""
        response = self.engine.query_with_ux_enhancements("test")

        ui_response = self.engine.get_formatted_ui_response(response)

        assert isinstance(ui_response, UIFormattedResponse)
        assert hasattr(ui_response, 'to_dict')

    def test_create_shareable_response_markdown(self):
        """Test creating shareable Markdown response"""
        response = self.engine.query_with_ux_enhancements("test")

        markdown = self.engine.create_shareable_response(
            response,
            format="markdown"
        )

        assert isinstance(markdown, str)
        assert len(markdown) > 0

    def test_get_conversation_context(self):
        """Test getting conversation context"""
        self.engine.query_with_ux_enhancements("Query 1")
        self.engine.query_with_ux_enhancements("Query 2")

        context = self.engine.get_conversation_context()

        assert isinstance(context, str)

    def test_get_conversation_stats(self):
        """Test getting conversation statistics"""
        self.engine.query_with_ux_enhancements("Query 1")

        stats = self.engine.get_conversation_stats()

        assert stats["total_turns"] == 1

    def test_clear_conversation(self):
        """Test clearing conversation"""
        self.engine.query_with_ux_enhancements("Query 1")

        assert self.engine.get_conversation_stats()["total_turns"] == 1

        self.engine.clear_conversation()

        assert self.engine.get_conversation_stats()["total_turns"] == 0

    def test_quality_badge_calculation(self):
        """Test quality badge calculation"""
        badge_excellent = self.engine._get_quality_badge(0.85)
        badge_good = self.engine._get_quality_badge(0.75)
        badge_poor = self.engine._get_quality_badge(0.55)

        assert badge_excellent == "excellent"
        assert badge_good == "good"
        assert badge_poor == "needs_improvement"

    def test_readability_calculation(self):
        """Test readability score calculation"""
        text = "Short. Sentences. Are. Easy. To. Read."
        score = self.engine._calculate_readability(text)

        assert 0 <= score <= 100


class TestUXIntegration:
    """Integration tests for UX features"""

    def test_complete_ux_pipeline(self):
        """Test complete UX enhancement pipeline"""
        engine = UXEnhancedRAGEngine()

        response = engine.query_with_ux_enhancements(
            "What is machine learning?",
            include_citations=True,
            include_suggestions=True,
            include_conversation_context=True
        )

        # Verify all components present
        assert response.answer is not None
        assert response.formatted_answer is not None
        assert response.ui_metadata is not None

    def test_multiple_queries_conversation_flow(self):
        """Test conversation flow with multiple queries"""
        engine = UXEnhancedRAGEngine()

        for i in range(3):
            response = engine.query_with_ux_enhancements(f"Query {i}")
            assert response is not None

        stats = engine.get_conversation_stats()
        assert stats["total_turns"] == 3

    def test_ui_response_serialization(self):
        """Test UI response can be serialized"""
        engine = UXEnhancedRAGEngine()
        response = engine.query_with_ux_enhancements("test")

        ui_response = engine.get_formatted_ui_response(response)
        response_dict = ui_response.to_dict()

        assert isinstance(response_dict, dict)
        assert "main_answer" in response_dict
        assert "citations" in response_dict
        assert "suggestions" in response_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
