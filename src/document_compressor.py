"""
Document Compressor - FASE 18
Multi-level compression engine for fitting documents in 1M token context
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.logging_config import get_logger

logger = get_logger(__name__)

class CompressionLevel(Enum):
    """Compression level enum"""
    FULL = 0              # Full text (100%)
    DETAILED = 1          # Detailed summary (20% of original)
    EXECUTIVE = 2         # Executive summary (5% of original)
    METADATA_ONLY = 3     # Metadata only (<1%)

@dataclass
class CompressedDocument:
    """Compressed document representation"""
    document_id: str
    original_text: str
    compression_level: CompressionLevel
    compressed_text: str
    metadata: Dict
    original_token_count: int
    compressed_token_count: int

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio"""
        if self.original_token_count == 0:
            return 0.0
        return self.compressed_token_count / self.original_token_count

@dataclass
class SummaryConfig:
    """Configuration for summarization strategy"""
    preserve_percentages = {
        CompressionLevel.FULL: 1.0,
        CompressionLevel.DETAILED: 0.2,
        CompressionLevel.EXECUTIVE: 0.05,
        CompressionLevel.METADATA_ONLY: 0.0,
    }

    # Sentences to preserve per level
    sentences_by_level = {
        CompressionLevel.FULL: 1000,           # Keep all
        CompressionLevel.DETAILED: 50,         # ~20% sentences
        CompressionLevel.EXECUTIVE: 10,        # ~5% sentences
        CompressionLevel.METADATA_ONLY: 0,     # None
    }

class DocumentCompressor:
    """Compress documents for fitting in context window"""

    def __init__(self, config: Optional[SummaryConfig] = None):
        """
        Initialize document compressor

        Args:
            config: Summarization configuration
        """
        self.config = config or SummaryConfig()
        logger.info("✓ DocumentCompressor initialized")

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens in text (~1.3 tokens per word)

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        words = len(text.split())
        return max(1, int(words * 1.3))

    def compress(self,
                 document_id: str,
                 text: str,
                 level: CompressionLevel,
                 metadata: Optional[Dict] = None) -> CompressedDocument:
        """
        Compress document to specified level

        Args:
            document_id: Document identifier
            text: Full document text
            level: Desired compression level
            metadata: Document metadata

        Returns:
            CompressedDocument with compression details
        """
        metadata = metadata or {}
        original_tokens = self.estimate_tokens(text)

        if level == CompressionLevel.FULL:
            compressed_text = text
        elif level == CompressionLevel.DETAILED:
            compressed_text = self._summarize_detailed(text)
        elif level == CompressionLevel.EXECUTIVE:
            compressed_text = self._summarize_executive(text)
        elif level == CompressionLevel.METADATA_ONLY:
            compressed_text = self._extract_metadata_only(text, metadata)
        else:
            compressed_text = text

        compressed_tokens = self.estimate_tokens(compressed_text)

        result = CompressedDocument(
            document_id=document_id,
            original_text=text,
            compression_level=level,
            compressed_text=compressed_text,
            metadata=metadata,
            original_token_count=original_tokens,
            compressed_token_count=compressed_tokens
        )

        logger.debug(f"Compressed {document_id}: {original_tokens} → {compressed_tokens} tokens "
                    f"({result.compression_ratio:.1%})")

        return result

    def _summarize_detailed(self, text: str) -> str:
        """
        Create detailed summary (~20% of original)

        Preserves:
        - First paragraph (introduction)
        - Key facts and numbers
        - Section headers
        - Important sentences
        """
        sentences = self._extract_sentences(text)

        # Keep ~20% of sentences
        target_count = max(5, int(len(sentences) * 0.2))

        # Score sentences by importance
        scored = self._score_sentences(sentences, text)

        # Select top-scoring sentences
        selected = sorted(scored[:target_count], key=lambda x: x[1])  # Keep original order
        selected_text = ' '.join([s[0] for s in selected])

        return selected_text

    def _summarize_executive(self, text: str) -> str:
        """
        Create executive summary (~5% of original)

        Preserves:
        - First sentence
        - Main topic
        - Key figures/findings
        - Conclusion
        """
        sentences = self._extract_sentences(text)

        # Keep ~5% of sentences (minimum 2)
        target_count = max(2, int(len(sentences) * 0.05))

        # Score sentences by importance
        scored = self._score_sentences(sentences, text)

        # Select most important sentences
        selected = sorted(scored[:target_count], key=lambda x: x[1])
        selected_text = ' '.join([s[0] for s in selected])

        return selected_text

    def _extract_metadata_only(self, text: str, metadata: Dict) -> str:
        """
        Extract metadata-only representation

        Returns minimal text representation with metadata
        """
        # Extract key information
        lines = text.strip().split('\n')
        first_line = lines[0] if lines else "Document"

        # Build metadata summary
        meta_parts = [first_line]

        if metadata:
            if 'source' in metadata:
                meta_parts.append(f"Source: {metadata['source']}")
            if 'page' in metadata:
                meta_parts.append(f"Pages: {metadata.get('page_count', '?')}")
            if 'date' in metadata:
                meta_parts.append(f"Date: {metadata['date']}")
            if 'keywords' in metadata:
                keywords = metadata['keywords']
                if isinstance(keywords, list):
                    meta_parts.append(f"Topics: {', '.join(keywords)}")

        return ' | '.join(meta_parts)

    def _extract_sentences(self, text: str) -> list[str]:
        """
        Extract sentences from text

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Simple sentence splitting (could be enhanced with NLTK)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences

    def _score_sentences(self,
                        sentences: list[str],
                        full_text: str) -> list[tuple]:
        """
        Score sentences by importance

        Args:
            sentences: List of sentences
            full_text: Original full text

        Returns:
            List of (sentence, score) tuples, sorted by score
        """
        scored = []

        for i, sentence in enumerate(sentences):
            score = 0

            # Position score: first and last sentences are important
            if i == 0 or i == len(sentences) - 1:
                score += 10

            # Length score: medium-length sentences are more informative
            word_count = len(sentence.split())
            if 10 <= word_count <= 30:
                score += 3
            elif word_count > 5:
                score += 1

            # Keyword score: sentences with important keywords
            important_words = ['important', 'significant', 'finding', 'result', 'conclusion',
                             'therefore', 'thus', 'in summary', 'key', 'critical']
            for word in important_words:
                if word.lower() in sentence.lower():
                    score += 5

            # Number score: sentences with numbers/data
            if re.search(r'\d+', sentence):
                score += 4

            # Quote score: sentences with quotes
            if '"' in sentence or "'" in sentence:
                score += 2

            scored.append((sentence, score, i))

        # Sort by score descending
        return sorted(scored, key=lambda x: -x[1])

    def compress_batch(self,
                      documents: list[Dict],
                      allocation: dict[str, CompressionLevel]) -> list[CompressedDocument]:
        """
        Compress a batch of documents

        Args:
            documents: List of documents {id, text, metadata}
            allocation: Dict mapping doc_id to compression level

        Returns:
            List of compressed documents
        """
        results = []

        for doc in documents:
            doc_id = doc['id']
            text = doc['text']
            metadata = doc.get('metadata', {})
            level = allocation.get(doc_id, CompressionLevel.FULL)

            compressed = self.compress(doc_id, text, level, metadata)
            results.append(compressed)

        total_original = sum(r.original_token_count for r in results)
        total_compressed = sum(r.compressed_token_count for r in results)
        avg_ratio = total_compressed / total_original if total_original > 0 else 0

        logger.info(f"Batch compressed {len(results)} documents: "
                   f"{total_original:,} → {total_compressed:,} tokens "
                   f"({avg_ratio:.1%} avg compression)")

        return results

    def auto_compress(self,
                     documents: list[Dict],
                     target_tokens: int,
                     relevance_scores: Optional[dict[str, float]] = None) -> list[CompressedDocument]:
        """
        Automatically compress documents to fit within token budget

        Strategy:
        1. Start with all documents at FULL level
        2. If exceeds budget, compress least relevant documents first
        3. Progressive compression: FULL → DETAILED → EXECUTIVE → METADATA_ONLY

        Args:
            documents: List of documents
            target_tokens: Maximum tokens to use
            relevance_scores: Relevance scores for each document (higher = keep full)

        Returns:
            List of compressed documents
        """
        relevance_scores = relevance_scores or {}

        # Initial allocation: all FULL
        allocation = {doc['id']: CompressionLevel.FULL for doc in documents}

        # Sort by relevance (lowest first for compression)
        sorted_docs = sorted(
            documents,
            key=lambda d: relevance_scores.get(d['id'], 0.0),
            reverse=False
        )

        # Calculate current size
        current_tokens = sum(self.estimate_tokens(doc['text']) for doc in documents)

        if current_tokens <= target_tokens:
            # Fits already
            return self.compress_batch(documents, allocation)

        # Progressive compression
        compression_order = [
            CompressionLevel.DETAILED,
            CompressionLevel.EXECUTIVE,
            CompressionLevel.METADATA_ONLY
        ]

        for target_level in compression_order:
            if current_tokens <= target_tokens:
                break

            # Compress next least-relevant document to this level
            for doc in sorted_docs:
                doc_id = doc['id']
                if allocation[doc_id].value < target_level.value:
                    # This document already at higher compression
                    continue

                # Try this compression level
                old_tokens = self.estimate_tokens(doc['text'])
                compressed = self.compress(doc_id, doc['text'], target_level)
                new_tokens = compressed.compressed_token_count
                saved = old_tokens - new_tokens

                allocation[doc_id] = target_level
                current_tokens -= saved

                if current_tokens <= target_tokens:
                    break

        logger.info(f"Auto-compression complete: {len(documents)} docs, "
                   f"{current_tokens:,} tokens (target: {target_tokens:,})")

        return self.compress_batch(documents, allocation)

def get_document_compressor() -> DocumentCompressor:
    """Get singleton document compressor instance"""
    if not hasattr(get_document_compressor, '_instance'):
        get_document_compressor._instance = DocumentCompressor()
    return get_document_compressor._instance
