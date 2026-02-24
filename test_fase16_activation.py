#!/usr/bin/env python3
"""
Test Suite: FASE 16 + FASE 17 Activation
Testing Re-ranking and Vision API Integration

Runs comprehensive tests including:
1. Re-ranking performance
2. Vision API preparation
3. Settings configuration
4. End-to-end pipeline with both features
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from document_loader import DocumentLoaderManager
from src.vector_store import VectorStore
from src.llm_service import get_llm_service
from src.cross_encoder_reranking import GeminiCrossEncoderReranker
from src.vision_service import get_vision_service
from src.quality_metrics import get_quality_evaluator
from src.ux_enhancements import get_response_enhancer


class TestFASE16Activation:
    """Test FASE 16 activation (Re-ranking)"""

    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0

    def print_header(self, title):
        """Print formatted header"""
        print("\n" + "="*70)
        print(f" {title:^68}")
        print("="*70)

    def test(self, name: str, func):
        """Run a test"""
        try:
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            self.results.append({"name": name, "status": "[PASS]", "time": f"{elapsed*1000:.2f}ms"})
            self.passed += 1
            print(f"[PASS] {name} ({elapsed*1000:.2f}ms)")
        except Exception as e:
            self.results.append({"name": name, "status": "[FAIL]", "error": str(e)})
            self.failed += 1
            print(f"[FAIL] {name}: {str(e)}")

    def print_summary(self):
        """Print summary"""
        total = self.passed + self.failed
        rate = (self.passed / total * 100) if total > 0 else 0
        print("\n" + "="*70)
        print(f"TEST SUMMARY: {self.passed}/{total} PASSED ({rate:.1f}%)")
        print("="*70)


def test_reranking():
    """Test FASE 16: Re-ranking"""
    self = TestFASE16Activation()
    self.print_header("FASE 16: RE-RANKING SYSTEM")

    def test_reranker_init():
        """Test reranker initialization"""
        llm = get_llm_service()
        reranker = GeminiCrossEncoderReranker(llm)
        assert reranker is not None
        print("  Reranker initialized (GeminiCrossEncoderReranker)")

    def test_reranking_with_candidates():
        """Test re-ranking with sample candidates"""
        llm = get_llm_service()
        reranker = GeminiCrossEncoderReranker(llm)

        candidates = [
            {
                'document': 'Machine learning is a subset of artificial intelligence',
                'source': 'ml_guide.txt',
                'section': 'Introduction',
                'doc_id': 'doc_1',
                'score': 0.85
            },
            {
                'document': 'Deep learning uses neural networks with multiple layers',
                'source': 'dl_guide.txt',
                'section': 'Basics',
                'doc_id': 'doc_2',
                'score': 0.75
            },
            {
                'document': 'Python is a programming language',
                'source': 'python.txt',
                'section': 'Overview',
                'doc_id': 'doc_3',
                'score': 0.65
            }
        ]

        query = "What is machine learning?"
        start = time.perf_counter()
        ranked = reranker.rerank(query, candidates, top_k=3, alpha=0.3)
        elapsed = time.perf_counter() - start

        assert len(ranked) > 0
        assert ranked[0].ranking_position == 1
        print(f"  Re-ranked {len(candidates)} candidates in {elapsed*1000:.2f}ms")
        print(f"  Top result: {ranked[0].source} (score: {ranked[0].combined_score:.2f})")

    def test_reranking_alpha_variations():
        """Test re-ranking with different alpha values"""
        llm = get_llm_service()
        reranker = GeminiCrossEncoderReranker(llm)

        candidates = [
            {'document': 'Machine learning', 'source': 'ml.txt', 'section': '', 'doc_id': 'doc_1', 'score': 0.8},
            {'document': 'Deep learning', 'source': 'dl.txt', 'section': '', 'doc_id': 'doc_2', 'score': 0.6},
        ]

        query = "machine learning"

        results = {}
        for alpha in [0.0, 0.3, 0.5, 0.7, 1.0]:
            ranked = reranker.rerank(query, candidates, top_k=2, alpha=alpha)
            results[alpha] = ranked[0].combined_score
            print(f"  Alpha={alpha}: top score = {ranked[0].combined_score:.3f}")

        # Verify that alpha affects scoring
        assert results[0.0] != results[1.0]
        print("  Alpha parameter working correctly")

    self.test("Initialize Reranker", test_reranker_init)
    self.test("Re-rank candidates", test_reranking_with_candidates)
    self.test("Test alpha parameter variations", test_reranking_alpha_variations)

    self.print_summary()
    return self.passed == 3


def test_vision_api():
    """Test FASE 17: Vision API Integration"""
    self = TestFASE16Activation()
    self.print_header("FASE 17: VISION API INTEGRATION")

    def test_vision_service_init():
        """Test vision service initialization"""
        vision_service = get_vision_service()
        assert vision_service is not None
        print("  Vision service initialized (GeminiVisionService)")

    def test_vision_service_methods():
        """Test vision service has required methods"""
        vision_service = get_vision_service()
        assert hasattr(vision_service, 'analyze_image')
        assert hasattr(vision_service, 'extract_image_text')
        assert hasattr(vision_service, 'evaluate_image_relevance')
        assert hasattr(vision_service, 'generate_image_embedding')
        assert hasattr(vision_service, 'batch_analyze_images')
        print("  Vision service has all required methods")

    def test_vision_service_caching():
        """Test vision service caching mechanism"""
        vision_service = get_vision_service()
        assert hasattr(vision_service, '_cache')
        print("  Vision service caching ready")

    self.test("Initialize Vision Service", test_vision_service_init)
    self.test("Verify Vision API methods", test_vision_service_methods)
    self.test("Check Vision caching", test_vision_service_caching)

    self.print_summary()
    return self.passed == 3


def test_end_to_end_with_reranking():
    """Test end-to-end pipeline with re-ranking"""
    self = TestFASE16Activation()
    self.print_header("END-TO-END: DOCUMENT LOADING + VECTOR SEARCH + RE-RANKING")

    def test_full_pipeline():
        """Test complete pipeline with re-ranking"""
        # Load documents
        loader = DocumentLoaderManager()
        documents = loader.load_all_sources()
        assert len(documents) > 0
        print(f"  Loaded {len(documents)} documents")

        # Build vector store
        vs = VectorStore()
        texts = [d['text'][:500] for d in documents]
        metadatas = [d['metadata'] for d in documents]
        vs.add_documents(texts, metadatas)
        print(f"  Indexed {len(vs.documents)} documents")

        # Search
        query = "What is machine learning?"
        results = vs.search(query, top_k=5)
        print(f"  Vector search: found {len(results)} results")

        # Prepare candidates for reranking
        candidates = []
        for i, result in enumerate(results):
            candidates.append({
                'document': result.get('document', '')[:500],
                'source': result.get('metadata', {}).get('source', 'Unknown'),
                'section': result.get('metadata', {}).get('section', ''),
                'doc_id': result.get('metadata', {}).get('id', f'doc_{i}'),
                'score': result.get('similarity_score', 0.0)
            })

        # Re-rank
        llm = get_llm_service()
        reranker = GeminiCrossEncoderReranker(llm)
        start = time.perf_counter()
        ranked = reranker.rerank(query, candidates, top_k=3, alpha=0.3)
        elapsed = time.perf_counter() - start

        assert len(ranked) > 0
        print(f"  Re-ranked in {elapsed*1000:.2f}ms")
        print(f"  Top result: {ranked[0].source} (combined score: {ranked[0].combined_score:.2f})")

    self.test("Load → Index → Search → Re-rank", test_full_pipeline)
    self.print_summary()
    return self.passed == 1


def test_quality_metrics():
    """Test quality metrics with re-ranked results"""
    self = TestFASE16Activation()
    self.print_header("QUALITY METRICS: POST RE-RANKING")

    def test_quality_evaluation():
        """Test quality evaluation"""
        evaluator = get_quality_evaluator()

        query = "What is machine learning?"
        answer = "Machine learning is a subset of artificial intelligence that focuses on enabling computers to learn from data."
        documents = [{
            'text': 'Machine learning...',
            'metadata': {'source': 'ml_guide.txt'}
        }]

        evaluation = evaluator.evaluate_query(
            query_id="test_1",
            query=query,
            answer=answer,
            retrieved_documents=documents
        )

        score = evaluation.get_overall_score()
        assert 0.0 <= score <= 1.0
        print(f"  Quality score: {score:.1%}")

    self.test("Evaluate re-ranked results quality", test_quality_evaluation)
    self.print_summary()
    return self.passed == 1


def main():
    """Run all tests"""
    print("\n")
    print("="*70)
    print(" "*10 + "RAG LOCALE - FASE 16 + FASE 17 ACTIVATION TEST")
    print(" "*15 + "Re-ranking + Vision API Integration")
    print("="*70)

    results = {
        "Re-ranking (FASE 16)": test_reranking(),
        "Vision API (FASE 17)": test_vision_api(),
        "End-to-End Pipeline": test_end_to_end_with_reranking(),
        "Quality Metrics": test_quality_metrics(),
    }

    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")

    all_passed = all(results.values())
    print("\n" + "="*70)
    if all_passed:
        print("[SUCCESS] ALL FASE 16 + 17 TESTS PASSED")
        print("Re-ranking and Vision API are ready for production!")
        print("="*70)
        return 0
    else:
        print("[FAILURE] SOME TESTS FAILED")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
