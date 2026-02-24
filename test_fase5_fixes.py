#!/usr/bin/env python3
"""
Test Suite per FASE 5 Hotfixes
Verifica:
1. Gemini API connectivity
2. PDF processing con timeout allungato
3. Performance ricerca vettorizzata (matrix optimization)
4. Cleanup file temporanei
5. Rate-limiting backoff
"""

import sys
import time
import logging
from pathlib import Path
import tempfile
import shutil

# Setup paths
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config, DOCUMENTS_DIR, VECTOR_DB_DIR
from llm_service import get_llm_service
from vector_store import get_vector_store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TEST_FASE5")

class TestFase5:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def log_pass(self, test_name, msg=""):
        self.passed += 1
        logger.info(f"[PASS] {test_name} {msg}")

    def log_fail(self, test_name, msg=""):
        self.failed += 1
        logger.error(f"[FAIL] {test_name} {msg}")

    def log_warn(self, test_name, msg=""):
        self.warnings += 1
        logger.warning(f"[WARN] {test_name} {msg}")

    def print_summary(self):
        print("\n" + "="*60)
        print("TEST SUMMARY - FASE 5 FIXES")
        print("="*60)
        print(f"[PASS] Passed: {self.passed}")
        print(f"[FAIL] Failed: {self.failed}")
        print(f"[WARN] Warnings: {self.warnings}")
        print("="*60 + "\n")

        if self.failed == 0 and self.warnings == 0:
            print("[OK] TUTTI I TEST PASSATI! Pronto per ingestione 71 documenti.\n")
            return True
        elif self.failed == 0:
            print("[OK] Funzionamento, ma leggere i warnings.\n")
            return True
        else:
            print("[ERROR] Correggere i failed test prima di procedere.\n")
            return False


def test_gemini_connection(tester):
    """Test 1: Verifica connessione Gemini API"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Gemini API Connection")
    logger.info("="*60)

    try:
        llm = get_llm_service()
        if llm.check_health():
            tester.log_pass("Gemini Health Check", f"Model: {llm.model_name}")
            return True
        else:
            tester.log_fail("Gemini Health Check", "Health check returned False")
            return False
    except Exception as e:
        tester.log_fail("Gemini Health Check", str(e))
        return False


def test_embedding_generation(tester):
    """Test 2: Genera embedding con rate-limit backoff"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Embedding Generation (con backoff)")
    logger.info("="*60)

    try:
        llm = get_llm_service()
        test_text = "Questo è un test di embedding per RAG Locale"

        start = time.perf_counter()
        embedding = llm.get_embedding(test_text)
        elapsed = time.perf_counter() - start

        if isinstance(embedding, list) and len(embedding) > 0:
            tester.log_pass(
                "Embedding Generation",
                f"len={len(embedding)}, time={elapsed:.2f}s (incl. 300ms backoff)"
            )

            # Verifica che il backoff è stato applicato (almeno 0.3s)
            if elapsed >= 0.3:
                tester.log_pass("Rate-Limit Backoff", f"Backoff applied: {elapsed:.2f}s ≥ 0.3s")
            else:
                tester.log_warn("Rate-Limit Backoff", f"Backoff < 0.3s: {elapsed:.2f}s (possibile caching)")
            return True
        else:
            tester.log_fail("Embedding Generation", "Invalid embedding returned")
            return False
    except Exception as e:
        tester.log_fail("Embedding Generation", str(e))
        return False


def test_vector_store_matrix_optimization(tester):
    """Test 3: Verifica matrix optimization per ricerca vettorizzata"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Vector Store Matrix Optimization (HIGH-5)")
    logger.info("="*60)

    try:
        vs = get_vector_store()

        # Verifica che la matrice è inizializzata
        if vs._embedding_matrix is None:
            tester.log_pass("Matrix Initialization", "Empty store, matrix = None (expected)")
        else:
            tester.log_pass("Matrix Initialization", f"Matrix shape: {vs._embedding_matrix.shape}")

        # Aggiungi documenti di test
        test_docs = [
            "Python è un linguaggio di programmazione versatile",
            "Il machine learning usa algoritmi e dati",
            "La programmazione è l'arte di risolvere problemi"
        ]

        docs_before = len(vs.documents)
        vs.add_documents(test_docs)
        docs_after = len(vs.documents)

        if vs._embedding_matrix is not None and docs_after > docs_before:
            tester.log_pass("Document Addition", f"Aggiunti {docs_after - docs_before} docs, matrix rebuilt: {vs._embedding_matrix.shape}")
        else:
            tester.log_fail("Document Addition", "Matrix not properly rebuilt")
            return False

        # Test ricerca veloce
        start = time.perf_counter()
        results = vs.search("linguaggio di programmazione", top_k=2)
        elapsed = time.perf_counter() - start

        if len(results) > 0 and elapsed < 0.05:  # Deve essere <50ms con matrix optimization
            tester.log_pass(
                "Search Performance",
                f"Found {len(results)} results in {elapsed*1000:.1f}ms (matrix optimization working)"
            )
            return True
        elif len(results) > 0:
            tester.log_warn(
                "Search Performance",
                f"Found {len(results)} results but took {elapsed*1000:.1f}ms (slower than expected)"
            )
            return True
        else:
            tester.log_fail("Search Performance", "No results found")
            return False

    except Exception as e:
        tester.log_fail("Vector Store Matrix", str(e))
        return False


def test_temp_file_cleanup(tester):
    """Test 4: Verifica cleanup file temporanei .json.temp"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Temporary File Cleanup (MEDIUM-3)")
    logger.info("="*60)

    try:
        # Controlla directory documents per file .json.temp orfani
        temp_files = list(DOCUMENTS_DIR.glob("*.json.temp"))

        if len(temp_files) == 0:
            tester.log_pass("Temp File Cleanup", "No orphaned .json.temp files found")
            return True
        else:
            tester.log_warn(
                "Temp File Cleanup",
                f"Found {len(temp_files)} orphaned files: {[f.name for f in temp_files]}"
            )
            # Pulizia automatica
            for f in temp_files:
                try:
                    f.unlink()
                    logger.info(f"Cleaned up: {f.name}")
                except:
                    pass
            return True

    except Exception as e:
        tester.log_fail("Temp File Cleanup", str(e))
        return False


def test_atomic_save(tester):
    """Test 5: Verifica save atomico con .pkl.tmp"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Atomic Save (MEDIUM-2)")
    logger.info("="*60)

    try:
        # Verifica che il file store principale esiste e che non ci sono .pkl.tmp orfani
        store_file = VECTOR_DB_DIR / "vector_store.pkl"
        temp_store_file = VECTOR_DB_DIR / "vector_store.pkl.tmp"

        if store_file.exists():
            tester.log_pass("Store File", f"Main store exists: {store_file.stat().st_size} bytes")
        else:
            tester.log_pass("Store File", "New store (will be created on first add)")

        if temp_store_file.exists():
            tester.log_warn("Atomic Save", f"Orphaned .pkl.tmp file found: {temp_store_file.name}")
            try:
                temp_store_file.unlink()
                logger.info("Cleaned up orphaned .pkl.tmp")
            except:
                pass
        else:
            tester.log_pass("Atomic Save", "No orphaned .pkl.tmp files")

        return True

    except Exception as e:
        tester.log_fail("Atomic Save", str(e))
        return False


def test_pdf_worker_availability(tester):
    """Test 6: Verifica che pdf_worker.py è disponibile e gc è compilato"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: PDF Worker Availability")
    logger.info("="*60)

    try:
        pdf_worker = Path(__file__).parent / "src" / "pdf_worker.py"

        if not pdf_worker.exists():
            tester.log_fail("PDF Worker", f"File not found: {pdf_worker}")
            return False

        # Verifica che contiene gc.collect()
        try:
            content = pdf_worker.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = pdf_worker.read_text(encoding='latin-1')

        if "gc.collect()" in content:
            tester.log_pass("PDF Worker GC", "gc.collect() found in pdf_worker.py")
        else:
            tester.log_fail("PDF Worker GC", "gc.collect() not found (FASE 5 fix missing?)")
            return False

        # Verifica timeout aggiornato in document_ingestion.py
        doc_ing = Path(__file__).parent / "src" / "document_ingestion.py"
        try:
            content = doc_ing.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = doc_ing.read_text(encoding='latin-1')

        if "timeout=300" in content:
            tester.log_pass("Subprocess Timeout", "timeout=300 found (5 minutes)")
        else:
            tester.log_warn("Subprocess Timeout", "timeout=300 not found, check FASE 5 implementation")

        return True

    except Exception as e:
        tester.log_fail("PDF Worker Availability", str(e))
        return False


def test_safety_filters(tester):
    """Test 7: Verifica safety filters abilitati"""
    logger.info("\n" + "="*60)
    logger.info("TEST 7: Safety Filters (CRITICAL-3)")
    logger.info("="*60)

    try:
        llm_service_file = Path(__file__).parent / "src" / "llm_service.py"
        try:
            content = llm_service_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = llm_service_file.read_text(encoding='latin-1')

        # Verifica BLOCK_MEDIUM_AND_ABOVE (non BLOCK_NONE)
        if "BLOCK_MEDIUM_AND_ABOVE" in content and "BLOCK_NONE" not in content:
            tester.log_pass("Safety Filters", "BLOCK_MEDIUM_AND_ABOVE enabled")
            return True
        else:
            tester.log_fail("Safety Filters", "Safety filters not properly configured")
            return False

    except Exception as e:
        tester.log_fail("Safety Filters", str(e))
        return False


def test_requirements_updated(tester):
    """Test 8: Verifica requirements.txt aggiornato"""
    logger.info("\n" + "="*60)
    logger.info("TEST 8: Requirements.txt Updated")
    logger.info("="*60)

    try:
        req_file = Path(__file__).parent / "setup" / "requirements.txt"
        try:
            content = req_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            content = req_file.read_text(encoding='latin-1')

        issues = []

        # Verifica che pypdf è presente (non pdfplumber)
        if "pypdf" not in content:
            issues.append("pypdf not found in requirements.txt")
        else:
            tester.log_pass("Requirements - pypdf", "pypdf is present")

        # Verifica python-docx (non python-pptx per DOCX)
        if "python-docx" not in content:
            issues.append("python-docx not found")
        else:
            tester.log_pass("Requirements - python-docx", "python-docx is present")

        # Verifica fastapi, streamlit, numpy
        for pkg in ["fastapi", "streamlit", "numpy"]:
            if pkg not in content:
                issues.append(f"{pkg} not found")
            else:
                tester.log_pass(f"Requirements - {pkg}", f"{pkg} is present")

        # Verifica che NON c'è llama-index-embeddings-ollama (incompatibile Python 3.14)
        if "llama-index-embeddings-ollama" in content:
            tester.log_warn("Requirements", "llama-index-embeddings-ollama still present (Python 3.14 incompatible)")
        else:
            tester.log_pass("Requirements - Python 3.14", "Incompatible packages removed")

        return len(issues) == 0

    except Exception as e:
        tester.log_fail("Requirements Check", str(e))
        return False


def main():
    logger.info("\n" + "=" * 60)
    logger.info("INIZIO TEST FASE 5 HOTFIXES")
    logger.info("=" * 60)

    tester = TestFase5()

    # Esegui tutti i test
    tests = [
        ("Gemini Connection", test_gemini_connection),
        ("Embedding Generation", test_embedding_generation),
        ("Matrix Optimization", test_vector_store_matrix_optimization),
        ("Temp File Cleanup", test_temp_file_cleanup),
        ("Atomic Save", test_atomic_save),
        ("PDF Worker", test_pdf_worker_availability),
        ("Safety Filters", test_safety_filters),
        ("Requirements", test_requirements_updated),
    ]

    for test_name, test_func in tests:
        try:
            test_func(tester)
        except Exception as e:
            logger.error(f"Unexpected error in {test_name}: {e}", exc_info=True)
            tester.log_fail(test_name, f"Unexpected exception: {e}")

    # Stampa summary
    success = tester.print_summary()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
