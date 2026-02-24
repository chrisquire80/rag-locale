"""
Multimodal Search Engine - FASE 17
Combines text and image retrieval for unified search results
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass, field
from pathlib import Path
import time

from src.hybrid_search import HybridSearchEngine, SearchResult
from src.vision_service import get_vision_service
from src.pdf_image_extraction import ExtractedImage

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ImageSearchResult:
    """Result from image search"""
    image_id: str
    image_path: str
    page_number: int
    source_pdf: str
    relevance_score: float
    description: str
    extracted_text: str
    embedding: Optional[np.ndarray] = None
    rank: int = 0

@dataclass
class MultimodalResult:
    """Combined text + image retrieval result"""
    result_id: str
    result_type: str  # "text" or "image"
    content: str  # Document text or image description
    source: str
    relevance_score: float
    retrieval_method: str
    page_number: Optional[int] = None
    image_path: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict = field(default_factory=dict)
    rank: int = 0

class MultimodalSearchEngine:
    """Extends HybridSearchEngine with image search capabilities"""

    def __init__(
        self,
        documents: list[Dict],
        embeddings: Optional[np.ndarray] = None,
        extracted_images: Optional[list[ExtractedImage]] = None
    ):
        """
        Initialize multimodal search engine

        Args:
            documents: List of document dicts
            embeddings: Document embeddings
            extracted_images: List of ExtractedImage objects
        """
        # Initialize hybrid text search
        self.hybrid_engine = HybridSearchEngine(documents, embeddings)
        self.documents = documents
        self.embeddings = embeddings

        # Initialize vision service
        self.vision_service = get_vision_service()

        # Store extracted images
        self.extracted_images = extracted_images or []
        self.image_embeddings = {}  # image_id -> embedding
        self.image_analysis_cache = {}  # image_path -> analysis

        logger.info(
            f"✓ MultimodalSearchEngine initialized with {len(documents)} docs "
            f"and {len(self.extracted_images)} images"
        )

    def search_images(
        self,
        query: str,
        top_k: int = 5
    ) -> list[ImageSearchResult]:
        """
        Search through extracted images

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of ImageSearchResult ranked by relevance
        """
        if not self.extracted_images:
            logger.debug("No images available for search")
            return []

        results = []
        logger.info(f"Searching {len(self.extracted_images)} images for: {query}")

        for i, image in enumerate(self.extracted_images):
            if not image.image_path or not Path(image.image_path).exists():
                logger.warning(f"Image path not found: {image.image_path}")
                continue

            try:
                # Get relevance score from vision service
                relevance = self.vision_service.evaluate_image_relevance(
                    image.image_path,
                    query
                )

                # Get image analysis (description + text)
                if image.image_path not in self.image_analysis_cache:
                    description = self.vision_service.analyze_image(image.image_path)
                    extracted_text = self.vision_service.extract_image_text(
                        image.image_path
                    )
                    self.image_analysis_cache[image.image_path] = {
                        "description": description,
                        "extracted_text": extracted_text
                    }
                else:
                    cached = self.image_analysis_cache[image.image_path]
                    description = cached["description"]
                    extracted_text = cached["extracted_text"]

                # Create result
                result = ImageSearchResult(
                    image_id=image.image_id,
                    image_path=image.image_path,
                    page_number=image.page_number,
                    source_pdf=image.source_pdf,
                    relevance_score=relevance,
                    description=description,
                    extracted_text=extracted_text
                )

                results.append(result)
                logger.debug(
                    f"Image {i+1}/{len(self.extracted_images)}: "
                    f"relevance={relevance:.2f}"
                )

            except Exception as e:
                logger.warning(
                    f"Error processing image {image.image_id}: {e}"
                )
                continue

        # Sort by relevance and return top-k
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        for rank, result in enumerate(results[:top_k], 1):
            result.rank = rank

        logger.info(f"✓ Image search complete: {len(results)} results")
        return results[:top_k]

    def search_multimodal(
        self,
        query: str,
        include_text: bool = True,
        include_images: bool = True,
        top_k: int = 5,
        query_embedding: Optional[np.ndarray] = None,
        alpha: float = 0.5
    ) -> list[MultimodalResult]:
        """
        Unified multimodal search combining text and images

        Args:
            query: Search query
            include_text: Include text search results
            include_images: Include image search results
            top_k: Total number of results to return
            query_embedding: Optional pre-computed query embedding
            alpha: Weight for combining text scores (0=BM25, 1=vector)

        Returns:
            Combined ranked results
        """
        all_results = []

        # Search text documents
        if include_text:
            try:
                text_results = self.hybrid_engine.search(
                    query,
                    query_embedding=query_embedding,
                    top_k=top_k * 2,  # Get more candidates for filtering
                    alpha=alpha
                )

                for sr in text_results:
                    mm_result = MultimodalResult(
                        result_id=sr.doc_id,
                        result_type="text",
                        content=sr.text[:500],
                        source=sr.metadata.get("source", "unknown"),
                        relevance_score=sr.combined_score,
                        retrieval_method="hybrid",
                        page_number=sr.metadata.get("page_number"),
                        confidence=1.0,
                        metadata=sr.metadata
                    )
                    all_results.append(mm_result)

                logger.debug(f"Text search returned {len(text_results)} results")

            except Exception as e:
                logger.error(f"Text search failed: {e}")

        # Search images
        if include_images:
            try:
                image_results = self.search_images(query, top_k=top_k * 2)

                for ir in image_results:
                    mm_result = MultimodalResult(
                        result_id=ir.image_id,
                        result_type="image",
                        content=ir.description[:500],
                        source=ir.source_pdf,
                        relevance_score=ir.relevance_score,
                        retrieval_method="vision",
                        page_number=ir.page_number,
                        image_path=ir.image_path,
                        confidence=ir.relevance_score,
                        metadata={
                            "image_id": ir.image_id,
                            "extracted_text": ir.extracted_text[:200],
                            "source_pdf": ir.source_pdf
                        }
                    )
                    all_results.append(mm_result)

                logger.debug(f"Image search returned {len(image_results)} results")

            except Exception as e:
                logger.error(f"Image search failed: {e}")

        # Sort by relevance score and return top-k
        all_results.sort(key=lambda x: x.relevance_score, reverse=True)
        for rank, result in enumerate(all_results[:top_k], 1):
            result.rank = rank

        logger.info(
            f"✓ Multimodal search complete: {len(all_results)} total results "
            f"({sum(1 for r in all_results if r.result_type == 'text')} text, "
            f"{sum(1 for r in all_results if r.result_type == 'image')} images)"
        )

        return all_results[:top_k]

    def add_images(self, extracted_images: list[ExtractedImage]):
        """Add images to search engine"""
        self.extracted_images.extend(extracted_images)
        logger.info(f"Added {len(extracted_images)} images to search engine")

    def get_image_statistics(self) -> Dict:
        """Get statistics about indexed images"""
        return {
            "total_images": len(self.extracted_images),
            "unique_pdfs": len(set(img.source_pdf for img in self.extracted_images)),
            "total_size_bytes": sum(img.file_size_bytes or 0 for img in self.extracted_images),
            "extraction_methods": list(
                set(img.extraction_method for img in self.extracted_images)
            ),
            "cache_size": len(self.image_analysis_cache)
        }

    def get_multimodal_statistics(self) -> Dict:
        """Get comprehensive multimodal statistics"""
        text_stats = self.hybrid_engine.get_statistics()
        image_stats = self.get_image_statistics()

        return {
            "text_search": text_stats,
            "image_search": image_stats,
            "total_searchable_items": (
                text_stats.get("total_documents", 0) +
                image_stats["total_images"]
            ),
            "has_text_embeddings": text_stats.get("has_embeddings", False),
            "has_image_embeddings": len(self.image_embeddings) > 0
        }

    def clear_image_cache(self):
        """Clear image analysis cache"""
        self.image_analysis_cache.clear()
        self.vision_service.clear_cache()
        logger.info("✓ Image cache cleared")

def get_multimodal_search_engine(
    documents: list[Dict],
    embeddings: Optional[np.ndarray] = None,
    extracted_images: Optional[list[ExtractedImage]] = None
) -> MultimodalSearchEngine:
    """Get or create multimodal search engine"""
    if not hasattr(get_multimodal_search_engine, "_instance"):
        get_multimodal_search_engine._instance = MultimodalSearchEngine(
            documents, embeddings, extracted_images
        )
    return get_multimodal_search_engine._instance

if __name__ == "__main__":

    # Test
    docs = [
        {"id": "1", "text": "Sample document", "metadata": {"source": "test.pdf"}},
    ]
    engine = MultimodalSearchEngine(docs)
    # Add test code here
