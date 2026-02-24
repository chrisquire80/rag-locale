"""
RAG Engine V2 - FASE 16-20 Enhanced Implementation
Integrates hybrid search, re-ranking, multimodal support, and quality metrics
"""

import logging
import time
from datetime import datetime
from functools import lru_cache
from typing import Optional
from dataclasses import dataclass

from src.config import config
from src.vector_store import get_vector_store
from src.llm_service import get_llm_service
from src.hybrid_search import HybridSearchEngine
from src.reranker import GeminiReRanker
from src.query_expansion import QueryExpander

logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    """Risultato di una ricerca nel vector store"""
    document: str
    score: float
    source: str
    section: str
    doc_id: str
    relevance_score: float = 0.0  # FASE 16: Re-ranking score
    retrieval_method: str = "bm25"  # FASE 16: "bm25", "vector", "hybrid", "reranked"

@dataclass
class RAGResponse:
    """Risposta generata dal RAG system"""
    answer: str
    sources: list[RetrievalResult]
    approved: bool
    hitl_required: bool
    model: str
    retrieval_strategy: str = "hybrid"  # FASE 16: hybrid search strategy
    query_variants: list[str] = None  # FASE 16: query expansion variants
    latency_breakdown: dict = None  # FASE 16: performance metrics

class RAGEngineV2:
    """Enhanced RAG Engine with FASE 16-20 features"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.llm = get_llm_service()
        self.enable_hitl = config.rag.enable_hitl
        self.score_threshold = config.rag.hitl_score_threshold
        self.top_k = config.rag.similarity_top_k
        self.system_prompt = config.rag.system_prompt

        # FASE 16: Hybrid search + Re-ranking
        self._init_hybrid_search()
        self._init_reranker()
        self._init_query_expander()

        # Performance tracking
        self.latency_breakdown = {}

    def _init_hybrid_search(self):
        """Initialize hybrid search engine (FASE 16)"""
        try:
            # Convert vector store documents to format expected by HybridSearchEngine
            docs = []
            for doc_id, doc in self.vector_store.documents.items():
                docs.append({
                    "id": doc_id,
                    "text": doc.text,
                    "metadata": doc.metadata or {}
                })
            self.hybrid_engine = HybridSearchEngine(docs) if docs else None
            logger.info(f"✓ Hybrid search initialized with {len(docs)} documents")
        except Exception as e:
            logger.warning(f"Hybrid search initialization failed: {e}")
            self.hybrid_engine = None

    def _init_reranker(self):
        """Initialize Gemini re-ranker (FASE 16)"""
        try:
            self.reranker = GeminiReRanker(self.llm, batch_size=5)
            logger.info("✓ Gemini re-ranker initialized")
        except Exception as e:
            logger.warning(f"Re-ranker initialization failed: {e}")
            self.reranker = None

    def _init_query_expander(self):
        """Initialize query expansion (FASE 16)"""
        try:
            self.query_expander = QueryExpander(self.llm)
            logger.info("✓ Query expander initialized")
        except Exception as e:
            logger.warning(f"Query expander initialization failed: {e}")
            self.query_expander = None

    def query(self, user_query: str, retrieval_method: str = "hybrid") -> RAGResponse:
        """
        Process user query with FASE 16+ enhancements

        Args:
            user_query: User question
            retrieval_method: "bm25", "vector", "hybrid", or "reranked"

        Returns:
            RAGResponse with answer and sources
        """
        start_time = time.time()
        self.latency_breakdown = {
            "expansion_ms": 0,
            "retrieval_ms": 0,
            "reranking_ms": 0,
            "generation_ms": 0
        }

        try:
            # FASE 16: Query Expansion
            query_variants = [user_query]
            if self.query_expander:
                try:
                    start = time.time()
                    expanded = self.query_expander.expand_query(user_query, num_variants=2)
                    query_variants = [user_query] + expanded.variants[:2]
                    self.latency_breakdown["expansion_ms"] = (time.time() - start) * 1000
                except Exception as e:
                    logger.debug(f"Query expansion failed: {e}")

            # FASE 16: Retrieval with selected method
            start = time.time()
            sources = self._retrieve_documents(user_query, method=retrieval_method, variants=query_variants)
            self.latency_breakdown["retrieval_ms"] = (time.time() - start) * 1000

            if not sources:
                return RAGResponse(
                    answer="Non ho trovato documenti pertinenti per rispondere.",
                    sources=[],
                    approved=False,
                    hitl_required=False,
                    model="gemini",
                    retrieval_strategy=retrieval_method,
                    query_variants=query_variants,
                    latency_breakdown=self.latency_breakdown
                )

            # FASE 16: Re-ranking if available
            if self.reranker and retrieval_method == "reranked":
                try:
                    start = time.time()
                    candidates = [
                        {
                            "doc_id": s.doc_id,
                            "text": s.document,
                            "retrieval_score": s.score,
                            "metadata": {"source": s.source}
                        }
                        for s in sources
                    ]
                    ranked = self.reranker.rerank_results(user_query, candidates, top_k=3)
                    # Update sources with re-ranking scores
                    for i, result in enumerate(ranked):
                        if i < len(sources):
                            sources[i].relevance_score = result.relevance_score
                            sources[i].retrieval_method = "reranked"
                    self.latency_breakdown["reranking_ms"] = (time.time() - start) * 1000
                except Exception as e:
                    logger.debug(f"Re-ranking failed: {e}")

            # Generate response
            start = time.time()
            answer = self._generate_response(user_query, sources)
            self.latency_breakdown["generation_ms"] = (time.time() - start) * 1000

            total_ms = (time.time() - start_time) * 1000
            logger.info(f"Query processed in {total_ms:.0f}ms (expansion: {self.latency_breakdown['expansion_ms']:.0f}ms, "
                       f"retrieval: {self.latency_breakdown['retrieval_ms']:.0f}ms, "
                       f"reranking: {self.latency_breakdown['reranking_ms']:.0f}ms, "
                       f"generation: {self.latency_breakdown['generation_ms']:.0f}ms)")

            return RAGResponse(
                answer=answer,
                sources=sources,
                approved=True,
                hitl_required=False,
                model="gemini",
                retrieval_strategy=retrieval_method,
                query_variants=query_variants,
                latency_breakdown=self.latency_breakdown
            )

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return RAGResponse(
                answer=f"Errore durante l'elaborazione: {str(e)}",
                sources=[],
                approved=False,
                hitl_required=True,
                model="gemini",
                retrieval_strategy=retrieval_method,
                query_variants=query_variants,
                latency_breakdown=self.latency_breakdown
            )

    def _retrieve_documents(self, query: str, method: str = "hybrid", variants: list[str] = None) -> list[RetrievalResult]:
        """
        Retrieve documents using selected method

        Methods:
        - "bm25": Keyword-based search only
        - "vector": Vector similarity only
        - "hybrid": Combined BM25 + vector (alpha=0.5)
        - "reranked": Hybrid + Gemini re-ranking
        """
        if variants is None:
            variants = [query]

        all_results = []

        # Try each query variant
        for variant in variants:
            try:
                if method == "hybrid" and self.hybrid_engine:
                    # FASE 16: Hybrid search
                    search_results = self.hybrid_engine.search(variant, top_k=self.top_k, alpha=0.5)
                    for sr in search_results:
                        doc = self.vector_store.documents.get(sr.doc_id)
                        if doc:
                            all_results.append(RetrievalResult(
                                document=doc.text,
                                score=sr.combined_score,
                                source=doc.metadata.get("source", "unknown"),
                                section=doc.metadata.get("section", ""),
                                doc_id=sr.doc_id,
                                retrieval_method="hybrid"
                            ))
                else:
                    # Fallback: vector search
                    results = self.vector_store.search(variant, top_k=self.top_k)
                    for r in results:
                        all_results.append(RetrievalResult(
                            document=r["document"],
                            score=r["similarity_score"],
                            source=r["metadata"].get("source", "unknown"),
                            section=r["metadata"].get("section", ""),
                            doc_id=r["id"],
                            retrieval_method="vector"
                        ))
            except Exception as e:
                logger.debug(f"Retrieval with variant '{variant}' failed: {e}")

        # Deduplicate and sort by score
        seen_docs = set()
        unique_results = []
        for result in all_results:
            if result.doc_id not in seen_docs:
                seen_docs.add(result.doc_id)
                unique_results.append(result)

        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:self.top_k]

    def _generate_response(self, query: str, sources: list[RetrievalResult]) -> str:
        """Generate response from retrieved sources"""
        if not sources:
            return "Non ho trovato informazioni per rispondere."

        # Prepare context
        context = "\n\n".join([
            f"Fonte: {s.source}\n{s.document[:500]}..."
            for s in sources[:3]
        ])

        prompt = f"""{self.system_prompt}

Informazioni disponibili:
{context}

Domanda: {query}

Rispondi in base alle informazioni disponibili, citando le fonti."""

        try:
            response = self.llm.completion(
                prompt=prompt,
                temperature=0.7,
                max_tokens=1000
            )
            return response
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return f"Errore nella generazione della risposta: {str(e)}"

def get_rag_engine_v2() -> RAGEngineV2:
    """Get or create RAG Engine V2 singleton"""
    if not hasattr(get_rag_engine_v2, "_instance"):
        get_rag_engine_v2._instance = RAGEngineV2()
    return get_rag_engine_v2._instance
