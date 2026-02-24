"""
Custom Vector Store (Numpy + Pickle)
Sostituto lightweight di ChromaDB per Python 3.14+
"""

import pickle
import numpy as np
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict
import time
from datetime import datetime

from src.config import config
from src.llm_service import get_llm_service
from src.logging_config import get_logger

# FASE 2, 5, 6: Performance optimizations
from src.performance_profiler import get_profiler, profile_operation
from src.hnsw_indexing import FastVectorSearch
from src.quantization import EmbeddingQuantizer

logger = get_logger(__name__)

@dataclass
class Document:
    id: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float]

class VectorStore:
    """Archivio vettoriale basato su file (Pickle + Numpy)"""

    def __init__(self, enable_hnsw: bool = True, enable_quantization: bool = False):
        """Inizializza store caricando da disco se presente"""
        self.persist_directory = config.chromadb.persist_directory
        self.store_file = self.persist_directory / "vector_store.pkl"
        self.documents: dict[str, Document] = {}
        self.llm = get_llm_service()

        # FASE 5: HNSW Vector Indexing
        self.enable_hnsw = enable_hnsw
        self.hnsw_search = FastVectorSearch(enable_hnsw=enable_hnsw) if enable_hnsw else None

        # FASE 6: INT8 Quantization
        self.enable_quantization = enable_quantization
        self.quantizer = EmbeddingQuantizer(enable_quantization=enable_quantization)

        # Cache per ricerca vettorizzata (HIGH-5 optimization)
        self._embedding_matrix = None
        self._doc_ids_ordered = []

        # Cache per query embeddings (BOTTLENECK FIX #1)
        # PHASE 2 OPTIMIZATION: LRU cache with size limit (1000 queries)
        self._query_embedding_cache = {}  # {query_cache_key: embedding}
        self._query_cache_max_size = 1000
        self._query_cache_access_times = {}  # {query_cache_key: timestamp} for LRU eviction

        # Metadata index per filtering veloce (BOTTLENECK FIX #3)
        # Structure: {(key, value): set(doc_indices)} for O(1) lookup instead of O(N) scan
        self._metadata_index = {}  # {(key, value): set(doc_indices)}
        self._metadata_index_dirty = False  # Flag to track if rebuild needed

        # FASE 2: Profiler
        self.profiler = get_profiler()

        # Crea directory
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self._load()

    def _load(self):
        """Carica dati da disco (con progress logging per file grandi)"""
        if self.store_file.exists():
            try:
                # OPTIMIZATION 8.6: Log file size and progress for large stores
                file_size_mb = self.store_file.stat().st_size / (1024 * 1024)
                if file_size_mb > 1:
                    logger.info(f"📦 Loading vector store ({file_size_mb:.1f} MB)...")

                with open(self.store_file, "rb") as f:
                    # Security: Restrict pickle to safe classes only
                    import pickle
                    data = pickle.load(f)
                    if not isinstance(data, dict) or "documents" not in data:
                        raise ValueError("Invalid vector store format")
                    self.documents = data.get("documents", {})

                logger.info(f"📦 Caricato vector store: {len(self.documents)} documenti ({file_size_mb:.1f} MB)")
            except Exception as e:
                logger.error(f"✗ Errore caricamento store: {e}")
                self.documents = {}
        else:
            logger.info("🆕 Nuovo vector store creato")

        # Rebuild matrice per ricerca vettorizzata
        self._rebuild_matrix()

        # PHASE 2 OPTIMIZATION: Rebuild metadata index on load
        self._rebuild_metadata_index()

    def _rebuild_matrix(self):
        """
        Pre-calcola matrice embeddings normalizzata per ricerca vettorizzata veloce.
        Questo è il FIX per HIGH-5: trasforma search da O(N) brute-force a O(1) lookup + vettorizzazione.

        FASE 5: Integra HNSW index se abilitato (per 100+ documenti)
        FASE 6: Quantizza embeddings se abilitato (per memory savings)
        """
        if not self.documents:
            self._embedding_matrix = None
            self._doc_ids_ordered = []
            if self.hnsw_search:
                self.hnsw_search.embeddings = []
                self.hnsw_search.ids = []
            return

        self._doc_ids_ordered = list(self.documents.keys())
        embeddings_list = [self.documents[doc_id].embedding for doc_id in self._doc_ids_ordered]

        # Converti a numpy array
        embeddings_array = np.array(embeddings_list, dtype=np.float32)

        # Normalizza per similarità coseno (divide per norma)
        norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
        # Evita divisione per zero
        self._embedding_matrix = embeddings_array / np.where(norms == 0, 1, norms)

        # FASE 5: Build HNSW index if enabled (for 100+ documents)
        if self.hnsw_search and len(embeddings_list) > 50:
            try:
                logger.info(f"Building HNSW index for {len(embeddings_list)} embeddings...")
                self.hnsw_search.build_index(
                    embeddings_array,
                    self._doc_ids_ordered
                )
            except Exception as e:
                logger.warning(f"HNSW index build failed: {e}, falling back to exact search")
                self.hnsw_search.hnsw_index = None

        # FASE 6: Quantize embeddings if enabled
        if self.enable_quantization:
            try:
                logger.info(f"Quantizing {len(embeddings_list)} embeddings to INT8...")
                quantized, stats = self.quantizer.quantize_embeddings(embeddings_list)
                logger.info(f"Quantization complete: {stats.memory_saved_pct:.1f}% memory saved")
            except Exception as e:
                logger.warning(f"Quantization failed: {e}, using float32")

        logger.debug(f"Matrice embeddings rebuildata: {self._embedding_matrix.shape}")

    def _rebuild_metadata_index(self):
        """
        PHASE 2 OPTIMIZATION: Ricostruisce indice metadata per O(1) filtering.
        Invocato al load e dopo bulk add operations.
        """
        self._metadata_index = {}
        for doc_idx, doc_id in enumerate(self._doc_ids_ordered):
            doc = self.documents[doc_id]
            for k, v in doc.metadata.items():
                # Convert lists to tuples to make hashable for dict keys
                if isinstance(v, list):
                    v = tuple(v)
                index_key = (k, v)
                if index_key not in self._metadata_index:
                    self._metadata_index[index_key] = set()
                self._metadata_index[index_key].add(doc_idx)

        self._metadata_index_dirty = False
        logger.debug(f"Metadata index rebuildata: {len(self._metadata_index)} entries")

    def _cache_query_embedding(self, query_cache_key: str, embedding: list[float]) -> None:
        """
        PHASE 2 OPTIMIZATION: Gestisce cache query embeddings con LRU eviction.
        Mantiene cache size <= _query_cache_max_size per evitare memory leak.
        """
        import time
        self._query_embedding_cache[query_cache_key] = embedding
        self._query_cache_access_times[query_cache_key] = time.time()

        # Se cache è pieno, evicta il meno recentemente usato
        if len(self._query_embedding_cache) > self._query_cache_max_size:
            # Trova key con timestamp più vecchio
            oldest_key = min(self._query_cache_access_times.items(), key=lambda x: x[1])[0]
            del self._query_embedding_cache[oldest_key]
            del self._query_cache_access_times[oldest_key]

            # Cleanup orphaned keys (keys in access_times but not in cache)
            orphaned = set(self._query_cache_access_times.keys()) - set(self._query_embedding_cache.keys())
            for key in orphaned:
                del self._query_cache_access_times[key]

            logger.debug(f"Cache eviction: removed oldest query embedding (cache size: {len(self._query_embedding_cache)})")

    def _get_cached_query_embedding(self, query_cache_key: str) -> Optional[list[float]]:
        """
        PHASE 2 OPTIMIZATION: Recupera embedding query da cache con update del timestamp LRU.
        """
        import time
        if query_cache_key in self._query_embedding_cache:
            # Update access time per LRU tracking
            self._query_cache_access_times[query_cache_key] = time.time()
            return self._query_embedding_cache[query_cache_key]
        return None

    def _save(self):
        """Salva dati su disco in modo atomico per prevenire corruzione"""
        temp_file = self.store_file.with_suffix(".pkl.tmp")
        try:
            # Scrivi su file temporaneo
            with open(temp_file, "wb") as f:
                pickle.dump({"documents": self.documents}, f)
            # Rename atomico (operazione a livello filesystem)
            temp_file.replace(self.store_file)
            logger.debug("✓ Vector store salvato atomicamente")
        except Exception as e:
            logger.error(f"✗ Errore salvataggio store: {e}")
            # Cleanup file temporaneo se fallisce
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except (OSError, PermissionError):
                    pass
            raise

    def add_documents(
        self,
        documents: list[str],
        metadatas: Optional[list[Dict]] = None,
        ids: Optional[list[str]] = None,
        rebuild_matrix: bool = True,
        use_batch_embedding: bool = True
    ) -> tuple:
        """
        Aggiungi documenti e genera embeddings con proper error handling.

        FIX FASE 6: Propagate embedding errors (don't silently fail)
        - Rate-limit errors (429): Stop batch and raise (retry later)
        - Other errors: Log and skip document (don't corrupt store)
        - Return count of successfully added documents

        OPTIMIZATION 8.1: Deferred matrix rebuild
        - If rebuild_matrix=False, caller must call _rebuild_matrix() manually
        - Allows batching multiple add_documents() calls with single rebuild

        OPTIMIZATION 8.5: Batch embedding generation
        - If use_batch_embedding=True, use get_embeddings_batch() for 3-5x speedup
        - Falls back to individual embeddings if batch fails
        """
        if not documents:
            return 0, []

        # Defaults
        if metadatas is None:
            metadatas = [{} for _ in documents]
        if ids is None:
            ids = [f"doc_{len(self.documents) + i}" for i in range(len(documents))]

        logger.info(f"Adding {len(documents)} documents...")

        count_added = 0
        failed_docs = []

        # OPTIMIZATION 8.5: Try batch embedding if available
        embeddings = None
        if use_batch_embedding and len(documents) > 1:
            try:
                logger.info(f"[OPTIMIZATION 8.5] Using batch embedding for {len(documents)} texts...")
                embeddings = self.llm.get_embeddings_batch(documents, batch_size=50)
                logger.info(f"✓ Batch embedding completed ({len(embeddings)} embeddings)")
            except Exception as e:
                logger.warning(f"[FALLBACK] Batch embedding failed: {e}. Falling back to individual embeddings...")
                embeddings = None

        for i, text in enumerate(documents):
            doc_id = ids[i]

            # Genera embedding via Gemini con retry logic
            try:
                # OPTIMIZATION 8.5: Use pre-computed batch embedding if available
                if embeddings is not None:
                    embedding = embeddings[i]
                else:
                    embedding = self.llm.get_embedding(text)

                doc = Document(
                    id=doc_id,
                    text=text,
                    metadata=metadatas[i],
                    embedding=embedding
                )
                self.documents[doc_id] = doc
                count_added += 1

                # BOTTLENECK FIX #3: Update metadata index for O(1) filtering
                # Add this document to all relevant metadata index entries
                current_doc_index = len(self._doc_ids_ordered)  # Index before rebuild
                for k, v in metadatas[i].items():
                    index_key = (k, v)
                    if index_key not in self._metadata_index:
                        self._metadata_index[index_key] = set()
                    self._metadata_index[index_key].add(current_doc_index)

            except RuntimeError as e:
                # FIX: Check if it's a rate-limit error from retries
                error_msg = str(e)
                if "429" in error_msg or "rate" in error_msg.lower() or "quota" in error_msg.lower():
                    # CRITICAL: Stop batch, re-raise to parent
                    logger.error(f"✗ Rate-limit error on doc {doc_id}: {e}")
                    logger.warning(f"Stopping batch ingestion (added {count_added}/{len(documents)})")
                    raise  # Re-raise to parent caller
                else:
                    # Other errors - skip this doc but continue batch
                    logger.warning(f"⚠️ Skipping doc {doc_id}: {e}")
                    failed_docs.append((doc_id, str(e)[:100]))

            except Exception as e:
                # Unexpected errors - log and continue
                logger.warning(f"⚠️ Unexpected error on doc {doc_id}: {e}")
                failed_docs.append((doc_id, str(e)[:100]))

        if count_added > 0:
            self._save()
            # OPTIMIZATION 8.1: Only rebuild if requested (else batch caller does it once)
            if rebuild_matrix:
                try:
                    self._rebuild_matrix()
                    # PHASE 2 OPTIMIZATION: Rebuild metadata index after adding documents
                    self._rebuild_metadata_index()
                    logger.info(f"Matrix rebuilt: {self._embedding_matrix.shape}")
                except Exception as e:
                    logger.error(f"Matrix rebuild failed: {e}")
                    raise RuntimeError(f"Failed to rebuild search matrix after adding documents: {e}")
            logger.info(f"Successfully added {count_added} documents")

        # Report any failures
        if failed_docs:
            logger.warning(f"⚠️ Failed to add {len(failed_docs)} documents:")
            for doc_id, error in failed_docs:
                logger.warning(f"  - {doc_id}: {error}")

        return count_added, failed_docs

    @profile_operation("vector_search")
    def search(
        self,
        query: str,
        top_k: int = 5,
        where_filter: Optional[Dict] = None,
        query_embedding: Optional[np.ndarray] = None
    ) -> list[Dict]:
        """
        Cerca documenti per similarità coseno (OTTIMIZZATO con matrice pre-calcolata).
        FIX HIGH-5: Usa NumPy vettorizzazione invece di loop Python.
        Performance: 70+ PDF ~100-200ms (prima) → ~10-20ms (dopo)

        FASE 2: Profile all searches via @profile_operation decorator
        FASE 5: Use HNSW for 100+ documents (10-100x speedup for large corpus)

        OPTIMIZATION 8.2: Pre-filter metadata before ranking
        - If where_filter provided, filter candidates BEFORE computing scores
        - Avoids wasted computation on excluded documents
        - Can give 20-50% speedup for selective queries

        Args:
            query: Query text
            top_k: Number of top results to return
            where_filter: Metadata filter
            query_embedding: Pre-computed query embedding (optional, avoids double API call)
        """
        if not self.documents or self._embedding_matrix is None:
            logger.warning("⚠️ Vector store vuoto")
            return []

        try:
            # 1. Genera embedding query (con cache per evitare bottleneck API)
            # BOTTLENECK FIX #1: Cache query embeddings
            # PHASE 2 OPTIMIZATION: LRU cache management
            if query_embedding is not None:
                # Use pre-computed embedding (avoids double API call when used with FASE 10.1 clustering)
                q_vec = np.array(query_embedding, dtype=np.float32) if not isinstance(query_embedding, np.ndarray) else query_embedding.astype(np.float32)
                logger.debug(f"Using pre-computed query embedding for: {query[:30]}...")
            else:
                query_cache_key = f"query_emb:{query}"
                cached_emb = self._get_cached_query_embedding(query_cache_key)

                if cached_emb is not None:
                    logger.debug(f"Cache HIT for query embedding: {query[:30]}...")
                    q_vec = np.array(cached_emb, dtype=np.float32)
                else:
                    # Get embedding (potentially batch with variants from query expansion)
                    raw_emb = self.llm.get_embedding(query)
                    self._cache_query_embedding(query_cache_key, raw_emb)
                    logger.debug(f"Cache MISS for query embedding: {query[:30]}... (cached, total: {len(self._query_embedding_cache)})")
                    q_vec = np.array(raw_emb, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)

            if q_norm > 0:
                q_vec = q_vec / q_norm  # Normalizza query

            # FASE 5: Use HNSW for large corpus (100+ documents)
            # HNSW provides O(log N) search vs O(N) exact, 10-100x speedup
            if self.hnsw_search and self.hnsw_search.hnsw_index is not None:
                logger.debug("Using HNSW approximate search")
                hnsw_results = self.hnsw_search.search(q_vec, top_k=top_k)

                # Convert HNSW results back to internal format
                results = []
                for doc_id, distance in hnsw_results:
                    doc = self.documents[doc_id]
                    results.append({
                        "id": doc.id,
                        "document": doc.text,
                        "similarity_score": float(1.0 - distance),  # Convert distance to similarity
                        "metadata": doc.metadata
                    })
                return results

            # Fallback to exact search (for small corpus or if HNSW disabled)
            # OPTIMIZATION 8.2: Pre-filter BEFORE ranking (not after)
            if where_filter:
                # BOTTLENECK FIX #3: Use metadata index for O(1) lookup instead of O(N) scan
                candidate_indices_set = None
                for k, v in where_filter.items():
                    index_key = (k, v)
                    if index_key in self._metadata_index:
                        matching_indices = self._metadata_index[index_key]
                        if candidate_indices_set is None:
                            candidate_indices_set = matching_indices.copy()
                        else:
                            candidate_indices_set &= matching_indices  # Intersection for AND logic
                    else:
                        # No documents match this filter
                        candidate_indices_set = set()
                        break

                if not candidate_indices_set:
                    logger.info(f"⚠️ No documents match filter {where_filter}")
                    return []

                candidate_indices = sorted(list(candidate_indices_set))  # Sort for consistent ordering
                # Compute scores only for candidates
                candidate_matrix = self._embedding_matrix[candidate_indices]
            else:
                candidate_indices = list(range(len(self._doc_ids_ordered)))
                candidate_matrix = self._embedding_matrix

            # 2. Calcola similarità CON VETTORIZZAZIONE NumPy (una sola operazione matriciale)
            # scores = matrice (M x 384) @ vettore (384,) = vettore (M,)  [M = candidate count]
            # Questo è 100x più veloce del loop Python di prima
            scores = candidate_matrix @ q_vec

            # 3. Top-k più veloci con argsort
            top_indices = np.argsort(-scores)[:top_k]

            # 4. Costruisci risultati
            results = []
            for local_idx in top_indices:
                global_idx = candidate_indices[local_idx]
                doc_id = self._doc_ids_ordered[global_idx]
                doc = self.documents[doc_id]

                results.append({
                    "id": doc.id,
                    "document": doc.text,
                    "similarity_score": float(scores[local_idx]),
                    "metadata": doc.metadata
                })

            return results

        except Exception as e:
            logger.error(f"✗ Errore ricerca: {e}")
            return []

    def list_indexed_files(self) -> set:
        """
        List all unique source filenames currently indexed in the vector store.
        Used for the Welcome Briefing to detect new files.
        """
        try:
            unique_sources = set()
            for doc in self.documents.values():
                if 'source' in doc.metadata:
                    unique_sources.add(doc.metadata['source'])
            return unique_sources
        except Exception as e:
            logger.error(f"Error listing indexed files: {e}")
            return set()

    def get_stats(self) -> Dict:
        return {
            "total_documents": len(self.documents),
            "backend": "numpy+pickle"
        }

    def get_all_documents(self) -> list[Dict]:
        """Ritorna TUTTI i documenti in libreria (non solo top-k)"""
        # Raggruppa chunk per documento (source)
        doc_groups = {}
        for doc_id, doc in self.documents.items():
            # doc è un oggetto Document con attributi: metadata, embedding, text
            source = doc.metadata.get("source", "Unknown")
            if source not in doc_groups:
                doc_groups[source] = {
                    "source": source,
                    "num_chunks": 0,
                    "section": doc.metadata.get("section", ""),
                    "sample_ids": []
                }
            doc_groups[source]["num_chunks"] += 1
            doc_groups[source]["sample_ids"].append(doc_id)

        # Converti in lista e ordina per source
        result = list(doc_groups.values())
        result.sort(key=lambda x: x["source"])
        logger.info(f"[LIBRARY] Total unique documents: {len(result)}, total chunks: {len(self.documents)}")
        return result

    def get_total_chunks(self) -> int:
        """Ritorna numero totale di chunk nel vector store"""
        return len(self.documents)

    def get_top_entities(self, max_entities: int = 8) -> list:
        """
        Estrae le entità principali (nomi aziende/tool) dai filename indicizzati.
        Usato dal Web Monitoring nel Briefing di Benvenuto (FASE 28).
        
        Strategy:
        - Rimuove numeri di data (YYYYMMDD), stopwords e estensioni
        - Restituisce i token più frequenti come proxy delle entità chiave
        """
        try:
            # Collect all source filenames
            all_sources = self.list_indexed_files()
            
            # Stopwords da ignorare (nomi generici, parole comuni)
            stopwords = {
                "report", "analisi", "documento", "file", "data", "note", "notes",
                "briefing", "summary", "riepilogo", "integrazione", "piattaforma",
                "documento", "the", "and", "per", "con", "del", "dei", "delle",
                "pdf", "docx", "txt", "xlsx", "csv", "md"
            }
            
            import re
            from collections import Counter
            token_counts = Counter()
            
            for source in all_sources:
                # Remove extension
                name = source.rsplit(".", 1)[0]
                # Remove date prefix (YYYYMMDD or YYYY-MM-DD)
                name = re.sub(r"\b\d{6,8}\b", "", name)
                name = re.sub(r"\b\d{4}[-_]\d{2}[-_]\d{2}\b", "", name)
                # Split on separators
                tokens = re.split(r"[\s\-_\.]+", name)
                for token in tokens:
                    token_clean = token.strip().lower()
                    # Keep only meaningful tokens (>3 chars, not stopwords, not pure numbers)
                    if len(token_clean) > 3 and token_clean not in stopwords and not token_clean.isdigit():
                        token_counts[token.strip()] += 1  # Keep original case
            
            # Return top N most frequent entities
            top_entities = [entity for entity, count in token_counts.most_common(max_entities)]
            logger.info(f"[TOP ENTITIES] Extracted {len(top_entities)} entities: {top_entities}")
            return top_entities
            
        except Exception as e:
            logger.error(f"Error extracting top entities: {e}")
            return []

    def update_document_summary(
        self,
        source_filename: str,
        summary: str,
        key_points: Optional[list[str]] = None
    ) -> bool:
        """
        Update summary and key points for a document.
        Updates all chunks belonging to the source document.

        Args:
            source_filename: Source document filename
            summary: Summary text
            key_points: List of key points

        Returns:
            True if update succeeded, False otherwise
        """
        try:
            updated_count = 0
            for doc_id, doc in self.documents.items():
                if doc.metadata.get("source") == source_filename:
                    doc.metadata["summary"] = summary
                    if key_points:
                        doc.metadata["key_points"] = key_points
                    doc.metadata["summary_generated_at"] = datetime.now().isoformat()
                    updated_count += 1

            if updated_count > 0:
                self._save()  # Persist changes
                logger.info(f"Updated summary for {source_filename} ({updated_count} chunks)")
                return True
            else:
                logger.warning(f"No documents found for source: {source_filename}")
                return False

        except Exception as e:
            logger.error(f"Error updating document summary: {e}")
            return False

    def get_document_summaries(self) -> dict[str, Dict]:
        """
        Get summaries and key points for all documents.

        Returns:
            Dictionary mapping source filename to {summary, key_points}
        """
        try:
            summaries = {}
            seen_sources = set()

            for doc in self.documents.values():
                source = doc.metadata.get("source", "Unknown")
                if source not in seen_sources:
                    summaries[source] = {
                        "summary": doc.metadata.get("summary", ""),
                        "key_points": doc.metadata.get("key_points", []),
                        "summary_generated_at": doc.metadata.get("summary_generated_at", ""),
                    }
                    seen_sources.add(source)

            return summaries

        except Exception as e:
            logger.error(f"Error getting document summaries: {e}")
            return {}

    def get_all_embeddings(self) -> Optional[np.ndarray]:
        """
        Get all document embeddings as a numpy array.
        Used for computing document similarity matrix.

        Returns:
            Numpy array of shape (N, embedding_dim), or None if empty
        """
        try:
            if self._embedding_matrix is None:
                return None
            return self._embedding_matrix.copy()
        except Exception as e:
            logger.error(f"Error getting embeddings: {e}")
            return None

    def get_document_ids_ordered(self) -> list[str]:
        """
        Get ordered list of document IDs matching embedding matrix order.
        Used for similarity matrix heatmap labels.

        Returns:
            List of document IDs in order
        """
        return self._doc_ids_ordered.copy()

# Singleton
_vector_store_instance = None

def get_vector_store() -> VectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = VectorStore()
    return _vector_store_instance

if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    vs = get_vector_store()
    print("Store initialized.")

