"""
RAG Engine con Human-in-the-Loop (HITL)
Impedisce allucinazioni validando chunk pertinenti prima di generare risposta
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

# FASE 2: Performance profiling
from src.performance_profiler import get_profiler, profile_operation

# FASE 7: Advanced search filters
from src.search_filters import SearchFilter, SearchFilterBuilder

# FASE 10.1: Semantic query clustering for improved cache hit rates
from src.semantic_query_clustering import get_semantic_query_clusterer

# FASE 10.3: Context deduplication for optimized LLM input
from src.context_deduplicator import get_context_deduplicator

logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    """Risultato di una ricerca nel vector store"""
    document: str
    score: float
    source: str
    section: str
    doc_id: str

@dataclass
class RAGResponse:
    """Risposta generata dal RAG system"""
    answer: str
    sources: list[RetrievalResult]
    approved: bool
    hitl_required: bool
    model: str
    confidence_score: float = 0.0  # Confidence 0-100, calculated from source scores

class RAGEngine:
    """Core logic RAG con validazione HITL"""

    def __init__(self):
        self.vector_store = get_vector_store()
        self.llm = get_llm_service()
        self.enable_hitl = config.rag.enable_hitl
        self.score_threshold = config.rag.hitl_score_threshold
        self.top_k = config.rag.similarity_top_k
        self.system_prompt = config.rag.system_prompt

        # OPTIMIZATION 8.4: Query result caching with TTL
        self._query_cache = {}  # {query_hash: (timestamp, results)}
        self._cache_ttl = 7200  # 2 hours cache TTL (increased from 5 min for better UI responsiveness)

        # FASE 10.1: Semantic query clustering for improved cache hit rates
        self._query_clusterer = get_semantic_query_clusterer()

        # FASE 10.3: Context deduplication for optimized LLM input
        self._context_deduplicator = get_context_deduplicator()

    def _get_cache_key(self, query: str, metadata_filter: Optional[dict] = None) -> str:
        """Genera cache key da query e filter"""
        filter_str = str(sorted(metadata_filter.items())) if metadata_filter else "none"
        return f"{query}:{filter_str}"

    def _get_cached_result(self, cache_key: str) -> Optional[list]:
        """Recupera risultato da cache se valido (non scaduto)"""
        if cache_key in self._query_cache:
            timestamp, results = self._query_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info(f"✨ Cache HIT per query (TTL: {self._cache_ttl}s)")
                return results
            else:
                # Cache expired, remove
                del self._query_cache[cache_key]
        return None

    def _set_cache_result(self, cache_key: str, results: list) -> None:
        """Salva risultato in cache"""
        self._query_cache[cache_key] = (time.time(), results)

    def invalidate_cache(self) -> None:
        """
        Svuota la cache query risultati e la cluster cache.
        Da chiamare dopo ogni ingestion di nuovi documenti per evitare
        che le query restituiscano risultati obsoleti (TTL 2h).
        """
        count = len(self._query_cache)
        self._query_cache.clear()
        logger.info(f"🗑️ Query cache invalidata ({count} entries rimosse)")

        # FASE 10.1: Also invalidate cluster cache (contains responses based on old documents)
        self._query_clusterer.invalidate_clusters()

    @profile_operation("rag_query")
    def query(
        self,
        user_query: str,
        auto_approve_if_high_confidence: bool = False,
        metadata_filter: Optional[dict] = None,
        # FASE 7: Advanced filter parameters
        similarity_threshold: float = 0.0,
        document_types: Optional[list[str]] = None,
        date_range: Optional[tuple[datetime, datetime]] = None,
        tags: Optional[list[str]] = None,
        source_documents: Optional[list[str]] = None,
    ) -> RAGResponse:
        """
        Esegui query RAG con HITL opzionale e advanced filtering.

        Args:
            user_query: Domanda utente
            auto_approve_if_high_confidence: Skip HITL se score >= threshold
            metadata_filter: Filtro su metadata (es: {"dept": "IT"})
            similarity_threshold: Minimum relevance score (0.0-1.0)
            document_types: Filter by file type ["pdf", "txt", "md"]
            date_range: Tuple of (date_from, date_to) for ingestion date filtering
            tags: Filter by document tags (OR logic)
            source_documents: Filter to specific document names

        Returns:
            RAGResponse con answer, sources e approval status

        OPTIMIZATION 8.4: Query result caching
        - Cache retrieval results with 5-minute TTL
        - Identical queries return cached results (2-3x faster)

        FASE 10: Query metrics collection
        - Track search latency, LLM latency, cache hits

        FASE 7: Advanced filtering
        - Support multi-criteria filtering via SearchFilterBuilder
        - Apply similarity threshold to filter out low-relevance results
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"QUERY: {user_query}")
        logger.info(f"{'='*60}")

        # FASE 7: Build metadata filter from advanced filter parameters
        if any([document_types, date_range, tags, source_documents, similarity_threshold > 0.0]):
            search_filter = SearchFilter(
                document_types=document_types,
                date_from=date_range[0] if date_range else None,
                date_to=date_range[1] if date_range else None,
                tags=tags,
                source_documents=source_documents,
                similarity_threshold=SearchFilterBuilder.validate_similarity_threshold(similarity_threshold),
            )
            filter_from_params = SearchFilterBuilder.build_metadata_filter(search_filter)
            # Merge with any existing metadata_filter
            if metadata_filter and filter_from_params:
                metadata_filter = {"$and": [metadata_filter, filter_from_params]}
            elif filter_from_params:
                metadata_filter = filter_from_params
            if search_filter.similarity_threshold > 0.0:
                logger.info(f"🔍 Applying filters: {search_filter.to_dict()}")

        # Check if this is a library query (asking for all documents)
        if self.is_library_query(user_query):
            logger.info("[LIBRARY] Detected library query - returning all documents")
            return self.get_library_summary()

        # FASE 10: Initialize metrics
        from src.metrics import get_metrics_collector, QueryMetrics
        metrics_collector = get_metrics_collector()
        query_start = time.perf_counter()

        # Step 1: Retrieval (with caching)
        logger.info("Step 1: Retrieval...")

        # OPTIMIZATION 8.4: Check cache first
        cache_key = self._get_cache_key(user_query, metadata_filter)
        retrieval_results = self._get_cached_result(cache_key)
        cache_hit = retrieval_results is not None
        cluster_cache_hit = False

        # FASE 10.1: Check semantic query clustering (if direct cache miss)
        cluster_id = None
        query_embedding = None
        if retrieval_results is None:
            # Compute embedding ONCE and reuse for both clustering and retrieval
            # This avoids the double API call (saves ~150-400ms per query)
            try:
                embeddings = self.llm.get_embeddings([user_query])
                if embeddings:
                    import numpy as np
                    query_embedding = np.array(embeddings[0])
            except Exception as e:
                logger.warning(f"Could not pre-compute query embedding: {e}")

            cluster_id = self._query_clusterer.cluster_query(user_query, embedding=query_embedding)
            cluster_cached = self._query_clusterer.get_cluster_results(cluster_id)
            if cluster_cached is not None and metadata_filter is None:
                # Only use cluster cache if no filters applied
                # (filters can change which results are relevant)
                logger.info(f"✨ Cluster cache HIT (cluster: {cluster_id})")
                retrieval_results = cluster_cached.sources
                cache_hit = True
                cluster_cache_hit = True

        search_start = time.perf_counter()
        if retrieval_results is None:
            # Cache miss - perform actual retrieval (pass pre-computed embedding to avoid double API call)
            retrieval_results = self._retrieve(
                user_query,
                top_k=self.top_k,
                where_filter=metadata_filter,
                query_embedding=query_embedding
            )
            # FASE 7: Apply similarity threshold filter post-retrieval
            if retrieval_results and similarity_threshold > 0.0:
                initial_count = len(retrieval_results)
                retrieval_results = SearchFilterBuilder.apply_similarity_threshold(
                    retrieval_results, similarity_threshold
                )
                logger.info(f"⚙️  Similarity threshold filter: {len(retrieval_results)}/{initial_count} results passed threshold {similarity_threshold:.2f}")
            # Cache the results
            if retrieval_results:
                self._set_cache_result(cache_key, retrieval_results)
        else:
            # Cache hit - already retrieved (results were populated from cache)
            pass
        search_end = time.perf_counter()

        if not retrieval_results:
            logger.warning("⚠️  Nessun documento trovato. Genero risposta fallback.")
            return RAGResponse(
                answer="Non ho trovato documenti pertinenti nella knowledge base.",
                sources=[],
                approved=True,
                hitl_required=False,
                model=config.gemini.model_name
            )

        # Step 2: HITL Validation
        logger.info("👤 Step 2: HITL Validation...")
        hitl_required, approved = self._hitl_validation(
            user_query,
            retrieval_results,
            auto_approve_if_high_confidence
        )

        if hitl_required and not approved:
            logger.warning("⛔ HITL: Generazione annullata")
            return RAGResponse(
                answer="L'operatore ha declinato la generazione della risposta.",
                sources=retrieval_results,
                approved=False,
                hitl_required=True,
                model=config.gemini.model_name
            )

        # Step 3: Generation
        logger.info("Step 3: Generation...")
        context = self._build_context(retrieval_results)

        llm_start = time.perf_counter()
        answer = self._generate_response(
            user_query,
            context,
            retrieval_results
        )
        llm_end = time.perf_counter()

        # FASE 10: Record query metrics
        search_latency_ms = (search_end - search_start) * 1000
        llm_latency_ms = (llm_end - llm_start) * 1000
        query_metrics = QueryMetrics(
            query_text=user_query,
            documents_searched=self.top_k,
            documents_found=len(retrieval_results),
            search_latency_ms=search_latency_ms,
            llm_latency_ms=llm_latency_ms,
            cache_hit=cache_hit,
            timestamp=datetime.now()
        )
        metrics_collector.record_query(query_metrics)

        # Calculate response confidence score
        try:
            from src.confidence import ConfidenceCalculator
            confidence_calc = ConfidenceCalculator()
            confidence_score = confidence_calc.calculate_response_confidence(retrieval_results)
            logger.info(f"📊 Response confidence: {confidence_score:.0f}%")
        except Exception as e:
            logger.warning(f"Could not calculate confidence: {e}")
            confidence_score = 0.0

        # Create response object
        response = RAGResponse(
            answer=answer,
            sources=retrieval_results,
            approved=approved,
            hitl_required=hitl_required,
            model=config.gemini.model_name,
            confidence_score=confidence_score
        )

        # FASE 10.1: Cache response in cluster (if not a cache hit and no filters)
        if not cluster_cache_hit and cluster_id and metadata_filter is None:
            self._query_clusterer.add_to_cache(user_query, cluster_id, response)
            logger.debug(f"Cached response for cluster {cluster_id}")

        return response

    @profile_operation("rag_retrieve")
    def _retrieve(
        self,
        query: str,
        top_k: int = 5,
        where_filter: Optional[dict] = None,
        query_embedding = None
    ) -> list[RetrievalResult]:
        """Ricerca nel vector store"""
        try:
            raw_results = self.vector_store.search(
                query=query,
                top_k=top_k,
                where_filter=where_filter,
                query_embedding=query_embedding
            )

            results = []
            for r in raw_results:
                results.append(RetrievalResult(
                    document=r["document"],
                    score=r["similarity_score"],
                    source=r["metadata"].get("source", "unknown"),
                    section=r["metadata"].get("section", "default"),
                    doc_id=r["id"]
                ))

            # Log risultati
            logger.info(f"✓ Recuperati {len(results)} documenti")
            for i, r in enumerate(results, 1):
                logger.info(
                    f"   [{i}] Score: {r.score:.3f} | "
                    f"Fonte: {r.source} | {r.document[:60]}..."
                )

            return results

        except Exception as e:
            logger.error(f"✗ Errore retrieval: {e}")
            return []

    def _hitl_validation(
        self,
        user_query: str,
        retrieval_results: list[RetrievalResult],
        auto_approve: bool
    ) -> tuple[bool, bool]:
        """
        Valida manualmente i chunk recuperati.

        Returns:
            (hitl_required, approved)
            - hitl_required=True se intervento umano necessario
            - approved=True se utente ha approvato
        """
        if not self.enable_hitl:
            logger.info("ℹ️  HITL disabilitato, procedo...")
            return (False, True)

        # Calcola confidence media
        avg_score = sum(r.score for r in retrieval_results) / len(retrieval_results)
        logger.info(f"   Confidence media: {avg_score:.3f}")

        # Auto-approve se score alto
        if auto_approve and avg_score >= self.score_threshold:
            logger.info(f"✓ Auto-approval (score >= {self.score_threshold})")
            return (False, True)

        # Richiedi approvazione umana
        logger.warning("[HITL REQUIRED] Validazione manuale richiesta")
        print("\n" + "="*60)
        print("HUMAN-IN-THE-LOOP: Validazione Chunk Recuperati")
        print("="*60)
        print(f"\nQuery: {user_query}\n")

        for i, result in enumerate(retrieval_results, 1):
            print(f"\n--- CHUNK {i} (Score: {result.score:.3f}) ---")
            print(f"Fonte: {result.source} | Sezione: {result.section}")
            print(f"\n{result.document}\n")

        print("="*60)
        approval = input(
            "\nSono i dati recuperati pertinenti? (si/no): "
        ).lower().strip()

        approved = approval in ['si', 'yes', 'y', 's']
        logger.info(f"[Approval] {'APPROVED' if approved else 'DECLINED'}")

        return (True, approved)

    def _build_context(self, retrieval_results: list[RetrievalResult]) -> str:
        """
        Costruisci prompt context dai chunk recuperati.
        FASE 10.3: Apply context deduplication to remove redundant information
        """
        if not retrieval_results:
            return ""

        # FASE 10.3: Deduplicate chunks to reduce redundancy
        try:
            deduplicated_results = self._context_deduplicator.deduplicate_chunks(retrieval_results)
            original_count = len(retrieval_results)
            dedup_count = len(deduplicated_results)

            if dedup_count < original_count:
                logger.info(f"📦 Context deduplication: {original_count} → {dedup_count} chunks ({100*(1-dedup_count/original_count):.0f}% removed)")
                retrieval_results = deduplicated_results
        except Exception as e:
            logger.warning(f"Deduplication failed, using all chunks: {e}")
            # Continue with original results if deduplication fails

        context_parts = []

        for i, result in enumerate(retrieval_results, 1):
            context_parts.append(
                f"[Fonte {i}: {result.source} - Sezione: {result.section}]\n{result.document}"
            )

        context = "\n\n".join(context_parts)
        logger.debug(f"📄 Context length: {len(context)} caratteri")
        return context

    @profile_operation("rag_generate")
    def _generate_response(
        self,
        user_query: str,
        context: str,
        retrieval_results: list[RetrievalResult]
    ) -> str:
        """Genera risposta usando Gemini"""
        # Costruisci prompt con inline citations
        prompt = f"""
Basandoti ESCLUSIVAMENTE sul contesto sottostante, rispondi alla seguente domanda:

DOMANDA: {user_query}

CONTESTO DISPONIBILE:
{context}

ISTRUZIONI CRITICHE:
1. Rispondi SOLO se il contesto contiene informazioni rilevanti
2. **INLINE CITATIONS OBBLIGATORIE**: Cita le fonti DENTRO il testo, ad esempio:
   "Factorial è una piattaforma [Fonte 1] che gestisce il talento [Fonte 2]"
   NON solo alla fine della risposta
3. Se una parola ha molteplici significati, usa il contesto dei documenti per risolverla
4. Se il contesto non è sufficiente per NESSUNO dei significati, dichiara che non hai dati
5. Usa linguaggio tecnico preciso, professionale e ben strutturato

FORMATO RISPOSTA:
- Paragrafi con inline citations [Fonte N] sparse nel testo
- Non mettere le fonti solo alla fine
- Se hai risolto un'ambiguità, menzioniala brevemente

RISPOSTA:
"""

        try:
            logger.debug("📤 Invio al modello Gemini...")
            answer = self.llm.completion(
                prompt=prompt,
                system_prompt=self.system_prompt,
                max_tokens=config.gemini.max_tokens,
                temperature=config.gemini.temperature
            )

            logger.info("✓ Risposta generata")
            return answer

        except Exception as e:
            logger.error(f"✗ Errore generazione: {e}")
            return f"Errore durante la generazione della risposta: {e}"

    def print_response(self, response: RAGResponse) -> None:
        """Formatta e stampa la risposta per l'utente"""
        print("\n" + "="*60)
        print("🤖 RISPOSTA")
        print("="*60)
        print(f"\n{response.answer}\n")

        print("="*60)
        print("📚 FONTI UTILIZZATE")
        print("="*60)
        for i, source in enumerate(response.sources, 1):
            print(f"\n[Fonte {i}]")
            print(f"  Documento: {source.source}")
            print(f"  Sezione: {source.section}")
            print(f"  Score: {source.score:.3f}")
            print(f"  {source.document[:100]}...")

        print("\n" + "="*60)
        print(f"Model: {response.model} | HITL: {response.hitl_required} | Approved: {response.approved}")
        print("="*60 + "\n")

    # FEATURE: Library queries - show all documents
    _LIBRARY_KEYWORDS = [
        # Italian
        "mostrami tutti", "elenca tutti", "lista completa", "tutti i documenti",
        "quanti documenti", "elenco documenti", "libreria completa", "documenti disponibili",
        "quali documenti", "mostra tutti", "quanti hanno", "numero di documenti",
        # English
        "show all", "list all", "complete list", "all documents", "how many documents",
        "document list", "document library", "available documents"
    ]

    def is_library_query(self, query: str) -> bool:
        """Rileva se l'utente chiede la lista completa di documenti"""
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self._LIBRARY_KEYWORDS)

    def get_library_summary(self) -> RAGResponse:
        """Ritorna TUTTI i documenti in libreria formattati"""
        try:
            all_docs = self.vector_store.get_all_documents()
            total_chunks = self.vector_store.get_total_chunks()

            if not all_docs:
                answer = "La libreria è vuota. Nessun documento caricato."
                return RAGResponse(
                    answer=answer,
                    sources=[],
                    approved=True,
                    hitl_required=False,
                    model=config.gemini.model_name
                )

            # Formatta lista
            answer = f"**📚 Libreria Completa: {len(all_docs)} Documenti Unici ({total_chunks} chunk totali)**\n\n"
            for i, doc_info in enumerate(all_docs, 1):
                source = doc_info.get("source", "Unknown")
                chunks = doc_info.get("num_chunks", 0)
                answer += f"{i}. **{source}** ({chunks} chunk)\n"

            logger.info(f"[LIBRARY] Returned list of {len(all_docs)} unique documents")

            return RAGResponse(
                answer=answer,
                sources=[],
                approved=True,
                hitl_required=False,
                model=config.gemini.model_name
            )
        except Exception as e:
            logger.error(f"[LIBRARY] Error: {e}")
            return RAGResponse(
                answer=f"Errore nel recupero della libreria: {e}",
                sources=[],
                approved=True,
                hitl_required=False,
                model=config.gemini.model_name
            )

    def query_stream(
        self,
        user_query: str,
        auto_approve_if_high_confidence: bool = False,
        metadata_filter: Optional[dict] = None
    ):
        """
        Esegui query RAG in STREAMING.
        
        Yields:
            1. RAGResponse (con answer="" e sources populate) - Metadata iniziale
            2. str - Chunks di testo della risposta man mano che vengono generati
        """
        logger.info(f"STREAM QUERY: {user_query}")
        
        # Check library query
        if self.is_library_query(user_query):
             response = self.get_library_summary()
             yield response
             yield response.answer # Yield full answer as single chunk for compatibility
             return

        # 1. Retrieval
        retrieval_results = self._retrieve(user_query, self.top_k, metadata_filter)
        
        if not retrieval_results:
            fallback_response = RAGResponse(
                answer="Non ho trovato documenti pertinenti.",
                sources=[],
                approved=True,
                hitl_required=False,
                model=config.gemini.model_name
            )
            yield fallback_response
            yield "Non ho trovato documenti pertinenti nella knowledge base."
            return

        # 2. HITL (Skip for streaming usually, or handle before stream start)
        # For simplicity in streaming, we assume auto-approve or skip HITL
        # If strict HITL is needed, it breaks streaming UX slightly (pause before stream)
        hitl_required = False
        approved = True
        
        if self.enable_hitl:
             hitl_required, approved = self._hitl_validation(user_query, retrieval_results, auto_approve_if_high_confidence)
             if not approved:
                 yield RAGResponse(
                     answer="Generazione annullata dall'utente.",
                     sources=retrieval_results,
                     approved=False,
                     hitl_required=True,
                     model=config.gemini.model_name
                 )
                 yield "Generazione annullata."
                 return

        # 3. Yield Initial Metadata
        initial_response = RAGResponse(
            answer="", # Empty initially
            sources=retrieval_results,
            approved=approved,
            hitl_required=hitl_required,
            model=config.gemini.model_name
        )
        yield initial_response

        # 4. Stream Generation
        context = self._build_context(retrieval_results)
        prompt = f"""
Basandoti ESCLUSIVAMENTE sul contesto sottostante, rispondi alla seguente domanda:

DOMANDA: {user_query}

CONTESTO DISPONIBILE:
{context}

ISTRUZIONI CRITICHE:
1. Rispondi SOLO se il contesto contiene informazioni rilevanti
2. **INLINE CITATIONS OBBLIGATORIE**: Cita le fonti DENTRO il testo, ad esempio:
   "Factorial è una piattaforma [Fonte 1] che gestisce il talento [Fonte 2]"
   NON solo alla fine della risposta
3. Usa linguaggio tecnico preciso, professionale e ben strutturato

RISPOSTA:
"""
        try:
            for chunk in self.llm.completion_stream(
                prompt=prompt,
                system_prompt=self.system_prompt,
                max_tokens=config.gemini.max_tokens,
                temperature=config.gemini.temperature
            ):
                yield chunk
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"\n[Errore durante la generazione: {e}]"

def interactive_rag_session():
    """Sessione interattiva RAG"""
    engine = RAGEngine()

    print("\n" + "="*60)
    print("🚀 RAG LOCALE - Sessione Interattiva")
    print("="*60)
    print("\nInserisci domande sulla documentazione IT aziendale.")
    print("Scrivi 'esci' per terminare.\n")

    # Verifica connessione Gemini
    if not engine.llm.check_health():
        logger.error("❌ Gemini non disponibile. Esci.")
        return

    while True:
        query = input("\n💬 Domanda: ").strip()

        if query.lower() in ['esci', 'exit', 'quit']:
            print("\n👋 Arrivederci!\n")
            break

        if not query:
            print("⚠️  Inserisci una domanda valida")
            continue

        # Esegui query
        response = engine.query(
            user_query=query,
            auto_approve_if_high_confidence=False  # Forza HITL per demo
        )

        # Stampa risultato
        engine.print_response(response)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    interactive_rag_session()
