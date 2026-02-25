"""
Document Tag Manager
Extracts, manages, and aggregates document tags using LLM-based analysis.
Tags are stored in chunk metadata for filtering and organization.
"""

import re
from typing import List, Dict, Any, Optional
from collections import defaultdict

from src.logging_config import get_logger

logger = get_logger(__name__)

class TagManager:
    """Manages document tags using LLM-based extraction"""

    def __init__(self, llm_service=None):
        """
        Initialize TagManager.

        Args:
            llm_service: Optional LLMService instance for tag extraction.
                        If None, uses keyword-based extraction fallback.
        """
        self.llm_service = llm_service
        self.tag_cache: dict[str, list[str]] = {}

    def extract_tags_for_document(
        self, filename: str, content: str, num_tags: int = 3
    ) -> list[str]:
        """
        Extract tags from document content using LLM or keyword fallback.

        Args:
            filename: Name of the document
            content: Document text content (first 2000 chars used for efficiency)
            num_tags: Number of tags to extract (default 3)

        Returns:
            List of normalized tag strings, empty list if extraction fails
        """
        try:
            # Use only first 2000 chars to avoid token limits
            text_sample = content[:2000] if content else ""

            if not text_sample:
                logger.warning(f"No content to extract tags from: {filename}")
                return []

            # Try LLM-based extraction first if service available
            if self.llm_service:
                return self._extract_tags_llm(text_sample, num_tags)
            else:
                # Fallback to keyword-based extraction
                return self._extract_tags_keywords(text_sample, num_tags)

        except Exception as e:
            logger.warning(f"Failed to extract tags from {filename}: {e}")
            return []

    def _extract_tags_llm(self, text_sample: str, num_tags: int) -> list[str]:
        """
        Extract tags using LLM-based analysis.

        Args:
            text_sample: Document text to analyze
            num_tags: Number of tags to extract

        Returns:
            List of tags
        """
        try:
            prompt = f"""Analyze the following document excerpt and extract exactly {num_tags} brief, concise tags that describe the main topics.

Document excerpt:
{text_sample}

Return ONLY the tags as a comma-separated list with no explanations. Each tag should be 1-3 words.
Example: machine learning, data science, AI"""

            response = self.llm_service.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                generation_config={"max_output_tokens": 100, "temperature": 0.3},
            )

            if response.text:
                tags = [self.normalize_tag(tag) for tag in response.text.split(",")]
                tags = [t for t in tags if t]  # Remove empty strings
                return tags[:num_tags]  # Limit to requested number

            return []

        except Exception as e:
            logger.warning(f"LLM tag extraction failed, falling back to keywords: {e}")
            return self._extract_tags_keywords(text_sample, num_tags)

    def _extract_tags_keywords(self, text_sample: str, num_tags: int) -> list[str]:
        """
        Extract tags using keyword-based analysis (fallback).

        Args:
            text_sample: Document text to analyze
            num_tags: Number of tags to extract

        Returns:
            List of tags based on common keywords
        """
        try:
            text_lower = text_sample.lower()

            # Define keyword categories
            keyword_categories = {
                "Machine Learning": [
                    "machine learning",
                    "neural network",
                    "deep learning",
                    "algorithm",
                    "model training",
                ],
                "Data Science": ["data science", "data analysis", "dataset", "statistics"],
                "Python": ["python", "programming", "code", "script"],
                "Web Development": ["web", "html", "css", "javascript", "api", "backend"],
                "Cloud": ["cloud", "aws", "azure", "gcp", "kubernetes"],
                "Security": ["security", "encryption", "authentication", "vulnerability"],
                "Database": ["database", "sql", "mongodb", "sql server", "postgresql"],
                "DevOps": ["devops", "docker", "ci/cd", "deployment", "infrastructure"],
                "AI": ["ai", "artificial intelligence", "nlp", "computer vision"],
                "Business": ["business", "strategy", "management", "sales", "marketing"],
            }

            # Count keyword matches
            tag_scores: dict[str, int] = {}
            for category, keywords in keyword_categories.items():
                score = sum(text_lower.count(keyword) for keyword in keywords)
                if score > 0:
                    tag_scores[category] = score

            # Return top N categories as tags
            if tag_scores:
                sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
                return [tag[0] for tag in sorted_tags[:num_tags]]

            # If no keyword matches, extract common words
            words = re.findall(r"\b\w{4,}\b", text_lower)  # Words 4+ chars
            word_freq = defaultdict(int)
            for word in words:
                # Skip common stop words
                if word not in {
                    "that",
                    "this",
                    "with",
                    "from",
                    "also",
                    "have",
                    "been",
                    "such",
                }:
                    word_freq[word] += 1

            if word_freq:
                top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[
                    :num_tags
                ]
                return [word[0].capitalize() for word in top_words]

            return []

        except Exception as e:
            logger.warning(f"Keyword tag extraction failed: {e}")
            return []

    def get_all_tags(self, vector_store) -> dict[str, int]:
        """
        Aggregate all unique tags from indexed documents with frequency counts.

        Args:
            vector_store: ChromaVectorStore instance

        Returns:
            Dict mapping tag name to count of documents with that tag
        """
        try:
            tag_counts: dict[str, int] = defaultdict(int)

            # Get all documents from vector store
            all_docs = vector_store.get_all_documents()

            for doc in all_docs:
                # Extract tags from metadata
                if hasattr(doc, "metadata"):
                    tags = doc.metadata.get("tags", [])
                elif isinstance(doc, dict):
                    tags = doc.get("metadata", {}).get("tags", [])
                else:
                    continue

                # Count each tag
                if isinstance(tags, list):
                    for tag in tags:
                        if tag:
                            tag_counts[tag] += 1

            return dict(tag_counts)

        except Exception as e:
            logger.warning(f"Failed to aggregate tags: {e}")
            return {}

    def get_documents_by_tag(self, vector_store, tag: str) -> list[str]:
        """
        Get list of document filenames that have a specific tag.

        Args:
            vector_store: ChromaVectorStore instance
            tag: Tag to search for

        Returns:
            List of document filenames with this tag
        """
        try:
            documents = []

            # Get all documents from vector store
            all_docs = vector_store.get_all_documents()

            for doc in all_docs:
                # Extract tags from metadata
                if hasattr(doc, "metadata"):
                    tags = doc.metadata.get("tags", [])
                    filename = doc.metadata.get("filename", "")
                elif isinstance(doc, dict):
                    tags = doc.get("metadata", {}).get("tags", [])
                    filename = doc.get("metadata", {}).get("filename", "")
                else:
                    continue

                # Check if document has this tag
                if isinstance(tags, list) and tag in tags and filename:
                    if filename not in documents:
                        documents.append(filename)

            return documents

        except Exception as e:
            logger.warning(f"Failed to get documents by tag: {e}")
            return []

    def normalize_tag(self, tag: str) -> str:
        """
        Normalize tag string: lowercase, strip whitespace, remove special chars.

        Args:
            tag: Raw tag string

        Returns:
            Normalized tag string
        """
        if not tag:
            return ""

        # Strip whitespace
        tag = tag.strip()

        # Lowercase
        tag = tag.lower()

        # Remove special characters, keep alphanumeric and spaces/hyphens
        tag = re.sub(r"[^a-z0-9\s\-]", "", tag)

        # Remove extra whitespace
        tag = re.sub(r"\s+", " ", tag).strip()

        # Remove leading/trailing hyphens
        tag = tag.strip("-")

        return tag if tag else ""

    def build_tag_filter(self, selected_tags: list[str]) -> Optional[Dict]:
        """
        Build a metadata filter for vector store search by tags.

        Args:
            selected_tags: List of tags to filter by

        Returns:
            Dictionary in ChromaDB where_filter format, or None if no tags
        """
        if not selected_tags:
            return None

        # Build filter for ChromaDB metadata search
        # Using $in operator for "contains any of these tags"
        return {
            "$or": [{"tags": {"$eq": tag}} for tag in selected_tags]
        }
