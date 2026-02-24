"""
Context Window Manager - FASE 18
Manages 1M token context window allocation for Gemini 2.0 Flash
"""

import logging
from typing import Optional
from dataclasses import dataclass
import re

logger = logging.getLogger(__name__)

@dataclass
class TokenAllocation:
    """Token allocation strategy"""
    document_id: str
    compression_level: int  # 0=full, 1=detailed (20%), 2=executive (5%), 3=metadata
    estimated_tokens: int
    relevance_score: float

class ContextWindowManager:
    """Manage allocation of 1M token context window"""

    def __init__(self, max_tokens: int = 1_000_000):
        """
        Initialize context window manager

        Args:
            max_tokens: Maximum tokens available (default: 1M for Gemini 2.0 Flash)
        """
        self.max_tokens = max_tokens
        self.system_prompt_tokens = 500  # Estimated system prompt size
        self.user_query_tokens = 200     # Estimated query size
        self.safety_buffer_percent = 0.10  # 10% safety buffer

        # Available tokens after system overhead
        self.available_tokens = max_tokens - self.system_prompt_tokens - self.user_query_tokens

        # Current usage tracking
        self.current_tokens = 0
        self.allocated_documents = []

        logger.info(f"✓ ContextWindowManager initialized with {max_tokens:,} token capacity")
        logger.info(f"  Available for context: {self.available_tokens:,} tokens")

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count from text (without API call)

        Approximation: ~1.3 tokens per word for English text
        More accurate than character count, fast enough for planning

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Count words
        words = len(text.split())

        # Estimate tokens (1.3 tokens per word average)
        estimated = int(words * 1.3)

        return max(estimated, 1)  # At least 1 token

    def allocate_context(
        self,
        documents: list[Dict],
        query: str,
        relevance_scores: Optional[dict[str, float]] = None
    ) -> Dict:
        """
        Intelligently allocate context tokens across documents

        Strategy:
        1. Score documents by relevance to query
        2. Full text for high-relevance docs (>0.7)
        3. Summary for medium-relevance (0.3-0.7)
        4. Metadata only for low-relevance (<0.3)
        5. Stop adding when approaching safety buffer

        Args:
            documents: List of documents to allocate
            query: User query for relevance calculation
            relevance_scores: Pre-computed relevance scores (optional)

        Returns:
            Allocation plan with compression levels
        """
        logger.info(f"Allocating context for {len(documents)} documents")

        allocations = []
        total_allocated = 0
        safety_limit = self.available_tokens * (1 - self.safety_buffer_percent)

        for doc in documents:
            doc_id = doc.get('id', doc.get('source', 'unknown'))

            # Get relevance score
            if relevance_scores and doc_id in relevance_scores:
                relevance = relevance_scores[doc_id]
            else:
                # Default: assume medium relevance if not provided
                relevance = 0.5

            # Determine compression level based on relevance
            if relevance > 0.7:
                compression_level = 0  # Full text
                text = doc.get('content', '')
            elif relevance > 0.4:
                compression_level = 1  # Detailed summary (~20% of original)
                text = self._get_summary_level_1(doc)
            elif relevance > 0.2:
                compression_level = 2  # Executive summary (~5% of original)
                text = self._get_summary_level_2(doc)
            else:
                compression_level = 3  # Metadata only (~1% of original)
                text = self._get_metadata(doc)

            # Estimate tokens for this compression level
            token_count = self.estimate_tokens(text)

            # Check if we can fit this document
            if total_allocated + token_count <= safety_limit:
                allocations.append(TokenAllocation(
                    document_id=doc_id,
                    compression_level=compression_level,
                    estimated_tokens=token_count,
                    relevance_score=relevance
                ))
                total_allocated += token_count
            else:
                logger.debug(f"Document {doc_id} would exceed token limit")
                break

        logger.info(f"Allocated {len(allocations)} documents")
        logger.info(f"Total tokens used: {total_allocated:,} / {self.available_tokens:,}")

        return {
            'allocations': allocations,
            'total_tokens': total_allocated,
            'document_count': len(allocations),
            'utilization_percent': (total_allocated / self.available_tokens) * 100,
            'documents_excluded': len(documents) - len(allocations)
        }

    def _get_summary_level_1(self, doc: Dict) -> str:
        """Get detailed summary (~20% of original)"""
        content = doc.get('content', '')
        # Simple heuristic: take first 20% + last 5% (intro + conclusion)
        words = content.split()
        cutoff = max(len(words) // 5, 100)
        summary = ' '.join(words[:cutoff])
        if len(words) > cutoff:
            summary += '\n\n[...middle section omitted...]\n\n'
            summary += ' '.join(words[-50:])
        return summary

    def _get_summary_level_2(self, doc: Dict) -> str:
        """Get executive summary (~5% of original)"""
        content = doc.get('content', '')
        words = content.split()
        # Take first 5%
        cutoff = max(len(words) // 20, 20)
        return ' '.join(words[:cutoff])

    def _get_metadata(self, doc: Dict) -> str:
        """Get metadata only (~1% of original)"""
        return f"""
Document: {doc.get('source', 'unknown')}
Type: {doc.get('type', 'text')}
Size: {len(doc.get('content', '').split())} words
Topics: {doc.get('topics', 'unknown')}
"""

    def optimize_allocation(self, allocation_plan: Dict) -> Dict:
        """
        Further optimize allocation by removing redundancy

        Args:
            allocation_plan: Output from allocate_context()

        Returns:
            Optimized allocation plan
        """
        logger.info("Optimizing token allocation")

        allocations = allocation_plan['allocations']

        # Could add deduplication, information consolidation, etc.
        # For now, just return the plan as-is

        return allocation_plan

    def get_utilization(self) -> Dict:
        """
        Get current context window utilization

        Returns:
            Dictionary with utilization metrics
        """
        return {
            'total_capacity': self.max_tokens,
            'system_overhead': self.system_prompt_tokens,
            'query_overhead': self.user_query_tokens,
            'available_for_context': self.available_tokens,
            'used_tokens': self.current_tokens,
            'remaining_tokens': self.available_tokens - self.current_tokens,
            'utilization_percent': (self.current_tokens / self.available_tokens) * 100,
            'safety_buffer_percent': self.safety_buffer_percent * 100
        }

    def can_fit_tokens(self, token_count: int) -> bool:
        """Check if token count fits in remaining capacity"""
        remaining = self.available_tokens - self.current_tokens
        safety_threshold = remaining * (1 - self.safety_buffer_percent)
        return token_count <= safety_threshold

    def add_tokens(self, token_count: int, document_id: str) -> bool:
        """
        Add tokens to current usage

        Args:
            token_count: Number of tokens to add
            document_id: Document identifier

        Returns:
            True if successful, False if would exceed limit
        """
        if self.can_fit_tokens(token_count):
            self.current_tokens += token_count
            self.allocated_documents.append(document_id)
            return True
        else:
            logger.warning(f"Cannot add {token_count} tokens - would exceed limit")
            return False

    def reset(self):
        """Reset usage tracking"""
        self.current_tokens = 0
        self.allocated_documents = []

def get_context_window_manager() -> ContextWindowManager:
    """Get singleton context window manager"""
    if not hasattr(get_context_window_manager, '_instance'):
        get_context_window_manager._instance = ContextWindowManager()
    return get_context_window_manager._instance
