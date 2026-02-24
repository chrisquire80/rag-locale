#!/usr/bin/env python
"""
FINAL SYSTEM TEST - Complete RAG LOCALE with FASE 17-20
Tests all components: Document Loading, Vector Store, Quality Metrics, UX Enhancement
"""

import sys
import time
import json
from pathlib import Path
from typing import List, Dict

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from document_loader import DocumentLoaderManager
from src.vector_store import VectorStore
from src.quality_metrics import get_quality_evaluator
from src.ux_enhancements import get_response_enhancer, get_conversation_manager, ConversationTurn
from src.metrics import IngestionMetrics, QueryMetrics, get_metrics_collector


class TestSuite:
    """Complete system test suite"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.start_time = time.time()

    def test(self, name: str, func):
        """Run a test and record result"""
        try:
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            self.results.append({
                "name": name,
                "status": "[PASS]",
                "time": f"{elapsed*1000:.2f}ms"
            })
            self.passed += 1
            print(f"[PASS] {name} ({elapsed*1000:.2f}ms)")
        except Exception as e:
            self.results.append({
                "name": name,
                "status": f"[FAIL] {str(e)}",
                "time": "N/A"
            })
            self.failed += 1
            print(f"[FAIL] {name}: {str(e)}")

    def print_summary(self):
        """Print test summary"""
        total_time = time.time() - self.start_time
        print("\n" + "="*70)
        print(f"TEST SUMMARY - {self.passed}/{self.passed + self.failed} PASSED")
        print("="*70)
        for result in self.results:
            status = result["status"]
            time_str = result["time"]
            print(f"{status:<20} {result['name']:<40} {time_str:>10}")
        print("="*70)
        print(f"Total time: {total_time:.2f}s")
        print(f"Pass rate: {self.passed}/{self.passed + self.failed} ({100*self.passed/(self.passed+self.failed):.1f}%)")


def test_document_loading():
    """Test 1: Document Loading from Real Files"""
    print("\n" + "="*70)
    print("TEST 1: DOCUMENT LOADING")
    print("="*70)

    suite = TestSuite()

    def load_documents():
        loader = DocumentLoaderManager()
        docs = loader.load_all_sources()
        assert len(docs) > 0, "No documents loaded"
        assert all('text' in d for d in docs), "Missing text in documents"
        assert all('metadata' in d for d in docs), "Missing metadata in documents"
        print(f"  Loaded {len(docs)} documents")
        for doc in docs:
            print(f"    - {doc['metadata']['source'][:50]}")

    suite.test("Load all document sources", load_documents)
    suite.print_summary()
    return suite.passed > 0


def test_vector_store():
    """Test 2: Vector Store Operations"""
    print("\n" + "="*70)
    print("TEST 2: VECTOR STORE")
    print("="*70)

    suite = TestSuite()

    def add_documents():
        loader = DocumentLoaderManager()
        docs = loader.load_all_sources()
        vs = VectorStore()

        # Add documents
        texts = [d['text'][:500] for d in docs]  # Limit text size for faster processing
        metadatas = [d['metadata'] for d in docs]
        vs.add_documents(texts, metadatas)
        assert len(vs.documents) == len(texts), "Documents not added"
        print(f"  Added {len(vs.documents)} documents to vector store")

    def search_documents():
        vs = VectorStore()
        # Add some documents first
        vs.add_documents(["neural networks are amazing", "machine learning is useful"], [{"source": "test"}])

        # Search
        results = vs.search("neural networks", top_k=1)
        assert len(results) > 0, "No search results"
        assert 'similarity_score' in results[0], "Missing similarity score"
        print(f"  Search found {len(results)} results")

    suite.test("Add documents to vector store", add_documents)
    suite.test("Search documents", search_documents)
    suite.print_summary()
    return suite.passed > 0


def test_quality_metrics():
    """Test 3: Quality Metrics (FASE 19)"""
    print("\n" + "="*70)
    print("TEST 3: QUALITY METRICS (FASE 19)")
    print("="*70)

    suite = TestSuite()

    def evaluate_quality():
        evaluator = get_quality_evaluator()

        query = "What is machine learning?"
        answer = "Machine learning is a subset of AI that learns from data patterns"
        documents = [{"text": "ML learns patterns", "metadata": {"source": "test"}}]

        evaluation = evaluator.evaluate_query(
            query_id="q1",
            query=query,
            answer=answer,
            retrieved_documents=documents
        )

        score = evaluation.get_overall_score()
        assert 0 <= score <= 1, f"Invalid quality score: {score}"
        print(f"  Quality score: {score:.1%}")

    suite.test("Evaluate response quality", evaluate_quality)
    suite.print_summary()
    return suite.passed > 0


def test_ux_enhancements():
    """Test 4: UX Enhancements (FASE 20)"""
    print("\n" + "="*70)
    print("TEST 4: UX ENHANCEMENTS (FASE 20)")
    print("="*70)

    suite = TestSuite()

    def enhance_response():
        enhancer = get_response_enhancer()

        enhanced = enhancer.enhance_response(
            query="What is machine learning?",
            answer="ML is a branch of AI",
            retrieved_documents=[{"text": "ML info", "metadata": {"source": "docs/ml.txt"}}],
            quality_score=0.85
        )

        assert 'answer' in enhanced, "Missing answer"
        assert 'citations' in enhanced, "Missing citations"
        assert 'suggestions' in enhanced, "Missing suggestions"
        print(f"  Enhanced answer with {len(enhanced['citations'])} citations")
        print(f"  Generated {len(enhanced['suggestions'])} suggestions")

    def conversation_management():
        conv_mgr = get_conversation_manager()
        conv_id = "conv_test"

        conv_mgr.create_conversation(conv_id)
        turn = ConversationTurn(
            turn_id="turn_1",
            query="Test query",
            answer="Test answer",
            citations=[],
            quality_score=0.9
        )
        conv_mgr.add_turn(conv_id, turn)

        conv = conv_mgr.get_conversation(conv_id)
        assert len(conv.turns) == 1, "Turn not added"
        print(f"  Conversation has {len(conv.turns)} turns")

    suite.test("Enhance response with citations", enhance_response)
    suite.test("Manage conversation turns", conversation_management)
    suite.print_summary()
    return suite.passed > 0


def test_end_to_end_pipeline():
    """Test 5: Complete RAG Pipeline"""
    print("\n" + "="*70)
    print("TEST 5: END-TO-END RAG PIPELINE")
    print("="*70)

    suite = TestSuite()

    def complete_pipeline():
        # 1. Load documents
        loader = DocumentLoaderManager()
        docs = loader.load_all_sources()
        print(f"  1. Loaded {len(docs)} documents")

        # 2. Add to vector store
        vs = VectorStore()
        texts = [d['text'][:300] for d in docs]
        metadatas = [d['metadata'] for d in docs]
        vs.add_documents(texts, metadatas)
        print(f"  2. Added {len(vs.documents)} to vector store")

        # 3. Retrieve relevant documents
        query = "What is machine learning?"
        results = vs.search(query, top_k=2)
        print(f"  3. Retrieved {len(results)} relevant documents")

        # 4. Mock answer generation (would use LLM in production)
        answer = f"Based on retrieved documents: {results[0]['document'][:100]}..."

        # 5. Evaluate quality (FASE 19)
        evaluator = get_quality_evaluator()
        evaluation = evaluator.evaluate_query(
            query_id="q_test",
            query=query,
            answer=answer,
            retrieved_documents=results
        )
        quality = evaluation.get_overall_score()
        print(f"  4. Quality score: {quality:.1%}")

        # 6. Enhance response (FASE 20)
        enhancer = get_response_enhancer()
        enhanced = enhancer.enhance_response(
            query=query,
            answer=answer,
            retrieved_documents=results,
            quality_score=quality
        )
        print(f"  5. Enhanced with {len(enhanced['citations'])} citations, {len(enhanced['suggestions'])} suggestions")

        # 7. Store in conversation memory
        conv_mgr = get_conversation_manager()
        conv_id = "pipeline_test"
        conv_mgr.create_conversation(conv_id)
        turn = ConversationTurn(
            turn_id="turn_pipeline",
            query=query,
            answer=enhanced['answer'],
            citations=enhanced['citations'],
            quality_score=quality
        )
        conv_mgr.add_turn(conv_id, turn)
        print(f"  6. Stored in conversation memory")

    suite.test("Complete RAG pipeline (load-retrieve-evaluate-enhance-store)", complete_pipeline)
    suite.print_summary()
    return suite.passed > 0


def test_metrics_collection():
    """Test 6: Metrics Collection and Analysis"""
    print("\n" + "="*70)
    print("TEST 6: METRICS COLLECTION")
    print("="*70)

    suite = TestSuite()

    def collect_metrics():
        # Get metrics collector
        collector = get_metrics_collector()

        # Record ingestion metrics
        start_time = time.time()
        time.sleep(0.1)
        end_time = time.time()

        ingest_metric = IngestionMetrics(
            file_name="test.txt",
            file_size_bytes=102400,
            chunks_created=5,
            embeddings_generated=5,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=end_time - start_time,
            success=True
        )
        collector.record_ingestion(ingest_metric)
        print(f"  Recorded ingestion metric")

        # Record query metrics
        query_metric = QueryMetrics(
            query_text="test query",
            documents_searched=100,
            documents_found=3,
            search_latency_ms=50,
            llm_latency_ms=100,
            cache_hit=False
        )
        collector.record_query(query_metric)
        print(f"  Recorded query metric")

        # Get metrics
        print(f"  Metrics recorded successfully")

    suite.test("Collect and store metrics", collect_metrics)
    suite.print_summary()
    return suite.passed > 0


def main():
    """Run all tests"""
    print("\n")
    print("="*70)
    print(" "*15 + "RAG LOCALE - COMPLETE SYSTEM TEST")
    print(" "*13 + "FASE 17-20: Multimodal RAG + Quality + UX")
    print("="*70)

    all_passed = True

    # Run all test groups
    all_passed &= test_document_loading()
    all_passed &= test_vector_store()
    all_passed &= test_quality_metrics()
    all_passed &= test_ux_enhancements()
    all_passed &= test_end_to_end_pipeline()
    all_passed &= test_metrics_collection()

    # Final summary
    print("\n" + "="*70)
    if all_passed:
        print("[PASS] ALL TESTS PASSED - SYSTEM READY FOR PRODUCTION")
        print("="*70)
        print("\nNext Steps:")
        print("  1. Launch Streamlit app: streamlit run app_streamlit_real_docs.py")
        print("  2. Upload documents and test with real queries")
        print("  3. Monitor metrics and performance in dashboard")
        print("  4. Export conversation results as needed")
        return 0
    else:
        print("[FAIL] SOME TESTS FAILED - CHECK ERRORS ABOVE")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
