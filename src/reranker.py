"""
Advanced Re-ranker using Gemini 2.0 Flash
Evaluates and re-ranks search results based on relevance to query
"""

import logging
import json
import re
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import time

logger = logging.getLogger(__name__)

@dataclass
class RankedResult:
    """Re-ranked search result with confidence"""
    rank: int
    doc_id: str
    text: str
    metadata: Dict
    relevance_score: float  # 0-1
    reasoning: str
    retrieval_score: float  # Original BM25/Vector score

class GeminiReRanker:
    """Re-rank documents using Gemini's understanding of context and relevance

    This uses Gemini 2.0 Flash's 1M+ token context window to analyze
    relevance more thoroughly than simple vector similarity.
    """

    def __init__(self, llm_service, batch_size: int = 5):
        """
        Initialize re-ranker

        Args:
            llm_service: LLM service instance (Gemini)
            batch_size: Process results in batches (default 5)
        """
        self.llm = llm_service
        self.batch_size = batch_size
        self.rerank_history = []

        logger.info(f"Initialized Gemini Re-Ranker (batch_size={batch_size})")

    def rerank_results(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int = 5,
        use_batching: bool = True
    ) -> list[RankedResult]:
        """
        Re-rank search results using Gemini

        Args:
            query: Search query
            candidates: List of candidate docs with id, text, score, metadata
            top_k: Return top-k results
            use_batching: Use batch processing for efficiency

        Returns:
            Sorted list of RankedResult
        """
        if len(candidates) <= top_k:
            return self._candidates_to_ranked(candidates)

        start_time = time.time()

        if use_batching and len(candidates) > self.batch_size:
            results = self._rerank_batched(query, candidates, top_k)
        else:
            results = self._rerank_direct(query, candidates, top_k)

        elapsed = time.time() - start_time
        logger.info(f"Re-ranked {len(candidates)} docs to {len(results)} in {elapsed:.2f}s")

        # Record in history
        self.rerank_history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "input_count": len(candidates),
            "output_count": len(results),
            "elapsed_seconds": elapsed
        })

        return results

    def _rerank_direct(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int
    ) -> list[RankedResult]:
        """Direct re-ranking of all candidates"""
        prompt = self._create_rerank_prompt(query, candidates)

        try:
            response = self.llm.generate_response(prompt)
            scores, reasonings = self._parse_gemini_response(response, len(candidates))
        except Exception as e:
            logger.error(f"Gemini re-ranking failed: {e}")
            return self._candidates_to_ranked(candidates)[:top_k]

        # Combine with original scores
        ranked = []
        for i, (candidate, score, reasoning) in enumerate(zip(candidates, scores, reasonings)):
            ranked.append(RankedResult(
                rank=i + 1,
                doc_id=candidate.get('id', f'doc_{i}'),
                text=candidate['text'],
                metadata=candidate.get('metadata', {}),
                relevance_score=score,
                reasoning=reasoning,
                retrieval_score=candidate.get('combined_score', 0)
            ))

        # Re-rank by relevance
        ranked.sort(key=lambda x: x.relevance_score, reverse=True)
        for i, result in enumerate(ranked):
            result.rank = i + 1

        return ranked[:top_k]

    def _rerank_batched(
        self,
        query: str,
        candidates: list[Dict],
        top_k: int
    ) -> list[RankedResult]:
        """Batch re-ranking for large candidate sets"""
        ranked_results = []

        # First pass: score all in batches
        for batch_start in range(0, len(candidates), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(candidates))
            batch = candidates[batch_start:batch_end]

            prompt = self._create_rerank_prompt(query, batch)

            try:
                response = self.llm.generate_response(prompt)
                scores, reasonings = self._parse_gemini_response(response, len(batch))
            except Exception as e:
                logger.warning(f"Batch re-ranking failed: {e}, skipping batch")
                continue

            for i, (candidate, score, reasoning) in enumerate(zip(batch, scores, reasonings)):
                ranked_results.append(RankedResult(
                    rank=batch_start + i + 1,
                    doc_id=candidate.get('id', f'doc_{batch_start + i}'),
                    text=candidate['text'],
                    metadata=candidate.get('metadata', {}),
                    relevance_score=score,
                    reasoning=reasoning,
                    retrieval_score=candidate.get('combined_score', 0)
                ))

        # Second pass: re-rank all results
        ranked_results.sort(key=lambda x: x.relevance_score, reverse=True)
        for i, result in enumerate(ranked_results):
            result.rank = i + 1

        return ranked_results[:top_k]

    def _create_rerank_prompt(self, query: str, candidates: list[Dict]) -> str:
        """Create prompt for Gemini to evaluate relevance"""
        prompt = f"""You are an expert document relevance evaluator.

Query: "{query}"

Evaluate how relevant each document is to this query.
Consider:
1. Direct relevance (does it answer the query?)
2. Information quality (is it accurate and complete?)
3. Context match (is the domain/context appropriate?)

Rate each on a scale of 0-10, where:
- 10: Highly relevant, directly answers the query
- 7-9: Very relevant, addresses the query with good information
- 4-6: Somewhat relevant, may contain useful information
- 1-3: Slightly relevant or partially related
- 0: Not relevant

Documents:
"""
        for i, candidate in enumerate(candidates):
            doc_text = candidate['text']
            if len(doc_text) > 300:
                doc_text = doc_text[:300] + "..."

            prompt += f"\n[Doc {i+1}]\n{doc_text}\n"

        prompt += """
Respond in this exact JSON format:
{
    "evaluations": [
        {"doc_num": 1, "score": 9, "reason": "Directly answers the query..."},
        {"doc_num": 2, "score": 6, "reason": "Partially relevant..."}
    ]
}

Only return the JSON, no other text."""

        return prompt

    def _parse_gemini_response(
        self,
        response: str,
        expected_count: int
    ) -> tuple[list[float], list[str]]:
        """Parse Gemini response to extract scores and reasoning"""
        scores = []
        reasonings = []

        try:
            # Extract JSON from response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError("No JSON found in response")

            data = json.loads(match.group())

            # Parse evaluations
            for eval_item in data.get('evaluations', []):
                score = eval_item.get('score', 5) / 10.0  # Normalize to [0, 1]
                reason = eval_item.get('reason', 'No reason provided')
                scores.append(min(score, 1.0))
                reasonings.append(reason)

            # Pad if needed
            while len(scores) < expected_count:
                scores.append(0.5)
                reasonings.append("Unable to evaluate")

            return scores[:expected_count], reasonings[:expected_count]

        except Exception as e:
            logger.warning(f"Failed to parse Gemini response: {e}")
            return [0.5] * expected_count, ["Parse error"] * expected_count

    def _candidates_to_ranked(self, candidates: list[Dict]) -> list[RankedResult]:
        """Convert candidates to RankedResult preserving original order"""
        results = []
        for i, candidate in enumerate(candidates):
            results.append(RankedResult(
                rank=i + 1,
                doc_id=candidate.get('id', f'doc_{i}'),
                text=candidate['text'],
                metadata=candidate.get('metadata', {}),
                relevance_score=candidate.get('combined_score', 0),
                reasoning="Original retrieval score",
                retrieval_score=candidate.get('combined_score', 0)
            ))
        return results

    def get_statistics(self) -> Dict:
        """Get re-ranker statistics"""
        if not self.rerank_history:
            return {"reranks_performed": 0}

        total_elapsed = sum(h['elapsed_seconds'] for h in self.rerank_history)
        avg_elapsed = total_elapsed / len(self.rerank_history)

        return {
            "reranks_performed": len(self.rerank_history),
            "total_documents_reranked": sum(h['input_count'] for h in self.rerank_history),
            "avg_time_per_rerank": avg_elapsed,
            "total_time": total_elapsed
        }

class ParentDocumentRetriever:
    """Retrieves parent documents when a chunk is found

    When a small chunk matches the query, this returns the
    full paragraph or page for better context.
    """

    def __init__(self, documents: list[Dict], chunk_size: int = 200):
        """
        Initialize parent document retriever

        Args:
            documents: Full documents with text and chunks
            chunk_size: Size of chunks (for splitting context)
        """
        self.documents = documents
        self.chunk_size = chunk_size
        logger.info(f"Initialized Parent Document Retriever")

    def get_parent_document(
        self,
        doc_id: str,
        chunk_text: str,
        context_words: int = 150
    ) -> Dict:
        """
        Get parent document/paragraph containing the chunk

        Args:
            doc_id: Document ID
            chunk_text: The chunk that matched
            context_words: Words of context to add before/after

        Returns:
            Dict with full text and metadata
        """
        # Find document
        doc = next((d for d in self.documents if d.get('id') == doc_id), None)
        if not doc:
            return {"text": chunk_text, "type": "chunk_only"}

        full_text = doc.get('text', '')

        # Find chunk position
        chunk_pos = full_text.find(chunk_text)
        if chunk_pos == -1:
            return {"text": chunk_text, "type": "chunk_only"}

        # Extract context
        start = max(0, chunk_pos - context_words * 5)  # ~5 chars per word
        end = min(len(full_text), chunk_pos + len(chunk_text) + context_words * 5)

        parent_text = full_text[start:end]

        return {
            "text": parent_text,
            "type": "parent_document",
            "original_chunk": chunk_text,
            "context_words": context_words,
            "metadata": doc.get('metadata', {})
        }

# Global instances
_reranker = None
_parent_retriever = None

def get_reranker(llm_service) -> GeminiReRanker:
    """Get or create global re-ranker"""
    global _reranker
    if _reranker is None:
        _reranker = GeminiReRanker(llm_service)
    return _reranker

def get_parent_retriever(documents: list[Dict]) -> ParentDocumentRetriever:
    """Get or create global parent document retriever"""
    global _parent_retriever
    if _parent_retriever is None:
        _parent_retriever = ParentDocumentRetriever(documents)
    return _parent_retriever

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test example
    print("Parent Document Retriever Test:")
    docs = [
        {
            "id": "doc1",
            "text": "The quick brown fox jumps over the lazy dog. This is an important fact.",
            "metadata": {"source": "test"}
        }
    ]

    retriever = ParentDocumentRetriever(docs)
    parent = retriever.get_parent_document("doc1", "brown fox jumps", context_words=20)
    print(f"Parent: {parent['text']}")
    print(f"Type: {parent['type']}")
