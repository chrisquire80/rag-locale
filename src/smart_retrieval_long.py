"""
Smart Retrieval for Long Context - FASE 18
Intelligent retrieval optimization for 1M token context window
Selects and orders documents for maximum relevance within token budget
"""

import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RetrievalStrategy(Enum):
    """Strategies for document retrieval and ordering"""
    RELEVANCE_FIRST = "relevance"    # Highest relevance first
    SIZE_FIRST = "size"              # Smallest docs first (fit more)
    DIVERSITY_FIRST = "diversity"    # Mix of topics for comprehensive view
    HYBRID = "hybrid"                # Combination of above

@dataclass
class RetrievalResult:
    """Result of document retrieval"""
    selected_documents: list[Dict]
    total_tokens: int
    relevance_scores: dict[str, float]
    retrieval_strategy: RetrievalStrategy
    coverage_percent: float          # % of available context used
    diversity_score: float           # 0-1, higher = more diverse topics

class SmartRetrieverLong:
    """Smart retrieval for long context windows"""

    def __init__(self, max_tokens: int = 900_000):
        """
        Initialize smart retriever

        Args:
            max_tokens: Maximum tokens for retrieval
        """
        self.max_tokens = max_tokens
        logger.info(f"✓ SmartRetrieverLong initialized ({max_tokens:,} token budget)")

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens in text"""
        words = len(text.split())
        return max(1, int(words * 1.3))

    def retrieve(self,
                documents: list[Dict],
                query: str,
                strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
                relevance_scores: Optional[dict[str, float]] = None,
                min_documents: int = 1) -> RetrievalResult:
        """
        Retrieve documents optimized for long context

        Args:
            documents: Available documents
            query: User query for context
            strategy: Retrieval strategy
            relevance_scores: Pre-computed relevance scores for documents
            min_documents: Minimum documents to retrieve

        Returns:
            RetrievalResult with selected documents
        """
        if not documents:
            return RetrievalResult(
                selected_documents=[],
                total_tokens=0,
                relevance_scores={},
                retrieval_strategy=strategy,
                coverage_percent=0.0,
                diversity_score=0.0
            )

        # Default relevance scores
        if relevance_scores is None:
            relevance_scores = {doc.get('id', i): 0.5 for i, doc in enumerate(documents)}

        # Apply strategy
        if strategy == RetrievalStrategy.RELEVANCE_FIRST:
            selected = self._retrieve_by_relevance(documents, relevance_scores, min_documents)
        elif strategy == RetrievalStrategy.SIZE_FIRST:
            selected = self._retrieve_by_size(documents, relevance_scores, min_documents)
        elif strategy == RetrievalStrategy.DIVERSITY_FIRST:
            selected = self._retrieve_by_diversity(documents, relevance_scores, min_documents)
        else:  # HYBRID
            selected = self._retrieve_hybrid(documents, relevance_scores, min_documents)

        # Calculate metrics
        total_tokens = sum(self.estimate_tokens(doc['text']) for doc in selected)
        coverage = (total_tokens / self.max_tokens * 100) if self.max_tokens > 0 else 0
        diversity = self._calculate_diversity(selected)

        result = RetrievalResult(
            selected_documents=selected,
            total_tokens=total_tokens,
            relevance_scores={doc.get('id'): relevance_scores.get(doc.get('id'), 0)
                             for doc in selected},
            retrieval_strategy=strategy,
            coverage_percent=coverage,
            diversity_score=diversity
        )

        logger.info(f"Retrieved {len(selected)} documents using {strategy.value} strategy: "
                   f"{total_tokens:,} tokens ({coverage:.1f}% coverage)")

        return result

    def _retrieve_by_relevance(self,
                               documents: list[Dict],
                               relevance_scores: dict[str, float],
                               min_documents: int) -> list[Dict]:
        """
        Retrieve highest-relevance documents within token budget

        Args:
            documents: Available documents
            relevance_scores: Relevance scores
            min_documents: Minimum to retrieve

        Returns:
            Selected documents, ordered by relevance
        """
        # Score and sort documents
        scored = [
            (doc, relevance_scores.get(doc.get('id'), 0.0))
            for doc in documents
        ]
        scored.sort(key=lambda x: -x[1])  # Descending relevance

        # Select documents within budget
        selected = []
        current_tokens = 0

        for doc, score in scored:
            tokens = self.estimate_tokens(doc['text'])

            if current_tokens + tokens > self.max_tokens and len(selected) >= min_documents:
                break

            selected.append(doc)
            current_tokens += tokens

        return selected

    def _retrieve_by_size(self,
                         documents: list[Dict],
                         relevance_scores: dict[str, float],
                         min_documents: int) -> list[Dict]:
        """
        Retrieve smallest documents first (fit more content)

        Args:
            documents: Available documents
            relevance_scores: Relevance scores (used as tiebreaker)
            min_documents: Minimum to retrieve

        Returns:
            Selected documents, ordered by size (smallest first)
        """
        # Score by size, then relevance as tiebreaker
        scored = [
            (doc, self.estimate_tokens(doc['text']),
             relevance_scores.get(doc.get('id'), 0.0))
            for doc in documents
        ]

        # Sort by size ascending, relevance descending as tiebreaker
        scored.sort(key=lambda x: (x[1], -x[2]))

        selected = []
        current_tokens = 0

        for doc, tokens, score in scored:
            if current_tokens + tokens > self.max_tokens and len(selected) >= min_documents:
                break

            selected.append(doc)
            current_tokens += tokens

        # Re-order selected by relevance
        selected.sort(key=lambda d: -relevance_scores.get(d.get('id'), 0.0))

        return selected

    def _retrieve_by_diversity(self,
                              documents: list[Dict],
                              relevance_scores: dict[str, float],
                              min_documents: int) -> list[Dict]:
        """
        Retrieve diverse documents across topics

        Args:
            documents: Available documents
            relevance_scores: Relevance scores
            min_documents: Minimum to retrieve

        Returns:
            Selected documents with diverse topics
        """
        if not documents:
            return []

        selected = []
        current_tokens = 0
        used_sources = set()

        # Sort by relevance
        scored = sorted(
            [(doc, relevance_scores.get(doc.get('id'), 0.0)) for doc in documents],
            key=lambda x: -x[1]
        )

        # Select diverse documents
        for doc, score in scored:
            tokens = self.estimate_tokens(doc['text'])

            # Check if source already represented
            source = doc.get('metadata', {}).get('source', 'unknown')
            if source in used_sources and len(selected) >= min_documents * 2:
                continue

            if current_tokens + tokens > self.max_tokens and len(selected) >= min_documents:
                break

            selected.append(doc)
            current_tokens += tokens
            used_sources.add(source)

        return selected

    def _retrieve_hybrid(self,
                        documents: list[Dict],
                        relevance_scores: dict[str, float],
                        min_documents: int) -> list[Dict]:
        """
        Hybrid retrieval: balance relevance, size, and diversity

        Args:
            documents: Available documents
            relevance_scores: Relevance scores
            min_documents: Minimum to retrieve

        Returns:
            Selected documents
        """
        if not documents:
            return []

        # Score documents with hybrid formula
        # hybrid_score = 0.5 * relevance + 0.3 * (1 - size_normalized) + 0.2 * diversity_bonus

        # Normalize sizes
        sizes = [self.estimate_tokens(doc['text']) for doc in documents]
        max_size = max(sizes) if sizes else 1
        min_size = min(sizes) if sizes else 1
        size_range = max_size - min_size if max_size > min_size else 1

        selected = []
        current_tokens = 0
        used_sources = set()

        # Calculate hybrid scores
        scored = []
        for doc in documents:
            doc_id = doc.get('id')
            relevance = relevance_scores.get(doc_id, 0.5)
            size = self.estimate_tokens(doc['text'])
            size_normalized = (size - min_size) / size_range if size_range > 0 else 0
            source = doc.get('metadata', {}).get('source', 'unknown')

            # Diversity bonus (negative if source already used)
            diversity_bonus = 0.2 if source not in used_sources else -0.1

            hybrid_score = (0.5 * relevance +
                           0.3 * (1 - size_normalized) +
                           0.2 * (0.5 + diversity_bonus))

            scored.append((doc, hybrid_score, source))

        # Sort by hybrid score
        scored.sort(key=lambda x: -x[1])

        # Select documents
        for doc, score, source in scored:
            tokens = self.estimate_tokens(doc['text'])

            if current_tokens + tokens > self.max_tokens and len(selected) >= min_documents:
                break

            selected.append(doc)
            current_tokens += tokens
            used_sources.add(source)

        return selected

    def _calculate_diversity(self, documents: list[Dict]) -> float:
        """
        Calculate diversity score for document set (0-1)

        Args:
            documents: Selected documents

        Returns:
            Diversity score
        """
        if len(documents) <= 1:
            return 0.0

        sources = set()
        topics = set()

        for doc in documents:
            meta = doc.get('metadata', {})
            sources.add(meta.get('source', 'unknown'))
            if 'topic' in meta:
                topics.add(meta['topic'])

        # Diversity = unique sources / total documents
        source_diversity = len(sources) / len(documents) if documents else 0
        topic_diversity = len(topics) / len(documents) if documents and topics else 0

        # Average of both metrics
        diversity = (source_diversity + topic_diversity) / 2
        return min(diversity, 1.0)

    def reorder_for_context(self,
                           documents: list[Dict],
                           query: str,
                           order_by: str = "relevance") -> list[Dict]:
        """
        Reorder documents for optimal reading in context

        Strategies:
        - relevance: Most relevant first (good for QA)
        - source: Grouped by source (good for comprehension)
        - size: Largest to smallest (natural flow)
        - chronological: By date (good for historical context)

        Args:
            documents: Documents to reorder
            query: User query for relevance context
            order_by: Ordering strategy

        Returns:
            Reordered documents
        """
        if order_by == "source":
            return sorted(documents, key=lambda d: d.get('metadata', {}).get('source', ''))
        elif order_by == "size":
            return sorted(documents, key=lambda d: -self.estimate_tokens(d['text']))
        elif order_by == "chronological":
            return sorted(documents,
                         key=lambda d: d.get('metadata', {}).get('date', ''),
                         reverse=True)
        else:  # relevance
            # Use a simple keyword overlap for relevance scoring
            query_words = set(query.lower().split())
            scored = []
            for doc in documents:
                doc_text = (doc['text'] + ' ' +
                           str(doc.get('metadata', {}))).lower()
                overlap = len([w for w in query_words if w in doc_text])
                scored.append((doc, overlap))
            return [doc for doc, _ in sorted(scored, key=lambda x: -x[1])]

def get_smart_retriever() -> SmartRetrieverLong:
    """Get singleton smart retriever instance"""
    if not hasattr(get_smart_retriever, '_instance'):
        get_smart_retriever._instance = SmartRetrieverLong()
    return get_smart_retriever._instance
