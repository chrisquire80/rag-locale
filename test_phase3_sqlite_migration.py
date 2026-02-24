"""
PHASE 3: SQLite Migration Tests
Tests for SQLite vector store backend and migration from pickle
"""

import pytest
import logging
import sys
import time
import tempfile
import json
from pathlib import Path

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vector_store_sqlite import SQLiteVectorStore, SQLiteDocument, migrate_pickle_to_sqlite
from vector_store import VectorStore, Document

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TestSQLiteVectorStore:
    """Test SQLite vector store implementation (PHASE 3)"""

    def setup_method(self):
        """Setup fresh SQLite store for each test"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_store.db"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_sqlite_initialization(self):
        """Test SQLite store can be initialized"""
        store = SQLiteVectorStore(self.db_path)
        assert self.db_path.exists()
        logger.info(f"✓ SQLite store initialized at {self.db_path}")

    def test_add_single_document(self):
        """Test adding a single document to SQLite"""
        store = SQLiteVectorStore(self.db_path)

        doc = SQLiteDocument(
            id="doc_1",
            text="Test document about machine learning",
            metadata={"source": "test", "year": 2024},
            embedding=[0.1, 0.2, 0.3] + [0.0] * 381  # 384 dims
        )

        assert store.add_document(doc)
        logger.info("✓ Document added to SQLite")

    def test_get_document_from_sqlite(self):
        """Test retrieving document from SQLite"""
        store = SQLiteVectorStore(self.db_path)

        original = SQLiteDocument(
            id="doc_1",
            text="Test document",
            metadata={"source": "book"},
            embedding=[0.1] * 384
        )

        store.add_document(original)
        retrieved = store.get_document("doc_1")

        assert retrieved is not None
        assert retrieved.id == "doc_1"
        assert retrieved.text == "Test document"
        assert retrieved.metadata == {"source": "book"}
        assert len(retrieved.embedding) == 384
        logger.info("✓ Document retrieval working")

    def test_batch_add_documents(self):
        """Test adding multiple documents efficiently"""
        store = SQLiteVectorStore(self.db_path)

        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={"index": i},
                embedding=[0.1 * i] * 384
            )
            for i in range(10)
        ]

        count_added, errors = store.add_documents_batch(docs)
        assert count_added == 10
        assert len(errors) == 0
        logger.info(f"✓ Batch added {count_added} documents")

    def test_metadata_filtering(self):
        """Test metadata filtering with SQLite index"""
        store = SQLiteVectorStore(self.db_path)

        # Add documents with metadata
        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={"source": "book" if i % 2 == 0 else "paper"},
                embedding=[0.1] * 384
            )
            for i in range(10)
        ]

        store.add_documents_batch(docs)

        # Filter by metadata
        book_docs = store.filter_by_metadata("source", "book")
        assert len(book_docs) == 5
        logger.info(f"✓ Metadata filtering returned {len(book_docs)} documents")

    def test_delete_document(self):
        """Test deleting documents from SQLite"""
        store = SQLiteVectorStore(self.db_path)

        doc = SQLiteDocument(
            id="doc_1",
            text="Test",
            metadata={},
            embedding=[0.1] * 384
        )

        store.add_document(doc)
        assert store.get_document("doc_1") is not None

        assert store.delete_document("doc_1")
        assert store.get_document("doc_1") is None
        logger.info("✓ Document deletion working")

    def test_get_all_documents(self):
        """Test retrieving all documents"""
        store = SQLiteVectorStore(self.db_path)

        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={},
                embedding=[0.1] * 384
            )
            for i in range(5)
        ]

        store.add_documents_batch(docs)
        all_docs = store.get_all_documents()

        assert len(all_docs) == 5
        logger.info(f"✓ Retrieved all {len(all_docs)} documents")

    def test_clear_all_documents(self):
        """Test clearing all documents"""
        store = SQLiteVectorStore(self.db_path)

        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={},
                embedding=[0.1] * 384
            )
            for i in range(5)
        ]

        store.add_documents_batch(docs)
        assert len(store.get_all_documents()) == 5

        assert store.clear_all()
        assert len(store.get_all_documents()) == 0
        logger.info("✓ Clear all working")

    def test_get_stats(self):
        """Test getting store statistics"""
        store = SQLiteVectorStore(self.db_path)

        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={"tag": "test"},
                embedding=[0.1] * 384
            )
            for i in range(5)
        ]

        store.add_documents_batch(docs)
        stats = store.get_stats()

        assert stats["total_documents"] == 5
        assert stats["backend"] == "sqlite"
        assert stats["database_size_mb"] > 0
        logger.info(f"✓ Stats: {stats}")

    def test_sqlite_incremental_saves(self):
        """Test that SQLite supports incremental saves (PHASE 3 benefit)"""
        store = SQLiteVectorStore(self.db_path)

        # Add documents incrementally
        doc1 = SQLiteDocument(
            id="doc_1",
            text="Document 1" * 10,
            metadata={"index": 1},
            embedding=[0.1] * 384
        )
        store.add_document(doc1)
        size_1 = self.db_path.stat().st_size

        # Add more documents
        for i in range(2, 6):
            doc = SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}" * 10,
                metadata={"index": i},
                embedding=[0.1 * i] * 384
            )
            store.add_document(doc)

        size_5 = self.db_path.stat().st_size

        # Database should exist and have reasonable size
        assert size_1 > 0
        assert size_5 > size_1
        # 5 documents should not require exponential space growth
        assert size_5 < 1024 * 100  # Less than 100KB for 5 documents
        logger.info(f"✓ Incremental save: {size_1} bytes -> {size_5} bytes for 5 documents")


class TestPickleToSQLiteMigration:
    """Test migration from pickle to SQLite (PHASE 3)"""

    def setup_method(self):
        """Setup temp directories"""
        self.temp_dir = tempfile.mkdtemp()
        self.pickle_file = Path(self.temp_dir) / "test.pkl"
        self.sqlite_db = Path(self.temp_dir) / "test.db"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_export_to_pickle_format(self):
        """Test exporting SQLite to pickle format"""
        store = SQLiteVectorStore(self.sqlite_db)

        # Add documents
        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={"index": i},
                embedding=[0.1] * 384
            )
            for i in range(3)
        ]

        store.add_documents_batch(docs)

        # Export to pickle format
        pickle_data = store.export_to_pickle_format()
        assert "documents" in pickle_data
        assert len(pickle_data["documents"]) == 3
        logger.info("✓ Export to pickle format working")

    def test_import_from_pickle_format(self):
        """Test importing from pickle format"""
        from vector_store import Document

        # Create pickle-format data
        pickle_data = {
            "documents": {
                "doc_1": Document(
                    id="doc_1",
                    text="Test document",
                    metadata={"source": "test"},
                    embedding=[0.1] * 384
                ),
                "doc_2": Document(
                    id="doc_2",
                    text="Another document",
                    metadata={"source": "test"},
                    embedding=[0.2] * 384
                )
            }
        }

        # Import into SQLite
        store = SQLiteVectorStore(self.sqlite_db)
        count_added, errors = store.import_from_pickle_format(pickle_data)

        assert count_added == 2
        assert len(errors) == 0
        assert len(store.get_all_documents()) == 2
        logger.info("✓ Import from pickle format working")

    def test_backward_compatibility_round_trip(self):
        """Test round-trip: SQLite -> Pickle -> SQLite"""
        from vector_store import Document

        # Create initial SQLite store
        store1 = SQLiteVectorStore(self.sqlite_db)

        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={"index": i, "type": "test"},
                embedding=[float(i) / 10] * 384
            )
            for i in range(5)
        ]

        store1.add_documents_batch(docs)

        # Export to pickle format
        pickle_data = store1.export_to_pickle_format()

        # Create new SQLite store and import
        store2_db = Path(self.temp_dir) / "test2.db"
        store2 = SQLiteVectorStore(store2_db)
        count_added, errors = store2.import_from_pickle_format(pickle_data)

        # Verify data integrity
        assert count_added == 5
        assert len(errors) == 0

        docs_restored = store2.get_all_documents()
        assert len(docs_restored) == 5

        # Check specific document
        doc = store2.get_document("doc_2")
        assert doc.text == "Document 2"
        assert doc.metadata["index"] == 2
        assert len(doc.embedding) == 384
        logger.info("✓ Round-trip backward compatibility working")


class TestPhase3Performance:
    """Performance tests for SQLite (PHASE 3)"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "perf_test.db"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_sqlite_bulk_insert_performance(self):
        """Test SQLite performance for bulk inserts"""
        store = SQLiteVectorStore(self.db_path)

        # Create 100 documents
        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i} with some content",
                metadata={"index": i, "batch": i // 10},
                embedding=[float(i) / 100] * 384
            )
            for i in range(100)
        ]

        start = time.time()
        count_added, errors = store.add_documents_batch(docs)
        elapsed = time.time() - start

        assert count_added == 100
        logger.info(f"✓ SQLite bulk insert (100 docs): {elapsed*1000:.2f}ms ({elapsed/100*1000:.2f}ms per doc)")
        assert elapsed < 10.0  # Should complete in reasonable time

    def test_sqlite_metadata_filter_performance(self):
        """Test SQLite metadata filtering performance"""
        store = SQLiteVectorStore(self.db_path)

        # Create corpus
        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}",
                metadata={
                    "source": "arxiv" if i % 3 == 0 else "paper",
                    "year": 2023 + (i % 2)
                },
                embedding=[0.1] * 384
            )
            for i in range(100)
        ]

        store.add_documents_batch(docs)

        # Measure filter performance
        start = time.time()
        for _ in range(20):
            results = store.filter_by_metadata("year", "2024")
        elapsed = time.time() - start

        logger.info(f"✓ SQLite metadata filter (20x): {elapsed*1000:.2f}ms avg ({elapsed/20*1000:.2f}ms per query)")
        assert elapsed < 1.0

    def test_sqlite_storage_efficiency(self):
        """Test SQLite storage efficiency"""
        store = SQLiteVectorStore(self.db_path)

        # Add 50 documents
        docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i} " * 20,  # Repeated text
                metadata={"index": i},
                embedding=[0.1 * i] * 384
            )
            for i in range(50)
        ]

        store.add_documents_batch(docs)
        stats = store.get_stats()

        logger.info(f"✓ SQLite storage: {stats['database_size_mb']:.2f}MB for {stats['total_documents']} documents")
        # Should be reasonably efficient
        assert stats['database_size_mb'] < 20  # 50 documents should be well under 20MB


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
