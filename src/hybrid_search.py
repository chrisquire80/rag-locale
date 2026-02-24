"""
Hybrid Search Engine - BM25 + Vector Similarity
Combines keyword-based (BM25) and semantic (vector) search for better retrieval
"""

import logging
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Result from hybrid search"""
    doc_id: str
    text: str
    metadata: Dict
    bm25_score: float
    vector_score: float
    combined_score: float
    rank: int

class BM25:
    """BM25 (Best Matching 25) - Probabilistic Ranking Function

    BM25 is the industry standard for keyword-based search.
    It scores documents based on term frequency and document frequency.
    """

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 with corpus

        Args:
            corpus: List of documents (strings)
            k1: Controls term frequency saturation (default 1.5)
            b: Controls length normalization (default 0.75)
        """
        self.k1 = k1
        self.b = b
        self.corpus = corpus

        # Build inverted index
        self.inverted_index = defaultdict(list)  # term -> [(doc_id, freq)]
        self.doc_freqs = defaultdict(lambda: defaultdict(int))  # doc_id -> term -> freq
        self.doc_lengths = {}  # doc_id -> length

        self._build_index()
        self.avg_doc_length = sum(self.doc_lengths.values()) / len(self.doc_lengths) if self.doc_lengths else 0

    def _build_index(self):
        """Build inverted index from corpus"""
        for doc_id, doc in enumerate(self.corpus):
            words = self._tokenize(doc)
            self.doc_lengths[doc_id] = len(words)

            for term in set(words):
                freq = words.count(term)
                self.doc_freqs[doc_id][term] = freq
                self.inverted_index[term].append(doc_id)

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization (lowercase, split by whitespace)"""
        return text.lower().split()

    def _idf(self, term: str) -> float:
        """Calculate Inverse Document Frequency"""
        n = len(self.corpus)
        df = len(set(self.inverted_index[term]))
        if df == 0:
            return 0
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> np.ndarray:
        """Score all documents for a query

        Args:
            query: Search query string

        Returns:
            Array of scores, one per document
        """
        scores = np.zeros(len(self.corpus))
        query_terms = self._tokenize(query)

        for term in set(query_terms):
            idf = self._idf(term)

            for doc_id in range(len(self.corpus)):
                freq = self.doc_freqs[doc_id].get(term, 0)
                if freq == 0:
                    continue

                # BM25 formula
                norm_length = (1 - self.b) + self.b * (self.doc_lengths[doc_id] / self.avg_doc_length)
                score = idf * (freq * (self.k1 + 1)) / (freq + self.k1 * norm_length)
                scores[doc_id] += score

        return scores

class HybridSearchEngine:
    """Hybrid Search combining BM25 (keyword) + Vector (semantic) search"""

    def __init__(self, documents: list[Dict], embeddings: Optional[np.ndarray] = None):
        """
        Initialize hybrid search engine

        Args:
            documents: List of document dicts with 'id', 'text', 'metadata'
            embeddings: Optional pre-computed embeddings (n_docs x embedding_dim)
        """
        self.documents = documents
        self.embeddings = embeddings
        self.doc_texts = [doc['text'] for doc in documents]

        # Initialize BM25
        self.bm25 = BM25(self.doc_texts)
        logger.info(f"Initialized Hybrid Search with {len(documents)} documents")

    def search(
        self,
        query: str,
        query_embedding: Optional[np.ndarray] = None,
        top_k: int = 10,
        alpha: float = 0.5
    ) -> list[SearchResult]:
        """
        Hybrid search combining BM25 and vector similarity

        Args:
            query: Search query text
            query_embedding: Optional pre-computed query embedding
            top_k: Number of results to return
            alpha: Weight for combining scores (0=BM25 only, 1=vector only, 0.5=equal)

        Returns:
            Sorted list of SearchResult objects
        """
        # BM25 scores
        bm25_scores = self.bm25.score(query)
        bm25_scores = self._normalize_scores(bm25_scores)

        # Vector scores
        vector_scores = np.zeros(len(self.documents))
        if query_embedding is not None and self.embeddings is not None:
            vector_scores = self._vector_similarity(query_embedding)

        # Combine scores
        combined_scores = alpha * vector_scores + (1 - alpha) * bm25_scores

        # Sort and return top-k
        top_indices = np.argsort(-combined_scores)[:top_k]

        results = []
        for rank, doc_idx in enumerate(top_indices):
            doc = self.documents[doc_idx]
            results.append(SearchResult(
                doc_id=doc['id'],
                text=doc['text'],
                metadata=doc.get('metadata', {}),
                bm25_score=float(bm25_scores[doc_idx]),
                vector_score=float(vector_scores[doc_idx]),
                combined_score=float(combined_scores[doc_idx]),
                rank=rank + 1
            ))

        return results

    def _normalize_scores(self, scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1]"""
        if scores.max() == 0:
            return scores
        return scores / scores.max()

    def _vector_similarity(self, query_embedding: np.ndarray) -> np.ndarray:
        """Calculate cosine similarity with query embedding"""
        query_norm = np.linalg.norm(query_embedding)
        if query_norm == 0:
            return np.zeros(len(self.documents))

        query_normalized = query_embedding / query_norm
        embeddings_normalized = self.embeddings / np.linalg.norm(
            self.embeddings, axis=1, keepdims=True
        )

        similarities = embeddings_normalized @ query_normalized
        return np.maximum(similarities, 0)  # Clamp to [0, 1]

    def get_statistics(self) -> Dict:
        """Get search engine statistics"""
        return {
            "total_documents": len(self.documents),
            "avg_doc_length": self.bm25.avg_doc_length,
            "vocabulary_size": len(self.bm25.inverted_index),
            "has_embeddings": self.embeddings is not None
        }

class ReRanker:
    """Re-rank search results using LLM-based relevance scoring

    Instead of just returning top-k from retrieval, re-rank them
    using a more sophisticated relevance metric.
    """

    def __init__(self, llm_service):
        """
        Initialize re-ranker with LLM service

        Args:
            llm_service: LLM service instance (Gemini)
        """
        self.llm = llm_service

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        top_k: int = 5
    ) -> list[SearchResult]:
        """
        Re-rank candidates using LLM

        Args:
            query: Original search query
            candidates: List of SearchResult from hybrid search
            top_k: Number to return after re-ranking

        Returns:
            Re-ranked list of top-k results
        """
        if len(candidates) <= top_k:
            return candidates

        # Create re-ranking prompt
        prompt = self._create_reranking_prompt(query, candidates)

        # Get LLM scores
        try:
            response = self.llm.generate_response(prompt)
            scores = self._extract_relevance_scores(response, len(candidates))
        except Exception as e:
            logger.warning(f"Re-ranking failed: {e}, returning original order")
            return candidates[:top_k]

        # Re-rank
        scored_results = [
            (result, score) for result, score in zip(candidates, scores)
        ]
        scored_results.sort(key=lambda x: x[1], reverse=True)

        return [result for result, _ in scored_results[:top_k]]

    def _create_reranking_prompt(
        self,
        query: str,
        candidates: list[SearchResult]
    ) -> str:
        """Create prompt for re-ranking"""
        prompt = f"""Rate the relevance of each document to the query on a scale of 0-10.

Query: {query}

Documents to rank:
"""
        for i, result in enumerate(candidates):
            prompt += f"\n[{i+1}] {result.text[:200]}..."

        prompt += """

Respond with a JSON list of relevance scores (0-10 for each document, in order):
[score1, score2, score3, ...]"""

        return prompt

    def _extract_relevance_scores(self, response: str, n_docs: int) -> list[float]:
        """Extract relevance scores from LLM response"""
        import json
        import re

        try:
            # Find JSON array in response
            match = re.search(r'\[.*?\]', response, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                # Normalize to [0, 1]
                return [min(s / 10.0, 1.0) for s in scores[:n_docs]]
        except Exception as e:
            logger.warning(f"Could not parse scores: {e}")

        # Fallback: return original order (equal scores)
        return [1.0] * n_docs

# Global instance
_hybrid_engine = None

def get_hybrid_search_engine(
    documents: list[Dict],
    embeddings: Optional[np.ndarray] = None
) -> HybridSearchEngine:
    """Get or create global hybrid search engine"""
    global _hybrid_engine
    if _hybrid_engine is None:
        _hybrid_engine = HybridSearchEngine(documents, embeddings)
    return _hybrid_engine

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test BM25
    corpus = [
        "The quick brown fox jumps over the lazy dog",
        "A fast brown fox is jumping over the dog",
        "The dog is lazy and sleeps all day",
        "The cat and the dog are friends"
    ]

    bm25 = BM25(corpus)
    query = "quick brown fox"
    scores = bm25.score(query)

    print(f"\nBM25 Scores for '{query}':")
    for i, (doc, score) in enumerate(zip(corpus, scores)):
        print(f"  Doc {i}: {score:.3f} - {doc[:50]}...")

    # Test Hybrid Search
    documents = [
        {"id": str(i), "text": doc, "metadata": {"source": f"doc_{i}"}}
        for i, doc in enumerate(corpus)
    ]

    engine = HybridSearchEngine(documents)
    results = engine.search(query, top_k=2)

    print(f"\nHybrid Search Results for '{query}':")
    for result in results:
        print(f"  Rank {result.rank}: {result.combined_score:.3f}")
        print(f"    BM25: {result.bm25_score:.3f}, Vector: {result.vector_score:.3f}")
        print(f"    Text: {result.text[:50]}...")
