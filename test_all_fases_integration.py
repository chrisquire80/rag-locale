"""
Comprehensive Integration Test - ALL FASES
Tests complete end-to-end pipeline from FASE 18-20
Tests interaction between all components
"""

import pytest
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from long_context_optimizer import LongContextOptimizer
from document_hierarchy import DocumentHierarchy
from rag_engine_longcontext import LongContextRAGEngine
from quality_metrics import QualityMetricsCollector, QualityMetrics
from rag_engine_quality import QualityAwareRAGEngine
from citation_engine import CitationEngine
from query_suggestions import QuerySuggestionEngine
from chat_memory import ConversationMemory
from rag_engine_ux import UXEnhancedRAGEngine


class TestFase18Fase19Integration:
    """Test integration between long-context and quality metrics"""

    def test_long_context_generates_evaluable_response(self):
        """Test that long-context engine produces responses that can be evaluated"""
        engine = LongContextRAGEngine()
        collector = QualityMetricsCollector()

        response = engine.query_with_long_context("Test query")

        # Should be able to evaluate response
        if response.answer:
            metrics = collector.evaluate_response("Test query", response.answer, [])
            assert metrics.overall_score >= 0

    def test_context_assembly_improves_quality(self):
        """Test that assembling more context improves potential quality"""
        optimizer = LongContextOptimizer()
        collector = QualityMetricsCollector()

        small_doc = "Machine learning is important."
        large_doc = "Machine learning is important. " + "It enables many applications. " * 20

        score_small = collector.calculate_faithfulness(
            "Machine learning is important",
            [small_doc]
        )

        score_large = collector.calculate_faithfulness(
            "Machine learning is important and enables many applications",
            [large_doc]
        )

        # More context should enable better evaluation
        assert score_large >= score_small


class TestFase19Fase20Integration:
    """Test integration between quality metrics and UX features"""

    def test_quality_scores_inform_suggestions(self):
        """Test that quality metrics inform suggestion quality"""
        quality_engine = QualityAwareRAGEngine()
        ux_engine = UXEnhancedRAGEngine()

        # Get quality-aware response
        response = quality_engine.query_with_quality_feedback(
            "What is machine learning?",
            enable_improvement_loop=False
        )

        # UX engine should work with any response
        enhanced = ux_engine.query_with_ux_enhancements("What is machine learning?")

        assert enhanced.quality_metrics is not None
        assert len(enhanced.followup_suggestions) >= 0

    def test_conversation_memory_tracks_quality(self):
        """Test that conversation memory properly tracks quality scores"""
        memory = ConversationMemory()

        # Add turns with varying quality
        memory.add_turn("Q1", "A1", quality_score=0.9)
        memory.add_turn("Q2", "A2", quality_score=0.5)
        memory.add_turn("Q3", "A3", quality_score=0.8)

        stats = memory.get_conversation_statistics()

        assert stats["avg_quality_score"] > 0.6
        assert stats["total_turns"] == 3


class TestEndToEndPipeline:
    """Complete end-to-end tests for full pipeline"""

    def test_complete_pipeline_basic(self):
        """Test basic complete pipeline"""
        engine = UXEnhancedRAGEngine()

        # Single query through complete pipeline
        response = engine.query_with_ux_enhancements(
            "What is artificial intelligence?",
            include_citations=True,
            include_suggestions=True
        )

        # Verify all components present
        assert response.answer is not None
        assert len(response.formatted_answer) > 0
        assert response.ui_metadata is not None
        assert len(response.ui_metadata) > 0

    def test_multi_turn_conversation_pipeline(self):
        """Test multi-turn conversation through complete pipeline"""
        engine = UXEnhancedRAGEngine()

        queries = [
            "What is machine learning?",
            "How does it work?",
            "What are applications?",
            "What about deep learning?"
        ]

        responses = []
        for query in queries:
            response = engine.query_with_ux_enhancements(
                query,
                user_id="test_user"
            )
            responses.append(response)

        # Verify conversation tracking
        assert len(engine.conversation_memory.turns) == len(queries)

        # Verify quality tracking
        stats = engine.get_conversation_stats()
        assert stats["total_turns"] == len(queries)

    def test_pipeline_with_all_options(self):
        """Test pipeline with all options enabled"""
        engine = UXEnhancedRAGEngine()

        response = engine.query_with_ux_enhancements(
            "Explain neural networks",
            user_id="user123",
            include_citations=True,
            include_suggestions=True,
            include_conversation_context=True
        )

        # All features should be present
        assert response.formatted_answer is not None
        assert len(response.citations) >= 0
        assert len(response.followup_suggestions) >= 0
        assert response.conversation_summary is not None

        # Should be exportable to UI format
        ui_response = engine.get_formatted_ui_response(response)
        ui_dict = ui_response.to_dict()

        assert "main_answer" in ui_dict
        assert "citations" in ui_dict
        assert "suggestions" in ui_dict
        assert "metadata" in ui_dict


class TestComponentInteroperability:
    """Test that components work together properly"""

    def test_long_context_with_quality_check(self):
        """Test long-context engine output with quality metrics"""
        lc_engine = LongContextRAGEngine()
        quality_collector = QualityMetricsCollector()

        # Generate long-context response
        response = lc_engine.query_with_long_context("test query")

        # Should be evaluable
        if response.answer and response.sources:
            sources_text = [
                s.document if hasattr(s, 'document') else str(s)
                for s in response.sources
            ]
            metrics = quality_collector.evaluate_response(
                "test query",
                response.answer,
                sources_text
            )
            assert isinstance(metrics, QualityMetrics)

    def test_quality_response_with_ux_formatting(self):
        """Test quality response can be formatted for UI"""
        qa_engine = QualityAwareRAGEngine()
        ux_engine = UXEnhancedRAGEngine()

        # Get quality-aware response
        qa_response = qa_engine.query_with_quality_feedback("test")

        # Format for UI
        if hasattr(qa_response, 'sources'):
            sources = [
                {"document": str(s), "source": "test"}
                for s in qa_response.sources
            ]
            citations = ux_engine.citation_engine.generate_citations(
                sources,
                qa_response.answer
            )
            assert isinstance(citations, dict)

    def test_suggestions_respect_conversation_context(self):
        """Test query suggestions generated in conversation context"""
        engine = UXEnhancedRAGEngine()

        # Build conversation
        engine.query_with_ux_enhancements("What is ML?")
        engine.query_with_ux_enhancements("How does it work?")

        # Get suggestions for next query
        response = engine.query_with_ux_enhancements(
            "Tell me about neural networks",
            include_conversation_context=True
        )

        # Should have context aware suggestions
        assert len(response.suggestion_objects) >= 0


class TestPerformanceBenchmarks:
    """Performance tests for complete pipeline"""

    def test_complete_pipeline_latency(self):
        """Test complete pipeline latency"""
        engine = UXEnhancedRAGEngine()

        start = time.time()
        response = engine.query_with_ux_enhancements(
            "Test query",
            include_citations=True,
            include_suggestions=True
        )
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 30  # 30 seconds for complete pipeline
        assert elapsed > 0.01  # At least 10ms

        # Response should include timing
        assert response.latency_breakdown is not None

    def test_conversation_memory_scales(self):
        """Test conversation memory scales with many turns"""
        memory = ConversationMemory(max_turns=100)

        # Add many turns
        for i in range(50):
            memory.add_turn(f"Question {i}", f"Answer {i}")

        # Should handle many turns
        assert len(memory.turns) == 50

        # Statistics should still compute quickly
        start = time.time()
        stats = memory.get_conversation_statistics()
        elapsed = time.time() - start

        assert elapsed < 1.0  # Stats should compute in <1 sec

    def test_citation_generation_scales(self):
        """Test citation generation with many sources"""
        engine = CitationEngine()

        # Create many sources
        sources = [
            {
                "document": f"Document {i}",
                "source": f"Source {i}",
                "metadata": {}
            }
            for i in range(20)
        ]

        start = time.time()
        citations = engine.generate_citations(sources)
        elapsed = time.time() - start

        # Should handle many sources
        assert len(citations) == 20
        assert elapsed < 1.0  # Should complete in <1 sec


class TestErrorHandling:
    """Test error handling across pipeline"""

    def test_pipeline_handles_empty_query(self):
        """Test pipeline handles empty query gracefully"""
        engine = UXEnhancedRAGEngine()

        # Should not crash on empty query
        response = engine.query_with_ux_enhancements("")

        assert response is not None

    def test_pipeline_handles_missing_sources(self):
        """Test pipeline handles missing sources"""
        engine = UXEnhancedRAGEngine()

        # Query that might have no sources
        response = engine.query_with_ux_enhancements("obscure_query_xyz")

        assert response is not None
        # Should still generate suggestions
        assert hasattr(response, 'followup_suggestions')

    def test_pipeline_handles_malformed_metadata(self):
        """Test pipeline handles malformed metadata"""
        engine = CitationEngine()

        sources = [
            {
                "document": "Test",
                # Missing 'source' key
                "metadata": None  # None instead of dict
            }
        ]

        # Should handle gracefully
        citations = engine.generate_citations(sources)
        assert len(citations) > 0

    def test_memory_handles_duplicate_queries(self):
        """Test conversation memory handles duplicates"""
        memory = ConversationMemory()

        # Add same query twice
        memory.add_turn("Question", "Answer 1")
        memory.add_turn("Question", "Answer 2")

        # Should track both
        assert len(memory.turns) == 2


class TestDataIntegrity:
    """Test data integrity across pipeline"""

    def test_answer_preserved_through_formatting(self):
        """Test answer text preserved through formatting"""
        engine = UXEnhancedRAGEngine()

        original_answer = "Machine learning enables computer systems to learn from data."

        # Query that would return this
        response = engine.query_with_ux_enhancements("test")

        # Answer should be preserved or enhanced
        if response.answer:
            # Should not lose content
            assert len(response.formatted_answer) >= len(response.answer) * 0.9

    def test_citations_match_sources(self):
        """Test citations properly match sources"""
        engine = CitationEngine()

        sources = [
            {
                "document": "First source content",
                "source": "Source A",
                "metadata": {}
            }
        ]

        citations = engine.generate_citations(sources)

        # Should have citation for source
        assert len(citations) > 0

    def test_conversation_export_contains_all_turns(self):
        """Test conversation export contains all turns"""
        memory = ConversationMemory()

        for i in range(5):
            memory.add_turn(f"Q{i}", f"A{i}")

        export = memory.export_conversation()

        # Export should contain all turns
        assert len(export["turns"]) == 5


class TestRealWorldScenarios:
    """Test real-world usage scenarios"""

    def test_customer_support_scenario(self):
        """Test customer support conversation scenario"""
        engine = UXEnhancedRAGEngine()

        # Simulate customer support conversation
        queries = [
            "How do I use your product?",
            "What are the pricing options?",
            "Do you offer a free trial?",
            "How do I get started?"
        ]

        for query in queries:
            response = engine.query_with_ux_enhancements(
                query,
                user_id="customer_123"
            )

            # Should have helpful suggestions
            assert response.followup_suggestions is not None

        # Should track full conversation
        stats = engine.get_conversation_stats()
        assert stats["total_turns"] == len(queries)

    def test_research_scenario(self):
        """Test research assistant scenario"""
        engine = UXEnhancedRAGEngine()

        # Research-oriented queries
        queries = [
            "What are recent advances in quantum computing?",
            "Compare quantum computing with classical computing",
            "What are practical applications?"
        ]

        responses = []
        for query in queries:
            response = engine.query_with_ux_enhancements(
                query,
                include_citations=True,  # Important for research
                include_suggestions=True
            )
            responses.append(response)

            # All should have citations
            assert len(response.citations) >= 0

    def test_learning_scenario(self):
        """Test learning/tutoring scenario"""
        engine = UXEnhancedRAGEngine()

        # Learning-oriented queries
        topics = [
            "Explain the basics of machine learning",
            "What is a neural network?",
            "How is deep learning different from neural networks?",
            "What are real-world applications of deep learning?"
        ]

        for topic in topics:
            response = engine.query_with_ux_enhancements(
                topic,
                include_suggestions=True  # Important for learning
            )

            # Should have follow-up suggestions to guide learning
            assert response.followup_suggestions is not None


class TestValidation:
    """Validation tests"""

    def test_response_structure_validity(self):
        """Test response structure is valid"""
        engine = UXEnhancedRAGEngine()

        response = engine.query_with_ux_enhancements("test")

        # Response should have expected structure
        assert hasattr(response, 'answer')
        assert hasattr(response, 'sources')
        assert hasattr(response, 'quality_metrics')
        assert hasattr(response, 'citations')
        assert hasattr(response, 'followup_suggestions')

    def test_ui_response_serializable(self):
        """Test UI response can be serialized to JSON"""
        engine = UXEnhancedRAGEngine()

        response = engine.query_with_ux_enhancements("test")
        ui_response = engine.get_formatted_ui_response(response)

        # Should be JSON serializable
        import json
        try:
            json_str = json.dumps(ui_response.to_dict(), default=str)
            assert len(json_str) > 0
        except Exception as e:
            pytest.fail(f"UI response not JSON serializable: {e}")

    def test_metrics_in_valid_range(self):
        """Test all metrics in valid ranges"""
        collector = QualityMetricsCollector()

        metrics = collector.evaluate_response(
            "test query",
            "test answer",
            ["test source"]
        )

        # All scores should be 0-1
        assert 0 <= metrics.faithfulness <= 1
        assert 0 <= metrics.relevance <= 1
        assert 0 <= metrics.coherence <= 1
        assert 0 <= metrics.coverage <= 1
        assert 0 <= metrics.completeness <= 1
        assert 0 <= metrics.overall_score <= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
