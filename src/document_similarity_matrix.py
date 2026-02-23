"""
Document Similarity Matrix
Computes and visualizes document relationships using embedding similarity.
Provides clustering, related documents suggestions, and interactive visualizations.
"""

import logging
import numpy as np
from typing import List, Dict, Tuple, Optional
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class DocumentSimilarityMatrix:
    """
    Computes and manages document similarity matrices based on embedding vectors.
    Uses cosine similarity to measure document relationships.
    """

    CACHE_DIR = ".similarity_cache"
    MATRIX_CACHE_FILE = "similarity_matrix.npy"
    LABELS_CACHE_FILE = "doc_labels.json"

    def __init__(self, vector_store=None):
        """
        Initialize DocumentSimilarityMatrix.

        Args:
            vector_store: Optional ChromaVectorStore instance for embeddings
        """
        self.vector_store = vector_store
        self.similarity_matrix: Optional[np.ndarray] = None
        self.doc_ids_ordered: List[str] = []
        self.doc_labels: Dict[str, str] = {}
        self._matrix_valid = False
        self._load_cached_matrix()

    def _load_cached_matrix(self):
        """Load cached similarity matrix from disk if available."""
        try:
            cache_path = os.path.join(self.CACHE_DIR, self.MATRIX_CACHE_FILE)
            labels_path = os.path.join(self.CACHE_DIR, self.LABELS_CACHE_FILE)

            if os.path.exists(cache_path) and os.path.exists(labels_path):
                self.similarity_matrix = np.load(cache_path)
                with open(labels_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.doc_ids_ordered = data.get("doc_ids", [])
                    self.doc_labels = data.get("doc_labels", {})
                    self._matrix_valid = True
                logger.info(f"Loaded cached similarity matrix ({len(self.doc_ids_ordered)} documents)")
        except Exception as e:
            logger.debug(f"Could not load cached similarity matrix: {e}")
            self._matrix_valid = False

    def _save_cached_matrix(self):
        """Save computed similarity matrix to disk cache."""
        try:
            os.makedirs(self.CACHE_DIR, exist_ok=True)
            cache_path = os.path.join(self.CACHE_DIR, self.MATRIX_CACHE_FILE)
            labels_path = os.path.join(self.CACHE_DIR, self.LABELS_CACHE_FILE)

            if self.similarity_matrix is not None:
                np.save(cache_path, self.similarity_matrix)

            if self.doc_ids_ordered or self.doc_labels:
                data = {
                    "doc_ids": self.doc_ids_ordered,
                    "doc_labels": self.doc_labels,
                    "timestamp": datetime.now().isoformat(),
                }
                with open(labels_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                logger.info(f"Cached similarity matrix ({len(self.doc_ids_ordered)} documents)")
        except Exception as e:
            logger.warning(f"Failed to cache similarity matrix: {e}")

    def compute_similarity_matrix(self) -> Optional[np.ndarray]:
        """
        Compute cosine similarity matrix between all documents.
        Uses embeddings from vector store.

        Returns:
            NxN numpy array of similarity scores (0.0-1.0), or None if failed
        """
        try:
            if self.vector_store is None:
                logger.error("No vector store available for computing similarity")
                return None

            # Get all embeddings
            embeddings = self.vector_store.get_all_embeddings()
            if embeddings is None or len(embeddings) == 0:
                logger.warning("No embeddings available for similarity computation")
                return None

            self.doc_ids_ordered = self.vector_store.get_document_ids_ordered()

            if len(embeddings) == 0:
                logger.warning("No documents to compute similarity for")
                return None

            logger.info(f"Computing similarity matrix for {len(embeddings)} documents...")

            # Normalize embeddings for cosine similarity (already normalized in vector_store)
            # But ensure they are properly normalized
            embeddings_norm = embeddings.copy()
            norms = np.linalg.norm(embeddings_norm, axis=1, keepdims=True)
            embeddings_norm = embeddings_norm / np.where(norms == 0, 1, norms)

            # Compute cosine similarity matrix: [N, D] @ [D, N] = [N, N]
            similarity_matrix = embeddings_norm @ embeddings_norm.T

            # Zero out diagonal (document not similar to itself for ranking)
            np.fill_diagonal(similarity_matrix, 0.0)

            # Clamp to [0, 1] range (shouldn't be needed but safety)
            similarity_matrix = np.clip(similarity_matrix, 0.0, 1.0)

            # Build labels from doc IDs (source filenames)
            self.doc_labels = {}
            for i, doc_id in enumerate(self.doc_ids_ordered):
                # doc_id format: "filename_XXX", extract filename
                source = doc_id.rsplit("_", 1)[0] if "_" in doc_id else doc_id
                self.doc_labels[doc_id] = source

            self.similarity_matrix = similarity_matrix
            self._matrix_valid = True

            # Cache the result
            self._save_cached_matrix()

            logger.info(f"Similarity matrix computed: {similarity_matrix.shape}")
            return similarity_matrix

        except Exception as e:
            logger.error(f"Error computing similarity matrix: {e}")
            return None

    def get_related_documents(
        self, doc_index: int, top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Get most similar documents to a given document.

        Args:
            doc_index: Index of document in the matrix
            top_k: Number of related documents to return

        Returns:
            List of (doc_id, similarity_score) tuples, sorted by score descending
        """
        try:
            if self.similarity_matrix is None:
                logger.warning("Similarity matrix not computed")
                return []

            if doc_index < 0 or doc_index >= len(self.similarity_matrix):
                logger.warning(f"Invalid document index: {doc_index}")
                return []

            # Get similarity scores for this document
            scores = self.similarity_matrix[doc_index]

            # Find top-k indices (excluding self, which has score 0)
            top_indices = np.argsort(-scores)[:top_k]

            # Build results
            results = []
            for idx in top_indices:
                if idx < len(self.doc_ids_ordered):
                    doc_id = self.doc_ids_ordered[idx]
                    score = float(scores[idx])
                    if score > 0:  # Only include if there's actual similarity
                        results.append((doc_id, score))

            return results

        except Exception as e:
            logger.error(f"Error getting related documents: {e}")
            return []

    def build_heatmap_data(self) -> Dict:
        """
        Build data structure for Plotly heatmap visualization.

        Returns:
            Dictionary with z (matrix), x (labels), y (labels), text (annotations)
        """
        try:
            if self.similarity_matrix is None:
                logger.warning("Similarity matrix not computed")
                return {}

            # Get document labels (short source filenames)
            labels = [self.doc_labels.get(doc_id, doc_id[:20]) for doc_id in self.doc_ids_ordered]

            # Build hover text (show actual similarity values)
            text = []
            for i in range(len(labels)):
                row_text = []
                for j in range(len(labels)):
                    score = self.similarity_matrix[i, j]
                    row_text.append(f"{score:.3f}")
                text.append(row_text)

            return {
                "z": self.similarity_matrix.tolist(),
                "x": labels,
                "y": labels,
                "text": text,
                "colorscale": "Viridis",  # Blue (low) to Yellow (high)
                "colorbar_title": "Similarity",
            }

        except Exception as e:
            logger.error(f"Error building heatmap data: {e}")
            return {}

    def get_clustering(self, num_clusters: int = 3) -> Dict[int, List[str]]:
        """
        Simple clustering of documents based on similarity.
        Uses hierarchical clustering approach.

        Args:
            num_clusters: Number of clusters to create

        Returns:
            Dictionary mapping cluster_id to list of document IDs
        """
        try:
            if self.similarity_matrix is None:
                logger.warning("Similarity matrix not computed")
                return {}

            from scipy.cluster.hierarchy import linkage, fcluster
            from scipy.spatial.distance import squareform

            # Convert similarity to distance (1 - similarity)
            distance_matrix = 1.0 - self.similarity_matrix
            np.fill_diagonal(distance_matrix, 0)

            # Perform hierarchical clustering
            condensed_dist = squareform(distance_matrix)
            linkage_matrix = linkage(condensed_dist, method="ward")
            clusters = fcluster(linkage_matrix, num_clusters, criterion="maxclust")

            # Build cluster dictionary
            clustering = {}
            for cluster_id in range(1, num_clusters + 1):
                cluster_indices = np.where(clusters == cluster_id)[0]
                doc_ids = [self.doc_ids_ordered[i] for i in cluster_indices if i < len(self.doc_ids_ordered)]
                if doc_ids:
                    clustering[cluster_id] = doc_ids

            logger.info(f"Created {num_clusters} document clusters")
            return clustering

        except ImportError:
            logger.warning("scipy not available for clustering")
            return {}
        except Exception as e:
            logger.error(f"Error performing clustering: {e}")
            return {}

    def invalidate_cache(self):
        """Invalidate cached similarity matrix (call when documents change)."""
        self._matrix_valid = False
        self.similarity_matrix = None
        self.doc_ids_ordered = []
        self.doc_labels = {}
        logger.info("Similarity matrix cache invalidated")

    def get_statistics(self) -> Dict:
        """
        Get statistics about the similarity matrix.

        Returns:
            Dictionary with min, max, mean, median similarity scores
        """
        try:
            if self.similarity_matrix is None:
                return {}

            # Only consider non-zero similarities (off-diagonal)
            mask = self.similarity_matrix > 0
            similarities = self.similarity_matrix[mask]

            if len(similarities) == 0:
                return {
                    "total_documents": len(self.doc_ids_ordered),
                    "avg_similarity": 0.0,
                    "max_similarity": 0.0,
                    "min_similarity": 0.0,
                    "median_similarity": 0.0,
                }

            return {
                "total_documents": len(self.doc_ids_ordered),
                "avg_similarity": float(np.mean(similarities)),
                "max_similarity": float(np.max(similarities)),
                "min_similarity": float(np.min(similarities)),
                "median_similarity": float(np.median(similarities)),
                "std_similarity": float(np.std(similarities)),
            }

        except Exception as e:
            logger.error(f"Error computing statistics: {e}")
            return {}

    def get_most_similar_pairs(self, top_n: int = 10) -> List[Tuple[str, str, float]]:
        """
        Get the most similar document pairs in the collection.

        Args:
            top_n: Number of top pairs to return

        Returns:
            List of (doc_id1, doc_id2, similarity_score) tuples
        """
        try:
            if self.similarity_matrix is None:
                return []

            pairs = []

            # Get upper triangle indices (avoid duplicates)
            upper_indices = np.triu_indices(len(self.similarity_matrix), k=1)

            for i, j in zip(upper_indices[0], upper_indices[1]):
                score = float(self.similarity_matrix[i, j])
                if score > 0:
                    doc_id1 = self.doc_ids_ordered[i]
                    doc_id2 = self.doc_ids_ordered[j]
                    pairs.append((doc_id1, doc_id2, score))

            # Sort by similarity descending
            pairs.sort(key=lambda x: x[2], reverse=True)

            return pairs[:top_n]

        except Exception as e:
            logger.error(f"Error getting most similar pairs: {e}")
            return []

    def is_valid(self) -> bool:
        """Check if similarity matrix is currently valid."""
        return self._matrix_valid and self.similarity_matrix is not None
