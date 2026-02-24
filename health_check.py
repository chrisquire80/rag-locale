#!/usr/bin/env python3
"""
Health check: verifica stato vector store e connessione API
"""

import sys
import os
from pathlib import Path
import pickle

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import config, VECTOR_DB_DIR, DOCUMENTS_DIR
from llm_service import get_llm_service

def check_vector_store():
    """Verifica che il vector store contiene dati"""
    print("\n" + "="*70)
    print("1. CHECKING VECTOR STORE")
    print("="*70)

    vector_store_path = VECTOR_DB_DIR / "vector_store.pkl"
    print(f"Vector store path: {vector_store_path}")

    if not vector_store_path.exists():
        print("[FAIL] Vector store file NOT FOUND")
        return False

    try:
        with open(vector_store_path, 'rb') as f:
            data = pickle.load(f)

        file_size_mb = vector_store_path.stat().st_size / (1024*1024)
        print(f"[PASS] Vector store exists")
        print(f"  File size: {file_size_mb:.2f} MB")

        # Try to get stats if available
        if hasattr(data, '__dict__'):
            print(f"  Type: {type(data).__name__}")
            if hasattr(data, 'get_stats'):
                try:
                    stats = data.get_stats()
                    print(f"  [PASS] Stats: {stats}")
                except:
                    pass

        return True

    except Exception as e:
        print(f"[FAIL] Error reading vector store: {e}")
        return False


def check_documents():
    """Verifica documenti nel folder"""
    print("\n" + "="*70)
    print("2. CHECKING DOCUMENTS FOLDER")
    print("="*70)

    print(f"Documents folder: {DOCUMENTS_DIR}")

    if not DOCUMENTS_DIR.exists():
        print("[FAIL] Documents folder doesn't exist")
        return False

    docs = list(DOCUMENTS_DIR.glob('*'))
    doc_files = [d for d in docs if d.is_file()]

    print(f"[PASS] Folder exists")
    print(f"  Total items: {len(docs)}")
    print(f"  Files: {len(doc_files)}")

    if doc_files:
        print(f"  Sample files:")
        for doc in doc_files[:5]:
            size_kb = doc.stat().st_size / 1024
            print(f"    - {doc.name} ({size_kb:.1f} KB)")
        if len(doc_files) > 5:
            print(f"    ... and {len(doc_files) - 5} more")

    return len(doc_files) > 0


def check_api_connection():
    """Verifica connessione API Gemini"""
    print("\n" + "="*70)
    print("3. CHECKING GEMINI API CONNECTION")
    print("="*70)

    try:
        print(f"Model: {config.gemini.model_name}")
        print(f"Embedding model: {config.gemini.embedding_model}")
        print(f"Timeouts configured:")
        print(f"  - Request: {config.gemini.request_timeout}s")
        print(f"  - Embedding: {config.gemini.embedding_timeout}s")
        print(f"  - Completion: {config.gemini.completion_timeout}s")
        print(f"  - Max retries: {config.gemini.max_retries}")

        llm_service = get_llm_service()

        print("\nTesting API health check...")
        if llm_service.check_health():
            print("[PASS] API connection successful")
            return True
        else:
            print("[FAIL] API health check failed")
            return False

    except Exception as e:
        print(f"[FAIL] Error connecting to API: {e}")
        return False


def test_embedding():
    """Test embedding function"""
    print("\n" + "="*70)
    print("4. TESTING EMBEDDING")
    print("="*70)

    try:
        llm_service = get_llm_service()

        test_text = "Questo e un test di embedding con timeout handling migliorato"
        print(f"Test text: '{test_text}'")

        print("Generating embedding (with improved timeout handling)...")
        embedding = llm_service.get_embedding(test_text)

        if embedding and len(embedding) > 0:
            print(f"[PASS] Embedding successful")
            print(f"  Vector length: {len(embedding)}")
            print(f"  Sample values: {embedding[:3]}")
            return True
        else:
            print("[FAIL] Empty embedding returned")
            return False

    except Exception as e:
        print(f"[FAIL] Error in embedding test: {e}")
        return False


def test_completion():
    """Test completion function"""
    print("\n" + "="*70)
    print("5. TESTING COMPLETION")
    print("="*70)

    try:
        llm_service = get_llm_service()

        prompt = "Rispondi brevemente: Cos'e un RAG system?"
        print(f"Prompt: '{prompt}'")

        print("Generating completion (with improved timeout handling)...")
        response = llm_service.completion(prompt)

        if response and len(response) > 0:
            print(f"[PASS] Completion successful")
            print(f"  Response length: {len(response)} chars")
            print(f"  Preview: {response[:100]}...")
            return True
        else:
            print("[FAIL] Empty completion returned")
            return False

    except Exception as e:
        print(f"[FAIL] Error in completion test: {e}")
        return False


def main():
    print("\n" + "="*70)
    print("RAG LOCALE - HEALTH CHECK")
    print("="*70)

    results = {
        "Vector Store": check_vector_store(),
        "Documents": check_documents(),
        "API Connection": check_api_connection(),
        "Embedding Test": test_embedding(),
        "Completion Test": test_completion(),
    }

    print("\n" + "="*70)
    print("HEALTH CHECK SUMMARY")
    print("="*70)

    for check_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{check_name}: {status}")

    all_passed = all(results.values())
    print("\n" + "="*70)
    if all_passed:
        print("[PASS] ALL CHECKS PASSED - SYSTEM READY!")
    else:
        print("[FAIL] SOME CHECKS FAILED - SEE DETAILS ABOVE")
    print("="*70 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
