"""
Centralized Entity Extraction Module

Consolidates keyword extraction, entity recognition, and text normalization
across the entire RAG system. Eliminates duplicated logic in query_expansion,
document_summarizer, and other modules.

Features:
- Keyword extraction from queries and documents
- Entity recognition (named entities, dates, numbers)
- Text normalization and tokenization
- Caching for performance
"""

import re
import json
from typing import Optional
from dataclasses import dataclass
from collections import Counter

from src.logging_config import get_logger

logger = get_logger(__name__)

# Common stopwords in English and Italian
STOPWORDS = {
    # English
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
    'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'or', 'that',
    'the', 'to', 'was', 'will', 'with', 'what', 'when', 'where', 'which', 'who',
    'i', 'me', 'my', 'you', 'your', 'we', 'our', 'they', 'their',

    # Italian
    'il', 'la', 'lo', 'le', 'un', 'una', 'uno', 'unà',
    'e', 'o', 'di', 'da', 'a', 'per', 'con', 'su', 'in', 'è', 'sono',
    'ho', 'hai', 'ha', 'abbiamo', 'avete', 'hanno',
    'io', 'tu', 'lui', 'lei', 'noi', 'voi', 'loro',
    'questo', 'quello', 'questo', 'quello', 'che', 'chi', 'quando', 'dove',
}

@dataclass
class ExtractedEntity:
    """Represents an extracted entity"""
    text: str
    entity_type: str  # 'keyword', 'entity', 'number', 'date'
    confidence: float
    position: tuple[int, int]  # (start, end) in original text

class EntityExtractor:
    """
    Centralizes all entity and keyword extraction logic.

    This module consolidates extraction patterns that were previously duplicated
    across query_expansion.py and document_summarizer.py.
    """

    def __init__(self, llm_service=None):
        """
        Initialize entity extractor.

        Args:
            llm_service: Optional LLM service for advanced extraction
        """
        self.llm = llm_service
        if not self.llm:
            try:
                from src.llm_service import get_llm_service
                self.llm = get_llm_service()
            except Exception:
                self.llm = None

        self.extraction_cache: dict[str, list[str]] = {}
        self.max_cache_size = 1000

    def extract_keywords(
        self,
        text: str,
        num_keywords: int = 5,
        use_llm: bool = True,
        remove_stopwords: bool = True
    ) -> list[str]:
        """
        Extract important keywords from text.

        Strategy:
        1. Try LLM extraction if available and use_llm=True
        2. Fallback to frequency-based extraction
        3. Filter stopwords if requested
        4. Return top N keywords

        Args:
            text: Input text
            num_keywords: Number of keywords to extract
            use_llm: Whether to use LLM for extraction
            remove_stopwords: Whether to filter common words

        Returns:
            List of keywords sorted by importance
        """
        if not text or len(text.strip()) < 10:
            return []

        # Check cache
        cache_key = f"keywords_{text[:50]}_{num_keywords}"
        if cache_key in self.extraction_cache:
            return self.extraction_cache[cache_key]

        keywords = []

        # Try LLM extraction first
        if use_llm and self.llm:
            keywords = self._extract_keywords_llm(text, num_keywords)

        # Fallback to frequency-based extraction
        if not keywords:
            keywords = self._extract_keywords_frequency(
                text,
                num_keywords,
                remove_stopwords
            )

        # Cache result
        if len(self.extraction_cache) < self.max_cache_size:
            self.extraction_cache[cache_key] = keywords

        return keywords

    def _extract_keywords_llm(self, text: str, num_keywords: int) -> list[str]:
        """
        Extract keywords using LLM.

        Uses LLM to identify semantically important keywords.
        """
        if not self.llm:
            return []

        try:
            prompt = f"""Extract the {num_keywords} most important keywords from this text.
Return as a JSON list of keywords.

Text: "{text[:500]}"

Return ONLY valid JSON array of keywords, no other text."""

            response = self.llm.generate_response(prompt)

            # Parse JSON response
            try:
                match = re.search(r'\[.*\]', response, re.DOTALL)
                if match:
                    keywords = json.loads(match.group())
                    if isinstance(keywords, list):
                        return [str(kw).lower().strip() for kw in keywords[:num_keywords]]
            except (json.JSONDecodeError, ValueError):
                pass

            return []

        except Exception as e:
            logger.debug(f"LLM keyword extraction failed: {e}")
            return []

    def _extract_keywords_frequency(
        self,
        text: str,
        num_keywords: int,
        remove_stopwords: bool = True
    ) -> list[str]:
        """
        Extract keywords based on word frequency.

        Fallback method using simple frequency analysis.
        """
        # Tokenize
        tokens = self._tokenize(text, remove_stopwords=remove_stopwords)

        if not tokens:
            return []

        # Count frequencies
        freq = Counter(tokens)

        # Get top keywords
        top_keywords = [word for word, _ in freq.most_common(num_keywords)]

        return top_keywords

    def extract_entities(self, text: str, entity_types: list[str] = None) -> list[ExtractedEntity]:
        """
        Extract named entities from text.

        Identifies:
        - Named entities (people, places, organizations)
        - Numbers (quantities, measurements)
        - Dates and times
        - Other important entities

        Args:
            text: Input text
            entity_types: Types to extract (if None, extract all)

        Returns:
            List of ExtractedEntity objects
        """
        entities = []

        # Extract numbers
        if not entity_types or 'number' in entity_types:
            entities.extend(self._extract_numbers(text))

        # Extract dates
        if not entity_types or 'date' in entity_types:
            entities.extend(self._extract_dates(text))

        # Extract capitalized sequences (likely proper nouns)
        if not entity_types or 'entity' in entity_types:
            entities.extend(self._extract_proper_nouns(text))

        return sorted(entities, key=lambda e: e.position[0])

    def _extract_numbers(self, text: str) -> list[ExtractedEntity]:
        """Extract numbers and quantities"""
        entities = []
        # Match numbers (integers and decimals)
        pattern = r'\b\d+[.,]?\d*\s*(?:%|USD|EUR|kg|m|cm|l|ml)?\b'

        for match in re.finditer(pattern, text):
            entity = ExtractedEntity(
                text=match.group().strip(),
                entity_type='number',
                confidence=0.9,
                position=(match.start(), match.end())
            )
            entities.append(entity)

        return entities

    def _extract_dates(self, text: str) -> list[ExtractedEntity]:
        """Extract dates and time expressions"""
        entities = []

        # Common date patterns
        patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY or MM/DD/YYYY
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY-MM-DD
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                entity = ExtractedEntity(
                    text=match.group(),
                    entity_type='date',
                    confidence=0.85,
                    position=(match.start(), match.end())
                )
                entities.append(entity)

        return entities

    def _extract_proper_nouns(self, text: str) -> list[ExtractedEntity]:
        """Extract capitalized sequences (likely proper nouns)"""
        entities = []

        # Match sequences of capitalized words
        pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'

        for match in re.finditer(pattern, text):
            word = match.group()
            # Filter out common words
            if len(word) > 2 and word not in ['The', 'A', 'An', 'Is']:
                entity = ExtractedEntity(
                    text=word,
                    entity_type='entity',
                    confidence=0.7,
                    position=(match.start(), match.end())
                )
                entities.append(entity)

        return entities

    def normalize_query(self, query: str) -> str:
        """
        Normalize a query for processing.

        - Convert to lowercase
        - Strip whitespace
        - Remove extra spaces
        - Remove special characters (except hyphens and underscores)

        Args:
            query: Input query

        Returns:
            Normalized query
        """
        if not query:
            return ""

        # Lowercase
        normalized = query.lower().strip()

        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)

        # Remove special characters (keep letters, numbers, spaces, hyphens, underscores)
        normalized = re.sub(r'[^\w\s\-]', '', normalized)

        return normalized.strip()

    def split_into_tokens(
        self,
        text: str,
        remove_stopwords: bool = True,
        min_length: int = 1
    ) -> list[str]:
        """
        Split text into tokens.

        Args:
            text: Input text
            remove_stopwords: Filter common stopwords
            min_length: Minimum token length

        Returns:
            List of tokens
        """
        # Normalize and split
        tokens = self._tokenize(text, remove_stopwords, min_length)
        return tokens

    def _tokenize(
        self,
        text: str,
        remove_stopwords: bool = True,
        min_length: int = 1
    ) -> list[str]:
        """
        Internal tokenization method.

        Args:
            text: Input text
            remove_stopwords: Filter stopwords
            min_length: Minimum token length

        Returns:
            List of tokens
        """
        if not text:
            return []

        # Convert to lowercase and split on whitespace/punctuation
        tokens = re.findall(r'\b\w+\b', text.lower())

        # Filter stopwords if requested
        if remove_stopwords:
            tokens = [t for t in tokens if t not in STOPWORDS]

        # Filter by minimum length
        tokens = [t for t in tokens if len(t) >= min_length]

        return tokens

    def combine_keywords(
        self,
        keywords_list: list[list[str]]
    ) -> list[str]:
        """
        Combine and deduplicate keywords from multiple extractions.

        Args:
            keywords_list: List of keyword lists

        Returns:
            Combined, deduplicated keyword list
        """
        combined = []
        seen = set()

        for keywords in keywords_list:
            for kw in keywords:
                kw_lower = kw.lower().strip()
                if kw_lower not in seen:
                    combined.append(kw_lower)
                    seen.add(kw_lower)

        return combined

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.extraction_cache),
            "max_size": self.max_cache_size,
            "utilization_percent": 100 * len(self.extraction_cache) / self.max_cache_size
        }

    def clear_cache(self):
        """Clear extraction cache"""
        self.extraction_cache.clear()
        logger.info("Entity extraction cache cleared")

# Global instance
_entity_extractor = None

def get_entity_extractor() -> EntityExtractor:
    """Get or create global entity extractor"""
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor
