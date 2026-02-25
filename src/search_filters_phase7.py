"""
Advanced Search Filters - Phase 7 Feature 2
Multi-criteria filtering for search: date range, document type, similarity threshold, tags
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SearchFilter:
    """Multi-criteria search filter configuration"""

    # Document type filter (e.g., ["pdf", "txt", "md"])
    document_types: Optional[List[str]] = None

    # Date range filter
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

    # Tags filter (integrates with Feature 1)
    tags: Optional[List[str]] = None
    tag_match_all: bool = False  # If True, doc must have ALL tags

    # Source document filter
    source_documents: Optional[List[str]] = None

    # Similarity threshold (0.0-1.0)
    similarity_threshold: float = 0.0

    # Custom metadata filters
    metadata_filters: Optional[Dict[str, any]] = None


class SearchFilterBuilder:
    """Builds metadata filters from SearchFilter for vector store"""

    @staticmethod
    def build_metadata_filter(search_filter: SearchFilter) -> Dict:
        """
        Convert SearchFilter to vector store metadata filter format

        Args:
            search_filter: SearchFilter configuration

        Returns:
            Dict with metadata filter criteria
        """
        where_filter = {}

        # Document type filter
        if search_filter.document_types:
            where_filter["file_type"] = {
                "$in": [ft.lower() for ft in search_filter.document_types]
            }

        # Source document filter
        if search_filter.source_documents:
            where_filter["source"] = {"$in": search_filter.source_documents}

        # Tag filter
        if search_filter.tags:
            if search_filter.tag_match_all:
                # Document must have ALL tags (AND logic)
                # This is complex in MongoDB-like query syntax
                # Simplified: just add all tags as array condition
                where_filter["tags"] = {"$all": search_filter.tags}
            else:
                # Document must have ANY tag (OR logic)
                where_filter["tags"] = {"$in": search_filter.tags}

        # Custom metadata filters
        if search_filter.metadata_filters:
            where_filter.update(search_filter.metadata_filters)

        return where_filter if where_filter else None

    @staticmethod
    def apply_similarity_threshold(
        results: List[Dict],
        threshold: float
    ) -> List[Dict]:
        """
        Filter results by similarity threshold

        Args:
            results: Search results with similarity_score
            threshold: Minimum similarity score (0.0-1.0)

        Returns:
            Filtered results above threshold
        """
        if threshold <= 0.0:
            return results

        filtered = [
            r for r in results if r.get("similarity_score", 0.0) >= threshold
        ]

        logger.debug(f"Applied similarity threshold {threshold}: {len(results)} → {len(filtered)} results")
        return filtered

    @staticmethod
    def apply_date_range_filter(
        results: List[Dict],
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Filter results by date range

        Args:
            results: Search results with metadata containing timestamp
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            Filtered results within date range
        """
        if not date_from and not date_to:
            return results

        filtered = []
        for result in results:
            metadata = result.get("metadata", {})
            timestamp = metadata.get("ingestion_date")

            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue

            if timestamp:
                if date_from and timestamp < date_from:
                    continue
                if date_to and timestamp > date_to:
                    continue
                filtered.append(result)

        logger.debug(f"Applied date range filter: {len(results)} → {len(filtered)} results")
        return filtered


class AdvancedSearchEngine:
    """Advanced search with multiple criteria"""

    def __init__(self, vector_store, tag_manager=None):
        """
        Initialize advanced search engine

        Args:
            vector_store: Vector store instance
            tag_manager: TagManager instance (optional, for tag filtering)
        """
        self.vector_store = vector_store
        self.tag_manager = tag_manager
        logger.info("Initialized AdvancedSearchEngine")

    def search(
        self,
        query: str,
        search_filter: Optional[SearchFilter] = None,
        top_k: int = 5
    ) -> List[Dict]:
        """
        Advanced search with multi-criteria filtering

        Args:
            query: Search query
            search_filter: Optional SearchFilter with criteria
            top_k: Maximum results to return

        Returns:
            Filtered search results
        """
        if not search_filter:
            search_filter = SearchFilter()

        # Build metadata filter from search criteria
        metadata_filter = SearchFilterBuilder.build_metadata_filter(search_filter)

        # Perform vector search with metadata filter
        results = self.vector_store.search(
            query=query,
            top_k=top_k * 2,  # Get more results to account for filtering
            where_filter=metadata_filter
        )

        # Apply similarity threshold
        results = SearchFilterBuilder.apply_similarity_threshold(
            results, search_filter.similarity_threshold
        )

        # Apply date range filter
        results = SearchFilterBuilder.apply_date_range_filter(
            results, search_filter.date_from, search_filter.date_to
        )

        # Return top K after filtering
        return results[:top_k]

    def get_available_filters(self) -> Dict:
        """
        Get available filter options for UI

        Returns:
            Dict with available filter values
        """
        available_filters = {
            "document_types": ["pdf", "txt", "md"],
            "similarity_thresholds": [
                {"value": 0.0, "label": "All (0.0)"},
                {"value": 0.5, "label": "Medium (0.5)"},
                {"value": 0.7, "label": "High (0.7)"},
                {"value": 0.85, "label": "Very High (0.85)"},
            ],
            "tags": [],
        }

        # Get available tags from tag manager if available
        if self.tag_manager:
            try:
                # Get all docs from vector store
                all_docs = self.vector_store.get_all_documents()
                all_tags = self.tag_manager.get_all_tags(all_docs)
                available_filters["tags"] = [
                    {"name": tag, "count": count}
                    for tag, count in all_tags.items()
                ]
            except Exception as e:
                logger.warning(f"Could not get tags: {e}")

        return available_filters

    def create_filter_from_ui_inputs(
        self,
        document_types: Optional[List[str]] = None,
        date_range: Optional[Tuple[str, str]] = None,
        similarity_threshold: float = 0.0,
        tags: Optional[List[str]] = None,
        source_documents: Optional[List[str]] = None,
    ) -> SearchFilter:
        """
        Create SearchFilter from UI input values

        Args:
            document_types: Selected document types
            date_range: Tuple of (from_date, to_date) as ISO strings
            similarity_threshold: Minimum similarity (0.0-1.0)
            tags: Selected tags
            source_documents: Selected source documents

        Returns:
            SearchFilter object
        """
        date_from = None
        date_to = None

        if date_range and len(date_range) == 2:
            try:
                date_from = datetime.fromisoformat(date_range[0])
                date_to = datetime.fromisoformat(date_range[1])
            except (ValueError, TypeError):
                logger.warning(f"Invalid date range: {date_range}")

        return SearchFilter(
            document_types=document_types,
            date_from=date_from,
            date_to=date_to,
            similarity_threshold=similarity_threshold,
            tags=tags,
            source_documents=source_documents,
        )
