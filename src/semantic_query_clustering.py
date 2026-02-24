"""
Semantic Query Clustering for improved cache hit rates.
Groups semantically similar queries to reuse cached results and expansions.

PHASE 10.1: Advanced Retrieval & Semantic Search
- Maps similar queries to cluster centroids for cache reuse
- Expected improvement: 60-70% cache hit rate (vs current 40-50%)
- Threshold: 0.85 cosine similarity = semantic equivalence
"""

import logging
import time
import numpy as np
from collections import deque
from typing import Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class QueryCluster:
    """Represents a semantic cluster of similar queries"""
    cluster_id: str
    centroid_embedding: np.ndarray
    queries: List[str]
    results_cache: Optional[dict] = None  # Cached RAGResponse for this cluster
    timestamp: datetime = None  # When cluster was created

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class SemanticQueryClusterer:
    """
    Clusters semantically similar queries to improve cache hit rates.

    Strategy:
    1. Embed incoming query using Gemini embeddings
    2. Compare to recent queries (last 100) with >0.85 similarity threshold
    3. If match found, return cluster ID and cached results if available
    4. Otherwise, create new cluster or add to existing one

    Expected impact:
    - Similar queries: "What is ML?" vs "Define machine learning?" → same cluster
    - Cache hit rate: 60-70% (vs current 40-50% with simple string matching)
    - Expansion reuse: Query variants shared across cluster members
    """

    def __init__(self, max_recent_queries: int = 100, similarity_threshold: float = 0.85):
        """
        Initialize semantic query clusterer.

        Args:
            max_recent_queries: Max number of recent queries to track for clustering
            similarity_threshold: Cosine similarity threshold for clustering (0.85 = very similar)
        """
        self.max_recent_queries = max_recent_queries
        self.similarity_threshold = similarity_threshold

        # Track recent queries and their embeddings (deque is O(1) for both append and maxlen eviction)
        self._recent_queries: deque = deque(maxlen=max_recent_queries)  # [(query, embedding), ...]
        self._query_clusters: dict[str, QueryCluster] = {}  # {cluster_id: QueryCluster}
        self._query_to_cluster: dict[str, str] = {}  # {query: cluster_id}

        # For embedding generation
        self._llm = None  # Lazy loaded
        self._cluster_counter = 0

    @property
    def llm(self):
        """Lazy load LLM service for embeddings"""
        if self._llm is None:
            from src.llm_service import get_llm_service
            self._llm = get_llm_service()
        return self._llm

    def _get_query_embedding(self, query: str) -> np.ndarray:
        """
        Get embedding for a query using Gemini embeddings.

        Args:
            query: Query text

        Returns:
            Embedding vector (1536-dimensional for Gemini)
        """
        try:
            embeddings = self.llm.get_embeddings([query])
            if embeddings:
                return np.array(embeddings[0])
            else:
                logger.warning(f"Failed to get embedding for query: {query}")
                return None
        except Exception as e:
            logger.warning(f"Error generating query embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0.0-1.0)
        """
        try:
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return np.dot(vec1, vec2) / (norm1 * norm2)
        except Exception as e:
            logger.warning(f"Error calculating cosine similarity: {e}")
            return 0.0

    def get_similarity_to_recent(self, query: str, embedding: Optional[np.ndarray] = None) -> Optional[Tuple[str, float]]:
        """
        Check similarity of query to recent queries.
        Returns matching cluster if similarity > threshold.

        Args:
            query: Query text
            embedding: Pre-computed embedding (optional, will compute if not provided)

        Returns:
            Tuple of (cluster_id, similarity_score) if match found, else None
        """
        if embedding is None:
            embedding = self._get_query_embedding(query)

        if embedding is None or len(self._recent_queries) == 0:
            return None

        # Find highest similarity to recent queries
        best_similarity = 0.0
        best_cluster_id = None

        for recent_query, recent_embedding in self._recent_queries:
            similarity = self._cosine_similarity(embedding, recent_embedding)

            if similarity > self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                # Get cluster ID for this query
                if recent_query in self._query_to_cluster:
                    best_cluster_id = self._query_to_cluster[recent_query]
                    logger.info(f"🎯 Semantic match found: '{query}' clusters with '{recent_query}' (similarity: {similarity:.3f})")

        if best_cluster_id:
            return (best_cluster_id, best_similarity)
        return None

    def cluster_query(self, query: str, embedding: Optional[np.ndarray] = None) -> str:
        """
        Map query to a cluster (either existing or new).

        Args:
            query: Query text
            embedding: Pre-computed embedding (optional)

        Returns:
            Cluster ID
        """
        # Check if query already has a cluster
        if query in self._query_to_cluster:
            cluster_id = self._query_to_cluster[query]
            logger.debug(f"Query already in cluster {cluster_id}")
            return cluster_id

        # Get or compute embedding
        if embedding is None:
            embedding = self._get_query_embedding(query)

        if embedding is None:
            # Fallback: create new cluster for this query
            cluster_id = f"cluster_{self._cluster_counter}"
            self._cluster_counter += 1
            logger.debug(f"No embedding, creating new cluster {cluster_id}")
        else:
            # Check similarity to existing clusters
            similarity_result = self.get_similarity_to_recent(query, embedding)

            if similarity_result:
                cluster_id, similarity = similarity_result
                logger.info(f"✨ Query clustered with existing cluster {cluster_id} (sim: {similarity:.3f})")
            else:
                # Create new cluster
                cluster_id = f"cluster_{self._cluster_counter}"
                self._cluster_counter += 1
                logger.debug(f"No similar queries, creating new cluster {cluster_id}")

                # Create cluster
                self._query_clusters[cluster_id] = QueryCluster(
                    cluster_id=cluster_id,
                    centroid_embedding=embedding.copy(),
                    queries=[query],
                    timestamp=datetime.now()
                )

        # Register query to cluster
        self._query_to_cluster[query] = cluster_id

        # Add query to recent queries (deque handles eviction automatically)
        self._recent_queries.append((query, embedding if embedding is not None else np.zeros(1536)))

        # Update cluster's query list if cluster exists
        if cluster_id in self._query_clusters:
            if query not in self._query_clusters[cluster_id].queries:
                self._query_clusters[cluster_id].queries.append(query)

        return cluster_id

    def get_cluster_results(self, cluster_id: str) -> Optional[dict]:
        """
        Retrieve cached results for a cluster (if available).

        Args:
            cluster_id: Cluster ID

        Returns:
            Cached RAGResponse for cluster, or None if not cached
        """
        if cluster_id in self._query_clusters:
            return self._query_clusters[cluster_id].results_cache
        return None

    def add_to_cache(self, query: str, cluster_id: str, response: 'RAGResponse') -> None:
        """
        Cache RAGResponse for a cluster.

        Args:
            query: Query text
            cluster_id: Cluster ID
            response: RAGResponse to cache
        """
        # Ensure cluster exists
        if cluster_id not in self._query_clusters:
            # Create cluster if doesn't exist (shouldn't happen normally)
            embedding = self._get_query_embedding(query)
            self._query_clusters[cluster_id] = QueryCluster(
                cluster_id=cluster_id,
                centroid_embedding=embedding if embedding is not None else np.zeros(1536),
                queries=[query],
                results_cache=response,
                timestamp=datetime.now()
            )
        else:
            # Cache results for cluster
            self._query_clusters[cluster_id].results_cache = response
            logger.debug(f"Cached response for cluster {cluster_id}")

    def get_cache_stats(self) -> dict:
        """
        Get statistics about clustering and cache effectiveness.

        Returns:
            Dictionary with stats
        """
        total_clusters = len(self._query_clusters)
        total_queries_tracked = len(self._query_to_cluster)
        cached_clusters = sum(1 for c in self._query_clusters.values() if c.results_cache is not None)

        avg_cluster_size = total_queries_tracked / total_clusters if total_clusters > 0 else 0

        return {
            "total_clusters": total_clusters,
            "total_queries_tracked": total_queries_tracked,
            "cached_clusters": cached_clusters,
            "avg_cluster_size": avg_cluster_size,
            "recent_queries_tracked": len(self._recent_queries),
            "similarity_threshold": self.similarity_threshold,
        }

    def clear_expired_clusters(self, max_age_hours: int = 24) -> int:
        """
        Remove clusters older than max_age_hours.

        Args:
            max_age_hours: Max age in hours

        Returns:
            Number of clusters removed
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        expired_clusters = [
            cid for cid, cluster in self._query_clusters.items()
            if cluster.timestamp < cutoff_time
        ]

        # Remove expired clusters and their query mappings
        for cluster_id in expired_clusters:
            cluster = self._query_clusters[cluster_id]
            for query in cluster.queries:
                if query in self._query_to_cluster:
                    del self._query_to_cluster[query]
            del self._query_clusters[cluster_id]

        if expired_clusters:
            logger.info(f"Cleared {len(expired_clusters)} expired clusters (>={max_age_hours}h old)")

        return len(expired_clusters)


    def invalidate_clusters(self) -> None:
        """
        Svuota tutta la cache cluster.
        Da chiamare quando RAGEngine.invalidate_cache() viene invocato
        (es. dopo upload di nuovi documenti) per evitare risposte stale.
        """
        count = len(self._query_clusters)
        self._query_clusters.clear()
        self._query_to_cluster.clear()
        self._recent_queries.clear()
        logger.info(f"🗑️ Cluster cache invalidata ({count} cluster rimossi)")


# Global instance
_query_clusterer = None


def get_semantic_query_clusterer() -> SemanticQueryClusterer:
    """Get or create global semantic query clusterer"""
    global _query_clusterer
    if _query_clusterer is None:
        _query_clusterer = SemanticQueryClusterer()
    return _query_clusterer
