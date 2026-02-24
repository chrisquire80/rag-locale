"""
Document Loader - Load Real Documents from Various Sources
Integrates with Streamlit app for real RAG pipeline
"""

import os
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# File-Based Document Loading
# ============================================================================

class FileDocumentLoader:
    """Load documents from local files"""

    @staticmethod
    def load_from_text_files(directory: str = "documents") -> List[Dict]:
        """Load documents from text files"""
        documents = []
        docs_path = Path(directory)

        if not docs_path.exists():
            logger.warning(f"Directory {directory} not found")
            return documents

        for file_path in docs_path.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                documents.append({
                    'id': file_path.stem,
                    'text': content,
                    'metadata': {
                        'source': file_path.stem,
                        'filename': file_path.name,
                        'size': len(content),
                        'relevance': 0.8
                    }
                })
                logger.info(f"Loaded {file_path.name}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        return documents

    @staticmethod
    def load_from_markdown_files(directory: str = "documents") -> List[Dict]:
        """Load documents from Markdown files"""
        documents = []
        docs_path = Path(directory)

        if not docs_path.exists():
            logger.warning(f"Directory {directory} not found")
            return documents

        for file_path in docs_path.glob("*.md"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Extract title from markdown
                lines = content.split('\n')
                title = next(
                    (line.replace('# ', '').strip()
                     for line in lines if line.startswith('#')),
                    file_path.stem
                )

                documents.append({
                    'id': file_path.stem,
                    'text': content,
                    'metadata': {
                        'source': title,
                        'filename': file_path.name,
                        'type': 'markdown',
                        'size': len(content),
                        'relevance': 0.85
                    }
                })
                logger.info(f"Loaded {file_path.name}")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        return documents

    @staticmethod
    def load_from_pdf_files(directory: str = "documents") -> List[Dict]:
        """Load documents from PDF files"""
        try:
            import PyPDF2
        except ImportError:
            logger.error("PyPDF2 not installed. Install with: pip install PyPDF2")
            return []

        documents = []
        docs_path = Path(directory)

        if not docs_path.exists():
            logger.warning(f"Directory {directory} not found")
            return documents

        for file_path in docs_path.glob("*.pdf"):
            try:
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)

                    for page_num, page in enumerate(reader.pages):
                        try:
                            text = page.extract_text()

                            if text.strip():  # Only add if has content
                                documents.append({
                                    'id': f"{file_path.stem}_p{page_num}",
                                    'text': text,
                                    'metadata': {
                                        'source': file_path.stem,
                                        'filename': file_path.name,
                                        'page': page_num + 1,
                                        'type': 'pdf',
                                        'relevance': 0.82
                                    }
                                })
                        except Exception as e:
                            logger.error(f"Error extracting page {page_num}: {e}")

                logger.info(f"Loaded {file_path.name} ({len(reader.pages)} pages)")
            except Exception as e:
                logger.error(f"Error loading {file_path}: {e}")

        return documents


# ============================================================================
# Database-Based Document Loading
# ============================================================================

class DatabaseDocumentLoader:
    """Load documents from database"""

    def __init__(self, db_path: str = "documents.db"):
        """Initialize database loader"""
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Create database if it doesn't exist"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    relevance REAL DEFAULT 0.8,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()
            conn.close()
            logger.info(f"Database initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    def load_all(self) -> List[Dict]:
        """Load all documents from database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, content, source, relevance
                FROM documents
                ORDER BY relevance DESC
            """)

            documents = []
            for doc_id, content, source, relevance in cursor.fetchall():
                documents.append({
                    'id': doc_id,
                    'text': content,
                    'metadata': {
                        'source': source,
                        'relevance': relevance,
                        'type': 'database'
                    }
                })

            conn.close()
            logger.info(f"Loaded {len(documents)} documents from database")
            return documents

        except Exception as e:
            logger.error(f"Error loading from database: {e}")
            return []

    def load_by_query(self, query: str, limit: int = 10) -> List[Dict]:
        """Load documents matching search query"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Simple full-text search
            cursor.execute("""
                SELECT id, content, source, relevance
                FROM documents
                WHERE content LIKE ?
                ORDER BY relevance DESC
                LIMIT ?
            """, (f"%{query}%", limit))

            documents = []
            for doc_id, content, source, relevance in cursor.fetchall():
                documents.append({
                    'id': doc_id,
                    'text': content,
                    'metadata': {
                        'source': source,
                        'relevance': relevance,
                        'type': 'database'
                    }
                })

            conn.close()
            logger.info(f"Found {len(documents)} documents matching query")
            return documents

        except Exception as e:
            logger.error(f"Error searching database: {e}")
            return []

    def insert_document(self, doc_id: str, content: str, source: str, relevance: float = 0.8):
        """Insert a document into database"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO documents (id, content, source, relevance)
                VALUES (?, ?, ?, ?)
            """, (doc_id, content, source, relevance))

            conn.commit()
            conn.close()
            logger.info(f"Inserted document: {doc_id}")
        except Exception as e:
            logger.error(f"Error inserting document: {e}")


# ============================================================================
# Combined Document Loader
# ============================================================================

class DocumentLoaderManager:
    """Manage document loading from multiple sources"""

    def __init__(self, db_path: str = "documents.db"):
        """Initialize document loader"""
        self.file_loader = FileDocumentLoader()
        self.db_loader = DatabaseDocumentLoader(db_path)
        self.documents: List[Dict] = []

    def load_all_sources(self, documents_dir: str = "documents") -> List[Dict]:
        """Load documents from all available sources"""
        all_documents = []

        # Load from files
        logger.info("Loading from text files...")
        all_documents.extend(self.file_loader.load_from_text_files(documents_dir))

        logger.info("Loading from markdown files...")
        all_documents.extend(self.file_loader.load_from_markdown_files(documents_dir))

        logger.info("Loading from PDF files...")
        all_documents.extend(self.file_loader.load_from_pdf_files(documents_dir))

        # Load .docx files (if python-docx is available)
        logger.info("Loading from DOCX files...")
        docs_path = Path(documents_dir)
        if docs_path.exists():
            for file_path in docs_path.glob("*.docx"):
                try:
                    import docx
                    doc = docx.Document(str(file_path))
                    text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
                    if text.strip():
                        all_documents.append({
                            'id': file_path.stem,
                            'text': text,
                            'metadata': {
                                'source': file_path.stem,
                                'filename': file_path.name,
                                'type': 'docx',
                                'size': len(text),
                                'relevance': 0.85
                            }
                        })
                        logger.info(f"Loaded {file_path.name}")
                except ImportError:
                    logger.warning("python-docx not installed — skipping .docx files")
                    break
                except Exception as e:
                    logger.error(f"Error loading {file_path}: {e}")

        # Load from database
        logger.info("Loading from database...")
        all_documents.extend(self.db_loader.load_all())

        self.documents = all_documents
        logger.info(f"Total documents loaded: {len(all_documents)}")
        return all_documents


    def search_documents(self, query: str) -> List[Dict]:
        """Search loaded documents by query"""
        if not query:
            return self.documents

        query_lower = query.lower()
        results = []

        for doc in self.documents:
            text = doc['text'].lower()
            if query_lower in text:
                results.append(doc)

        return results[:10]  # Return top 10

    def get_document_summary(self) -> Dict:
        """Get summary of loaded documents"""
        return {
            'total_documents': len(self.documents),
            'total_size_kb': sum(
                len(doc['text']) for doc in self.documents
            ) / 1024,
            'sources': list(set(
                doc['metadata'].get('source', 'Unknown')
                for doc in self.documents
            )),
            'types': list(set(
                doc['metadata'].get('type', 'unknown')
                for doc in self.documents
            ))
        }


# ============================================================================
# Utility Functions for Streamlit Integration
# ============================================================================

def create_sample_documents(output_dir: str = "documents"):
    """Create sample documents for testing"""
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Sample text file
    (output_path / "sample1.txt").write_text("""
Machine Learning Basics

Machine learning is a subset of artificial intelligence that focuses on
enabling computers to learn from data without being explicitly programmed.

Key Concepts:
1. Supervised Learning - Learning from labeled data
2. Unsupervised Learning - Finding patterns in unlabeled data
3. Reinforcement Learning - Learning through interaction and feedback

Applications:
- Image recognition
- Natural language processing
- Recommendation systems
- Autonomous vehicles
""", encoding='utf-8')

    # Sample markdown file
    (output_path / "sample2.md").write_text("""
# Deep Learning Guide

## What is Deep Learning?

Deep learning is a subset of machine learning that uses artificial neural networks
with multiple layers (hence "deep") to learn patterns in large amounts of data.

## Key Components

### Neural Networks
- Input layer
- Hidden layers
- Output layer
- Activation functions

### Training Process
1. Forward pass
2. Calculate loss
3. Backward pass
4. Update weights

## Popular Frameworks
- TensorFlow
- PyTorch
- Keras
- JAX
""", encoding='utf-8')

    logger.info(f"Sample documents created in {output_dir}")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create sample documents
    create_sample_documents()

    # Load documents
    manager = DocumentLoaderManager()
    docs = manager.load_all_sources()

    print(f"\nLoaded {len(docs)} documents")
    print(f"\nSummary: {manager.get_document_summary()}")

    # Test search
    search_results = manager.search_documents("machine learning")
    print(f"\nSearch results for 'machine learning': {len(search_results)} found")
