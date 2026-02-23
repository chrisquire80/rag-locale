"""
Tests for Phase 8 Feature 2: Document Similarity Matrix
Tests DocumentSimilarityMatrix, cosine similarity computation, and clustering
"""

import pytest
import numpy as np
import logging
from src.document_similarity_matrix import DocumentSimilarityMatrix
from src.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class TestDocumentSimilarityMatrix:
    """Test suite for DocumentSimilarityMatrix class"""

    @pytest.fixture
    def vector_store(self):
        """Get the vector store instance"""
        return get_vector_store()

    @pytest.fixture
    def similarity_manager(self, vector_store):
        """Create a DocumentSimilarityMatrix instance"""
        return DocumentSimilarityMatrix(vector_store)

    def test_similarity_manager_initialization(self, similarity_manager):
        """Test that DocumentSimilarityMatrix initializes correctly"""
        assert similarity_manager is not None
        assert hasattr(similarity_manager, 'compute_similarity_matrix')
        assert hasattr(similarity_manager, 'get_related_documents')
        assert hasattr(similarity_manager, 'get_statistics')
        logger.info("✓ Similarity manager initialized")

    def test_compute_similarity_matrix(self, similarity_manager):
        """Test similarity matrix computation"""
        matrix = similarity_manager.compute_similarity_matrix()

        if matrix is not None:
            assert isinstance(matrix, np.ndarray)
            assert matrix.shape[0] == matrix.shape[1]  # Square matrix
            assert matrix.shape[0] > 0

            # Check that diagonal is zero (no self-similarity)
            diagonal = np.diag(matrix)
            assert np.allclose(diagonal, 0)

            # Check that values are in [0, 1]
            assert np.all(matrix >= 0) and np.all(matrix <= 1)
            logger.info(f"✓ Similarity matrix computed: {matrix.shape}")
        else:
            logger.info("⊘ No similarity matrix (expected if no documents)")

    def test_similarity_matrix_statistics(self, similarity_manager):
        """Test that statistics are calculated correctly"""
        similarity_manager.compute_similarity_matrix()
        stats = similarity_manager.get_statistics()

        assert stats is not None
        if len(stats) > 0:
            assert 'total_documents' in stats
            assert 'avg_similarity' in stats
            assert 'max_similarity' in stats
            assert 'min_similarity' in stats

            # Validate ranges
            assert stats['avg_similarity'] >= 0 and stats['avg_similarity'] <= 1
            assert stats['max_similarity'] >= 0 and stats['max_similarity'] <= 1
            logger.info(f"✓ Stats: avg={stats['avg_similarity']:.3f}, max={stats['max_similarity']:.3f}")

    def test_get_related_documents(self, similarity_manager):
        """Test retrieval of related documents"""
        similarity_manager.compute_similarity_matrix()

        if similarity_manager.similarity_matrix is not None:
            # Get documents related to first document
            related = similarity_manager.get_related_documents(doc_index=0, top_k=5)

            assert related is not None
            assert isinstance(related, list)
            if len(related) > 0:
                # Check format of returned results
                doc_id, score = related[0]
                assert isinstance(doc_id, str)
                assert isinstance(score, float)
                assert 0 <= score <= 1
                logger.info(f"✓ Found {len(related)} related documents")
        else:
            logger.info("⊘ No similarity matrix for related documents test")

    def test_get_most_similar_pairs(self, similarity_manager):
        """Test retrieval of most similar document pairs"""
        similarity_manager.compute_similarity_matrix()

        if similarity_manager.similarity_matrix is not None:
            pairs = similarity_manager.get_most_similar_pairs(top_n=10)

            assert pairs is not None
            assert isinstance(pairs, list)
            if len(pairs) > 0:
                # Check format
                for doc1, doc2, score in pairs:
                    assert isinstance(doc1, str)
                    assert isinstance(doc2, str)
                    assert isinstance(score, float)
                    assert 0 <= score <= 1
                logger.info(f"✓ Found {len(pairs)} similar pairs")

    def test_clustering(self, similarity_manager):
        """Test document clustering"""
        similarity_manager.compute_similarity_matrix()

        if similarity_manager.similarity_matrix is not None:
            clusters = similarity_manager.get_clustering(num_clusters=3)

            assert clusters is not None
            if len(clusters) > 0:
                assert len(clusters) <= 3  # Should have at most 3 clusters
                for cluster_id, doc_ids in clusters.items():
                    assert isinstance(cluster_id, int)
                    assert isinstance(doc_ids, list)
                    assert len(doc_ids) > 0
                logger.info(f"✓ Created {len(clusters)} clusters")

    def test_heatmap_data_format(self, similarity_manager):
        """Test heatmap data generation for visualization"""
        similarity_manager.compute_similarity_matrix()

        heatmap_data = similarity_manager.build_heatmap_data()

        if heatmap_data and len(heatmap_data) > 0:
            assert 'z' in heatmap_data  # Matrix data
            assert 'x' in heatmap_data  # X labels
            assert 'y' in heatmap_data  # Y labels
            assert 'text' in heatmap_data  # Hover text
            assert 'colorscale' in heatmap_data

            # Validate data consistency
            assert len(heatmap_data['x']) == len(heatmap_data['y'])
            assert len(heatmap_data['z']) == len(heatmap_data['y'])
            logger.info(f"✓ Heatmap data valid: {len(heatmap_data['z'])} x {len(heatmap_data['z'][0])} grid")
