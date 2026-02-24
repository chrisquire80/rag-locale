#!/usr/bin/env python3
"""
Test ingestion di batch di PDF con nuova retry logic
"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config, DOCUMENTS_DIR
from document_ingestion import DocumentIngestionPipeline

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BATCH_TEST")

def test_batch_ingestion(batch_size: int = 10):
    """Test ingestione batch di PDF"""
    print("\n" + "="*70)
    print(f"BATCH INGESTION TEST - {batch_size} PDF max")
    print("="*70 + "\n")

    pipeline = DocumentIngestionPipeline()

    # Get all PDF files
    pdf_files = sorted(list(DOCUMENTS_DIR.glob("*.pdf")))[:batch_size]

    if not pdf_files:
        print("[ERROR] No PDF files found in", DOCUMENTS_DIR)
        return False

    print(f"Found {len(pdf_files)} PDF files to ingest\n")

    start_time = time.time()
    total_chunks = 0
    successful_files = 0
    failed_files = []

    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Ingesting: {pdf_file.name}")
        print("-" * 70)

        try:
            chunks = pipeline.ingest_single_file(pdf_file, max_retries=3)
            total_chunks += chunks
            successful_files += 1
            print(f"[OK] Success: {chunks} chunks ingested")

        except Exception as e:
            error_msg = str(e)[:100]
            print(f"[ERROR] Failed: {error_msg}")
            failed_files.append((pdf_file.name, str(e)[:50]))

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "="*70)
    print("BATCH INGESTION RESULTS")
    print("="*70)
    print(f"Total files: {len(pdf_files)}")
    print(f"Successful: {successful_files}/{len(pdf_files)}")
    print(f"Failed: {len(failed_files)}/{len(pdf_files)}")
    print(f"Total chunks: {total_chunks}")
    print(f"Total time: {elapsed:.1f}s ({elapsed/len(pdf_files):.1f}s per file)")
    print()

    if failed_files:
        print("Failed files:")
        for filename, error in failed_files:
            print(f"  - {filename}: {error}")
        print()

    # Check vector store
    vs = pipeline.vector_store
    print(f"Vector store: {len(vs.documents)} documents")
    if vs._embedding_matrix is not None:
        print(f"Matrix shape: {vs._embedding_matrix.shape}")
    print()

    success = len(failed_files) == 0 and successful_files >= batch_size * 0.8  # 80% success rate
    if success:
        print("[SUCCESS] Batch ingestion successful!")
    else:
        print("[WARNING] Batch ingestion had issues")

    print("="*70 + "\n")
    return success


if __name__ == "__main__":
    # Test with 10 PDF first (sanity check)
    success = test_batch_ingestion(batch_size=10)
    sys.exit(0 if success else 1)
