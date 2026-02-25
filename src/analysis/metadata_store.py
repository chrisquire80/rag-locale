"""
Phase 3A: MetadataStore — SQLite persistence layer for analysis results.

Schema design follows src/vector_store_sqlite.py conventions exactly:
- threading.Lock() for write serialization
- _get_connection() context manager
- _init_schema() called in __init__
- All public methods return plain Python objects, never SQLite Row objects.

Database path: data/analysis.db (separate from vector_store.db to avoid
schema coupling — both can be reset independently).

Tables:
  document_metadata   One row per ingested document.
  document_sections   One row per section node (parent-child via parent_id).
  extracted_elements  Tables, figures, code blocks (future extension point).
  knowledge_edges     Entity co-occurrence graph edges.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.logging_config import get_logger
from src.config import DATA_DIR

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models matching the SQLite schema
# (Used for validation when reading rows back from the DB)
# ---------------------------------------------------------------------------

class DocumentMetadataRow(BaseModel):
    """
    Mirrors the 'document_metadata' table schema exactly.
    Validated on read to catch schema drift early.
    """
    doc_id: str
    title: str
    language: str
    reading_level: str
    doc_type: str
    word_count: int
    chunk_count: int
    keywords_json: str          # JSON-encoded list[str]
    author: Optional[str] = None
    source_filename: str = ""

    @property
    def keywords(self) -> list[str]:
        try:
            return json.loads(self.keywords_json)
        except Exception:
            return []


class DocumentSectionRow(BaseModel):
    """Mirrors the 'document_sections' table schema."""
    section_id: str
    doc_id: str
    title: str
    level: int                  # HeadingLevel.value (1-4)
    parent_id: Optional[str]
    chunk_indices_json: str     # JSON-encoded list[int]

    @property
    def chunk_indices(self) -> list[int]:
        try:
            return json.loads(self.chunk_indices_json)
        except Exception:
            return []


class KnowledgeEdgeRow(BaseModel):
    """Mirrors the 'knowledge_edges' table schema."""
    id: Optional[int] = None    # AUTOINCREMENT, None on insert
    doc_id: str
    source_entity_id: str
    target_entity_id: str
    relationship: str
    weight: int


class ExtractedElementRow(BaseModel):
    """
    Mirrors the 'extracted_elements' table schema.
    Extension point: currently unused by Phase 3A plugins,
    reserved for table/figure/code extraction in Phase 3B.
    """
    id: Optional[int] = None
    doc_id: str
    element_type: str           # 'table' | 'figure' | 'code'
    content: str
    page: Optional[int] = None
    section_id: Optional[str] = None


# ---------------------------------------------------------------------------
# SQL DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS document_metadata (
    doc_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL DEFAULT '',
    language        TEXT NOT NULL DEFAULT 'unknown',
    reading_level   TEXT NOT NULL DEFAULT 'general',
    doc_type        TEXT NOT NULL DEFAULT 'other',
    word_count      INTEGER NOT NULL DEFAULT 0,
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    keywords_json   TEXT NOT NULL DEFAULT '[]',
    author          TEXT,
    source_filename TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_sections (
    section_id          TEXT PRIMARY KEY,
    doc_id              TEXT NOT NULL,
    title               TEXT NOT NULL,
    level               INTEGER NOT NULL,
    parent_id           TEXT,
    chunk_indices_json  TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (doc_id) REFERENCES document_metadata(doc_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES document_sections(section_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS extracted_elements (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      TEXT NOT NULL,
    element_type TEXT NOT NULL,
    content     TEXT NOT NULL,
    page        INTEGER,
    section_id  TEXT,
    FOREIGN KEY (doc_id) REFERENCES document_metadata(doc_id) ON DELETE CASCADE,
    FOREIGN KEY (section_id) REFERENCES document_sections(section_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS knowledge_edges (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id              TEXT NOT NULL,
    source_entity_id    TEXT NOT NULL,
    target_entity_id    TEXT NOT NULL,
    relationship        TEXT NOT NULL,
    weight              INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (doc_id) REFERENCES document_metadata(doc_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sections_doc_id     ON document_sections(doc_id);
CREATE INDEX IF NOT EXISTS idx_sections_parent_id  ON document_sections(parent_id);
CREATE INDEX IF NOT EXISTS idx_elements_doc_id     ON extracted_elements(doc_id);
CREATE INDEX IF NOT EXISTS idx_edges_doc_id        ON knowledge_edges(doc_id);
CREATE INDEX IF NOT EXISTS idx_edges_source        ON knowledge_edges(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_edges_target        ON knowledge_edges(target_entity_id);
"""


class MetadataStore:
    """
    SQLite-backed persistence for Phase 3A analysis results.

    Thread-safe via threading.Lock() on all write operations.
    All reads return Pydantic model instances (never raw Row objects).

    Usage:
        store = MetadataStore(db_path)
        store.upsert_document_metadata(metadata_obj)
        rows = store.get_document_metadata(doc_id)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()
        logger.info(f"MetadataStore initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager yielding a sqlite3 connection with WAL mode.

        PRAGMAs are set once per connection. WAL + synchronous=NORMAL
        provides a significant write-throughput improvement over the
        default DELETE journal + synchronous=FULL, while remaining
        safe against data loss on process crash (only an OS crash
        could lose the last transaction).
        """
        conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=30,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-8000")  # 8 MB page cache
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Create all tables and indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.executescript(_DDL)
        logger.debug("MetadataStore schema initialized")

    # ------------------------------------------------------------------
    # document_metadata CRUD
    # ------------------------------------------------------------------

    def upsert_document_metadata(self, meta: Any) -> None:
        """
        Insert or replace one row in document_metadata.

        Accepts a DocumentMetadata dataclass instance from MetadataPlugin.
        Uses INSERT OR REPLACE to handle re-ingestion of the same document.

        Args:
            meta: DocumentMetadata dataclass instance.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO document_metadata
                        (doc_id, title, language, reading_level, doc_type,
                         word_count, chunk_count, keywords_json,
                         author, source_filename, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        meta.doc_id,
                        meta.title,
                        meta.language,
                        meta.reading_level,
                        meta.doc_type,
                        meta.word_count,
                        meta.chunk_count,
                        json.dumps(meta.keywords),
                        meta.author,
                        meta.source_filename,
                    ),
                )
        logger.debug(f"Upserted document_metadata for '{meta.doc_id}'")

    def get_document_metadata(self, doc_id: str) -> Optional[DocumentMetadataRow]:
        """
        Retrieve metadata row for a document.

        Returns None if the document has not been analyzed yet.
        Returns a validated DocumentMetadataRow Pydantic instance.
        """
        with self._lock:  # Thread-safe read
            with self._get_connection() as conn:
                row = conn.execute(
                    """SELECT doc_id, title, language, reading_level, doc_type,
                              word_count, chunk_count, keywords_json,
                              author, source_filename
                       FROM document_metadata WHERE doc_id = ?""",
                    (doc_id,),
                ).fetchone()
            if row is None:
                return None
            return DocumentMetadataRow(**dict(row))

    def list_analyzed_documents(self) -> list[str]:
        """Return all doc_ids that have a metadata row."""
        with self._lock:  # Thread-safe read
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT doc_id FROM document_metadata ORDER BY updated_at DESC"
                ).fetchall()
            return [r["doc_id"] for r in rows]

    def delete_document(self, doc_id: str) -> None:
        """
        Delete all analysis data for a document.
        CASCADE deletes sections, elements, and edges automatically.
        """
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM document_metadata WHERE doc_id = ?", (doc_id,)
                )
        logger.info(f"Deleted all analysis data for '{doc_id}'")

    # ------------------------------------------------------------------
    # document_sections CRUD
    # ------------------------------------------------------------------

    def upsert_sections(self, sections: list[Any]) -> None:
        """
        Bulk insert/replace section rows for a document.

        Deletes existing sections for the doc_id first to handle
        re-ingestion cleanly (avoids duplicate or stale sections).

        Args:
            sections: list of Section dataclass instances from StructurePlugin.
        """
        if not sections:
            return

        # Extract doc_id from section - doc_id must be explicitly set
        # Fallback to first section's doc_id for safety
        if not hasattr(sections[0], 'doc_id') or not sections[0].doc_id:
            logger.error("Section must have explicit doc_id attribute")
            raise ValueError("Sections must have explicit doc_id attribute")

        doc_id = sections[0].doc_id

        with self._lock:
            with self._get_connection() as conn:
                # Remove stale sections before bulk insert
                conn.execute(
                    "DELETE FROM document_sections WHERE doc_id = ?", (doc_id,)
                )
                conn.executemany(
                    """
                    INSERT INTO document_sections
                        (section_id, doc_id, title, level, parent_id, chunk_indices_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            s.section_id,
                            doc_id,
                            s.title,
                            s.level.value,
                            s.parent_id,
                            json.dumps(s.chunk_indices),
                        )
                        for s in sections
                    ],
                )
        logger.debug(f"Upserted {len(sections)} sections for '{doc_id}'")

    def get_sections(self, doc_id: str) -> list[DocumentSectionRow]:
        """Return all sections for a document ordered by level."""
        with self._lock:  # Thread-safe read
            with self._get_connection() as conn:
                rows = conn.execute(
                    """SELECT section_id, doc_id, title, level,
                              parent_id, chunk_indices_json
                       FROM document_sections
                       WHERE doc_id = ? ORDER BY level ASC, section_id ASC""",
                    (doc_id,),
                ).fetchall()
            return [DocumentSectionRow(**dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # knowledge_edges CRUD
    # ------------------------------------------------------------------

    def upsert_edges(self, edges: list[Any]) -> None:
        """
        Bulk insert knowledge edges, replacing existing edges for doc_id.

        Args:
            edges: list of KnowledgeEdge dataclass instances.
        """
        if not edges:
            return
        doc_id = edges[0].doc_id

        with self._lock:
            with self._get_connection() as conn:
                conn.execute(
                    "DELETE FROM knowledge_edges WHERE doc_id = ?", (doc_id,)
                )
                conn.executemany(
                    """
                    INSERT INTO knowledge_edges
                        (doc_id, source_entity_id, target_entity_id, relationship, weight)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (e.doc_id, e.source_id, e.target_id, e.relationship, e.weight)
                        for e in edges
                    ],
                )
        logger.debug(f"Upserted {len(edges)} knowledge edges for '{doc_id}'")

    def get_edges(self, doc_id: str) -> list[KnowledgeEdgeRow]:
        """Return knowledge edges for a document, sorted by weight descending."""
        with self._lock:  # Thread-safe read
            with self._get_connection() as conn:
                rows = conn.execute(
                    """SELECT id, doc_id, source_entity_id, target_entity_id,
                              relationship, weight
                       FROM knowledge_edges
                       WHERE doc_id = ? ORDER BY weight DESC""",
                    (doc_id,),
                ).fetchall()
            return [KnowledgeEdgeRow(**dict(r)) for r in rows]
