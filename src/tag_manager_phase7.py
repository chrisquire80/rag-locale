"""
Document Tagging & Organization - Phase 7 Feature 1
Automatic tagging of documents using existing topic extraction
Enables document filtering and organization in UI
"""

from typing import List, Dict, Optional, Set
from collections import Counter
import logging

from src.logging_config import get_logger

logger = get_logger(__name__)


class TagManager:
    """Manages document tags for organization and filtering"""

    def __init__(self, max_tags_per_document: int = 3):
        """
        Initialize tag manager

        Args:
            max_tags_per_document: Maximum number of tags per document
        """
        self.max_tags_per_document = max_tags_per_document
        logger.info(f"Initialized TagManager (max {max_tags_per_document} tags per doc)")

    def extract_tags_for_document(
        self,
        filename: str,
        content: str,
        num_tags: int = 3
    ) -> List[str]:
        """
        Extract tags for a document using topic analysis

        Args:
            filename: Document filename
            content: Document content
            num_tags: Number of tags to extract

        Returns:
            List of tags (normalized, lowercase)
        """
        try:
            # Try to use existing topic analyzer if available
            try:
                from src.document_topic_analyzer import DocumentTopicAnalyzer
                analyzer = DocumentTopicAnalyzer()
                topics = analyzer.analyze_topics_hybrid(content)
                tags = [self.normalize_tag(topic) for topic in topics[:num_tags]]
                logger.debug(f"Extracted {len(tags)} tags from {filename}: {tags}")
                return tags
            except (ImportError, Exception) as e:
                logger.debug(f"Topic analyzer unavailable ({e}), using fallback")
                # Fallback: Extract tags from filename
                return self._extract_tags_from_filename(filename, num_tags)

        except Exception as e:
            logger.warning(f"Error extracting tags for {filename}: {e}")
            return []

    def _extract_tags_from_filename(self, filename: str, num_tags: int = 3) -> List[str]:
        """Fallback tag extraction from filename"""
        # Remove extension
        name = filename.rsplit(".", 1)[0] if "." in filename else filename

        # Split on common delimiters
        import re
        words = re.split(r"[-_\s]+", name.lower())

        # Filter common words
        common_words = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of"}
        words = [w for w in words if w and w not in common_words and len(w) > 2]

        return [self.normalize_tag(w) for w in words[:num_tags]]

    def normalize_tag(self, tag: str) -> str:
        """
        Normalize tag for consistency

        Args:
            tag: Raw tag string

        Returns:
            Normalized tag (lowercase, stripped, special chars removed)
        """
        # Lowercase
        tag = tag.lower().strip()

        # Remove special characters, keep only alphanumeric and hyphens
        import re
        tag = re.sub(r"[^\w\-]", "", tag)

        # Replace spaces with hyphens
        tag = tag.replace("_", "-")

        return tag

    def get_all_tags(self, documents_with_metadata: List[Dict]) -> Dict[str, int]:
        """
        Aggregate all unique tags from documents

        Args:
            documents_with_metadata: List of documents with metadata containing tags

        Returns:
            Dict of {tag: frequency} sorted by frequency
        """
        tag_counter = Counter()

        for doc in documents_with_metadata:
            metadata = doc.get("metadata", {})
            tags = metadata.get("tags", [])

            if isinstance(tags, list):
                tag_counter.update(tags)
            elif isinstance(tags, str):
                # Handle case where tags are comma-separated
                doc_tags = [self.normalize_tag(t) for t in tags.split(",")]
                tag_counter.update(doc_tags)

        # Return as sorted dict (most frequent first)
        return dict(sorted(tag_counter.items(), key=lambda x: x[1], reverse=True))

    def get_documents_by_tag(
        self,
        documents_with_metadata: List[Dict],
        tag: str
    ) -> List[str]:
        """
        Get document IDs that have a specific tag

        Args:
            documents_with_metadata: List of documents
            tag: Tag to filter by

        Returns:
            List of document filenames with this tag
        """
        normalized_tag = self.normalize_tag(tag)
        matching_docs = []

        for doc in documents_with_metadata:
            metadata = doc.get("metadata", {})
            tags = metadata.get("tags", [])

            if isinstance(tags, list):
                normalized_tags = [self.normalize_tag(t) for t in tags]
                if normalized_tag in normalized_tags:
                    matching_docs.append(doc.get("source", doc.get("filename", "")))
            elif isinstance(tags, str):
                doc_tags = [self.normalize_tag(t) for t in tags.split(",")]
                if normalized_tag in doc_tags:
                    matching_docs.append(doc.get("source", doc.get("filename", "")))

        logger.info(f"Found {len(matching_docs)} documents with tag '{tag}'")
        return matching_docs

    def filter_by_tags(
        self,
        documents: List[Dict],
        tags: List[str],
        match_all: bool = False
    ) -> List[Dict]:
        """
        Filter documents by tags

        Args:
            documents: List of documents
            tags: Tags to filter by
            match_all: If True, document must have ALL tags. If False, ANY tag.

        Returns:
            Filtered list of documents
        """
        normalized_filters = [self.normalize_tag(t) for t in tags]
        filtered = []

        for doc in documents:
            metadata = doc.get("metadata", {})
            doc_tags = metadata.get("tags", [])

            if isinstance(doc_tags, str):
                doc_tags = [self.normalize_tag(t) for t in doc_tags.split(",")]
            else:
                doc_tags = [self.normalize_tag(t) for t in doc_tags]

            # Check if document matches filter criteria
            if match_all:
                # Document must have ALL filter tags
                if all(t in doc_tags for t in normalized_filters):
                    filtered.append(doc)
            else:
                # Document must have ANY filter tag
                if any(t in doc_tags for t in normalized_filters):
                    filtered.append(doc)

        logger.debug(f"Filtered to {len(filtered)} documents by tags")
        return filtered

    def suggest_tags(
        self,
        all_tags: Dict[str, int],
        user_input: str,
        max_suggestions: int = 5
    ) -> List[str]:
        """
        Suggest tags based on user input

        Args:
            all_tags: Dict of available tags and frequencies
            user_input: User's partial tag input
            max_suggestions: Maximum suggestions to return

        Returns:
            List of suggested tags
        """
        normalized_input = self.normalize_tag(user_input)

        # Find tags that start with or contain the input
        suggestions = [
            tag
            for tag in all_tags.keys()
            if normalized_input in tag or tag.startswith(normalized_input)
        ]

        # Sort by frequency
        suggestions.sort(key=lambda t: all_tags[t], reverse=True)

        return suggestions[:max_suggestions]
