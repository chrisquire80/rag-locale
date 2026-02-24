"""
FASE 17: Multimodal RAG - Comprehensive Test Suite
Tests PDF image extraction, vision analysis, and multimodal retrieval
Total: 23 tests across 5 test classes
"""

import sys
import os
import logging
import tempfile
from pathlib import Path
import pytest
import json
import time

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pdf_image_extraction import (
    PDFImageExtractor,
    ExtractedImage,
    get_pdf_image_extractor
)
from vision_service import (
    GeminiVisionService,
    get_vision_service
)
from multimodal_search import (
    MultimodalSearchEngine,
    ImageSearchResult,
    MultimodalResult
)
from rag_engine_multimodal import (
    MultimodalRAGEngine,
    IngestionStats,
    get_multimodal_rag_engine
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# TEST 1: PDF Image Extraction (5 tests)
# ============================================================================

class TestPDFImageExtraction:
    """Test PDF image extraction functionality"""

    @pytest.fixture
    def extractor(self):
        """Create temp extractor"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield PDFImageExtractor(Path(tmpdir))

    def test_extractor_initialization(self, extractor):
        """Test PDFImageExtractor initialization"""
        print("\n" + "="*70)
        print("TEST 1.1: PDFImageExtractor Initialization")
        print("="*70)

        assert extractor is not None
        assert extractor.output_dir.exists()
        assert extractor.image_counter == 0
        print("✓ Extractor initialized successfully")

    def test_extracted_image_dataclass(self):
        """Test ExtractedImage dataclass"""
        print("\n" + "="*70)
        print("TEST 1.2: ExtractedImage Dataclass")
        print("="*70)

        image = ExtractedImage(
            image_id="test_img_1",
            page_number=1,
            source_pdf="test.pdf",
            extraction_date="2024-01-01T00:00:00",
            image_path="/tmp/test.png",
            width=800,
            height=600,
            file_size_bytes=50000
        )

        assert image.image_id == "test_img_1"
        assert image.page_number == 1
        assert image.width == 800

        # Test to_dict
        data = image.to_dict()
        assert isinstance(data, dict)
        assert data["image_id"] == "test_img_1"

        # Test from_dict
        restored = ExtractedImage.from_dict(data)
        assert restored.image_id == image.image_id

        print("✓ ExtractedImage dataclass working correctly")

    def test_image_metadata_persistence(self, extractor):
        """Test saving and loading image metadata"""
        print("\n" + "="*70)
        print("TEST 1.3: Image Metadata Persistence")
        print("="*70)

        images = [
            ExtractedImage(
                image_id=f"img_{i}",
                page_number=i,
                source_pdf="test.pdf",
                extraction_date="2024-01-01T00:00:00",
                image_path=f"/tmp/img_{i}.png",
                width=800,
                height=600,
                file_size_bytes=50000
            )
            for i in range(3)
        ]

        # Save metadata
        result = extractor.save_extracted_images(images)
        assert result["images_count"] == 3

        # Load metadata
        loaded = extractor.load_image_metadata(
            Path(result["metadata_file"])
        )
        assert len(loaded) == 3
        assert loaded[0].image_id == "img_0"

        print("✓ Metadata persistence working")

    def test_extraction_statistics(self, extractor):
        """Test extraction statistics"""
        print("\n" + "="*70)
        print("TEST 1.4: Extraction Statistics")
        print("="*70)

        images = [
            ExtractedImage(
                image_id=f"img_{i}",
                page_number=i,
                source_pdf="test.pdf",
                extraction_date="2024-01-01T00:00:00",
                extraction_method="pypdf",
                width=800 + i*100,
                height=600 + i*100,
                file_size_bytes=50000 + i*10000
            )
            for i in range(3)
        ]

        stats = extractor.get_extraction_statistics(images)
        assert stats["total_images"] == 3
        assert stats["total_size_bytes"] > 0
        assert "extraction_methods" in stats
        assert "pypdf" in stats["extraction_methods"]

        print(f"✓ Statistics: {json.dumps(stats, indent=2)}")

    def test_extractor_singleton(self):
        """Test PDFImageExtractor singleton pattern"""
        print("\n" + "="*70)
        print("TEST 1.5: PDFImageExtractor Singleton")
        print("="*70)

        ext1 = get_pdf_image_extractor()
        ext2 = get_pdf_image_extractor()
        assert ext1 is ext2

        print("✓ Singleton pattern working")


# ============================================================================
# TEST 2: Vision Service (6 tests)
# ============================================================================

class TestVisionService:
    """Test Gemini Vision API integration"""

    @pytest.fixture
    def vision_service(self):
        """Get vision service"""
        return get_vision_service()

    @pytest.fixture
    def sample_image(self):
        """Create sample test image"""
        try:
            from PIL import Image
            img = Image.new('RGB', (100, 100), color='red')
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                img.save(f.name)
                yield f.name
                Path(f.name).unlink()
        except ImportError:
            pytest.skip("PIL not available")

    def test_vision_service_initialization(self, vision_service):
        """Test vision service initialization"""
        print("\n" + "="*70)
        print("TEST 2.1: Vision Service Initialization")
        print("="*70)

        assert vision_service is not None
        assert hasattr(vision_service, 'analyze_image')
        assert hasattr(vision_service, 'extract_image_text')
        assert hasattr(vision_service, 'evaluate_image_relevance')

        print("✓ Vision service initialized")

    def test_mime_type_detection(self, vision_service):
        """Test MIME type detection"""
        print("\n" + "="*70)
        print("TEST 2.2: MIME Type Detection")
        print("="*70)

        assert vision_service._get_mime_type(Path("test.png")) == "image/png"
        assert vision_service._get_mime_type(Path("test.jpg")) == "image/jpeg"
        assert vision_service._get_mime_type(Path("test.gif")) == "image/gif"

        print("✓ MIME type detection working")

    def test_cache_management(self, vision_service):
        """Test caching mechanism"""
        print("\n" + "="*70)
        print("TEST 2.3: Cache Management")
        print("="*70)

        initial_cache_size = len(vision_service._cache)
        vision_service._cache["test_key"] = "test_value"
        assert len(vision_service._cache) > initial_cache_size

        vision_service.clear_cache()
        assert len(vision_service._cache) == 0

        print("✓ Cache management working")

    def test_vision_service_singleton(self):
        """Test vision service singleton"""
        print("\n" + "="*70)
        print("TEST 2.4: Vision Service Singleton")
        print("="*70)

        srv1 = get_vision_service()
        srv2 = get_vision_service()
        assert srv1 is srv2

        print("✓ Singleton pattern working")

    @pytest.mark.skip(reason="Requires valid Gemini API key")
    def test_analyze_image_with_gemini(self, vision_service, sample_image):
        """Test image analysis with Gemini"""
        print("\n" + "="*70)
        print("TEST 2.5: Analyze Image with Gemini (API)")
        print("="*70)

        description = vision_service.analyze_image(sample_image)
        assert isinstance(description, str)
        assert len(description) > 0

        print(f"✓ Image analyzed: {description[:100]}...")

    @pytest.mark.skip(reason="Requires valid Gemini API key")
    def test_extract_image_text_with_gemini(self, vision_service, sample_image):
        """Test text extraction with Gemini"""
        print("\n" + "="*70)
        print("TEST 2.6: Extract Image Text with Gemini (API)")
        print("="*70)

        text = vision_service.extract_image_text(sample_image)
        assert isinstance(text, str)

        print(f"✓ Text extracted: {text[:100] if text else 'No text found'}...")


# ============================================================================
# TEST 3: Multimodal Search (5 tests)
# ============================================================================

class TestMultimodalSearch:
    """Test multimodal search functionality"""

    @pytest.fixture
    def sample_documents(self):
        """Create sample documents"""
        return [
            {
                "id": "doc_1",
                "text": "Machine learning is a subset of artificial intelligence",
                "metadata": {"source": "ml_guide.pdf"}
            },
            {
                "id": "doc_2",
                "text": "Deep learning uses neural networks for data processing",
                "metadata": {"source": "dl_tutorial.pdf"}
            }
        ]

    @pytest.fixture
    def sample_images(self):
        """Create sample extracted images"""
        return [
            ExtractedImage(
                image_id="img_1",
                page_number=1,
                source_pdf="document.pdf",
                extraction_date="2024-01-01T00:00:00",
                extraction_method="pypdf"
            ),
            ExtractedImage(
                image_id="img_2",
                page_number=2,
                source_pdf="document.pdf",
                extraction_date="2024-01-01T00:00:00",
                extraction_method="pypdf"
            )
        ]

    def test_multimodal_engine_initialization(self, sample_documents, sample_images):
        """Test multimodal search engine initialization"""
        print("\n" + "="*70)
        print("TEST 3.1: Multimodal Engine Initialization")
        print("="*70)

        engine = MultimodalSearchEngine(sample_documents, extracted_images=sample_images)
        assert engine is not None
        assert len(engine.documents) == 2
        assert len(engine.extracted_images) == 2

        print("✓ Multimodal engine initialized")

    def test_add_images_to_engine(self, sample_documents, sample_images):
        """Test adding images to engine"""
        print("\n" + "="*70)
        print("TEST 3.2: Add Images to Engine")
        print("="*70)

        engine = MultimodalSearchEngine(sample_documents)
        assert len(engine.extracted_images) == 0

        engine.add_images(sample_images)
        assert len(engine.extracted_images) == 2

        print("✓ Images added to engine")

    def test_multimodal_statistics(self, sample_documents, sample_images):
        """Test statistics generation"""
        print("\n" + "="*70)
        print("TEST 3.3: Multimodal Statistics")
        print("="*70)

        engine = MultimodalSearchEngine(sample_documents, extracted_images=sample_images)
        stats = engine.get_multimodal_statistics()

        assert "text_search" in stats
        assert "image_search" in stats
        assert stats["total_searchable_items"] > 0

        print(f"✓ Statistics: {json.dumps(stats, indent=2)}")

    def test_image_statistics(self, sample_documents, sample_images):
        """Test image-specific statistics"""
        print("\n" + "="*70)
        print("TEST 3.4: Image Statistics")
        print("="*70)

        engine = MultimodalSearchEngine(sample_documents, extracted_images=sample_images)
        stats = engine.get_image_statistics()

        assert stats["total_images"] == 2
        assert "extraction_methods" in stats

        print(f"✓ Image stats: {json.dumps(stats, indent=2)}")

    def test_cache_clearing(self, sample_documents):
        """Test cache clearing"""
        print("\n" + "="*70)
        print("TEST 3.5: Cache Clearing")
        print("="*70)

        engine = MultimodalSearchEngine(sample_documents)
        engine.image_analysis_cache["test"] = "data"

        engine.clear_image_cache()
        assert len(engine.image_analysis_cache) == 0

        print("✓ Cache cleared successfully")


# ============================================================================
# TEST 4: Multimodal RAG Integration (4 tests)
# ============================================================================

class TestMultimodalRAGIntegration:
    """Test multimodal RAG engine integration"""

    def test_multimodal_rag_initialization(self):
        """Test multimodal RAG engine initialization"""
        print("\n" + "="*70)
        print("TEST 4.1: Multimodal RAG Initialization")
        print("="*70)

        engine = MultimodalRAGEngine()
        assert engine is not None
        assert hasattr(engine, 'image_extractor')
        assert hasattr(engine, 'vision_service')

        print("✓ Multimodal RAG engine initialized")

    def test_ingestion_stats(self):
        """Test ingestion statistics"""
        print("\n" + "="*70)
        print("TEST 4.2: Ingestion Statistics")
        print("="*70)

        stats = IngestionStats()
        stats.documents_processed = 1
        stats.images_extracted = 5
        stats.images_analyzed = 5

        assert stats.documents_processed == 1
        assert stats.images_extracted == 5

        print("✓ Ingestion stats working")

    def test_multimodal_rag_singleton(self):
        """Test RAG engine singleton"""
        print("\n" + "="*70)
        print("TEST 4.3: Multimodal RAG Singleton")
        print("="*70)

        engine1 = get_multimodal_rag_engine()
        engine2 = get_multimodal_rag_engine()
        assert engine1 is engine2

        print("✓ Singleton pattern working")

    def test_multimodal_statistics(self):
        """Test multimodal statistics"""
        print("\n" + "="*70)
        print("TEST 4.4: Multimodal Statistics")
        print("="*70)

        engine = MultimodalRAGEngine()
        stats = engine.get_multimodal_statistics()

        assert isinstance(stats, dict)
        assert "text_documents" in stats or "multimodal_engine_initialized" in stats

        print(f"✓ Stats: {json.dumps(stats, indent=2)}")


# ============================================================================
# TEST 5: Performance Benchmarks (3 tests)
# ============================================================================

class TestMultimodalPerformance:
    """Test performance characteristics"""

    def test_image_extraction_performance(self):
        """Benchmark image extraction"""
        print("\n" + "="*70)
        print("TEST 5.1: Image Extraction Performance")
        print("="*70)

        extractor = PDFImageExtractor()
        images = [
            ExtractedImage(
                image_id=f"img_{i}",
                page_number=i,
                source_pdf="test.pdf",
                extraction_date="2024-01-01T00:00:00"
            )
            for i in range(100)
        ]

        start = time.time()
        extractor.get_extraction_statistics(images)
        elapsed_ms = (time.time() - start) * 1000

        print(f"✓ Statistics for 100 images: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 100  # Should be very fast

    def test_multimodal_search_performance(self):
        """Benchmark multimodal search"""
        print("\n" + "="*70)
        print("TEST 5.2: Multimodal Search Performance")
        print("="*70)

        docs = [
            {"id": str(i), "text": f"Document {i} content", "metadata": {"source": f"doc_{i}.pdf"}}
            for i in range(50)
        ]

        engine = MultimodalSearchEngine(docs)
        start = time.time()
        stats = engine.get_multimodal_statistics()
        elapsed_ms = (time.time() - start) * 1000

        print(f"✓ Multimodal stats for 50 docs: {elapsed_ms:.2f}ms")
        assert elapsed_ms < 500

    def test_engine_memory_usage(self):
        """Test memory efficiency"""
        print("\n" + "="*70)
        print("TEST 5.3: Engine Memory Usage")
        print("="*70)

        import sys

        # Create engine with moderate data
        docs = [
            {"id": str(i), "text": "x" * 1000, "metadata": {"source": f"doc_{i}.pdf"}}
            for i in range(20)
        ]

        engine = MultimodalSearchEngine(docs)
        size = sys.getsizeof(engine)

        print(f"✓ Engine memory footprint: {size / 1024:.2f} KB")
        assert size < 10 * 1024 * 1024  # Less than 10MB


# ============================================================================
# Test Runner
# ============================================================================

def run_all_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("FASE 17: MULTIMODAL RAG - COMPREHENSIVE TEST SUITE")
    print("="*70)

    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-k", "not (Gemini or API)",
        "--color=yes"
    ])


if __name__ == "__main__":
    run_all_tests()
