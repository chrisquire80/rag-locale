"""
Long-Context RAG Engine - FASE 18
Extends MultimodalRAGEngine with 1M token context capabilities
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, field

try:
    from src.rag_engine_multimodal import MultimodalRAGEngine, MultimodalRAGResponse
except ImportError:
    # Fallback if multimodal module not available
    from src.rag_engine_v2 import RAGEngineV2 as MultimodalRAGEngine
    from src.rag_engine_v2 import RAGResponse as MultimodalRAGResponse

from src.long_context_optimizer import LongContextOptimizer, ContextChunk
from src.document_hierarchy import DocumentHierarchy, HierarchyNode
from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class LongContextRAGResponse(MultimodalRAGResponse):
    """Extended response with long-context metadata"""
    context_assembly_time_ms: float = 0.0
    context_token_count: int = 0
    context_coverage_pct: float = 0.0
    chunk_prioritization_strategy: str = "semantic"
    max_context_used: int = 900000
    prioritized_chunks: list[ContextChunk] = field(default_factory=list)
    document_hierarchy_used: bool = False

class LongContextRAGEngine(MultimodalRAGEngine):
    """RAG Engine leveraging Gemini 2.0 Flash 1M token context window"""

    def __init__(self):
        """Initialize long-context RAG engine"""
        super().__init__()

        # Initialize long-context components
        self.context_optimizer = LongContextOptimizer()
        self.doc_hierarchy = DocumentHierarchy()

        logger.info("✓ LongContextRAGEngine initialized")

    def query_with_long_context(
        self,
        query: str,
        use_full_context: bool = True,
        use_hierarchy: bool = True,
        top_k_docs: int = 10,
        max_context_tokens: int = 900000
    ) -> LongContextRAGResponse:
        """
        Process query with long-context optimization

        Strategy:
        1. Retrieve candidate documents
        2. Organize into hierarchy (optional)
        3. Chunk and prioritize by relevance
        4. Assemble optimal context
        5. Generate response with full context

        Args:
            query: User query
            use_full_context: Use full 1M context window
            use_hierarchy: Organize docs hierarchically
            top_k_docs: Top documents to include
            max_context_tokens: Maximum context tokens

        Returns:
            LongContextRAGResponse with assembly metadata
        """
        start_time = time.time()
        response = LongContextRAGResponse(
            answer="",
            sources=[],
            image_sources=[],
            text_sources=[],
            approved=False,
            hitl_required=False,
            model="gemini-2.0-flash",
            retrieval_strategy="long_context",
            multimodal_strategy="hybrid"
        )

        try:
            assembly_start = time.time()

            # 1. Retrieve candidate documents using multimodal search
            logger.info(f"Retrieving documents for: {query[:80]}...")
            search_results = self._retrieve_candidates(query, top_k_docs)

            if not search_results:
                response.answer = "No relevant documents found for your query."
                response.hitl_required = True
                return response

            response.text_sources = search_results

            # 2. Organize into hierarchy if requested
            if use_hierarchy:
                logger.info("Organizing documents into hierarchy...")
                self._organize_document_hierarchy([s.document for s in search_results])
                response.document_hierarchy_used = True

            # 3. Chunk and prioritize
            logger.info("Chunking and prioritizing documents...")
            prioritized_chunks = self._prioritize_documents(
                query,
                search_results
            )
            response.prioritized_chunks = prioritized_chunks

            # 4. Assemble optimal context
            logger.info("Assembling long-context...")
            assembled_context = self._assemble_optimal_context(
                prioritized_chunks,
                max_context_tokens
            )
            response.context_assembly_time_ms = (time.time() - assembly_start) * 1000

            # 5. Generate response
            logger.info("Generating response with long context...")
            response = self._generate_with_long_context(
                query,
                assembled_context,
                response
            )

            response.hitl_required = False
            response.approved = True

        except Exception as e:
            logger.error(f"Long-context query failed: {e}", exc_info=True)
            response.answer = f"Error processing query: {str(e)}"
            response.hitl_required = True

        response.latency_breakdown = {
            "total_ms": (time.time() - start_time) * 1000,
            "assembly_ms": response.context_assembly_time_ms,
            "generation_ms": (time.time() - start_time - response.context_assembly_time_ms / 1000) * 1000
        }

        return response

    def _retrieve_candidates(
        self,
        query: str,
        top_k: int
    ) -> list[Any]:
        """
        Retrieve candidate documents

        Uses existing search infrastructure
        """
        try:
            # Try multimodal search first
            if hasattr(self, 'multimodal_engine') and self.multimodal_engine:
                results = self.multimodal_engine.search(query, top_k=top_k)
                return [r for r in results if r]
        except Exception as e:
            logger.warning(f"Multimodal search failed: {e}")

        # Fallback to standard search
        try:
            if hasattr(self, 'hybrid_engine') and self.hybrid_engine:
                results = self.hybrid_engine.search(query, top_k=top_k)
                return [r for r in results if r]
        except Exception as e:
            logger.warning(f"Hybrid search failed: {e}")

        return []

    def _organize_document_hierarchy(self, documents: list[str]) -> None:
        """Organize retrieved documents into hierarchy"""
        try:
            doc_dicts = [
                {"id": f"doc_{i}", "text": doc, "metadata": {}}
                for i, doc in enumerate(documents)
            ]
            self.doc_hierarchy.organize_by_structure(doc_dicts)
            logger.info("Document hierarchy organized successfully")
        except Exception as e:
            logger.warning(f"Document hierarchy organization failed: {e}")

    def _prioritize_documents(
        self,
        query: str,
        search_results: list[Any]
    ) -> list[ContextChunk]:
        """
        Chunk and prioritize documents

        Args:
            query: User query
            search_results: Retrieved search results

        Returns:
            Prioritized list of chunks
        """
        all_chunks = []

        # Process each document
        for result_idx, result in enumerate(search_results):
            doc_text = result.document if hasattr(result, 'document') else str(result)

            # Chunk by semantics
            chunks = self.context_optimizer.chunk_by_semantics(doc_text)

            # Add metadata
            for chunk in chunks:
                chunk.source_doc = f"result_{result_idx}"
                if hasattr(result, 'source'):
                    chunk.source_doc = result.source

            all_chunks.extend(chunks)

        # Prioritize all chunks
        prioritized = self.context_optimizer.prioritize_chunks(
            query,
            all_chunks,
            top_k=None  # Get all, ranked
        )

        logger.info(f"Prioritized {len(prioritized)} chunks")
        return prioritized

    def _assemble_optimal_context(
        self,
        prioritized_chunks: list[ContextChunk],
        max_tokens: int = 900000
    ) -> str:
        """
        Assemble optimal context from prioritized chunks

        Args:
            prioritized_chunks: Ranked chunks
            max_tokens: Maximum tokens to include

        Returns:
            Assembled context string
        """
        assembled = ""
        current_tokens = 0
        included_chunks = 0

        # Build context respecting token limit
        for chunk in prioritized_chunks:
            chunk_tokens = chunk.token_count or self.context_optimizer.estimate_token_count(
                chunk.text
            )

            if current_tokens + chunk_tokens > max_tokens:
                # No more room
                logger.info(f"Context limit reached at {current_tokens} tokens")
                break

            # Add chunk with delimiter
            if included_chunks > 0:
                assembled += "\n\n---\n\n"

            if chunk.section:
                assembled += f"[{chunk.section}]\n"

            assembled += chunk.text
            current_tokens += chunk_tokens
            included_chunks += 1

        logger.info(
            f"Assembled {included_chunks} chunks, "
            f"{current_tokens}/{max_tokens} tokens used"
        )

        return assembled

    def _manage_context_window(
        self,
        documents: list[str],
        max_tokens: int = 900000
    ) -> str:
        """
        Intelligently manage context window

        Legacy method for backward compatibility

        Args:
            documents: Documents to include
            max_tokens: Maximum tokens

        Returns:
            Managed context string
        """
        return self.context_optimizer.assemble_long_context(
            documents,
            max_tokens
        )

    def _generate_with_long_context(
        self,
        query: str,
        context: str,
        response: LongContextRAGResponse
    ) -> LongContextRAGResponse:
        """
        Generate response using long context

        Args:
            query: User query
            context: Assembled context
            response: Response object to populate

        Returns:
            Updated response
        """
        try:
            # Count tokens in assembled context
            context_tokens = self.context_optimizer.estimate_token_count(context)
            response.context_token_count = context_tokens
            response.context_coverage_pct = 100 * context_tokens / 900000

            # Prepare prompt
            system_prompt = self.system_prompt
            user_message = f"""Use the following context to answer the user's question.

CONTEXT:
{context}

QUESTION: {query}

Answer based only on the provided context. If the context doesn't contain enough information, say so."""

            # Generate response using LLM
            if self.llm:
                answer = self.llm.generate(
                    user_message,
                    system_prompt=system_prompt,
                    max_tokens=2048,
                    temperature=0.3
                )
                response.answer = answer
                response.approved = True
            else:
                response.answer = "LLM service not available"
                response.hitl_required = True

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            response.answer = f"Error generating response: {str(e)}"
            response.hitl_required = True

        return response

    def get_context_stats(self) -> dict[str, Any]:
        """Get context optimization statistics"""
        return {
            "max_context_tokens": self.context_optimizer.max_context_tokens,
            "avg_tokens_per_word": self.context_optimizer.avg_tokens_per_word,
            "optimal_chunk_size": self.context_optimizer.estimate_optimal_chunk_size(),
            "hierarchy_stats": self.doc_hierarchy.get_statistics()
        }
