#!/usr/bin/env python3
"""
System Verification Script
Verifica che tutti i FASE 5 fix siano in place prima di procedere
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check(condition, message):
    if condition:
        print(f"[OK] {message}")
        return True
    else:
        print(f"[ERROR] {message}")
        return False

def main():
    print("\n" + "=" * 60)
    print("SYSTEM VERIFICATION - FASE 5")
    print("=" * 60 + "\n")

    checks_passed = 0
    checks_total = 0

    # Check 1: Python version
    checks_total += 1
    py_version = sys.version_info
    if check(py_version.major >= 3 and py_version.minor >= 10,
             f"Python {py_version.major}.{py_version.minor} (OK if >= 3.10)"):
        checks_passed += 1

    # Check 2: Dependencies
    checks_total += 1
    try:
        import google.genai
        import fastapi
        import streamlit
        import numpy
        import pypdf
        from docx import Document
        if check(True, "All critical dependencies installed"):
            checks_passed += 1
    except ImportError as e:
        check(False, f"Missing dependency: {e}")

    # Check 3: .env file
    checks_total += 1
    env_file = Path(__file__).parent / ".env"
    if check(env_file.exists(), ".env file exists"):
        checks_passed += 1
    else:
        print("  -> Create .env with: GEMINI_API_KEY=your-key")

    # Check 4: Directory structure
    checks_total += 1
    src_dir = Path(__file__).parent / "src"
    required_files = [
        "api.py",
        "config.py",
        "document_ingestion.py",
        "llm_service.py",
        "pdf_worker.py",
        "vector_store.py",
    ]
    all_exist = all((src_dir / f).exists() for f in required_files)
    if check(all_exist, f"All source files present ({len(required_files)} files)"):
        checks_passed += 1

    # Check 5: Vector store file (if exists)
    checks_total += 1
    vector_store = Path(__file__).parent / "data" / "vector_db" / "vector_store.pkl"
    if vector_store.exists():
        size_mb = vector_store.stat().st_size / (1024 * 1024)
        if check(size_mb > 0.1, f"Vector store exists ({size_mb:.1f} MB)"):
            checks_passed += 1
    else:
        if check(True, "Vector store doesn't exist (will be created)"):
            checks_passed += 1

    # Check 6: FASE 5 - Timeout 300s
    checks_total += 1
    doc_ing = Path(__file__).parent / "src" / "document_ingestion.py"
    content = doc_ing.read_text(encoding='utf-8', errors='ignore')
    if check("timeout=300" in content, "FASE 5: Subprocess timeout = 300s"):
        checks_passed += 1
    else:
        print("  -> Update timeout in src/document_ingestion.py line 137")

    # Check 7: FASE 5 - Rate limit backoff
    checks_total += 1
    llm_service = Path(__file__).parent / "src" / "llm_service.py"
    content = llm_service.read_text(encoding='utf-8', errors='ignore')
    if check("time.sleep(0.3)" in content, "FASE 5: Rate-limit backoff (300ms)"):
        checks_passed += 1
    else:
        print("  -> Add time.sleep(0.3) in src/llm_service.py get_embedding()")

    # Check 8: FASE 5 - GC in PDF worker
    checks_total += 1
    pdf_worker = Path(__file__).parent / "src" / "pdf_worker.py"
    content = pdf_worker.read_text(encoding='utf-8', errors='ignore')
    if check("gc.collect()" in content, "FASE 5: PDF GC collection every 10 pages"):
        checks_passed += 1
    else:
        print("  -> Add gc.collect() in src/pdf_worker.py")

    # Check 9: Safety filters enabled
    checks_total += 1
    content = llm_service.read_text(encoding='utf-8', errors='ignore')
    if check("BLOCK_MEDIUM_AND_ABOVE" in content and "BLOCK_NONE" not in content,
             "CRITICAL-3: Safety filters enabled (BLOCK_MEDIUM_AND_ABOVE)"):
        checks_passed += 1
    else:
        print("  -> Enable safety filters in src/llm_service.py")

    # Check 10: Requirements.txt
    checks_total += 1
    req_file = Path(__file__).parent / "setup" / "requirements.txt"
    content = req_file.read_text(encoding='utf-8', errors='ignore')
    has_required = all(pkg in content for pkg in ["pypdf", "python-docx", "fastapi", "streamlit", "numpy"])
    has_no_bad = "llama-index-embeddings-ollama" not in content
    if check(has_required and has_no_bad, "Requirements.txt updated for Python 3.14"):
        checks_passed += 1
    else:
        print("  -> Update setup/requirements.txt with new versions")

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {checks_passed}/{checks_total} checks passed")
    print("=" * 60)

    if checks_passed == checks_total:
        print("\n[SUCCESS] System ready! You can start:")
        print("  Terminal 1: python src/api.py")
        print("  Terminal 2: streamlit run src/frontend.py")
        return 0
    else:
        print(f"\n[WARNING] {checks_total - checks_passed} checks failed.")
        print("Fix the errors above before starting.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
