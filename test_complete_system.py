#!/usr/bin/env python3
"""
Test end-to-end completo del sistema RAG con timeout handling
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import config, VECTOR_DB_DIR, DOCUMENTS_DIR
from llm_service import get_llm_service
from rag_engine import RAGEngine

def test_vector_store_load():
    """Test 1: Load vector store"""
    print("\n" + "="*70)
    print("TEST 1: LOADING VECTOR STORE")
    print("="*70)

    try:
        from vector_store import VectorStore

        vs = VectorStore()
        stats = vs.get_stats()
        print(f"[PASS] Vector store loaded successfully")
        print(f"  Total documents: {stats.get('total_documents', 'N/A')}")
        print(f"  Total chunks: {stats.get('total_chunks', 'N/A')}")
        return True

    except Exception as e:
        print(f"[FAIL] Error loading vector store: {e}")
        return False


def test_rag_engine_init():
    """Test 2: Initialize RAG Engine"""
    print("\n" + "="*70)
    print("TEST 2: INITIALIZING RAG ENGINE")
    print("="*70)

    try:
        engine = RAGEngine()
        print(f"[PASS] RAG Engine initialized successfully")
        print(f"  Model: {config.gemini.model_name}")
        print(f"  Timeout: {config.gemini.request_timeout}s")
        return True, engine

    except Exception as e:
        print(f"[FAIL] Error initializing RAG Engine: {e}")
        return False, None


def test_llm_response(engine):
    """Test 3: LLM response generation test"""
    print("\n" + "="*70)
    print("TEST 3: LLM RESPONSE GENERATION")
    print("="*70)

    if not engine:
        print("[SKIP] Engine not initialized")
        return False

    try:
        prompt = "Cos'e il machine learning? Rispondi brevemente."
        print(f"Prompt: '{prompt}'")
        print("Generating response...")

        # Test LLM directly
        response = engine.llm.completion(prompt)

        if response and len(response) > 0:
            print(f"[PASS] LLM response generation successful")
            print(f"  Response length: {len(response)} chars")
            print(f"  Sample: {response[:80]}...")
            return True
        else:
            print("[FAIL] Empty LLM response")
            return False

    except Exception as e:
        print(f"[FAIL] Error in LLM response: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_embedding_batch():
    """Test 4: Batch embedding"""
    print("\n" + "="*70)
    print("TEST 4: BATCH EMBEDDING")
    print("="*70)

    try:
        llm_service = get_llm_service()

        texts = [
            "Test embedding numero uno",
            "Test embedding numero due",
            "Test embedding numero tre",
        ]

        print(f"Processing {len(texts)} texts...")
        embeddings = llm_service.get_embeddings_batch(texts, batch_size=10)

        if embeddings and len(embeddings) == len(texts):
            print(f"[PASS] Batch embedding successful")
            print(f"  Embeddings: {len(embeddings)}")
            print(f"  Vector lengths: {[len(e) for e in embeddings]}")
            return True
        else:
            print("[FAIL] Wrong number of embeddings")
            return False

    except Exception as e:
        print(f"[FAIL] Error in batch embedding: {e}")
        return False


def test_timeout_recovery():
    """Test 5: Timeout recovery (simulated)"""
    print("\n" + "="*70)
    print("TEST 5: TIMEOUT CONFIGURATION VERIFICATION")
    print("="*70)

    try:
        print(f"Request timeout: {config.gemini.request_timeout}s")
        print(f"Embedding timeout: {config.gemini.embedding_timeout}s")
        print(f"Completion timeout: {config.gemini.completion_timeout}s")
        print(f"Max retries: {config.gemini.max_retries}")
        print(f"Retry delay base: {config.gemini.retry_base_delay}s")

        if (config.gemini.request_timeout >= 300 and
            config.gemini.max_retries >= 5 and
            config.gemini.retry_base_delay >= 1.0):
            print("[PASS] Timeout configuration is adequate")
            return True
        else:
            print("[FAIL] Timeout configuration is insufficient")
            return False

    except Exception as e:
        print(f"[FAIL] Error checking configuration: {e}")
        return False


def main():
    print("\n" + "="*70)
    print("RAG LOCALE - COMPLETE SYSTEM TEST")
    print("="*70)

    results = {}

    # Test 1
    results["Vector Store Load"] = test_vector_store_load()

    # Test 2
    engine_result = test_rag_engine_init()
    results["RAG Engine Init"] = engine_result[0]
    engine = engine_result[1]

    # Test 3
    results["LLM Response"] = test_llm_response(engine)

    # Test 4
    results["Batch Embedding"] = test_embedding_batch()

    # Test 5
    results["Timeout Configuration"] = test_timeout_recovery()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = 0
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{test_name}: {status}")
        if result:
            passed += 1

    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    print("\n" + "="*70)
    if passed == total:
        print("[PASS] ALL TESTS PASSED - SYSTEM FULLY OPERATIONAL!")
    else:
        print(f"[WARN] {total - passed} test(s) failed - see details above")
    print("="*70 + "\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
