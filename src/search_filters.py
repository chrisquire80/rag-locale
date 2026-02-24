"""
Advanced Search Filters
Provides multi-criteria filtering for RAG queries with support for
document type, date range, tags, similarity threshold, and source documents.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class SearchFilter:
    """
    Multi-criteria search filter configuration.

    All filters are optional and work together with AND logic (all active filters must match).
    """

    # Document filtering
    document_types: Optional[list[str]] = None  # ["pdf", "txt", "md"]
    source_documents: Optional[list[str]] = None  # Specific filenames to limit search

    # Date range filtering
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    # Tag-based filtering
    tags: Optional[list[str]] = None  # Filter by document tags (OR within tags)

    # Relevance filtering
    similarity_threshold: float = 0.0  # Minimum similarity score (0.0-1.0)

    def is_empty(self) -> bool:
        """Check if any filters are actually set."""
        return (
            not self.document_types
            and not self.source_documents
            and not self.date_from
            and not self.date_to
            and not self.tags
            and self.similarity_threshold <= 0.0
        )

    def to_dict(self) -> Dict:
        """Convert filter to dictionary representation."""
        return {
            "document_types": self.document_types,
            "source_documents": self.source_documents,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "tags": self.tags,
            "similarity_threshold": self.similarity_threshold,
        }

class SearchFilterBuilder:
    """
    Builds and applies search filters for vector store queries.
    Converts high-level filter criteria to ChromaDB where_filter format.
    """

    @staticmethod
    def build_metadata_filter(filter: SearchFilter) -> Optional[Dict]:
        """
        Build ChromaDB metadata filter (where_filter) from SearchFilter criteria.

        Args:
            filter: SearchFilter instance with criteria

        Returns:
            Dictionary in ChromaDB where_filter format, or None if no filters

        Example:
            filter = SearchFilter(document_types=["pdf"], tags=["research"])
            where_filter = SearchFilterBuilder.build_metadata_filter(filter)
            # Returns: {"$and": [{"file_type": {"$eq": "pdf"}}, {"tags": {"$in": ["research"]}}]}
        """
        if filter.is_empty():
            return None

        conditions = []

        # Document type filter
        if filter.document_types:
            # Normalize document types to lowercase
            normalized_types = [dt.lower() for dt in filter.document_types]
            if len(normalized_types) == 1:
                conditions.append({"file_type": {"$eq": normalized_types[0]}})
            else:
                conditions.append({"file_type": {"$in": normalized_types}})

        # Source document filter
        if filter.source_documents:
            normalized_sources = [src.lower() for src in filter.source_documents]
            if len(normalized_sources) == 1:
                conditions.append({"filename": {"$eq": normalized_sources[0]}})
            else:
                conditions.append({"filename": {"$in": normalized_sources}})

        # Date range filter
        if filter.date_from or filter.date_to:
            date_condition = {}
            if filter.date_from:
                date_condition["$gte"] = filter.date_from.isoformat()
            if filter.date_to:
                date_condition["$lte"] = filter.date_to.isoformat()
            if date_condition:
                conditions.append({"ingestion_date": date_condition})

        # Tag filter (OR logic: match any of the tags)
        if filter.tags:
            normalized_tags = [tag.lower() for tag in filter.tags]
            if len(normalized_tags) == 1:
                conditions.append({"tags": {"$eq": normalized_tags[0]}})
            else:
                # Use $or for "match any of these tags"
                conditions.append(
                    {"$or": [{"tags": {"$eq": tag}} for tag in normalized_tags]}
                )

        # Combine all conditions with AND logic
        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    @staticmethod
    def apply_similarity_threshold(
        results: List, threshold: float = 0.0
    ) -> List:
        """
        Filter search results by similarity threshold.

        Args:
            results: List of RetrievalResult objects from vector search
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            Filtered list with only results above threshold
        """
        if threshold <= 0.0:
            return results

        filtered = []
        for result in results:
            # Get similarity score - try different attribute names
            score = None
            if hasattr(result, "score"):
                score = result.score
            elif isinstance(result, dict) and "score" in result:
                score = result["score"]
            elif hasattr(result, "metadata") and "similarity" in result.metadata:
                score = result.metadata["similarity"]

            if score is not None and float(score) >= threshold:
                filtered.append(result)
            else:
                logger.debug(
                    f"Filtered out result with score {score} < threshold {threshold}"
                )

        return filtered

    @staticmethod
    def normalize_document_type(file_path: str) -> str:
        """
        Normalize document type from file extension.

        Args:
            file_path: File path or filename

        Returns:
            Normalized document type (pdf, txt, md, docx)
        """
        extension = file_path.lower().split(".")[-1]
        type_map = {
            "pdf": "pdf",
            "txt": "txt",
            "text": "txt",
            "md": "md",
            "markdown": "md",
            "docx": "docx",
            "doc": "docx",
        }
        return type_map.get(extension, extension)

    @staticmethod
    def validate_similarity_threshold(threshold: float) -> float:
        """
        Validate and clamp similarity threshold to valid range.

        Args:
            threshold: Input threshold value

        Returns:
            Validated threshold in range [0.0, 1.0]
        """
        if threshold < 0.0:
            logger.warning(f"Similarity threshold {threshold} < 0.0, using 0.0")
            return 0.0
        if threshold > 1.0:
            logger.warning(f"Similarity threshold {threshold} > 1.0, using 1.0")
            return 1.0
        return threshold

    @staticmethod
    def build_date_range(
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Optional[tuple[datetime, datetime]]:
        """
        Validate and build date range.

        Args:
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            Valid tuple of (date_from, date_to), or None if invalid
        """
        if not date_from and not date_to:
            return None

        # If only one date provided, use sensible defaults
        if date_from and not date_to:
            date_to = datetime.now()

        if date_to and not date_from:
            date_from = datetime.min

        # Validate ordering
        if date_from > date_to:
            logger.warning(
                f"Date range invalid: {date_from} > {date_to}, swapping"
            )
            date_from, date_to = date_to, date_from

        return (date_from, date_to)

class FilterHistory:
    """Tracks recently used filter combinations for quick access."""

    def __init__(self, max_history: int = 10):
        """
        Initialize FilterHistory.

        Args:
            max_history: Maximum number of filter combinations to remember
        """
        self.max_history = max_history
        self.history: list[SearchFilter] = []

    def add_filter(self, filter: SearchFilter):
        """Add a filter to history (only if not empty)."""
        if not filter.is_empty():
            # Remove duplicate if it exists
            self.history = [f for f in self.history if f.to_dict() != filter.to_dict()]
            # Add to front
            self.history.insert(0, filter)
            # Trim to max size
            if len(self.history) > self.max_history:
                self.history = self.history[:self.max_history]

    def get_history(self) -> list[SearchFilter]:
        """Get filter history in order of most recent first."""
        return self.history.copy()

    def clear_history(self):
        """Clear all history."""
        self.history = []
