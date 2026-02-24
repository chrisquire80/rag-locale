"""
Semantic Document Summarizer
Generates automatic summaries and extracts key points from documents using LLM.
Provides efficient caching and batch processing capabilities.
"""

import logging
import hashlib
import json
from typing import Optional
from datetime import datetime
import time

from src.entity_extractor import get_entity_extractor

logger = logging.getLogger(__name__)

class DocumentSummarizer:
    """Generates semantic summaries and key points from document content using LLM."""

    # Configuration
    MAX_SUMMARY_TOKENS = 200
    MAX_KEYPOINTS = 5
    MIN_CONTENT_LENGTH = 100
    SUMMARY_CACHE_DIR = ".summary_cache"

    def __init__(self, llm_service=None):
        """
        Initialize DocumentSummarizer.

        Args:
            llm_service: Optional LLMService instance for summary generation.
                        If None, uses basic keyword extraction fallback.
        """
        self.llm_service = llm_service
        self.summary_cache: dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Load summary cache from file if available."""
        try:
            import os
            cache_file = os.path.join(self.SUMMARY_CACHE_DIR, "summaries.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    self.summary_cache = json.load(f)
                logger.info(f"Loaded {len(self.summary_cache)} cached summaries")
        except Exception as e:
            logger.warning(f"Failed to load summary cache: {e}")
            self.summary_cache = {}

    def _save_cache(self):
        """Save summary cache to file."""
        try:
            import os
            os.makedirs(self.SUMMARY_CACHE_DIR, exist_ok=True)
            cache_file = os.path.join(self.SUMMARY_CACHE_DIR, "summaries.json")
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(self.summary_cache, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save summary cache: {e}")

    def _get_content_hash(self, content: str) -> str:
        """Generate hash of content for caching."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def summarize_document(
        self,
        filename: str,
        content: str,
        max_length: int = 200,
        use_cache: bool = True
    ) -> str:
        """
        Generate a semantic summary of document content.

        Args:
            filename: Document filename for logging
            content: Full document text content
            max_length: Maximum summary length in tokens (approximate)
            use_cache: Whether to use cached summaries

        Returns:
            Summary string, empty string if generation fails
        """
        try:
            if not content or len(content) < self.MIN_CONTENT_LENGTH:
                logger.warning(f"Content too short to summarize: {filename}")
                return ""

            # Use first 3000 chars to avoid token limits
            content_sample = content[:3000]
            content_hash = self._get_content_hash(content_sample)

            # Check cache
            if use_cache and content_hash in self.summary_cache:
                cache_entry = self.summary_cache[content_hash]
                logger.info(f"Using cached summary for {filename}")
                return cache_entry.get("summary", "")

            # Try LLM-based summarization first
            if self.llm_service:
                summary = self._summarize_llm(content_sample, max_length)
            else:
                # Fallback to extractive summarization
                summary = self._summarize_extractive(content_sample)

            # Cache the result
            self.summary_cache[content_hash] = {
                "summary": summary,
                "timestamp": datetime.now().isoformat(),
                "length": len(summary.split()),
            }
            self._save_cache()

            return summary

        except Exception as e:
            logger.warning(f"Failed to summarize {filename}: {e}")
            return ""

    def _summarize_llm(self, content: str, max_length: int) -> str:
        """
        Generate summary using LLM (Gemini).

        Args:
            content: Document text to summarize
            max_length: Maximum summary length

        Returns:
            Summary string
        """
        try:
            prompt = f"""Please provide a concise summary of the following document in {max_length} words or less.
The summary should capture the main ideas and key information.

Document:
{content}

Summary:"""

            # Use centralized LLM wrapper with retry logic and error handling
            summary = self.llm_service.generate_response(prompt)

            if summary:
                summary = summary.strip()
                # Ensure it doesn't exceed max_length
                words = summary.split()
                if len(words) > max_length:
                    summary = " ".join(words[:max_length])
                return summary

            return ""

        except Exception as e:
            logger.warning(f"LLM summarization failed, using extractive: {e}")
            return self._summarize_extractive(content)

    def _summarize_extractive(self, content: str) -> str:
        """
        Extract key sentences as summary (fallback method).

        Args:
            content: Document text

        Returns:
            Extractive summary
        """
        try:
            # Split into sentences
            sentences = content.split(".")
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            if not sentences:
                return content[:200]

            # Score sentences by word frequency
            all_words = content.lower().split()
            word_freq = {}
            for word in all_words:
                if len(word) > 4:  # Only significant words
                    word_freq[word] = word_freq.get(word, 0) + 1

            sentence_scores = {}
            for i, sentence in enumerate(sentences[:10]):  # Limit to first 10
                score = 0
                for word in sentence.lower().split():
                    score += word_freq.get(word, 0)
                sentence_scores[i] = score

            # Select top 3 sentences
            top_sentences = sorted(
                sentence_scores.items(), key=lambda x: x[1], reverse=True
            )[:3]
            top_sentences = sorted(top_sentences, key=lambda x: x[0])

            summary = ". ".join([sentences[i] for i, _ in top_sentences])
            return summary[:200]  # Limit to 200 chars

        except Exception as e:
            logger.warning(f"Extractive summarization failed: {e}")
            return ""

    def extract_key_points(
        self, filename: str, content: str, num_points: int = 5
    ) -> list[str]:
        """
        Extract key points/bullet points from document content.

        Args:
            filename: Document filename for logging
            content: Document text content
            num_points: Number of key points to extract

        Returns:
            List of key point strings
        """
        try:
            if not content or len(content) < self.MIN_CONTENT_LENGTH:
                return []

            # Use first 2000 chars
            content_sample = content[:2000]

            # Try LLM-based extraction
            if self.llm_service:
                return self._extract_keypoints_llm(content_sample, num_points)
            else:
                # Fallback to keyword-based extraction
                return self._extract_keypoints_keywords(content_sample, num_points)

        except Exception as e:
            logger.warning(f"Failed to extract key points from {filename}: {e}")
            return []

    def _extract_keypoints_llm(
        self, content: str, num_points: int
    ) -> list[str]:
        """
        Extract key points using LLM.

        Args:
            content: Document text to analyze
            num_points: Number of points to extract

        Returns:
            List of key points
        """
        try:
            prompt = f"""Extract exactly {num_points} key points from the following document.
Return ONLY the bullet points as a numbered list with no additional text.

Document:
{content}

Key Points:"""

            # Use centralized LLM wrapper with retry logic and error handling
            response_text = self.llm_service.generate_response(prompt)

            if response_text:
                # Parse numbered list
                lines = response_text.strip().split("\n")
                points = []
                for line in lines:
                    # Remove numbering (1., 2., etc.)
                    cleaned = line.strip()
                    if cleaned and cleaned[0].isdigit():
                        cleaned = cleaned.split(".", 1)[1].strip() if "." in cleaned else cleaned
                    if cleaned:
                        points.append(cleaned)
                return points[:num_points]

            return []

        except Exception as e:
            logger.warning(f"LLM key point extraction failed: {e}")
            return self._extract_keypoints_keywords(content, num_points)

    def _extract_keypoints_keywords(
        self, content: str, num_points: int
    ) -> list[str]:
        """
        Extract key points using keyword analysis (fallback).

        Delegated to centralized EntityExtractor to eliminate
        duplicated keyword extraction logic.

        Args:
            content: Document text
            num_points: Number of points to extract

        Returns:
            List of key points based on frequent terms
        """
        try:
            # Use centralized entity extractor
            entity_extractor = get_entity_extractor()
            keywords = entity_extractor.extract_keywords(
                content,
                num_keywords=num_points,
                use_llm=False,  # Use frequency-based for speed
                remove_stopwords=True
            )
            return keywords if keywords else []

        except Exception as e:
            logger.warning(f"Keyword extraction failed: {e}")
            return []

    def get_summary_stats(self, summary: str) -> Dict:
        """
        Get statistics about a summary.

        Args:
            summary: Summary text

        Returns:
            Dictionary with stats: word_count, char_count, readability
        """
        try:
            words = summary.split()
            return {
                "word_count": len(words),
                "char_count": len(summary),
                "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
            }
        except Exception as e:
            logger.warning(f"Failed to compute summary stats: {e}")
            return {"word_count": 0, "char_count": 0, "avg_word_length": 0}

    def summarize_batch(
        self,
        documents: list[tuple[str, str]],
        callback=None
    ) -> list[str]:
        """
        Summarize multiple documents efficiently.

        Args:
            documents: List of (filename, content) tuples
            callback: Optional progress callback

        Returns:
            List of summary strings in same order as input
        """
        summaries = []

        for i, (filename, content) in enumerate(documents):
            if callback and hasattr(callback, "on_item_progress"):
                callback.on_item_progress(i, len(documents), filename)

            summary = self.summarize_document(filename, content)
            summaries.append(summary)

            time.sleep(0.1)  # Rate limiting for API

        return summaries

    def clear_cache(self):
        """Clear all cached summaries."""
        self.summary_cache = {}
        self._save_cache()
        logger.info("Cleared summary cache")

    def get_cache_stats(self) -> Dict:
        """
        Get statistics about the summary cache.

        Returns:
            Dictionary with cache size and entry count
        """
        return {
            "cached_summaries": len(self.summary_cache),
            "cache_size_bytes": len(json.dumps(self.summary_cache)),
        }
