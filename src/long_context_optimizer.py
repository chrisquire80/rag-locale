"""
Long-Context Strategy - FASE 18
Optimizes retrieval for Gemini 2.0 Flash 1M token context window
Implements semantic chunking, token estimation, and context assembly
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)

@dataclass
class ContextChunk:
    """Represents a semantically meaningful chunk"""
    text: str
    start_pos: int
    end_pos: int
    semantic_score: float = 0.0
    token_count: int = 0
    source_doc: str = ""
    section: str = ""

class LongContextOptimizer:
    """Optimizes context assembly for 1M token context windows"""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize optimizer

        Args:
            model_name: Model identifier for token estimation
        """
        self.model_name = model_name
        self.max_context_tokens = 900000  # Conservative estimate (1M - buffer)
        self.avg_tokens_per_word = 1.3    # Approximate ratio for English
        self.section_delimiters = [
            r"^#{1,6}\s+",  # Markdown headers
            r"^#+\s+",      # Alternative markdown
            r"^[A-Z][^.]*:\s*$",  # Label-style sections
            r"^Section\s+\d+",  # Numbered sections
        ]

    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count using approximation

        More accurate than character count, works without tiktoken

        Args:
            text: Text to estimate

        Returns:
            Approximate token count
        """
        if not text:
            return 0

        # Split on whitespace and punctuation
        words = re.findall(r"\b\w+\b|[^\w\s]", text)

        # Rough approximation: 1 word ≈ 1.3 tokens
        # Adjust based on text characteristics
        token_estimate = len(words) * self.avg_tokens_per_word

        # Add overhead for special tokens, formatting
        token_estimate *= 1.05

        return int(token_estimate)

    def chunk_by_semantics(
        self,
        text: str,
        target_chunk_size: int = 4000
    ) -> list[ContextChunk]:
        """
        Intelligently chunk text by semantic boundaries

        Prefers splitting at:
        1. Section/heading boundaries
        2. Paragraph boundaries
        3. Sentence boundaries
        4. Token limits

        Args:
            text: Text to chunk
            target_chunk_size: Target chunk size in tokens

        Returns:
            List of semantically coherent chunks
        """
        chunks = []
        current_chunk = ""
        current_start = 0

        # Try to split by semantic boundaries
        sentences = self._split_into_sentences(text)

        for i, sentence in enumerate(sentences):
            test_chunk = current_chunk + sentence
            token_count = self.estimate_token_count(test_chunk)

            # If adding this sentence exceeds target, save current chunk
            if token_count > target_chunk_size and current_chunk:
                chunks.append(ContextChunk(
                    text=current_chunk.strip(),
                    start_pos=current_start,
                    end_pos=current_start + len(current_chunk),
                    token_count=self.estimate_token_count(current_chunk),
                    section=self._extract_section(current_chunk)
                ))
                current_chunk = sentence
                current_start = current_start + len(current_chunk)
            else:
                current_chunk = test_chunk

        # Add final chunk
        if current_chunk:
            chunks.append(ContextChunk(
                text=current_chunk.strip(),
                start_pos=current_start,
                end_pos=current_start + len(current_chunk),
                token_count=self.estimate_token_count(current_chunk),
                section=self._extract_section(current_chunk)
            ))

        logger.info(f"Created {len(chunks)} semantic chunks from {len(sentences)} sentences")
        return chunks

    def prioritize_chunks(
        self,
        query: str,
        chunks: list[ContextChunk],
        top_k: Optional[int] = None
    ) -> list[ContextChunk]:
        """
        Rank chunks by relevance to query

        Strategy:
        1. Keyword matching (highest priority)
        2. Semantic similarity approximation
        3. Position in document (earlier = higher)
        4. Chunk quality score

        Args:
            query: User query
            chunks: Chunks to prioritize
            top_k: Return top-k chunks (None = return all, sorted)

        Returns:
            Sorted list of chunks by relevance
        """
        query_terms = set(query.lower().split())
        scored_chunks = []

        for i, chunk in enumerate(chunks):
            score = 0.0
            chunk_text_lower = chunk.text.lower()

            # 1. Keyword matching (40% weight)
            keyword_matches = sum(
                1 for term in query_terms
                if term in chunk_text_lower and len(term) > 3
            )
            keyword_score = min(keyword_matches / max(len(query_terms), 1) * 0.4, 0.4)
            score += keyword_score

            # 2. Query term frequency (30% weight)
            term_frequency = sum(
                len(re.findall(rf"\b{term}\b", chunk_text_lower))
                for term in query_terms if len(term) > 3
            )
            frequency_score = min(term_frequency / 10 * 0.3, 0.3)
            score += frequency_score

            # 3. Position bonus for earlier chunks (20% weight)
            position_score = (1.0 - (i / max(len(chunks), 1))) * 0.2
            score += position_score

            # 4. Section relevance (10% weight)
            if chunk.section:
                section_matches = sum(
                    1 for term in query_terms
                    if term in chunk.section.lower()
                )
                section_score = min(section_matches / 10 * 0.1, 0.1)
                score += section_score

            chunk.semantic_score = score
            scored_chunks.append((score, chunk))

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        result = [chunk for _, chunk in scored_chunks]

        if top_k:
            result = result[:top_k]

        logger.info(f"Prioritized {len(result)} chunks, top score: {scored_chunks[0][0]:.3f}")
        return result

    def assemble_long_context(
        self,
        documents: list[str],
        max_tokens: int = 900000,
        include_metadata: bool = True
    ) -> str:
        """
        Assemble optimal long context from multiple documents

        Combines documents while respecting token limit
        Preserves document boundaries and structure

        Args:
            documents: List of document texts
            max_tokens: Maximum tokens to include
            include_metadata: Add document separators and metadata

        Returns:
            Assembled context string
        """
        assembled = ""
        current_tokens = 0
        included_docs = 0

        # Sort documents by estimated quality/relevance
        # (In production, would use pre-computed scores)
        sorted_docs = sorted(
            documents,
            key=lambda d: (
                len(d),  # Longer docs first (more comprehensive)
                -d.count("\n")  # More structure is better
            ),
            reverse=True
        )

        for doc_idx, doc in enumerate(sorted_docs):
            doc_tokens = self.estimate_token_count(doc)

            # Check if adding this doc exceeds limit
            if current_tokens + doc_tokens > max_tokens:
                # Try to add partial doc
                available_tokens = max_tokens - current_tokens
                if available_tokens > 1000:  # Min threshold
                    partial_doc = self._truncate_by_tokens(doc, available_tokens - 100)
                    assembled += f"\n\n[Document {included_docs + 1} - Partial]\n{partial_doc}\n"
                    included_docs += 1
                break

            if include_metadata:
                assembled += f"\n\n[Document {included_docs + 1}]\n"
            else:
                assembled += "\n\n"

            assembled += doc
            current_tokens += doc_tokens
            included_docs += 1

        logger.info(
            f"Assembled context: {included_docs} docs, "
            f"{current_tokens}/{max_tokens} tokens ({100*current_tokens/max_tokens:.1f}%)"
        )

        return assembled

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences preserving structure"""
        # Simple sentence splitting with period, question mark, exclamation
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_section(self, text: str) -> str:
        """Extract section header from chunk if present"""
        lines = text.split('\n')
        for line in lines[:3]:  # Check first few lines
            for delimiter in self.section_delimiters:
                if re.match(delimiter, line):
                    return re.sub(r'^[#\s]+', '', line).strip()
        return ""

    def _truncate_by_tokens(self, text: str, target_tokens: int) -> str:
        """Intelligently truncate text to target token count"""
        sentences = self._split_into_sentences(text)
        result = ""

        for sentence in sentences:
            test_result = result + " " + sentence
            if self.estimate_token_count(test_result) > target_tokens:
                break
            result = test_result

        return result.strip()

    def estimate_optimal_chunk_size(self, avg_query_results: int = 5) -> int:
        """
        Estimate optimal chunk size for context assembly

        Formula: available_context / (expected_results * safety_factor)

        Args:
            avg_query_results: Expected number of retrieved results

        Returns:
            Recommended chunk size in tokens
        """
        # Reserve space for query, prompt, response buffer
        reserved_tokens = 50000
        available = self.max_context_tokens - reserved_tokens

        # Divide among results with safety factor
        optimal = int(available / (avg_query_results * 1.2))

        return optimal

    def create_context_window(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5
    ) -> dict[str, any]:
        """
        Complete pipeline: chunk → prioritize → assemble

        Args:
            query: User query
            documents: Documents to process
            top_k: Top documents to include

        Returns:
            Dictionary with assembled context and metadata
        """
        all_chunks = []
        doc_chunks_map = {}

        # Chunk each document
        for doc_idx, doc in enumerate(documents):
            chunks = self.chunk_by_semantics(doc)
            for chunk in chunks:
                chunk.source_doc = f"doc_{doc_idx}"
            doc_chunks_map[f"doc_{doc_idx}"] = chunks
            all_chunks.extend(chunks)

        # Prioritize all chunks
        prioritized = self.prioritize_chunks(query, all_chunks, top_k=top_k * 10)

        # Assemble context
        selected_docs = []
        included_sources = set()
        for chunk in prioritized[:top_k * 10]:
            if chunk.source_doc not in included_sources:
                selected_docs.append(chunk.text)
                included_sources.add(chunk.source_doc)
                if len(selected_docs) >= top_k:
                    break

        context = self.assemble_long_context(selected_docs)

        return {
            "context": context,
            "chunk_count": len(all_chunks),
            "prioritized_count": len(prioritized),
            "selected_docs": len(selected_docs),
            "context_tokens": self.estimate_token_count(context),
            "max_tokens": self.max_context_tokens,
            "coverage_pct": 100 * self.estimate_token_count(context) / self.max_context_tokens
        }
