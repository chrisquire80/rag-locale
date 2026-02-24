"""
Temporal Metadata Extraction - TASK 4
Extracts and processes date information from filenames and document metadata
Enables temporal filtering and date-aware RAG responses
"""

import re
from typing import Optional
from datetime import datetime, date
from dataclasses import dataclass
from pathlib import Path
import calendar

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class TemporalMetadata:
    """Temporal information extracted from documents"""
    document_name: str
    extracted_date: Optional[date] = None
    date_confidence: float = 0.0  # 0.0-1.0, higher = more confident
    date_formats_found: list[str] = None  # Which date formats were matched
    temporal_keywords: list[str] = None  # Keywords like "updated", "latest", "2025"
    extraction_method: str = "filename"  # filename, content, metadata, hybrid

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            "document_name": self.document_name,
            "extracted_date": self.extracted_date.isoformat() if self.extracted_date else None,
            "date_confidence": self.date_confidence,
            "date_formats_found": self.date_formats_found or [],
            "temporal_keywords": self.temporal_keywords or [],
            "extraction_method": self.extraction_method
        }

class TemporalMetadataExtractor:
    """Extract temporal information from document metadata"""

    # Common date patterns in Italian filenames
    # Format: YYYYMMDD, YYYY-MM-DD, DD/MM/YYYY, DDMMYYYY, etc.
    DATE_PATTERNS = [
        # ISO format: YYYY-MM-DD or YYYYMMDD
        (r'\b(\d{4})-(\d{2})-(\d{2})\b', 'ISO_DASH', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()),
        (r'\b(\d{4})(\d{2})(\d{2})\b', 'ISO_COMPACT', lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()),

        # European format: DD/MM/YYYY or DD-MM-YYYY
        (r'\b(\d{2})[/-](\d{2})[/-](\d{4})\b', 'EU_SLASH', lambda m: datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()),

        # Month name format: "January 2025", "Jan 25", "01 January 2025"
        (r'\b(\d{1,2})\s+(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b',
         'MONTH_FULL', None),  # Handled in method

        # Just year: "2025", "2024"
        (r'\b(202[0-9]|201[0-9]|199[0-9])\b', 'YEAR_ONLY', lambda m: date(int(m.group(1)), 1, 1)),

        # Year-Month: "2025-01", "202501", "January 2025"
        (r'\b(\d{4})[/-](\d{2})\b', 'YEAR_MONTH', lambda m: date(int(m.group(1)), int(m.group(2)), 1)),
    ]

    MONTH_MAP = {
        # Italian months
        'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
        'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
        'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12,
        # English months
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
        'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
        'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    TEMPORAL_KEYWORDS = {
        'latest': 1.0,
        'updated': 0.9,
        'new': 0.8,
        'current': 0.85,
        'recent': 0.8,
        'latest': 1.0,
        # Italian
        'ultimo': 1.0,
        'aggiornato': 0.9,
        'nuovo': 0.8,
        'attuale': 0.85,
        'recente': 0.8,
        'finale': 0.9
    }

    def __init__(self):
        """Initialize temporal metadata extractor"""
        self.cache = {}
        logger.info("Initialized Temporal Metadata Extractor")

    def extract_from_filename(self, filename: str) -> TemporalMetadata:
        """
        Extract temporal metadata from filename

        Args:
            filename: Document filename (e.g., "20250708 - Report.pdf")

        Returns:
            TemporalMetadata with extracted date and confidence
        """
        # Check cache
        if filename in self.cache:
            return self.cache[filename]

        metadata = TemporalMetadata(
            document_name=filename,
            date_formats_found=[],
            temporal_keywords=[]
        )

        # Clean filename
        clean_name = Path(filename).stem.lower()

        # Try each pattern
        best_date = None
        best_confidence = 0.0
        matched_formats = []

        for pattern, format_name, parser in self.DATE_PATTERNS:
            matches = re.finditer(pattern, clean_name)
            for match in matches:
                matched_formats.append(format_name)

                try:
                    if format_name == 'MONTH_FULL':
                        # Special handling for month names
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        year = int(match.group(3))
                        month = self.MONTH_MAP.get(month_name)
                        if month:
                            parsed_date = date(year, month, day)
                            confidence = 0.95  # High confidence for explicit format
                        else:
                            continue
                    elif format_name == 'YEAR_ONLY':
                        parsed_date = date(int(match.group(1)), 1, 1)
                        confidence = 0.6  # Lower confidence for year-only
                    else:
                        parsed_date = parser(match)
                        confidence = 0.9  # Standard confidence for structured formats

                    if confidence > best_confidence:
                        best_date = parsed_date
                        best_confidence = confidence

                except (ValueError, AttributeError, IndexError) as e:
                    logger.debug(f"Date parsing failed for {filename}: {e}")
                    continue

        # Extract temporal keywords
        temporal_keywords = []
        for keyword, keyword_weight in self.TEMPORAL_KEYWORDS.items():
            if keyword in clean_name:
                temporal_keywords.append(keyword)
                # Boost confidence slightly for temporal keywords
                best_confidence = min(1.0, best_confidence + 0.1 * keyword_weight)

        metadata.extracted_date = best_date
        metadata.date_confidence = best_confidence
        metadata.date_formats_found = matched_formats
        metadata.temporal_keywords = temporal_keywords

        # Cache result
        self.cache[filename] = metadata

        if best_date:
            logger.info(f"Extracted date from {filename}: {best_date} (confidence: {best_confidence:.2f})")

        return metadata

    def extract_from_content(
        self,
        content: str,
        filename: str = "unknown"
    ) -> TemporalMetadata:
        """
        Extract temporal metadata from document content
        Look for dates mentioned in the text
        """
        metadata = TemporalMetadata(
            document_name=filename,
            extraction_method="content",
            date_formats_found=[],
            temporal_keywords=[]
        )

        # Similar to filename extraction but on content
        best_date = None
        best_confidence = 0.0
        matched_formats = []

        for pattern, format_name, parser in self.DATE_PATTERNS:
            matches = re.finditer(pattern, content[:1000])  # Search first 1000 chars
            for match in matches:
                matched_formats.append(format_name)
                try:
                    if format_name == 'MONTH_FULL':
                        day = int(match.group(1))
                        month_name = match.group(2).lower()
                        year = int(match.group(3))
                        month = self.MONTH_MAP.get(month_name)
                        if month:
                            parsed_date = date(year, month, day)
                            confidence = 0.85
                        else:
                            continue
                    else:
                        parsed_date = parser(match)
                        confidence = 0.75  # Lower for content (less structured)

                    if confidence > best_confidence:
                        best_date = parsed_date
                        best_confidence = confidence

                except (ValueError, AttributeError, IndexError):
                    continue

        metadata.extracted_date = best_date
        metadata.date_confidence = best_confidence
        metadata.date_formats_found = matched_formats

        return metadata

    def is_recent(self, temporal_metadata: TemporalMetadata, days: int = 30) -> bool:
        """
        Check if document is recent (within N days)

        Args:
            temporal_metadata: Temporal metadata
            days: Number of days to consider "recent"

        Returns:
            True if document is recent, False otherwise
        """
        if not temporal_metadata.extracted_date:
            return False

        diff = (datetime.now().date() - temporal_metadata.extracted_date).days
        return 0 <= diff <= days

    def get_time_relevance_score(
        self,
        temporal_metadata: TemporalMetadata,
        query: str = ""
    ) -> float:
        """
        Calculate relevance score based on temporal information

        Higher score = more recent/relevant
        Lower score = older/less relevant

        Args:
            temporal_metadata: Temporal metadata
            query: User query (to detect temporal keywords like "latest")

        Returns:
            Relevance score 0.0-1.0
        """
        if not temporal_metadata.extracted_date:
            return 0.5  # Neutral score if no date found

        # Base score: recency decay (half-life = 90 days)
        days_old = (datetime.now().date() - temporal_metadata.extracted_date).days
        recency_score = pow(0.5, days_old / 90.0)  # Exponential decay

        # Boost if query contains temporal keywords
        query_lower = query.lower()
        temporal_boost = 1.0

        if any(keyword in query_lower for keyword in ['latest', 'ultimo', 'recent', 'recente']):
            temporal_boost = 1.3  # 30% boost if user asked for "latest"

        if temporal_metadata.temporal_keywords:
            temporal_boost = min(1.5, temporal_boost + 0.1 * len(temporal_metadata.temporal_keywords))

        final_score = min(1.0, recency_score * temporal_boost)
        return final_score

    def group_by_date(
        self,
        documents: list[tuple[str, TemporalMetadata]]
    ) -> dict[str, list[str]]:
        """
        Group documents by date ranges

        Returns:
            {
                "2025-01": ["doc1.pdf", "doc2.pdf"],
                "2024-Q4": ["doc3.pdf"],
                "unknown": ["doc4.pdf"]
            }
        """
        groups = {}

        for doc_name, metadata in documents:
            if metadata.extracted_date:
                # Group by year-month
                key = metadata.extracted_date.strftime("%Y-%m")
            else:
                key = "unknown"

            if key not in groups:
                groups[key] = []
            groups[key].append(doc_name)

        return groups

    def clear_cache(self):
        """Clear extraction cache"""
        self.cache.clear()
        logger.info("Temporal metadata cache cleared")

def get_temporal_extractor() -> TemporalMetadataExtractor:
    """Get or create global temporal metadata extractor"""
    global _extractor
    if '_extractor' not in globals():
        _extractor = TemporalMetadataExtractor()
    return _extractor

if __name__ == "__main__":

    # Test examples
    extractor = TemporalMetadataExtractor()

    test_filenames = [
        "20250708 - Meeting Notes.pdf",
        "2024-01-15 - Project Report.docx",
        "15/01/2025 - Implementation Guide.pdf",
        "January 2025 - Strategy Document.txt",
        "Report_2024.pdf",
        "Latest_Updates.md"
    ]

    print("Temporal Metadata Extraction Tests:")
    print("=" * 60)

    for filename in test_filenames:
        metadata = extractor.extract_from_filename(filename)
        print(f"\nFile: {filename}")
        print(f"  Date: {metadata.extracted_date}")
        print(f"  Confidence: {metadata.date_confidence:.2f}")
        print(f"  Formats: {metadata.date_formats_found}")
        print(f"  Keywords: {metadata.temporal_keywords}")

        if metadata.extracted_date:
            is_recent = extractor.is_recent(metadata, days=30)
            score = extractor.get_time_relevance_score(metadata)
            print(f"  Recent (30d): {is_recent}")
            print(f"  Relevance Score: {score:.2f}")
