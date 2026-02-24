"""
End-to-End Integration Tests for RAG LOCALE System
Tests complete workflow from quality metrics through UX enhancement
"""

import pytest
import uuid
from src.quality_metrics import get_quality_evaluator
from src.ux_enhancements import (
    get_response_enhancer,
    get_conversation_manager,
    ConversationTurn
)


class TestQualityMetrics:
    """Test FASE 19: Quality Metrics"""

    def test_evaluate_single_query(self):
        """Test evaluating a single query"""
        evaluator = get_quality_evaluator()

        evaluation = evaluator.evaluate_query(
            query_id="test_1",
            query="What is machine learning?",
            answer="Machine learning is a subset of artificial intelligence.",
            retrieved_documents=[
                {
                    'id': 'doc_1',
                    'text': 'Machine learning learns from data.',
                    'metadata': {'source': 'ML Guide'}
                }
            ]
        )

        assert evaluation is not None
        assert evaluation.query_id == "test_1"
        assert len(evaluation.metrics) > 0

    def test_quality_score_range(self):
        """Test that quality scores are in valid range"""
        evaluator = get_quality_evaluator()

        evaluation = evaluator.evaluate_query(
            query_id="test_2",
            query="How does AI work?",
            answer="AI uses algorithms and neural networks.",
            retrieved_documents=[
                {'id': 'doc_1', 'text': 'AI uses algorithms', 'metadata': {}}
            ]
        )

        score = evaluation.get_overall_score()
        assert 0 <= score <= 1

    def test_multiple_evaluations(self):
        """Test multiple sequential evaluations"""
        evaluator = get_quality_evaluator()

        for i in range(3):
            evaluation = evaluator.evaluate_query(
                query_id=f"test_{i}",
                query=f"Question {i}?",
                answer=f"Answer {i}.",
                retrieved_documents=[
                    {'id': f'doc_{i}', 'text': f'Content {i}', 'metadata': {}}
                ]
            )
            assert evaluation is not None
            assert evaluation.get_overall_score() >= 0


class TestResponseEnhancement:
    """Test FASE 20: Response Enhancement"""

    def test_enhance_response(self):
        """Test enhancing a response with citations and suggestions"""
        enhancer = get_response_enhancer()

        documents = [
            {
                'id': 'doc_1',
                'text': 'Machine learning is a powerful technology.',
                'metadata': {'source': 'Tech Magazine'}
            }
        ]

        enhanced = enhancer.enhance_response(
            query="What is machine learning?",
            answer="Machine learning is a powerful technology for analysis.",
            retrieved_documents=documents,
            quality_score=0.85
        )

        assert enhanced is not None
        assert 'answer' in enhanced
        assert 'citations' in enhanced
        assert 'suggestions' in enhanced
        assert enhanced['quality_score'] == 0.85

    def test_response_with_multiple_documents(self):
        """Test response enhancement with multiple source documents"""
        enhancer = get_response_enhancer()

        documents = [
            {'id': 'doc_1', 'text': 'Content 1.', 'metadata': {'source': 'Source 1'}},
            {'id': 'doc_2', 'text': 'Content 2.', 'metadata': {'source': 'Source 2'}},
        ]

        enhanced = enhancer.enhance_response(
            query="Multi-doc query?",
            answer="Answer from multiple sources.",
            retrieved_documents=documents,
            quality_score=0.90
        )

        assert enhanced['metadata']['citation_count'] >= 0
        assert enhanced['metadata']['suggestion_count'] >= 0


class TestConversationManagement:
    """Test FASE 20: Conversation Memory"""

    def test_single_turn(self):
        """Test single conversation turn"""
        conv_manager = get_conversation_manager()
        session_id = f"test_{uuid.uuid4().hex[:8]}"

        conv_manager.create_conversation(session_id)

        turn = ConversationTurn(
            turn_id="turn_1",
            query="What is AI?",
            answer="AI is artificial intelligence.",
            quality_score=0.80
        )

        conv_manager.add_turn(session_id, turn)

        conversation = conv_manager.get_conversation(session_id)
        assert len(conversation.turns) == 1
        assert conversation.turns[0].quality_score == 0.80

    def test_multi_turn_conversation(self):
        """Test multi-turn conversation with context"""
        conv_manager = get_conversation_manager()
        session_id = f"test_{uuid.uuid4().hex[:8]}"

        conv_manager.create_conversation(session_id)

        # Add 3 turns
        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Question {i}?",
                answer=f"Answer {i}.",
                quality_score=0.75 + (i * 0.05)
            )
            conv_manager.add_turn(session_id, turn)

        # Verify conversation
        conversation = conv_manager.get_conversation(session_id)
        assert len(conversation.turns) == 3

        # Get context
        context = conv_manager.get_context(session_id, max_turns=2)
        assert "Question" in context or "Answer" in context

    def test_conversation_summary(self):
        """Test conversation summarization"""
        conv_manager = get_conversation_manager()
        session_id = f"test_{uuid.uuid4().hex[:8]}"

        conv_manager.create_conversation(session_id)

        for i in range(3):
            turn = ConversationTurn(
                turn_id=f"turn_{i}",
                query=f"Q{i}?",
                answer=f"A{i}.",
                quality_score=0.80
            )
            conv_manager.add_turn(session_id, turn)

        summary = conv_manager.summarize_conversation(session_id)
        assert summary['turn_count'] == 3
        assert abs(summary['average_quality'] - 0.80) < 0.01


class TestIntegratedQualityAndUX:
    """Test integration between Quality Metrics and UX Enhancement"""

    def test_quality_score_in_enhanced_response(self):
        """Test that quality scores are properly included in enhanced response"""
        evaluator = get_quality_evaluator()
        enhancer = get_response_enhancer()

        documents = [
            {'id': 'doc_1', 'text': 'Test content here.', 'metadata': {'source': 'Test'}}
        ]

        # Evaluate quality
        evaluation = evaluator.evaluate_query(
            query_id="test_q",
            query="Test question?",
            answer="Test answer.",
            retrieved_documents=documents
        )

        quality_score = evaluation.get_overall_score()

        # Enhance with quality score
        enhanced = enhancer.enhance_response(
            query="Test question?",
            answer="Test answer.",
            retrieved_documents=documents,
            quality_score=quality_score
        )

        assert enhanced['quality_score'] == quality_score

    def test_full_workflow(self):
        """Test complete workflow: evaluate → enhance → store"""
        evaluator = get_quality_evaluator()
        enhancer = get_response_enhancer()
        conv_manager = get_conversation_manager()

        session_id = f"full_{uuid.uuid4().hex[:8]}"
        conv_manager.create_conversation(session_id)

        documents = [
            {'id': 'doc_1', 'text': 'Content about topic.', 'metadata': {'source': 'Source'}}
        ]

        # Step 1: Evaluate quality
        evaluation = evaluator.evaluate_query(
            query_id="full_test",
            query="What is the topic?",
            answer="The topic is important.",
            retrieved_documents=documents
        )

        # Step 2: Enhance response
        enhanced = enhancer.enhance_response(
            query="What is the topic?",
            answer="The topic is important.",
            retrieved_documents=documents,
            quality_score=evaluation.get_overall_score()
        )

        # Step 3: Store in conversation
        turn = ConversationTurn(
            turn_id="turn_1",
            query="What is the topic?",
            answer=enhanced['answer'],
            quality_score=enhanced['quality_score']
        )
        conv_manager.add_turn(session_id, turn)

        # Verify complete flow
        conversation = conv_manager.get_conversation(session_id)
        assert conversation is not None
        assert len(conversation.turns) == 1
        assert conversation.turns[0].quality_score > 0


class TestMultiTurnWithMetrics:
    """Test multi-turn conversations with quality metrics tracking"""

    def test_multi_turn_quality_tracking(self):
        """Test tracking quality scores across multiple turns"""
        evaluator = get_quality_evaluator()
        enhancer = get_response_enhancer()
        conv_manager = get_conversation_manager()

        session_id = f"multi_{uuid.uuid4().hex[:8]}"
        conv_manager.create_conversation(session_id)

        questions = [
            ("What is machine learning?", "Machine learning learns from data."),
            ("How does it work?", "It uses algorithms to find patterns."),
            ("What are applications?", "Applications include prediction and classification."),
        ]

        quality_scores = []

        for turn_num, (question, answer) in enumerate(questions):
            # Evaluate
            evaluation = evaluator.evaluate_query(
                query_id=f"turn_{turn_num}",
                query=question,
                answer=answer,
                retrieved_documents=[
                    {'id': f'doc_{turn_num}', 'text': answer, 'metadata': {}}
                ]
            )

            quality = evaluation.get_overall_score()
            quality_scores.append(quality)

            # Enhance
            enhanced = enhancer.enhance_response(
                query=question,
                answer=answer,
                retrieved_documents=[
                    {'id': f'doc_{turn_num}', 'text': answer, 'metadata': {}}
                ],
                quality_score=quality
            )

            # Store
            turn = ConversationTurn(
                turn_id=f"turn_{turn_num}",
                query=question,
                answer=enhanced['answer'],
                quality_score=quality
            )
            conv_manager.add_turn(session_id, turn)

        # Verify tracking
        conversation = conv_manager.get_conversation(session_id)
        assert len(conversation.turns) == 3

        summary = conv_manager.summarize_conversation(session_id)
        assert summary['average_quality'] > 0
        assert summary['turn_count'] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
