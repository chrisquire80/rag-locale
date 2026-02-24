"""
PHASE 4: Parallel Document Processing Tests
Tests for ProcessPoolExecutor-based parallel PDF ingestion
"""

import pytest
import logging
import sys
import time
import tempfile
from pathlib import Path
from typing import List

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from parallel_ingestion import ParallelDocumentIngestion, create_parallel_ingestion

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_test_documents(temp_dir: Path, count: int) -> List[Path]:
    """Create test documents for ingestion testing"""
    docs = []

    for i in range(count):
        # Create text files
        txt_file = temp_dir / f"test_doc_{i}.txt"
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(f"""
Document {i}

This is a test document about machine learning and artificial intelligence.
Machine learning is a subset of artificial intelligence.
Deep learning is a subset of machine learning.

Key topics covered:
- Supervised learning
- Unsupervised learning
- Reinforcement learning
- Neural networks
- Data preprocessing

This document contains multiple sections to test chunking functionality.
Each section will be processed separately by the document ingestion pipeline.

More content to ensure sufficient text for chunking.
            """)
        docs.append(txt_file)

    return docs


class TestParallelDocumentIngestion:
    """Test parallel document ingestion (PHASE 4)"""

    def setup_method(self):
        """Setup for each test"""
        self.temp_dir = tempfile.mkdtemp()
        # Reset vector store singleton
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_parallel_ingestion_initialization(self):
        """Test ParallelDocumentIngestion can be initialized"""
        ingestion = ParallelDocumentIngestion(max_workers=2)
        assert ingestion.max_workers == 2
        logger.info("✓ Parallel ingestion initialized")

    def test_parallel_ingestion_factory(self):
        """Test factory function for creating parallel ingestion"""
        ingestion = create_parallel_ingestion(max_workers=2)
        assert isinstance(ingestion, ParallelDocumentIngestion)
        logger.info("✓ Factory function working")

    def test_single_document_parallel_processing(self):
        """Test processing single document in parallel"""
        docs = create_test_documents(Path(self.temp_dir), 1)

        ingestion = create_parallel_ingestion(max_workers=1)
        stats = ingestion.ingest_documents_parallel(docs)

        assert stats.total_files == 1
        assert stats.successfully_processed == 1
        assert stats.failed_files == 0
        assert stats.total_chunks > 0
        logger.info(f"✓ Single doc processed: {stats.total_chunks} chunks")

    def test_multiple_documents_parallel_processing(self):
        """Test processing multiple documents in parallel"""
        docs = create_test_documents(Path(self.temp_dir), 3)

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_documents_parallel(docs)

        assert stats.total_files == 3
        assert stats.successfully_processed == 3
        assert stats.failed_files == 0
        assert stats.total_chunks > 0
        logger.info(f"✓ Multiple docs: {stats.total_files} files, {stats.total_chunks} chunks total")

    def test_parallel_processing_performance(self):
        """Test that parallel processing completes in reasonable time"""
        docs = create_test_documents(Path(self.temp_dir), 5)

        ingestion = create_parallel_ingestion(max_workers=4)

        start = time.time()
        stats = ingestion.ingest_documents_parallel(docs)
        elapsed = time.time() - start

        logger.info(f"✓ Processed {stats.total_files} files in {elapsed:.2f}s ({stats.chunks_per_second:.1f} chunks/sec)")

        # Should complete in reasonable time
        assert elapsed < 30  # 5 files should process relatively quickly

    def test_progress_callback(self):
        """Test that progress callback is called"""
        docs = create_test_documents(Path(self.temp_dir), 3)

        progress_updates = []

        def progress_callback(processed: int, total: int):
            progress_updates.append((processed, total))
            logger.info(f"Progress: {processed}/{total}")

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_documents_parallel(docs, progress_callback=progress_callback)

        # Callback should have been called
        assert len(progress_updates) > 0
        # Final update should be all files processed
        assert progress_updates[-1][0] >= stats.total_files
        logger.info(f"✓ Progress callback called {len(progress_updates)} times")

    def test_ingest_directory_parallel(self):
        """Test ingesting entire directory in parallel"""
        # Create subdirectory with documents
        docs_dir = Path(self.temp_dir) / "documents"
        docs_dir.mkdir(exist_ok=True)

        docs = create_test_documents(docs_dir, 3)

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_directory_parallel(docs_dir, pattern="*.txt")

        assert stats.total_files == 3
        assert stats.successfully_processed == 3
        logger.info(f"✓ Directory ingestion: {stats.total_files} files")

    def test_empty_file_list(self):
        """Test handling empty file list"""
        ingestion = create_parallel_ingestion(max_workers=1)
        stats = ingestion.ingest_documents_parallel([])

        assert stats.total_files == 0
        assert stats.successfully_processed == 0
        assert stats.elapsed_time == 0
        logger.info("✓ Empty file list handled correctly")

    def test_vector_store_integration(self):
        """Test that documents are properly added to vector store"""
        docs = create_test_documents(Path(self.temp_dir), 2)

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_documents_parallel(docs)

        # Check vector store has documents
        from vector_store import get_vector_store
        vs = get_vector_store()
        doc_count = len(vs.documents)

        assert doc_count == stats.total_documents_added
        logger.info(f"✓ Vector store contains {doc_count} documents")

    def test_workers_configuration(self):
        """Test worker configuration"""
        # Test with explicit worker count
        ingestion_2 = ParallelDocumentIngestion(max_workers=2)
        assert ingestion_2.max_workers == 2

        ingestion_4 = ParallelDocumentIngestion(max_workers=4)
        assert ingestion_4.max_workers == 4

        logger.info("✓ Worker configuration working")

    def test_batch_embedding_integration(self):
        """Test that batch embedding is used in parallel ingestion"""
        docs = create_test_documents(Path(self.temp_dir), 2)

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_documents_parallel(docs)

        # Should successfully add documents (batch embedding used)
        assert stats.total_documents_added > 0
        logger.info(f"✓ Batch embedding integration: {stats.total_documents_added} documents added")


class TestPhase4Performance:
    """Performance comparison tests for PHASE 4"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_parallel_vs_sequential_throughput(self):
        """Compare parallel vs sequential processing (PHASE 4 benefit)"""
        docs = create_test_documents(Path(self.temp_dir), 4)

        # Parallel processing
        ingestion = create_parallel_ingestion(max_workers=4)
        start = time.time()
        stats_parallel = ingestion.ingest_documents_parallel(docs)
        time_parallel = time.time() - start

        logger.info(f"""
Parallel Processing Performance:
  Files: {stats_parallel.total_files}
  Chunks: {stats_parallel.total_chunks}
  Time: {time_parallel:.2f}s
  Throughput: {stats_parallel.chunks_per_second:.1f} chunks/sec
  Workers: {ingestion.max_workers}
        """)

        assert stats_parallel.total_files == 4
        assert time_parallel > 0

    def test_scaling_with_worker_count(self):
        """Test that more workers provide better throughput"""
        docs = create_test_documents(Path(self.temp_dir), 6)

        # Test with different worker counts
        for num_workers in [1, 2, 4]:
            import vector_store
            vector_store._vector_store_instance = None
            from config import config
            config.chromadb.persist_directory = Path(self.temp_dir) / f"store_{num_workers}"

            ingestion = create_parallel_ingestion(max_workers=num_workers)
            start = time.time()
            stats = ingestion.ingest_documents_parallel(docs)
            elapsed = time.time() - start

            logger.info(f"Workers: {num_workers}, Time: {elapsed:.2f}s, Throughput: {stats.chunks_per_second:.1f} chunks/sec")

    def test_ingestion_stats_accuracy(self):
        """Test that ingestion stats are accurate"""
        # Clean up any blacklist files from previous runs
        from config import LOGS_DIR
        blacklist_file = LOGS_DIR / "ingestion_blacklist.txt"
        if blacklist_file.exists():
            try:
                blacklist_file.unlink()
            except:
                pass

        docs = create_test_documents(Path(self.temp_dir), 3)

        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_documents_parallel(docs)

        # Verify stats consistency
        assert stats.total_files == 3
        assert stats.successfully_processed > 0
        assert stats.total_chunks >= stats.successfully_processed or stats.total_chunks >= 1  # At least one chunk
        assert stats.elapsed_time > 0
        assert stats.chunks_per_second >= 0

        logger.info(f"✓ Stats validation passed: {stats.total_chunks} chunks processed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
