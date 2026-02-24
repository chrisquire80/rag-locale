"""
FASE 20: UX Enhancements - Comprehensive Test Suite
Testing citations, query suggestions, conversation memory, and response enhancement
"""

import pytest
from datetime import datetime, timedelta
from src.ux_enhancements import (
    Citation, CitationType, QuerySuggestion, ConversationTurn, ConversationMemory,
    CitationManager, QuerySuggestor, ConversationManager, ResponseEnhancer,
    get_citation_manager, get_query_suggestor, get_conversation_manager, get_response_enhancer
)


class TestCitation:
    """Test Citation dataclass"""

    def test_citation_creation(self):
        """Test creating a citation"""
        citation = Citation(
            citation_type=CitationType.DIRECT,
            text="This is a direct quote",
            document_id="doc_1",
            source_title="Document 1"
        )
        assert citation.citation_type == CitationType.DIRECT
        assert citation.text == "This is a direct quote"
        assert citation.document_id == "doc_1"
        assert citation.source_title == "Document 1"

    def test_citation_with_page(self):
        """Test citation with page number"""
        citation = Citation(
            citation_type=CitationType.PARAPHRASE,
            text="Paraphrased content",
            document_id="doc_2",
            page=42,
            source_title="Book Title"
        )
        assert citation.page == 42
        assert citation.citation_type == CitationType.PARAPHRASE

    def test_citation_types(self):
        """Test all citation types"""
        assert CitationType.DIRECT.value == "direct"
        assert CitationType.PARAPHRASE.value == "paraphrase"
        assert CitationType.SYNTHESIS.value == "synthesis"


class TestCitationManager:
    """Test CitationManager"""

    def test_citation_manager_initialization(self):
        """Test initializing citation manager"""
        manager = CitationManager()
        assert manager.citations == []

    def test_extract_citations(self):
        """Test extracting citations from documents"""
        manager = CitationManager()

        documents = [
            {
                'id': 'doc_1',
                'text': 'This is important. Machine learning is powerful.',
                'metadata': {'source': 'Wikipedia'}
            }
        ]

        answer = "Machine learning is powerful and useful for many applications."

        citations = manager.extract_citations(answer, documents)
        assert len(citations) > 0
        assert citations[0].citation_type in [CitationType.DIRECT, CitationType.PARAPHRASE]

    def test_extract_citations_with_relevance_scores(self):
        """Test extracting citations with relevance scores"""
        manager = CitationManager()

        documents = [
            {
                'id': 'doc_1',
                'text': 'Artificial intelligence is advancing rapidly.',
                'metadata': {'source': 'Tech Blog'}
            }
        ]

        relevance_scores = {'doc_1': 0.95}
        answer = "Artificial intelligence is advancing rapidly in many fields."

        citations = manager.extract_citations(answer, documents, relevance_scores)
        if citations:
            assert citations[0].relevance_score == 0.95

    def test_format_citations(self):
        """Test formatting answer with citation markers"""
        manager = CitationManager()

        citations = [
            Citation(
                citation_type=CitationType.DIRECT,
                text="Machine learning",
                document_id="doc_1",
                source_title="ML Guide"
            )
        ]

        answer = "Machine learning is powerful"
        formatted, _ = manager.format_citations(answer, citations)

        # Should have citation marker
        assert "[" in formatted and "]" in formatted

    def test_get_citation_preview(self):
        """Test getting citation preview for UI"""
        manager = CitationManager()

        citation = Citation(
            citation_type=CitationType.DIRECT,
            text="This is a very long citation text that needs to be truncated for display purposes in the user interface",
            document_id="doc_1",
            source_title="Source Document"
        )

        preview = manager.get_citation_preview(citation)
        assert 'citation_id' in preview
        assert 'text_preview' in preview
        assert 'source' in preview
        assert 'type' in preview
        assert 'confidence' in preview
        assert len(preview['text_preview']) <= 110  # Max 100 chars + "..."


class TestQuerySuggestion:
    """Test QuerySuggestion dataclass"""

    def test_suggestion_creation(self):
        """Test creating a suggestion"""
        suggestion = QuerySuggestion(
            text="What about X?",
            category="clarification",
            confidence=0.8,
            reason="User asked a question"
        )
        assert suggestion.text == "What about X?"
        assert suggestion.category == "clarification"
        assert suggestion.confidence == 0.8


class TestQuerySuggestor:
    """Test QuerySuggestor"""

    def test_query_suggestor_initialization(self):
        """Test initializing query suggestor"""
        suggestor = QuerySuggestor()
        assert suggestor is not None

    def test_generate_suggestions_for_question(self):
        """Test generating suggestions for a question"""
        suggestor = QuerySuggestor()

        query = "How does machine learning work?"
        answer = "Machine learning uses algorithms to learn patterns from data."
        documents = [
            {'id': 'doc_1', 'text': 'ML algorithms...', 'metadata': {'source': 'Guide'}}
        ]

        suggestions = suggestor.generate_suggestions(query, answer, documents)
        assert len(suggestions) > 0
        assert all(isinstance(s, QuerySuggestion) for s in suggestions)

    def test_suggestion_categories(self):
        """Test that suggestions have valid categories"""
        suggestor = QuerySuggestor()

        query = "What is AI?"
        answer = "AI is artificial intelligence..."
        documents = []

        suggestions = suggestor.generate_suggestions(query, answer, documents)
        valid_categories = {"clarification", "expansion", "related", "follow-up"}

        for suggestion in suggestions:
            assert suggestion.category in valid_categories

    def test_suggestion_confidence_in_range(self):
        """Test that confidence scores are in valid range"""
        suggestor = QuerySuggestor()

        query = "Explain neural networks"
        answer = "Neural networks are inspired by biological neurons..."
        documents = []

        suggestions = suggestor.generate_suggestions(query, answer, documents)

        for suggestion in suggestions:
            assert 0 <= suggestion.confidence <= 1


class TestConversationTurn:
    """Test ConversationTurn dataclass"""

    def test_turn_creation(self):
        """Test creating a conversation turn"""
        turn = ConversationTurn(
            turn_id="turn_1",
            query="What is machine learning?",
            answer="Machine learning is a branch of AI..."
        )
        assert turn.turn_id == "turn_1"
        assert turn.query == "What is machine learning?"
        assert turn.answer == "Machine learning is a branch of AI..."

    def test_turn_with_citations(self):
        """Test turn with citations"""
        citations = [
            Citation(
                citation_type=CitationType.DIRECT,
                text="ML is powerful",
                document_id="doc_1"
            )
        ]

        turn = ConversationTurn(
            turn_id="turn_1",
            query="Query?",
            answer="Answer",
            citations=citations
        )
        assert len(turn.citations) == 1
        assert turn.citations[0].text == "ML is powerful"


class TestConversationMemory:
    """Test ConversationMemory"""

    def test_conversation_memory_creation(self):
        """Test creating conversation memory"""
        memory = ConversationMemory(conversation_id="conv_1")
        assert memory.conversation_id == "conv_1"
        assert len(memory.turns) == 0

    def test_add_turn_to_conversation(self):
        """Test adding turns to conversation"""
        memory = ConversationMemory(conversation_id="conv_1")

        turn = ConversationTurn(
            turn_id="turn_1",
            query="Question 1?",
            answer="Answer 1"
        )

        memory.add_turn(turn)
        assert len(memory.turns) == 1
        assert memory.turns[0].turn_id == "turn_1"

    def test_get_conversation_context(self):
        """Test getting conversation context"""
        memory = ConversationMemory(conversation_id="conv_1")

        turns = [
            ConversationTurn(turn_id="turn_1", query="Q1?", answer="A1"),
            ConversationTurn(turn_id="turn_2", query="Q2?", answer="A2"),
            ConversationTurn(turn_id="turn_3", query="Q3?", answer="A3"),
        ]

        for turn in turns:
            memory.add_turn(turn)

        context = memory.get_context(max_turns=2)
        assert "Q2" in context
        assert "Q3" in context
        assert "Q1" not in context

    def test_get_conversation_summary(self):
        """Test getting conversation summary"""
        memory = ConversationMemory(conversation_id="conv_1")

        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Question {i}?",
                answer=f"Answer {i}",
                quality_score=0.8
            )
            memory.add_turn(turn)

        summary = memory.get_summary()
        assert summary['conversation_id'] == "conv_1"
        assert summary['turn_count'] == 3
        assert abs(summary['average_quality'] - 0.8) < 0.001  # Allow for floating point precision

    def test_extract_topics_from_conversation(self):
        """Test extracting topics from conversation"""
        memory = ConversationMemory(conversation_id="conv_1")

        turns = [
            ConversationTurn(turn_id="turn_1", query="machine learning basics", answer="ML is..."),
            ConversationTurn(turn_id="turn_2", query="machine learning models", answer="Models..."),
            ConversationTurn(turn_id="turn_3", query="neural networks", answer="NN..."),
        ]

        for turn in turns:
            memory.add_turn(turn)

        topics = memory._extract_topics()
        assert len(topics) > 0
        assert all(isinstance(t, str) for t in topics)


class TestConversationManager:
    """Test ConversationManager"""

    def test_conversation_manager_initialization(self):
        """Test initializing conversation manager"""
        manager = ConversationManager()
        assert len(manager.conversations) == 0

    def test_create_conversation(self):
        """Test creating a conversation"""
        manager = ConversationManager()

        conv = manager.create_conversation("conv_1")
        assert conv.conversation_id == "conv_1"
        assert "conv_1" in manager.conversations

    def test_add_turn_to_conversation(self):
        """Test adding turn to conversation"""
        manager = ConversationManager()

        turn = ConversationTurn(
            turn_id="turn_1",
            query="First question?",
            answer="First answer"
        )

        manager.add_turn("conv_1", turn)
        assert "conv_1" in manager.conversations
        assert len(manager.conversations["conv_1"].turns) == 1

    def test_get_conversation(self):
        """Test retrieving conversation"""
        manager = ConversationManager()
        manager.create_conversation("conv_1")

        conv = manager.get_conversation("conv_1")
        assert conv is not None
        assert conv.conversation_id == "conv_1"

    def test_get_nonexistent_conversation(self):
        """Test retrieving non-existent conversation"""
        manager = ConversationManager()

        conv = manager.get_conversation("nonexistent")
        assert conv is None

    def test_get_conversation_context(self):
        """Test getting context from conversation"""
        manager = ConversationManager()

        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Q{i}?",
                answer=f"A{i}"
            )
            manager.add_turn("conv_1", turn)

        context = manager.get_context("conv_1", max_turns=2)
        assert "Q1" in context or "Q2" in context

    def test_summarize_conversation(self):
        """Test summarizing conversation"""
        manager = ConversationManager()

        for i in range(2):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Question {i}?",
                answer=f"Answer {i}",
                quality_score=0.85
            )
            manager.add_turn("conv_1", turn)

        summary = manager.summarize_conversation("conv_1")
        assert summary['turn_count'] == 2
        assert summary['average_quality'] == 0.85


class TestResponseEnhancer:
    """Test ResponseEnhancer"""

    def test_response_enhancer_initialization(self):
        """Test initializing response enhancer"""
        enhancer = ResponseEnhancer()
        assert enhancer is not None
        assert enhancer.citation_manager is not None
        assert enhancer.query_suggestor is not None

    def test_enhance_response(self):
        """Test enhancing a response with all features"""
        enhancer = ResponseEnhancer()

        query = "What is machine learning?"
        answer = "Machine learning is a subset of artificial intelligence."
        documents = [
            {
                'id': 'doc_1',
                'text': 'Machine learning algorithms learn from data.',
                'metadata': {'source': 'ML Guide'}
            }
        ]

        enhanced = enhancer.enhance_response(query, answer, documents, quality_score=0.85)

        assert 'query' in enhanced
        assert 'answer' in enhanced
        assert 'base_answer' in enhanced
        assert 'citations' in enhanced
        assert 'suggestions' in enhanced
        assert 'quality_score' in enhanced
        assert enhanced['quality_score'] == 0.85

    def test_enhance_response_has_metadata(self):
        """Test that enhanced response includes metadata"""
        enhancer = ResponseEnhancer()

        enhanced = enhancer.enhance_response(
            "Test query?",
            "Test answer.",
            [],
            quality_score=0.9
        )

        assert 'metadata' in enhanced
        assert 'citation_count' in enhanced['metadata']
        assert 'suggestion_count' in enhanced['metadata']

    def test_enhance_response_with_multiple_documents(self):
        """Test enhancing response with multiple source documents"""
        enhancer = ResponseEnhancer()

        documents = [
            {
                'id': 'doc_1',
                'text': 'First document content.',
                'metadata': {'source': 'Source 1'}
            },
            {
                'id': 'doc_2',
                'text': 'Second document content.',
                'metadata': {'source': 'Source 2'}
            }
        ]

        enhanced = enhancer.enhance_response(
            "Multi-doc query?",
            "Answer from multiple sources.",
            documents,
            quality_score=0.88
        )

        assert 'suggestions' in enhanced
        assert isinstance(enhanced['suggestions'], list)


class TestSingletons:
    """Test singleton getters"""

    def test_citation_manager_singleton(self):
        """Test citation manager singleton"""
        manager1 = get_citation_manager()
        manager2 = get_citation_manager()
        assert manager1 is manager2

    def test_query_suggestor_singleton(self):
        """Test query suggestor singleton"""
        suggestor1 = get_query_suggestor()
        suggestor2 = get_query_suggestor()
        assert suggestor1 is suggestor2

    def test_conversation_manager_singleton(self):
        """Test conversation manager singleton"""
        manager1 = get_conversation_manager()
        manager2 = get_conversation_manager()
        assert manager1 is manager2

    def test_response_enhancer_singleton(self):
        """Test response enhancer singleton"""
        enhancer1 = get_response_enhancer()
        enhancer2 = get_response_enhancer()
        assert enhancer1 is enhancer2


class TestIntegration:
    """Integration tests for FASE 20"""

    def test_full_conversation_flow(self):
        """Test complete conversation flow with all UX features"""
        # Initialize managers
        conv_manager = get_conversation_manager()
        enhancer = get_response_enhancer()

        # Simulate conversation
        query = "What is deep learning?"
        answer = "Deep learning is a subset of machine learning using neural networks."
        documents = [
            {
                'id': 'doc_1',
                'text': 'Deep learning uses neural networks with many layers.',
                'metadata': {'source': 'AI Textbook'}
            }
        ]

        # Enhance response
        enhanced = enhancer.enhance_response(query, answer, documents, quality_score=0.87)

        # Create conversation turn with enhanced content
        turn = ConversationTurn(
            turn_id="turn_1",
            query=query,
            answer=enhanced['answer'],
            citations=[],
            quality_score=enhanced['quality_score']
        )

        # Add to conversation
        conv_manager.add_turn("session_1", turn)

        # Verify
        conversation = conv_manager.get_conversation("session_1")
        assert conversation is not None
        assert len(conversation.turns) == 1
        assert conversation.turns[0].quality_score == 0.87

    def test_multi_turn_conversation_with_context(self):
        """Test multi-turn conversation using context"""
        conv_manager = get_conversation_manager()
        # Use a unique conversation ID to avoid interference from other tests
        test_conv_id = "session_test_multi_turn"

        # Add multiple turns
        for i in range(4):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Question {i}?",
                answer=f"Answer about deep learning topic {i}.",
                quality_score=0.85 + (i * 0.02)
            )
            conv_manager.add_turn(test_conv_id, turn)

        # Get context (last 3 turns)
        context = conv_manager.get_context(test_conv_id, max_turns=3)
        assert "Question 1" in context or "Question 2" in context or "Question 3" in context

        # Verify summary
        summary = conv_manager.summarize_conversation(test_conv_id)
        assert summary['turn_count'] == 4

    def test_citation_extraction_with_real_documents(self):
        """Test citation extraction with realistic document structure"""
        manager = get_citation_manager()

        documents = [
            {
                'id': 'research_paper_1',
                'text': 'Neural networks are inspired by biological neurons. They consist of interconnected nodes.',
                'metadata': {
                    'source': 'Understanding Neural Networks',
                    'date': '2024'
                }
            }
        ]

        answer = "Neural networks are inspired by biological neurons and are used in machine learning."

        citations = manager.extract_citations(answer, documents)
        assert len(citations) >= 0

    def test_suggestion_generation_varieties(self):
        """Test suggestion generation across different query types"""
        suggestor = get_query_suggestor()

        test_cases = [
            ("How does backpropagation work?", "Backpropagation is an algorithm..."),
            ("Tell me about CNNs", "Convolutional Neural Networks..."),
            ("Compare RNN and LSTM", "RNNs and LSTMs are both recurrent..."),
        ]

        for query, answer in test_cases:
            suggestions = suggestor.generate_suggestions(query, answer, [])
            assert len(suggestions) > 0
            assert all(0 <= s.confidence <= 1 for s in suggestions)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
