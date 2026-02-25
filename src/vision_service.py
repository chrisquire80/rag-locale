"""
Vision Service - FASE 17 Multimodal RAG
Provides image analysis and text extraction using Google Gemini Vision API
"""

import time
import hashlib
import numpy as np
from typing import Optional, List
from pathlib import Path
from dataclasses import dataclass

try:
    from PIL import Image
except ImportError:
    raise ImportError("PIL not found. Install with: pip install pillow")

import google.genai as genai
from src.config import config
from src.cache import VisionProcessingCache
from src.logging_config import get_logger
from src.rate_limiter import rate_limit

logger = get_logger(__name__)


@dataclass
class ImageAnalysisResult:
    """Result of image analysis"""
    image_path: str
    description: str
    extracted_text: str
    relevance_score: float
    analysis_timestamp: str
    model: str = "gemini-2.0-flash"


class GeminiVisionService:
    """Vision analysis using Gemini API"""

    def __init__(self):
        """Initialize Gemini Vision Service"""
        self.api_key = config.gemini.api_key.get_secret_value()
        self.model_name = config.gemini.model_name
        self.client = genai.Client(api_key=self.api_key)
        self._cache = VisionProcessingCache(max_size=1000)
        logger.info("✓ GeminiVisionService initialized with caching enabled")

    def _compute_image_hash(self, image_path: str) -> Optional[str]:
        """
        Compute SHA-256 hash of image file for cache deduplication

        Args:
            image_path: Path to image file

        Returns:
            SHA-256 hash string or None if hash computation fails
        """
        try:
            with open(image_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Could not hash image {image_path}: {e}")
            return None

    @rate_limit(endpoint_name="vision_analyze", tokens_cost=5.0)
    def analyze_image(self, image_path: str) -> str:
        """
        Analyze image and generate description

        Args:
            image_path: Path to image file

        Returns:
            Image description from Gemini
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Compute image hash for content-based caching
        image_hash = self._compute_image_hash(str(image_path))
        if image_hash:
            cached = self._cache.get_by_hash(image_hash)
            if cached is not None:
                logger.debug(f"Using cached analysis for {image_path.name} (hash: {image_hash[:8]}...)")
                return cached

        try:
            # Read image
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Call Gemini Vision API
            prompt = """Analyze this image and provide a detailed description of:
1. Main objects and elements visible
2. Layout and composition
3. Text or data visible in the image
4. Key information that would be useful for document search
5. Any charts, diagrams, or structured information

Be concise but comprehensive."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": self._get_mime_type(image_path),
                                    "data": image_data
                                }
                            },
                            prompt
                        ]
                    }
                ],
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": 500
                }
            )

            description = response.text if response.text else "No analysis available"
            if image_hash:
                self._cache.set_by_hash(image_hash, description)
            logger.debug(f"✓ Analyzed image: {image_path.name}")
            return description

        except Exception as e:
            logger.error(f"Image analysis failed for {image_path}: {e}")
            raise

    @rate_limit(endpoint_name="vision_extract", tokens_cost=3.0)
    def extract_image_text(self, image_path: str) -> str:
        """
        Extract text from image (OCR-like functionality)

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Compute image hash for content-based caching
        image_hash = self._compute_image_hash(str(image_path))
        if image_hash:
            cached = self._cache.get_by_hash(f"ocr_{image_hash}")
            if cached is not None:
                logger.debug(f"Using cached OCR for {image_path.name} (hash: {image_hash[:8]}...)")
                return cached

        try:
            # Read image
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Call Gemini Vision API with OCR focus
            prompt = """Extract all text visible in this image.
Format the text exactly as it appears.
If there are tables or structured data, preserve the structure."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": self._get_mime_type(image_path),
                                    "data": image_data
                                }
                            },
                            prompt
                        ]
                    }
                ],
                generation_config={
                    "temperature": 0.0,  # Deterministic for OCR
                    "max_output_tokens": 1000
                }
            )

            extracted_text = response.text if response.text else ""
            if image_hash:
                self._cache.set_by_hash(f"ocr_{image_hash}", extracted_text)
            logger.debug(f"✓ Extracted text from image: {image_path.name}")
            return extracted_text

        except Exception as e:
            logger.error(f"Text extraction failed for {image_path}: {e}")
            raise

    def evaluate_image_relevance(
        self,
        image_path: str,
        query: str
    ) -> float:
        """
        Evaluate how relevant an image is to a query

        Args:
            image_path: Path to image file
            query: Search query

        Returns:
            Relevance score between 0.0 and 1.0
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Compute image hash for content-based caching
        image_hash = self._compute_image_hash(str(image_path))
        if image_hash:
            # Create cache key that includes both image hash and query
            # Use MD5 hash of normalized query to keep key reasonable length
            query_key = hashlib.sha256(query.lower().encode()).hexdigest()[:16]
            cache_key = f"relevance_{image_hash}_{query_key}"
            cached = self._cache.get_by_hash(cache_key)
            if cached is not None:
                logger.debug(f"Using cached relevance score for {image_path.name}")
                return cached

        try:
            # Read image
            with open(image_path, "rb") as f:
                image_data = f.read()

            # Call Gemini Vision API for relevance scoring
            prompt = f"""On a scale of 0-100, how relevant is this image to the following query?

Query: "{query}"

Consider:
1. Direct relevance of content to the query
2. How useful this image would be in answering the query
3. Content overlap with query terms

Respond with ONLY a number from 0 to 100, then briefly explain (one sentence)."""

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": self._get_mime_type(image_path),
                                    "data": image_data
                                }
                            },
                            prompt
                        ]
                    }
                ],
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 100
                }
            )

            # Parse score from response
            response_text = response.text.strip()
            try:
                # Extract first number from response
                score_str = response_text.split()[0]
                score = float(score_str) / 100.0  # Normalize to 0-1
                score = max(0.0, min(1.0, score))  # Clamp to [0, 1]

                # Cache the relevance score
                if image_hash:
                    self._cache.set_by_hash(cache_key, score)

                logger.debug(
                    f"✓ Relevance score for {image_path.name}: {score:.2f}"
                )
                return score
            except (ValueError, IndexError):
                logger.warning(
                    f"Could not parse relevance score from: {response_text}"
                )
                return 0.0

        except Exception as e:
            logger.error(
                f"Relevance evaluation failed for {image_path}: {e}"
            )
            return 0.0

    def generate_image_embedding(
        self,
        image_path: str,
        query_context: Optional[str] = None
    ) -> np.ndarray:
        """
        Generate embedding for image content

        Args:
            image_path: Path to image file
            query_context: Optional query for contextual embedding

        Returns:
            Embedding as numpy array
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            # First, get image description
            description = self.analyze_image(str(image_path))

            # Combine with OCR text
            ocr_text = self.extract_image_text(str(image_path))
            combined_text = f"{description}\n\n{ocr_text}"

            if query_context:
                combined_text = f"Query: {query_context}\n\nImage Analysis:\n{combined_text}"

            # Get embedding for the combined text
            from llm_service import get_llm_service
            llm = get_llm_service()
            embedding = llm.get_embedding(combined_text)

            logger.debug(f"✓ Generated embedding for {image_path.name}")
            return np.array(embedding)

        except Exception as e:
            logger.error(f"Embedding generation failed for {image_path}: {e}")
            # Return zero embedding on failure
            return np.zeros(768)

    def batch_analyze_images(
        self,
        image_paths: List[str],
        query: Optional[str] = None
    ) -> List[ImageAnalysisResult]:
        """
        Analyze multiple images (with rate limiting)

        Args:
            image_paths: List of image file paths
            query: Optional query for relevance scoring

        Returns:
            List of ImageAnalysisResult objects
        """
        results = []
        for i, image_path in enumerate(image_paths):
            try:
                logger.info(f"Analyzing image {i+1}/{len(image_paths)}: {Path(image_path).name}")

                description = self.analyze_image(image_path)
                extracted_text = self.extract_image_text(image_path)
                relevance = (
                    self.evaluate_image_relevance(image_path, query)
                    if query
                    else 0.5
                )

                results.append(
                    ImageAnalysisResult(
                        image_path=image_path,
                        description=description,
                        extracted_text=extracted_text,
                        relevance_score=relevance,
                        analysis_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                        model=self.model_name
                    )
                )

                # Rate limiting: wait 1 second between requests
                if i < len(image_paths) - 1:
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to analyze {image_path}: {e}")

        return results

    def _get_mime_type(self, image_path: Path) -> str:
        """Get MIME type for image"""
        suffix = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp"
        }
        return mime_types.get(suffix, "image/png")

    def clear_cache(self):
        """Clear analysis cache"""
        self._cache.clear()
        logger.info("✓ Vision service cache cleared")


    def detect_objects_in_image(self, image_bytes: bytes, prompt: str) -> str:
        """
        Detect objects in an image using a custom prompt.
        Returns the raw text response (expected to be JSON).
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": image_bytes
                                }
                            },
                            prompt
                        ]
                    }
                ],
                generation_config={
                    "temperature": 0.0,
                    "max_output_tokens": 1000
                }
            )
            return response.text if response.text else "[]"
        except Exception as e:
            logger.error(f"Object detection call failed: {e}")
            raise

def get_vision_service() -> GeminiVisionService:
    """Get or create Vision Service singleton"""
    if not hasattr(get_vision_service, "_instance"):
        get_vision_service._instance = GeminiVisionService()
    return get_vision_service._instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test
    service = get_vision_service()
    # Add test code here
