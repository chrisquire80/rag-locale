"""
Cross-Encoder Reranking - TASK 5
Uses semantic cross-encoder models to rerank retrieval results for better relevance
Implements semantic-based reranking without requiring additional embedding calls
"""

import logging
import numpy as np
from typing import Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class RankedResult:
    """Result with reranking information"""
    document: str
    source: str
    section: str
    doc_id: str
    original_score: float  # BM25 or vector similarity score
    rerank_score: float  # Cross-encoder relevance score (0-1)
    combined_score: float  # Final combined score
    ranking_position: int  # Final rank after reranking
    confidence: float = 1.0

class CrossEncoderReranker(ABC):
    """Abstract base for cross-encoder reranking"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[Dict]
    ) -> list[RankedResult]:
        """
        Rerank candidates based on query relevance

        Args:
            query: Search query
            candidates: List of candidate documents with scores

        Returns:
            Reranked results with updated scores
        """
        pass

    @abstractmethod
    def get_relevance_score(
        self,
        query: str,
        document: str
    ) -> float:
        """
        Calculate relevance score between query and document (0-1)

        Args:
            query: Search query
            document: Document text

        Returns:
            Relevance score 0.0-1.0
        """
        pass

class GeminiCrossEncoderReranker(CrossEncoderReranker):
    """Cross-encoder reranking using Gemini API"""

    def __init__(self, llm_service, batch_size: int = 10):
        """
        Initialize Gemini-based cross-encoder reranker

        Args:
            llm_service: LLM service instance (Gemini)
            batch_size: Batch size for API calls
        """
        self.llm = llm_service
        self.batch_size = batch_size
        self.cache = {}
        logger.info("Initialized Gemini Cross-Encoder Reranker")

    def rerank(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int = 5,
        alpha: float = 0.3,  # Weight for original score (1-alpha for rerank score)
    ) -> list[RankedResult]:
        """
        Rerank candidates using Gemini semantic relevance

        Args:
            query: Search query
            candidates: List of {document, source, section, doc_id, score}
            top_k: Return top K results
            alpha: Weight for original score in combined score
                   combined = alpha * original + (1-alpha) * rerank

        Returns:
            Reranked results ordered by combined_score
        """
        if not candidates:
            return []

        reranked = []

        # Process in batches
        for i in range(0, len(candidates), self.batch_size):
            batch = candidates[i:i+self.batch_size]

            # Get Gemini relevance scores for batch
            batch_scores = self._score_batch(query, batch)

            for idx, (candidate, relevance_score) in enumerate(zip(batch, batch_scores)):
                # Normalize original score to 0-1 range (assume it's already normalized or between 0-1)
                original_score = float(candidate.get('score', candidate.get('similarity_score', 0.5)))

                # Combined score: weighted average
                combined_score = alpha * original_score + (1.0 - alpha) * relevance_score

                result = RankedResult(
                    document=candidate.get('document', ''),
                    source=candidate.get('source', ''),
                    section=candidate.get('section', ''),
                    doc_id=candidate.get('id', candidate.get('doc_id', '')),
                    original_score=original_score,
                    rerank_score=relevance_score,
                    combined_score=combined_score,
                    ranking_position=0  # Will update after sorting
                )
                reranked.append(result)

        # Sort by combined score (descending)
        reranked.sort(key=lambda x: x.combined_score, reverse=True)

        # Update ranking positions
        for idx, result in enumerate(reranked[:top_k], 1):
            result.ranking_position = idx

        logger.info(f"Reranked {len(candidates)} candidates, returning top {min(top_k, len(reranked))}")

        return reranked[:top_k]

    def _score_batch(self, query: str, candidates: list[Dict]) -> list[float]:
        """
        Score a batch of candidates using Gemini

        Returns:
            List of relevance scores (0-1)
        """
        scores = []

        for candidate in candidates:
            doc_snippet = candidate.get('document', '')[:500]  # First 500 chars
            cache_key = f"{query}||{doc_snippet[:100]}"

            # Check cache
            if cache_key in self.cache:
                scores.append(self.cache[cache_key])
                continue

            score = self.get_relevance_score(query, doc_snippet)
            self.cache[cache_key] = score
            scores.append(score)

        return scores

    def get_relevance_score(
        self,
        query: str,
        document: str
    ) -> float:
        """
        Calculate relevance score using Gemini

        Args:
            query: Search query
            document: Document text

        Returns:
            Relevance score 0.0-1.0
        """
        prompt = f"""Valuta quanto questo documento è rilevante per la query data.

Query: "{query}"

Documento: "{document[:500]}"

Valuta la rilevanza su una scala 0-10 considerando:
- Corrispondenza semantica con la query
- Completezza della risposta
- Pertinenza del contenuto
- Autorevolezza della fonte

Rispondi SOLO con un numero tra 0 e 10, niente altro.
Esempio: "7" oppure "8.5"
"""

        try:
            response = self.llm.completion(
                prompt=prompt,
                max_tokens=5,
                temperature=0.0  # Deterministic scoring
            )

            # Extract score from response
            import re
            match = re.search(r'(\d+\.?\d*)', response.strip())
            if match:
                score = float(match.group(1))
                return min(1.0, max(0.0, score / 10.0))  # Normalize to 0-1
            else:
                return 0.5  # Default fallback
        except Exception as e:
            logger.error(f"Gemini scoring failed: {e}")
            return 0.5

class SemanticRelevanceReranker(CrossEncoderReranker):
    """Lightweight semantic reranking using embedding similarity"""

    def __init__(self, llm_service):
        """
        Initialize embedding-based semantic reranker

        Args:
            llm_service: LLM service with embedding capability
        """
        self.llm = llm_service
        self.cache = {}
        logger.info("Initialized Semantic Relevance Reranker")

    def rerank(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int = 5,
        alpha: float = 0.4,
    ) -> list[RankedResult]:
        """
        Rerank using semantic similarity between query and documents
        """
        if not candidates:
            return []

        try:
            # Get query embedding
            query_embedding = np.array(self.llm.get_embedding(query))

            reranked = []

            for candidate in candidates:
                doc_text = candidate.get('document', '')[:500]

                # Get document embedding
                doc_embedding = np.array(self.llm.get_embedding(doc_text))

                # Cosine similarity
                norm_q = np.linalg.norm(query_embedding)
                norm_d = np.linalg.norm(doc_embedding)

                if norm_q > 0 and norm_d > 0:
                    semantic_score = np.dot(query_embedding, doc_embedding) / (norm_q * norm_d)
                    semantic_score = max(0.0, min(1.0, semantic_score))  # Clamp to 0-1
                else:
                    semantic_score = 0.5

                # Get original score
                original_score = float(candidate.get('score', candidate.get('similarity_score', 0.5)))

                # Combined score
                combined_score = alpha * original_score + (1.0 - alpha) * semantic_score

                result = RankedResult(
                    document=candidate.get('document', ''),
                    source=candidate.get('source', ''),
                    section=candidate.get('section', ''),
                    doc_id=candidate.get('id', candidate.get('doc_id', '')),
                    original_score=original_score,
                    rerank_score=semantic_score,
                    combined_score=combined_score,
                    ranking_position=0
                )
                reranked.append(result)

            # Sort by combined score
            reranked.sort(key=lambda x: x.combined_score, reverse=True)

            # Update positions
            for idx, result in enumerate(reranked[:top_k], 1):
                result.ranking_position = idx

            return reranked[:top_k]

        except Exception as e:
            logger.error(f"Semantic reranking failed: {e}")
            # Fallback: return original order
            return [
                RankedResult(
                    document=c.get('document', ''),
                    source=c.get('source', ''),
                    section=c.get('section', ''),
                    doc_id=c.get('id', c.get('doc_id', '')),
                    original_score=float(c.get('score', 0.5)),
                    rerank_score=0.5,
                    combined_score=float(c.get('score', 0.5)),
                    ranking_position=idx
                )
                for idx, c in enumerate(candidates[:top_k], 1)
            ]

    def get_relevance_score(self, query: str, document: str) -> float:
        """Calculate semantic relevance using embeddings"""
        try:
            query_emb = np.array(self.llm.get_embedding(query))
            doc_emb = np.array(self.llm.get_embedding(document[:500]))

            norm_q = np.linalg.norm(query_emb)
            norm_d = np.linalg.norm(doc_emb)

            if norm_q > 0 and norm_d > 0:
                score = np.dot(query_emb, doc_emb) / (norm_q * norm_d)
                return max(0.0, min(1.0, score))
            return 0.5
        except Exception as e:
            logger.error(f"Embedding-based scoring failed: {e}")
            return 0.5

class HybridReranker:
    """Combines multiple reranking strategies"""

    def __init__(
        self,
        llm_service,
        use_gemini: bool = True,
        use_semantic: bool = True,
        gemini_weight: float = 0.6,
        semantic_weight: float = 0.4
    ):
        """
        Initialize hybrid reranker combining multiple methods

        Args:
            llm_service: LLM service
            use_gemini: Use Gemini cross-encoder
            use_semantic: Use semantic similarity reranking
            gemini_weight: Weight for Gemini scores
            semantic_weight: Weight for semantic scores
        """
        self.gemini_reranker = GeminiCrossEncoderReranker(llm_service) if use_gemini else None
        self.semantic_reranker = SemanticRelevanceReranker(llm_service) if use_semantic else None
        self.gemini_weight = gemini_weight
        self.semantic_weight = semantic_weight
        logger.info("Initialized Hybrid Reranker")

    def rerank(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int = 5
    ) -> list[RankedResult]:
        """
        Rerank using hybrid strategy combining multiple methods
        """
        if not candidates:
            return []

        # Get scores from each reranker
        combined_scores = {}

        if self.semantic_reranker:
            semantic_results = self.semantic_reranker.rerank(query, candidates, top_k=len(candidates), alpha=0.5)
            for result in semantic_results:
                combined_scores[result.doc_id] = self.semantic_weight * result.combined_score

        if self.gemini_reranker:
            gemini_results = self.gemini_reranker.rerank(query, candidates, top_k=len(candidates), alpha=0.5)
            for result in gemini_results:
                if result.doc_id not in combined_scores:
                    combined_scores[result.doc_id] = 0.0
                combined_scores[result.doc_id] += self.gemini_weight * result.combined_score

        # Sort by combined score
        ranked_results = []
        for idx, candidate in enumerate(candidates):
            doc_id = candidate.get('id', candidate.get('doc_id', f'doc_{idx}'))
            final_score = combined_scores.get(doc_id, 0.5)

            result = RankedResult(
                document=candidate.get('document', ''),
                source=candidate.get('source', ''),
                section=candidate.get('section', ''),
                doc_id=doc_id,
                original_score=float(candidate.get('score', 0.5)),
                rerank_score=final_score,
                combined_score=final_score,
                ranking_position=0
            )
            ranked_results.append(result)

        ranked_results.sort(key=lambda x: x.combined_score, reverse=True)

        for idx, result in enumerate(ranked_results[:top_k], 1):
            result.ranking_position = idx

        return ranked_results[:top_k]

def get_gemini_reranker(llm_service) -> GeminiCrossEncoderReranker:
    """Get or create global Gemini reranker"""
    if not hasattr(get_gemini_reranker, '_instance'):
        get_gemini_reranker._instance = GeminiCrossEncoderReranker(llm_service)
    return get_gemini_reranker._instance

def get_semantic_reranker(llm_service) -> SemanticRelevanceReranker:
    """Get or create global semantic reranker"""
    if not hasattr(get_semantic_reranker, '_instance'):
        get_semantic_reranker._instance = SemanticRelevanceReranker(llm_service)
    return get_semantic_reranker._instance

def get_hybrid_reranker(llm_service) -> HybridReranker:
    """Get or create global hybrid reranker"""
    if not hasattr(get_hybrid_reranker, '_instance'):
        get_hybrid_reranker._instance = HybridReranker(llm_service)
    return get_hybrid_reranker._instance

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Cross-Encoder Reranking Examples:")
    print("\n1. Gemini-based semantic relevance scoring")
    print("   - Uses Gemini API to score document relevance")
    print("   - Combines with original search score")
    print("   - Reranks top results for better quality")

    print("\n2. Embedding-based semantic reranking")
    print("   - Uses embeddings for semantic similarity")
    print("   - Faster than Gemini (no API call per doc)")
    print("   - Good for large result sets")

    print("\n3. Hybrid reranking")
    print("   - Combines Gemini + semantic methods")
    print("   - Weighted scoring for flexibility")
    print("   - Best accuracy for production use")
