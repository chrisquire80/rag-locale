"""
Multimodal RAG Engine - FASE 17
Extends RAGEngineV2 with multimodal (text + image) retrieval and generation
"""

import time
import numpy as np
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path

from src.rag_engine_v2 import RAGEngineV2, RAGResponse, RetrievalResult
from src.multimodal_search import MultimodalSearchEngine, MultimodalResult
from src.pdf_image_extraction import PDFImageExtractor, ExtractedImage
from src.vision_service import get_vision_service
from src.llm_service import get_llm_service
from src.vector_store import get_vector_store

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class MultimodalRAGResponse(RAGResponse):
    """Extended RAG response with multimodal content"""
    image_sources: list[MultimodalResult] = field(default_factory=list)
    text_sources: list[RetrievalResult] = field(default_factory=list)
    multimodal_strategy: str = "hybrid"  # "text_only", "image_only", "hybrid"
    image_retrieval_time_ms: float = 0.0
    image_processing_time_ms: float = 0.0

class IngestionStats:
    """Statistics from multimodal document ingestion"""
    def __init__(self):
        self.documents_processed = 0
        self.images_extracted = 0
        self.images_analyzed = 0
        self.total_pages = 0
        self.extraction_errors = []
        self.processing_time_ms = 0.0

class MultimodalRAGEngine(RAGEngineV2):
    """Enhanced RAG Engine with multimodal capabilities"""

    def __init__(self):
        """Initialize multimodal RAG engine"""
        super().__init__()

        # Initialize multimodal components
        self.image_extractor = PDFImageExtractor()
        self.vision_service = get_vision_service()
        self.multimodal_engine = None
        self.extracted_images = {}  # pdf_name -> list of ExtractedImage

        logger.info("✓ MultimodalRAGEngine initialized")

    def query_multimodal(
        self,
        user_query: str,
        include_text: bool = True,
        include_images: bool = True,
        retrieval_method: str = "hybrid",
        top_k: int = 5
    ) -> MultimodalRAGResponse:
        """
        Process query with multimodal retrieval

        Args:
            user_query: User question
            include_text: Include text results
            include_images: Include image results
            retrieval_method: "hybrid", "text_only", "image_only"
            top_k: Number of results

        Returns:
            MultimodalRAGResponse with text and image sources
        """
        start_time = time.time()
        response = MultimodalRAGResponse(
            answer="",
            sources=[],
            image_sources=[],
            text_sources=[],
            approved=False,
            hitl_required=False,
            model="gemini",
            retrieval_strategy=retrieval_method,
            multimodal_strategy="hybrid"
        )

        try:
            # Determine strategy
            if not include_images:
                retrieval_method = "text_only"
                response.multimodal_strategy = "text_only"
            elif not include_text:
                retrieval_method = "image_only"
                response.multimodal_strategy = "image_only"

            # Query expansion
            query_variants = [user_query]
            if self.query_expander:
                try:
                    start = time.time()
                    expanded = self.query_expander.expand_query(
                        user_query, num_variants=2
                    )
                    query_variants = [user_query] + expanded.variants[:2]
                    response.latency_breakdown["expansion_ms"] = (
                        time.time() - start
                    ) * 1000
                except Exception as e:
                    logger.debug(f"Query expansion failed: {e}")

            # Multimodal retrieval
            if self.multimodal_engine:
                start = time.time()

                all_results = []
                for variant in query_variants:
                    mm_results = self.multimodal_engine.search_multimodal(
                        variant,
                        include_text=include_text,
                        include_images=include_images,
                        top_k=top_k * 2
                    )
                    all_results.extend(mm_results)

                # Deduplicate and sort
                seen_ids = set()
                unique_results = []
                for result in all_results:
                    if result.result_id not in seen_ids:
                        seen_ids.add(result.result_id)
                        unique_results.append(result)

                unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
                all_results = unique_results[:top_k]

                response.image_retrieval_time_ms = (time.time() - start) * 1000

                # Separate text and image results
                for result in all_results:
                    if result.result_type == "text":
                        # Convert to RetrievalResult
                        retrieval_result = RetrievalResult(
                            document=result.content,
                            score=result.relevance_score,
                            source=result.source,
                            section=result.metadata.get("section", ""),
                            doc_id=result.result_id,
                            retrieval_method="multimodal_text"
                        )
                        response.text_sources.append(retrieval_result)
                        response.sources.append(retrieval_result)
                    else:
                        response.image_sources.append(result)

                logger.info(
                    f"✓ Multimodal retrieval: {len(response.text_sources)} text, "
                    f"{len(response.image_sources)} images"
                )

            else:
                # Fallback to text-only search
                logger.warning("Multimodal engine not initialized, using text search")
                start = time.time()
                response.sources = self._retrieve_documents(
                    user_query,
                    method=retrieval_method if retrieval_method != "image_only" else "hybrid",
                    variants=query_variants
                )
                response.image_retrieval_time_ms = (time.time() - start) * 1000

            if not response.sources and not response.image_sources:
                response.answer = "Non ho trovato documenti o immagini pertinenti."
                return response

            # Generate response from multimodal sources
            start = time.time()
            response.answer = self._generate_multimodal_response(
                user_query,
                response.text_sources,
                response.image_sources
            )
            response.image_processing_time_ms = (time.time() - start) * 1000

            response.approved = True
            response.hitl_required = False
            response.query_variants = query_variants

            total_ms = (time.time() - start_time) * 1000
            logger.info(f"Multimodal query processed in {total_ms:.0f}ms")

            return response

        except Exception as e:
            logger.error(f"Multimodal query failed: {e}")
            response.answer = f"Errore nella ricerca multimodale: {str(e)}"
            response.hitl_required = True
            return response

    def add_pdf_with_images(
        self,
        pdf_path: str,
        analyze_images: bool = True
    ) -> IngestionStats:
        """
        Add PDF with image extraction and analysis

        Args:
            pdf_path: Path to PDF file
            analyze_images: Whether to analyze images with vision service

        Returns:
            IngestionStats with processing results
        """
        pdf_path = Path(pdf_path)
        stats = IngestionStats()
        start_time = time.time()

        try:
            logger.info(f"Processing PDF with images: {pdf_path.name}")

            # Extract text and add to vector store (via parent class flow)
            # This would normally be done via document_ingestion pipeline

            # Extract images
            extracted_images, extraction_metadata = self.image_extractor.extract_images_from_pdf(
                str(pdf_path),
                convert_to_images=True
            )

            stats.images_extracted = len(extracted_images)
            stats.total_pages = extraction_metadata.get("total_pages", 0)
            stats.extraction_errors = extraction_metadata.get("errors", [])

            if extracted_images:
                logger.info(f"✓ Extracted {len(extracted_images)} images")

                # Analyze images if requested
                if analyze_images:
                    logger.info(f"Analyzing {len(extracted_images)} images...")
                    analyzed = 0

                    for i, image in enumerate(extracted_images):
                        try:
                            if image.image_path and Path(image.image_path).exists():
                                # Get analysis from vision service
                                description = self.vision_service.analyze_image(
                                    image.image_path
                                )
                                ocr_text = self.vision_service.extract_image_text(
                                    image.image_path
                                )

                                # Store analysis
                                image.analysis_text = f"{description}\n\n{ocr_text}"
                                analyzed += 1

                                if i % 5 == 0:
                                    logger.debug(
                                        f"Analyzed {i+1}/{len(extracted_images)} images"
                                    )

                        except Exception as e:
                            logger.warning(f"Failed to analyze image {image.image_id}: {e}")

                    stats.images_analyzed = analyzed
                    logger.info(f"✓ Analyzed {analyzed} images")

                # Store images for retrieval
                self.extracted_images[pdf_path.name] = extracted_images

                # Add to multimodal engine if available
                if self.multimodal_engine:
                    self.multimodal_engine.add_images(extracted_images)

                # Save metadata
                self.image_extractor.save_extracted_images(
                    extracted_images,
                    self.image_extractor.output_dir / pdf_path.stem
                )

            stats.processing_time_ms = (time.time() - start_time) * 1000
            logger.info(
                f"✓ PDF processing complete: {stats.images_extracted} images "
                f"in {stats.processing_time_ms:.0f}ms"
            )

            return stats

        except Exception as e:
            logger.error(f"Failed to process PDF with images: {e}")
            stats.extraction_errors.append(str(e))
            stats.processing_time_ms = (time.time() - start_time) * 1000
            return stats

    def initialize_multimodal_engine(self):
        """Initialize multimodal search engine with current documents"""
        try:
            if not self.vector_store or not self.vector_store.documents:
                logger.warning("No documents in vector store")
                return

            # Get documents and embeddings
            docs = []
            embeddings = []

            for doc_id, doc in self.vector_store.documents.items():
                docs.append({
                    "id": doc_id,
                    "text": doc.text,
                    "metadata": doc.metadata or {}
                })

                # Get embedding if available
                if hasattr(doc, "embedding") and doc.embedding is not None:
                    embeddings.append(doc.embedding)

            embeddings = (
                np.array(embeddings) if embeddings
                else None
            )

            # Collect all extracted images
            all_images = []
            for images_list in self.extracted_images.values():
                all_images.extend(images_list)

            # Create multimodal engine
            from multimodal_search import MultimodalSearchEngine
            self.multimodal_engine = MultimodalSearchEngine(
                docs,
                embeddings=embeddings,
                extracted_images=all_images
            )

            logger.info(
                f"✓ Multimodal engine initialized with {len(docs)} docs "
                f"and {len(all_images)} images"
            )

        except Exception as e:
            logger.error(f"Failed to initialize multimodal engine: {e}")

    def _generate_multimodal_response(
        self,
        query: str,
        text_sources: list[RetrievalResult],
        image_sources: list[MultimodalResult]
    ) -> str:
        """Generate response combining text and image sources"""
        if not text_sources and not image_sources:
            return "Non ho trovato informazioni."

        # Build context from text sources
        text_context = ""
        if text_sources:
            text_context = "\n\n".join([
                f"Fonte: {s.source}\n{s.document[:400]}..."
                for s in text_sources[:2]
            ])

        # Build context from image sources
        image_context = ""
        if image_sources:
            image_context = "\n\n".join([
                f"Immagine da {s.source} (pagina {s.page_number}): {s.content[:300]}..."
                for s in image_sources[:2]
            ])

        # Combine contexts
        combined_context = ""
        if text_context:
            combined_context += f"Documenti di testo:\n{text_context}\n\n"
        if image_context:
            combined_context += f"Analisi di immagini:\n{image_context}"

        prompt = f"""{self.system_prompt}

Informazioni disponibili:
{combined_context}

Domanda: {query}

Rispondi in base alle informazioni disponibili, citando sia i documenti che le immagini quando rilevante."""

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

    def get_multimodal_statistics(self) -> Dict:
        """Get comprehensive multimodal statistics"""
        if self.multimodal_engine:
            return self.multimodal_engine.get_multimodal_statistics()
        else:
            return {
                "text_documents": len(self.vector_store.documents) if self.vector_store else 0,
                "extracted_images": sum(
                    len(imgs) for imgs in self.extracted_images.values()
                ),
                "multimodal_engine_initialized": False
            }

def get_multimodal_rag_engine() -> MultimodalRAGEngine:
    """Get or create multimodal RAG engine"""
    if not hasattr(get_multimodal_rag_engine, "_instance"):
        get_multimodal_rag_engine._instance = MultimodalRAGEngine()
    return get_multimodal_rag_engine._instance

if __name__ == "__main__":

    # Test
    engine = get_multimodal_rag_engine()
    # Add test code here
