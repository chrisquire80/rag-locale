"""
HNSW Vector Indexing - Hierarchical Navigable Small World
FASE 5: Ricerca vettoriale veloce con approximate nearest neighbor search

HNSW offre:
- O(log N) ricerca approssimativa vs O(N) exact search
- Trade-off: 99-99.9% accuracy per guadagnare 10-100x speedup
- Ideale per corpus > 100 documenti

Nota: Utilizza numpy puro senza dipendenze esterne (hnswlib non supportato)
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass
import heapq

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class HNSWConfig:
    """Configurazione HNSW"""
    m: int = 16  # Numero di connessioni per layer (default=16, range 4-32)
    ef_construction: int = 200  # Parametro di costruzione (default=200, range 100-1000)
    ef_search: int = 50  # Parametro di ricerca (default=50, range 10-200)
    seed: int = 42
    max_m: int = 16
    max_m0: int = 32

class SimpleHNSWIndex:
    """
    Implementazione semplificata di HNSW usando NumPy puro
    (hnswlib non è disponibile su Python 3.14)

    Complessità:
    - Costruzione: O(N log N) con ef_construction
    - Ricerca: O(log N) approssimativa
    - Memory: O(N * M) dove M è il numero medio di connessioni
    """

    def __init__(self, config: HNSWConfig = None):
        self.config = config or HNSWConfig()
        self.data: list[np.ndarray] = []  # Embeddings
        self.ids: list[str] = []  # Document IDs
        self.graph: dict[int, list[tuple[int, float]]] = {}  # Navigable graph
        self.entry_point: Optional[int] = None
        self.levels: list[int] = []  # Layer for each node

        logger.info(
            f"✓ HNSW Index initialized (M={self.config.m}, "
            f"ef_construction={self.config.ef_construction})"
        )

    def add_items(self, embeddings: list[np.ndarray], ids: list[str]) -> None:
        """Aggiunge items all'indice"""
        logger.info(f"Building HNSW index for {len(embeddings)} items...")

        self.data = embeddings
        self.ids = ids
        self.levels = []
        self.graph = {}

        if not embeddings:
            return

        # Inserisci primo elemento come entry point
        self._insert_item(0, embeddings[0])

        # Inserisci rimanenti
        for i in range(1, len(embeddings)):
            self._insert_item(i, embeddings[i])

            if (i + 1) % 50 == 0:
                logger.debug(f"  Added {i+1}/{len(embeddings)} items...")

        logger.info(f"✓ HNSW index built ({len(self.ids)} items)")

    def _insert_item(self, idx: int, embedding: np.ndarray) -> None:
        """Inserisce un item nell'indice"""
        # Assign layer
        layer = int(-np.log(np.random.uniform()) * (1.0 / np.log(2.0)))
        self.levels.append(layer)

        if self.entry_point is None:
            self.entry_point = idx
            self.graph[idx] = []
        else:
            # Search for nearest neighbors
            nearest = self._search_layer(
                embedding,
                [self.entry_point],
                1
            )
            nearest_idx = nearest[0][1] if nearest else 0

            # Connect to neighbors at all layers
            for lc in range(min(layer, self.levels[nearest_idx])):
                neighbors = self._search_layer(
                    embedding,
                    self.graph.get(nearest_idx, [nearest_idx]),
                    self.config.ef_construction
                )

                m = self.config.max_m if lc > 0 else self.config.max_m0

                for _, neighbor_idx in neighbors[:m]:
                    if neighbor_idx not in [n[1] for n in self.graph.get(idx, [])]:
                        if idx not in self.graph:
                            self.graph[idx] = []
                        self.graph[idx].append((self._distance(embedding, self.data[neighbor_idx]), neighbor_idx))

    def _search_layer(
        self,
        query: np.ndarray,
        entry_points: list[int],
        ef: int
    ) -> list[tuple[float, int]]:
        """Ricerca entro un layer"""
        visited = set()
        candidates = []
        w = []

        # Initialize with entry points
        for ep in entry_points:
            d = self._distance(query, self.data[ep])
            heapq.heappush(candidates, (-d, ep))
            heapq.heappush(w, (d, ep))
            visited.add(ep)

        while candidates:
            current_dist, current = heapq.heappop(candidates)
            current_dist = -current_dist

            # Check if current distance is worse than worst in result set
            if w and current_dist > w[0][0]:
                break

            # Check neighbors
            neighbors = self.graph.get(current, [])
            for _, neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    d = self._distance(query, self.data[neighbor])

                    # Add if better than worst result or result set not full
                    if not w or d < w[0][0] or len(w) < ef:
                        heapq.heappush(candidates, (-d, neighbor))
                        heapq.heappush(w, (d, neighbor))

                        if len(w) > ef:
                            heapq.heappop(w)

        return sorted(w)

    def search(
        self,
        query: np.ndarray,
        k: int = 5
    ) -> list[tuple[int, float]]:
        """
        Ricerca k nearest neighbors

        Returns:
            List of (id_index, distance) tuples
        """
        if not self.data or self.entry_point is None:
            return []

        # Search with ef = k * 2 for good recall
        nearest = self._search_layer(
            query,
            [self.entry_point],
            max(self.config.ef_search, k * 2)
        )

        return [(idx, dist) for dist, idx in nearest[:k]]

    @staticmethod
    def _distance(a: np.ndarray, b: np.ndarray) -> float:
        """Euclidean distance"""
        return np.linalg.norm(a - b)

    def get_stats(self) -> Dict:
        """Ritorna statistiche dell'indice"""
        return {
            "num_items": len(self.ids),
            "entry_point": self.entry_point,
            "avg_connections": np.mean([len(v) for v in self.graph.values()]) if self.graph else 0,
            "max_layer": max(self.levels) if self.levels else 0,
        }

class FastVectorSearch:
    """Wrapper per ricerca vettoriale veloce con fallback"""

    def __init__(self, enable_hnsw: bool = True):
        self.enable_hnsw = enable_hnsw
        self.hnsw_index: Optional[SimpleHNSWIndex] = None
        self.embeddings: list[np.ndarray] = []
        self.ids: list[str] = []

    def build_index(self, embeddings: list[np.ndarray], ids: list[str]) -> None:
        """Costruisce indice HNSW"""
        self.embeddings = embeddings
        self.ids = ids

        if self.enable_hnsw and len(embeddings) > 50:
            logger.info("Building HNSW index for fast search...")
            self.hnsw_index = SimpleHNSWIndex()
            self.hnsw_index.add_items(embeddings, ids)
            stats = self.hnsw_index.get_stats()
            logger.info(f"  HNSW stats: {stats}")
        else:
            logger.info(f"Using exact search ({len(embeddings)} embeddings)")

    def search(self, query: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """
        Ricerca i top_k nearest neighbors

        Returns:
            List of (id, distance) tuples
        """
        if not self.embeddings:
            return []

        if self.hnsw_index is not None:
            # Use HNSW approximate search
            results = self.hnsw_index.search(query, k=top_k)
            return [(self.ids[idx], dist) for idx, dist in results]
        else:
            # Fallback to exact search
            distances = [
                np.linalg.norm(query - emb)
                for emb in self.embeddings
            ]
            top_indices = np.argsort(distances)[:top_k]
            return [(self.ids[idx], distances[idx]) for idx in top_indices]

    def get_index_stats(self) -> Dict:
        """Ritorna statistiche dell'indice"""
        if self.hnsw_index:
            return self.hnsw_index.get_stats()
        else:
            return {"type": "exact_search", "num_items": len(self.ids)}

def benchmark_hnsw_vs_exact(num_items: int = 1000, num_queries: int = 100):
    """Benchmark HNSW vs ricerca esatta"""
    import time

    logger.info(f"\n{'='*60}")
    logger.info(f"HNSW Benchmark: {num_items} items, {num_queries} queries")
    logger.info(f"{'='*60}")

    # Generate synthetic embeddings
    np.random.seed(42)
    embeddings = [np.random.randn(768).astype(np.float32) for _ in range(num_items)]
    ids = [f"doc_{i:05d}" for i in range(num_items)]

    # Queries
    query_embeddings = [np.random.randn(768).astype(np.float32) for _ in range(num_queries)]

    # HNSW Search
    logger.info("\nTesting HNSW search...")
    hnsw = FastVectorSearch(enable_hnsw=True)
    hnsw.build_index(embeddings, ids)

    start = time.perf_counter()
    for query in query_embeddings:
        hnsw.search(query, top_k=5)
    hnsw_time = time.perf_counter() - start

    # Exact Search
    logger.info("Testing exact search...")
    exact = FastVectorSearch(enable_hnsw=False)
    exact.build_index(embeddings, ids)

    start = time.perf_counter()
    for query in query_embeddings:
        exact.search(query, top_k=5)
    exact_time = time.perf_counter() - start

    speedup = exact_time / hnsw_time if hnsw_time > 0 else 1.0

    logger.info(f"\nResults:")
    logger.info(f"  HNSW:  {hnsw_time:.3f}s ({num_queries/hnsw_time:.1f} queries/sec)")
    logger.info(f"  Exact: {exact_time:.3f}s ({num_queries/exact_time:.1f} queries/sec)")
    logger.info(f"  Speedup: {speedup:.1f}x")

if __name__ == "__main__":
    benchmark_hnsw_vs_exact(num_items=1000, num_queries=100)
