#!/usr/bin/env python3
"""
Direct PDF Ingestion Script (No UI)
Ingestisce tutti i PDF senza Streamlit per evitare threading issues
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config, DOCUMENTS_DIR
from document_ingestion import DocumentIngestionPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("INGESTION")

def main():
    print("\n" + "="*80)
    print("RAG LOCALE - FULL PDF INGESTION (NO UI)")
    print("="*80 + "\n")

    pipeline = DocumentIngestionPipeline()

    # Get all PDF files
    pdf_files = sorted(list(DOCUMENTS_DIR.glob("*.pdf")))

    if not pdf_files:
        print("[ERROR] No PDF files found in", DOCUMENTS_DIR)
        return False

    print(f"[INFO] Found {len(pdf_files)} PDF files")
    print(f"[INFO] Starting ingestion...\n")

    start_time = time.time()
    total_chunks = 0
    successful = 0
    failed = 0
    failed_list = []

    for i, pdf_file in enumerate(pdf_files, 1):
        try:
            print(f"[{i:2d}/{len(pdf_files)}] ", end="", flush=True)

            chunks = pipeline.ingest_single_file(pdf_file, max_retries=3)

            if chunks > 0:
                total_chunks += chunks
                successful += 1
                print(f"OK: {pdf_file.name[:60]:<60} -> {chunks:2d} chunks")
            else:
                failed += 1
                failed_list.append(pdf_file.name)
                print(f"SKIP: {pdf_file.name[:60]:<60} (0 chunks)")

        except Exception as e:
            failed += 1
            failed_list.append(pdf_file.name)
            error_msg = str(e)[:50]
            print(f"FAIL: {pdf_file.name[:60]:<60} ({error_msg})")

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "="*80)
    print("INGESTION SUMMARY")
    print("="*80)
    print(f"Total files: {len(pdf_files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total chunks: {total_chunks}")
    print(f"Elapsed time: {elapsed:.1f}s ({elapsed/len(pdf_files):.1f}s per file)")
    print()

    if failed > 0:
        print(f"Failed files ({failed}):")
        for name in failed_list:
            print(f"  - {name}")
        print()

    # Vector store stats
    vs = pipeline.vector_store
    print(f"Vector store: {len(vs.documents)} documents")
    if vs._embedding_matrix is not None:
        print(f"Matrix shape: {vs._embedding_matrix.shape}")
        print(f"Vector dimensions: {vs._embedding_matrix.shape[1]}")
    print()

    # Success criteria
    success_rate = successful / len(pdf_files) if pdf_files else 0
    print(f"Success rate: {success_rate*100:.1f}%")

    if success_rate >= 0.95:  # 95% success
        print("\n[SUCCESS] Ingestion completed successfully!")
        return True
    elif success_rate >= 0.80:  # 80% success
        print("\n[WARNING] Ingestion mostly successful but with some failures")
        return True
    else:
        print("\n[FAILURE] Ingestion had too many failures")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] User cancelled ingestion")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
