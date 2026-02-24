"""
SQLite Vector Store Backend
PHASE 3 OPTIMIZATION: SQLite-based storage for better performance and incremental saves
Alternative to pickle-based storage with schema for metadata and embeddings
"""

import logging
import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)

@dataclass
class SQLiteDocument:
    """Document structure for SQLite"""
    id: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float]

class SQLiteVectorStore:
    """
    PHASE 3: SQLite-based vector store for better performance

    Features:
    - Structured schema with proper indexing
    - Incremental saves (no need to rewrite entire file)
    - Better handling of large datasets
    - Metadata query support
    - Backward compatible with pickle format
    """

    def __init__(self, db_path: Path):
        """Initialize SQLite vector store"""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Create/open database
        self._init_schema()

    def _init_schema(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Metadata index table for O(1) filtering
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE,
                    UNIQUE(key, value, doc_id)
                )
            """)

            # Create indices for fast lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_key_value ON metadata_index(key, value)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_doc_id ON metadata_index(doc_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_id ON documents(id)")

            conn.commit()
            logger.info("SQLite schema initialized")

    def _get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def add_document(self, doc: SQLiteDocument) -> bool:
        """Add single document"""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Serialize metadata and embedding
                    metadata_json = json.dumps(doc.metadata)
                    embedding_bytes = np.array(doc.embedding, dtype=np.float32).tobytes()

                    # Insert or update document
                    cursor.execute("""
                        INSERT OR REPLACE INTO documents (id, text, metadata, embedding)
                        VALUES (?, ?, ?, ?)
                    """, (doc.id, doc.text, metadata_json, embedding_bytes))

                    # Update metadata index
                    cursor.execute("DELETE FROM metadata_index WHERE doc_id = ?", (doc.id,))
                    for k, v in doc.metadata.items():
                        cursor.execute("""
                            INSERT INTO metadata_index (key, value, doc_id)
                            VALUES (?, ?, ?)
                        """, (str(k), str(v), doc.id))

                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error adding document {doc.id}: {e}")
            return False

    def add_documents_batch(self, documents: list[SQLiteDocument]) -> tuple:
        """
        Add multiple documents efficiently
        Returns: (count_added, list_of_errors)
        """
        count_added = 0
        errors = []

        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    for doc in documents:
                        try:
                            # Serialize metadata and embedding
                            metadata_json = json.dumps(doc.metadata)
                            embedding_bytes = np.array(doc.embedding, dtype=np.float32).tobytes()

                            # Insert or update document
                            cursor.execute("""
                                INSERT OR REPLACE INTO documents (id, text, metadata, embedding)
                                VALUES (?, ?, ?, ?)
                            """, (doc.id, doc.text, metadata_json, embedding_bytes))

                            # Update metadata index
                            cursor.execute("DELETE FROM metadata_index WHERE doc_id = ?", (doc.id,))
                            for k, v in doc.metadata.items():
                                cursor.execute("""
                                    INSERT INTO metadata_index (key, value, doc_id)
                                    VALUES (?, ?, ?)
                                """, (str(k), str(v), doc.id))

                            count_added += 1
                        except Exception as e:
                            logger.warning(f"Error adding document {doc.id}: {e}")
                            errors.append((doc.id, str(e)))

                    conn.commit()
        except Exception as e:
            logger.error(f"Batch add error: {e}")
            errors.append(("batch", str(e)))

        logger.info(f"Added {count_added} documents to SQLite store")
        return count_added, errors

    def get_document(self, doc_id: str) -> Optional[SQLiteDocument]:
        """Get document by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, text, metadata, embedding FROM documents WHERE id = ?
                """, (doc_id,))
                row = cursor.fetchone()

                if row:
                    metadata = json.loads(row['metadata'])
                    embedding = np.frombuffer(row['embedding'], dtype=np.float32).tolist()
                    return SQLiteDocument(
                        id=row['id'],
                        text=row['text'],
                        metadata=metadata,
                        embedding=embedding
                    )
        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")

        return None

    def get_all_documents(self) -> list[SQLiteDocument]:
        """Get all documents"""
        documents = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, text, metadata, embedding FROM documents")
                for row in cursor.fetchall():
                    metadata = json.loads(row['metadata'])
                    embedding = np.frombuffer(row['embedding'], dtype=np.float32).tolist()
                    documents.append(SQLiteDocument(
                        id=row['id'],
                        text=row['text'],
                        metadata=metadata,
                        embedding=embedding
                    ))
        except Exception as e:
            logger.error(f"Error getting all documents: {e}")

        return documents

    def filter_by_metadata(self, key: str, value: str) -> list[str]:
        """
        Get document IDs matching metadata filter
        PHASE 3: Uses metadata index for O(1) lookup
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT doc_id FROM metadata_index
                    WHERE key = ? AND value = ?
                """, (str(key), str(value)))
                return [row['doc_id'] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error filtering metadata: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """Delete document by ID"""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False

    def clear_all(self) -> bool:
        """Clear all documents"""
        try:
            with self._lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM metadata_index")
                    cursor.execute("DELETE FROM documents")
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Error clearing store: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Document count
                cursor.execute("SELECT COUNT(*) as count FROM documents")
                doc_count = cursor.fetchone()['count']

                # Metadata entries count
                cursor.execute("SELECT COUNT(*) as count FROM metadata_index")
                metadata_count = cursor.fetchone()['count']

                # Database file size
                db_size_mb = self.db_path.stat().st_size / (1024 * 1024)

                return {
                    "total_documents": doc_count,
                    "metadata_entries": metadata_count,
                    "database_size_mb": db_size_mb,
                    "backend": "sqlite"
                }
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

    def export_to_pickle_format(self) -> dict[str, Any]:
        """
        PHASE 3 COMPATIBILITY: Export to pickle-compatible format
        Allows seamless migration from pickle to SQLite
        """
        documents_dict = {}
        try:
            for doc in self.get_all_documents():
                # Convert to pickle format
                from vector_store import Document
                documents_dict[doc.id] = Document(
                    id=doc.id,
                    text=doc.text,
                    metadata=doc.metadata,
                    embedding=doc.embedding
                )
            return {"documents": documents_dict}
        except Exception as e:
            logger.error(f"Error exporting to pickle format: {e}")
            return {}

    def import_from_pickle_format(self, data: dict[str, Any]) -> tuple:
        """
        PHASE 3 COMPATIBILITY: Import from pickle format
        Allows seamless migration from pickle to SQLite
        """
        count_added = 0
        errors = []

        try:
            documents = data.get("documents", {})
            for doc_id, doc_obj in documents.items():
                try:
                    sqlite_doc = SQLiteDocument(
                        id=doc_obj.id,
                        text=doc_obj.text,
                        metadata=doc_obj.metadata,
                        embedding=doc_obj.embedding
                    )
                    if self.add_document(sqlite_doc):
                        count_added += 1
                except Exception as e:
                    logger.warning(f"Error importing document {doc_id}: {e}")
                    errors.append((doc_id, str(e)))

            logger.info(f"Imported {count_added} documents from pickle format")
        except Exception as e:
            logger.error(f"Error importing pickle format: {e}")
            errors.append(("import", str(e)))

        return count_added, errors

def migrate_pickle_to_sqlite(pickle_file: Path, sqlite_db: Path) -> bool:
    """
    PHASE 3: Utility function to migrate from pickle to SQLite
    """
    try:
        import pickle

        # Load pickle data
        logger.info(f"Loading pickle file: {pickle_file}")
        with open(pickle_file, "rb") as f:
            data = pickle.load(f)

        # Create SQLite store and import
        logger.info(f"Creating SQLite store: {sqlite_db}")
        sqlite_store = SQLiteVectorStore(sqlite_db)
        count_added, errors = sqlite_store.import_from_pickle_format(data)

        if errors:
            logger.warning(f"Migration completed with {len(errors)} errors")
        else:
            logger.info("Migration completed successfully")

        return count_added > 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False
