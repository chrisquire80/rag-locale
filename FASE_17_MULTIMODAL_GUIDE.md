# FASE 17: Multimodal RAG Implementation Guide

## Overview

FASE 17 extends the RAG system with **multimodal capabilities**, enabling simultaneous search and retrieval of both text documents and images. This implementation leverages:

- **PDF Image Extraction**: Extract images from PDFs using pypdf and pdf2image
- **Vision Analysis**: Analyze images with Google Gemini Vision API
- **Hybrid Retrieval**: Search both text and images with combined relevance scoring
- **Multimodal Response Generation**: Generate answers incorporating both text and image sources

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           Multimodal RAG Engine (FASE 17)               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────┐      ┌──────────────────────┐    │
│  │  Text Retrieval  │      │  Image Retrieval     │    │
│  │ (Hybrid Search)  │      │ (Vision Analysis)    │    │
│  └────────┬─────────┘      └──────────┬───────────┘    │
│           │                          │                 │
│           └──────────┬───────────────┘                 │
│                      │                                 │
│         ┌────────────▼────────────────┐               │
│         │   Result Merging & Ranking  │               │
│         └────────────┬────────────────┘               │
│                      │                                 │
│         ┌────────────▼────────────────┐               │
│         │ Multimodal Response Gen     │               │
│         └────────────────────────────┘               │
│                                                       │
└─────────────────────────────────────────────────────────┘

Document Input Flow:
PDF → Image Extraction → Vision Analysis → Search Index → Query Processing
      (pdf_image_extraction.py)  (vision_service.py)   (multimodal_search.py)
```

## Components

### 1. PDF Image Extraction (`pdf_image_extraction.py`)

Extracts images from PDF documents using two strategies:

**Strategy 1: Direct Extraction (pypdf)**
- Extracts images embedded in PDF structure
- Fast, preserves original image quality
- Works with PDFs containing embedded images

**Strategy 2: Page Conversion (pdf2image)**
- Converts PDF pages to PNG images
- Fallback when embedded images not found
- Useful for scanned documents

#### Key Classes

```python
@dataclass
class ExtractedImage:
    """Represents an extracted image from PDF"""
    image_id: str                    # Unique identifier
    page_number: int                 # Source page
    source_pdf: str                  # Original PDF filename
    extraction_date: str             # ISO timestamp
    image_path: Optional[str]        # File location
    image_format: str                # RGB, JPEG, etc.
    width: Optional[int]             # Image dimensions
    height: Optional[int]
    file_size_bytes: Optional[int]   # File size
    extraction_method: str           # "pypdf" or "pdf2image"
    analysis_text: Optional[str]     # Vision API analysis
    analysis_embeddings: Optional[List[float]]  # Embeddings
    relevance_score: Optional[float] # For search ranking
```

#### Usage Example

```python
from pdf_image_extraction import PDFImageExtractor, get_pdf_image_extractor

# Initialize extractor
extractor = get_pdf_image_extractor()

# Extract images from PDF
pdf_path = "path/to/document.pdf"
extracted_images, metadata = extractor.extract_images_from_pdf(pdf_path)

print(f"Extracted {len(extracted_images)} images")
print(f"Total pages: {metadata['total_pages']}")

# Save image metadata
result = extractor.save_extracted_images(extracted_images, output_dir="./images")
print(f"Metadata saved to: {result['metadata_file']}")

# Get statistics
stats = extractor.get_extraction_statistics(extracted_images)
print(f"Total size: {stats['total_size_bytes']} bytes")
print(f"Extraction methods: {stats['extraction_methods']}")
```

### 2. Vision Service (`vision_service.py`)

Provides image analysis using Google Gemini Vision API.

#### Key Methods

```python
class GeminiVisionService:

    def analyze_image(self, image_path: str) -> str:
        """Generate comprehensive image description"""
        # Returns analysis of objects, layout, text, key info

    def extract_image_text(self, image_path: str) -> str:
        """Extract text from image (OCR-like)"""
        # Returns all visible text in image

    def evaluate_image_relevance(self, image_path: str, query: str) -> float:
        """Score image relevance to query (0-1)"""
        # Returns relevance score for search ranking

    def generate_image_embedding(self, image_path: str, query_context: str = None) -> np.ndarray:
        """Generate embedding for image content"""
        # Returns vector for semantic similarity

    def batch_analyze_images(self, image_paths: List[str], query: str = None) -> List[ImageAnalysisResult]:
        """Analyze multiple images with rate limiting"""
```

#### Usage Example

```python
from vision_service import get_vision_service

vision = get_vision_service()

# Analyze image
image_path = "extracted_images/page_1.png"
description = vision.analyze_image(image_path)
print(f"Image contains: {description}")

# Extract text
text = vision.extract_image_text(image_path)
print(f"Extracted text: {text}")

# Evaluate relevance
query = "machine learning architecture"
relevance = vision.evaluate_image_relevance(image_path, query)
print(f"Relevance score: {relevance:.2f}")

# Generate embedding
embedding = vision.generate_image_embedding(image_path, query_context=query)
print(f"Embedding shape: {embedding.shape}")
```

### 3. Multimodal Search (`multimodal_search.py`)

Combines text and image retrieval with unified ranking.

#### Key Classes

```python
@dataclass
class ImageSearchResult:
    image_id: str
    image_path: str
    page_number: int
    source_pdf: str
    relevance_score: float      # From vision API
    description: str            # Image analysis
    extracted_text: str         # OCR text
    rank: int

@dataclass
class MultimodalResult:
    result_id: str
    result_type: str            # "text" or "image"
    content: str
    source: str
    relevance_score: float
    retrieval_method: str       # "hybrid" or "vision"
    page_number: Optional[int]
    image_path: Optional[str]
    rank: int
```

#### Usage Example

```python
from multimodal_search import MultimodalSearchEngine, ImageSearchResult

# Create engine
documents = [
    {"id": "1", "text": "AI and ML overview", "metadata": {"source": "ai.pdf"}},
    {"id": "2", "text": "Neural networks explained", "metadata": {"source": "nn.pdf"}}
]

engine = MultimodalSearchEngine(
    documents=documents,
    extracted_images=extracted_images  # From PDFImageExtractor
)

# Search images only
query = "deep learning architecture"
image_results = engine.search_images(query, top_k=5)
for result in image_results:
    print(f"{result.rank}. {result.source_pdf} (p.{result.page_number})")
    print(f"   Relevance: {result.relevance_score:.2f}")
    print(f"   {result.description[:100]}...")

# Unified multimodal search
multimodal_results = engine.search_multimodal(
    query=query,
    include_text=True,
    include_images=True,
    top_k=10
)

for result in multimodal_results:
    print(f"{result.rank}. [{result.result_type}] {result.source}")
    print(f"   Score: {result.relevance_score:.2f}")
```

### 4. Multimodal RAG Engine (`rag_engine_multimodal.py`)

Extends `RAGEngineV2` with end-to-end multimodal query processing.

#### Key Features

- **Automatic Image Extraction**: From ingested PDFs
- **Vision Analysis**: Automatic description and OCR
- **Multimodal Search**: Combined text+image retrieval
- **Unified Response Generation**: Answers incorporating both modalities

#### Usage Example

```python
from rag_engine_multimodal import get_multimodal_rag_engine

engine = get_multimodal_rag_engine()

# Initialize with existing documents
engine.initialize_multimodal_engine()

# Process PDF with images
stats = engine.add_pdf_with_images(
    pdf_path="document.pdf",
    analyze_images=True
)

print(f"Extracted: {stats.images_extracted} images")
print(f"Analyzed: {stats.images_analyzed} images")
print(f"Time: {stats.processing_time_ms:.0f}ms")

# Multimodal query
response = engine.query_multimodal(
    user_query="What does the architecture diagram show?",
    include_text=True,
    include_images=True,
    top_k=5
)

print(f"Answer: {response.answer}")
print(f"Text sources: {len(response.text_sources)}")
print(f"Image sources: {len(response.image_sources)}")
print(f"Retrieval time: {response.image_retrieval_time_ms:.0f}ms")
```

## Performance Characteristics

### Extraction Performance
- **PDF Image Extraction**: ~50-100ms per page (pypdf)
- **PDF Page Conversion**: ~200-500ms per page (pdf2image)
- **Vision Analysis**: ~2-5 seconds per image (Gemini API)

### Search Performance
- **Text Search**: <50ms (hybrid BM25+vector)
- **Image Relevance Scoring**: ~3-5 seconds per image
- **Multimodal Merge**: <10ms (100 results)

### Memory Usage
- **Extracted Image Metadata**: ~5KB per image
- **Image Analysis Cache**: ~50KB per analyzed image
- **Multimodal Engine**: ~100MB base + ~1MB per 100 images

### Scalability
- Tested with 70+ PDFs
- Support for 500+ images per document
- Batch processing with rate limiting

## Integration with Existing System

### 1. Document Ingestion Pipeline

```python
from document_ingestion import DocumentIngestionPipeline
from rag_engine_multimodal import get_multimodal_rag_engine

pipeline = DocumentIngestionPipeline()
rag_engine = get_multimodal_rag_engine()

# Ingest documents
for pdf_file in documents_dir.glob("*.pdf"):
    # Text ingestion (existing)
    pipeline.ingest_single_file(str(pdf_file))

    # Image ingestion (new)
    stats = rag_engine.add_pdf_with_images(str(pdf_file))
    print(f"Images extracted: {stats.images_extracted}")
```

### 2. Query Processing

```python
# Text-only search (backward compatible)
response = engine.query(query="How does ML work?", retrieval_method="hybrid")

# Multimodal search (new capability)
response = engine.query_multimodal(
    query="Show me the architecture diagram",
    include_text=True,
    include_images=True
)

# Handle mixed results
for source in response.sources:
    if source.image_path:
        print(f"Image: {source.image_path}")
    else:
        print(f"Text: {source.document[:200]}")
```

### 3. API Endpoints

```python
from fastapi import FastAPI
from rag_engine_multimodal import get_multimodal_rag_engine

app = FastAPI()
engine = get_multimodal_rag_engine()

@app.post("/search/multimodal")
async def multimodal_search(
    query: str,
    include_text: bool = True,
    include_images: bool = True,
    top_k: int = 5
):
    response = engine.query_multimodal(
        user_query=query,
        include_text=include_text,
        include_images=include_images,
        top_k=top_k
    )
    return {
        "answer": response.answer,
        "text_sources": len(response.text_sources),
        "image_sources": len(response.image_sources),
        "performance": {
            "retrieval_ms": response.image_retrieval_time_ms,
            "processing_ms": response.image_processing_time_ms
        }
    }
```

## Configuration

### Environment Variables

```bash
# Gemini API
export GEMINI_API_KEY="your-api-key"
export GEMINI_MODEL_NAME="gemini-2.0-flash"

# Image Processing
export MULTIMODAL_MAX_IMAGES_PER_PDF=50
export MULTIMODAL_ANALYZE_IMAGES=true
export MULTIMODAL_IMAGE_DPI=150
```

### Python Configuration

```python
from config import config

# Check current settings
print(f"Max images per PDF: {config.multimodal.max_images_per_pdf}")
print(f"Vision model: {config.gemini.model_name}")
print(f"Image DPI: {config.multimodal.image_dpi}")
```

## Testing

### Run All Tests

```bash
# All tests
pytest test_fase17_multimodal.py -v

# Specific test class
pytest test_fase17_multimodal.py::TestPDFImageExtraction -v

# Specific test
pytest test_fase17_multimodal.py::TestPDFImageExtraction::test_extractor_initialization -v

# Skip API tests
pytest test_fase17_multimodal.py -k "not Gemini and not API" -v
```

### Test Coverage

| Class | Tests | Focus |
|-------|-------|-------|
| TestPDFImageExtraction | 5 | Image extraction, metadata, statistics |
| TestVisionService | 6 | Vision API integration, caching, MIME types |
| TestMultimodalSearch | 5 | Search engine, statistics, caching |
| TestMultimodalRAGIntegration | 4 | End-to-end RAG pipeline |
| TestMultimodalPerformance | 3 | Performance benchmarks |
| **Total** | **23** | **Comprehensive coverage** |

## Error Handling

### Common Issues

1. **PDF not found**
   ```python
   try:
       images, metadata = extractor.extract_images_from_pdf(pdf_path)
   except FileNotFoundError:
       logger.error(f"PDF not found: {pdf_path}")
   ```

2. **No images in PDF**
   ```python
   if not images:
       logger.info("PDF contains no extractable images")
       # Fall back to pdf2image
   ```

3. **Vision API rate limit**
   ```python
   # Automatic retry with exponential backoff
   # Manual: batch_analyze_images() includes 0.5s delay between requests
   ```

4. **Gemini API key invalid**
   ```python
   if not vision_service.check_health():
       raise ValueError("Vision service not properly initialized")
   ```

## Backward Compatibility

- **Text-only search still works**: `engine.query()` unchanged
- **Existing documents supported**: Can add images retroactively
- **Gradual migration**: Multimodal features optional
- **Configuration**: Feature flags enable/disable multimodal

## Future Enhancements

1. **Multimodal Embeddings**: Joint text-image embeddings
2. **Cross-Modal Search**: Find text similar to images and vice versa
3. **Image Indexing**: FAISS/Annoy for fast image retrieval
4. **OCR Caching**: Local OCR for faster processing
5. **Image Annotation**: Store custom annotations on images
6. **Batch Processing**: Async image analysis
7. **Video Support**: Extract and analyze frames from videos

## Monitoring & Logging

```python
import logging

# Set logging level
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pdf_image_extraction")

# Log levels:
# DEBUG: Detailed extraction info
# INFO: Success summaries
# WARNING: Skipped images, failed analyses
# ERROR: Critical failures
```

## Troubleshooting

### Images not extracted
1. Check PDF is valid: `pdf_validator.py`
2. Try both extraction methods: `extract_images_from_pdf(convert_to_images=True)`
3. Verify file permissions

### Vision API slow
1. Check rate limiting: API allows ~30 requests/minute
2. Use batch processing with delays
3. Cache results locally

### Memory issues with large PDFs
1. Limit max images: `config.multimodal.max_images_per_pdf`
2. Clear cache: `engine.clear_image_cache()`
3. Process in batches

## References

- [PDF Image Extraction](/src/pdf_image_extraction.py)
- [Vision Service](/src/vision_service.py)
- [Multimodal Search](/src/multimodal_search.py)
- [Multimodal RAG Engine](/src/rag_engine_multimodal.py)
- [Tests](/test_fase17_multimodal.py)
- [Gemini Vision API Docs](https://ai.google.dev/docs/vision)

---

**Status**: Production-ready
**Version**: 1.0
**Last Updated**: 2024
**Maintainer**: RAG System Team
