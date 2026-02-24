"""
Query Expansion Module - Improve search by generating query variants
Uses Gemini to expand queries with synonyms, related terms, and reformulations
"""

import logging
import json
import re
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from src.cache import QueryExpansionCache
from src.entity_extractor import get_entity_extractor

logger = logging.getLogger(__name__)

@dataclass
class ExpandedQuery:
    """Expanded query with variants"""
    original: str
    variants: list[str]  # Alternative phrasings
    keywords: list[str]  # Important keywords
    intent: str  # What the user is really looking for
    difficulty: str  # "simple", "moderate", "complex"

class QueryExpander:
    """Expand and reformulate queries for better retrieval

    Uses techniques like:
    - Query decomposition (breaking into sub-questions)
    - Synonym generation
    - Concept expansion
    - Intent detection
    """

    def __init__(self, llm_service):
        """
        Initialize query expander

        Args:
            llm_service: LLM service instance (Gemini)
        """
        self.llm = llm_service
        self.expansion_cache = QueryExpansionCache(max_size=500)
        logger.info("Initialized Query Expander with caching enabled")

    def expand_query(
        self,
        query: str,
        num_variants: int = 3,
        use_cache: bool = True
    ) -> ExpandedQuery:
        """
        Expand query into variants and analyze intent

        Args:
            query: Original query string
            num_variants: Number of variants to generate
            use_cache: Use cached results if available

        Returns:
            ExpandedQuery with variants and analysis
        """
        # Check cache
        cache_key = query.lower().strip()
        if use_cache:
            cached = self.expansion_cache.get(cache_key)
            if cached is not None:
                return cached

        prompt = self._create_expansion_prompt(query, num_variants)

        try:
            response = self.llm.generate_response(prompt)
            expanded = self._parse_expansion_response(response, query)
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            # Fallback: use centralized entity extractor
            entity_extractor = get_entity_extractor()
            keywords = entity_extractor.extract_keywords(query, num_keywords=5)
            expanded = ExpandedQuery(
                original=query,
                variants=[query],
                keywords=keywords if keywords else query.split()[:5],
                intent="search",
                difficulty="unknown"
            )

        # Cache result
        if use_cache:
            self.expansion_cache.set(cache_key, expanded)

        return expanded

    def _create_expansion_prompt(self, query: str, num_variants: int) -> str:
        """Create prompt for Gemini to expand query"""
        prompt = f"""Expand this search query to improve retrieval.

Original Query: "{query}"

Generate:
1. {num_variants} alternative ways to express this query
2. List of 3-5 key concepts or keywords in the query
3. The underlying intent (what is the user really looking for?)
4. Difficulty level (simple/moderate/complex)

Consider:
- Synonyms and related terms
- Different phrasings
- Breaking down complex queries
- Domain-specific terminology
- Implicit context

Respond in JSON format:
{{
    "variants": [
        "alternative phrasing 1",
        "alternative phrasing 2",
        "alternative phrasing 3"
    ],
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "intent": "What the user is really asking for",
    "difficulty": "simple|moderate|complex",
    "explanation": "Why these variants help"
}}

Only return the JSON, no other text."""

        return prompt

    def _parse_expansion_response(self, response: str, original_query: str) -> ExpandedQuery:
        """Parse Gemini response"""
        entity_extractor = get_entity_extractor()

        try:
            # Extract JSON
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError("No JSON found")

            data = json.loads(match.group())

            # Extract keywords from data or use centralized extractor
            keywords = data.get('keywords')
            if not keywords:
                keywords = entity_extractor.extract_keywords(original_query, num_keywords=5)
            if not keywords:
                keywords = original_query.split()[:5]

            return ExpandedQuery(
                original=original_query,
                variants=data.get('variants', [original_query]),
                keywords=keywords,
                intent=data.get('intent', 'search'),
                difficulty=data.get('difficulty', 'moderate')
            )
        except Exception as e:
            logger.warning(f"Failed to parse query expansion: {e}")
            # Use centralized extractor for fallback
            keywords = entity_extractor.extract_keywords(original_query, num_keywords=5)
            return ExpandedQuery(
                original=original_query,
                variants=[original_query],
                keywords=keywords if keywords else original_query.split()[:5],
                intent="search",
                difficulty="unknown"
            )

    def decompose_query(self, query: str) -> list[str]:
        """
        Decompose complex query into sub-questions

        For multi-part queries, generate smaller focused queries
        that can be searched independently and combined.
        """
        prompt = f"""Decompose this query into smaller, focused sub-questions.

Query: "{query}"

Generate 2-3 focused sub-questions that together answer the original query.
Each sub-question should be simple and specific.

Respond as a JSON list:
["sub-question 1", "sub-question 2", "sub-question 3"]

Only return the JSON, no other text."""

        try:
            response = self.llm.generate_response(prompt)
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                sub_questions = json.loads(match.group())
                return sub_questions if isinstance(sub_questions, list) else [query]
        except Exception as e:
            logger.warning(f"Query decomposition failed: {e}")

        return [query]

    def generate_keywords(self, query: str, num_keywords: int = 5) -> list[str]:
        """
        Extract important keywords from query.

        Delegated to centralized EntityExtractor for consistency
        and to eliminate duplicated extraction logic.
        """
        entity_extractor = get_entity_extractor()
        return entity_extractor.extract_keywords(query, num_keywords, use_llm=True)

    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        stats = self.expansion_cache.get_stats()
        return {
            "cached_queries": stats.get("items_in_cache", 0),
            "cache_size_bytes": stats.get("cache_size_bytes", 0),
            "hit_rate": stats.get("hit_rate", 0),
            "hits": stats.get("hits", 0),
            "misses": stats.get("misses", 0),
            "evictions": stats.get("evictions", 0)
        }

    def clear_cache(self):
        """Clear expansion cache"""
        self.expansion_cache.clear()
        logger.info("Query expansion cache cleared")

class HyDEExpander:
    """Hypothetical Document Embeddings

    Generate hypothetical documents that would match the query,
    then use their embeddings for better semantic search.

    Reference: "Precise Zero-shot Dense Retrieval without Relevance Labels"
    """

    def __init__(self, llm_service):
        """Initialize HyDE expander"""
        self.llm = llm_service
        logger.info("Initialized HyDE Expander")

    def generate_hypothetical_documents(
        self,
        query: str,
        num_docs: int = 3
    ) -> list[str]:
        """
        Generate hypothetical documents that answer the query

        Args:
            query: Search query
            num_docs: Number of hypothetical documents to generate

        Returns:
            List of generated documents
        """
        prompt = f"""Write {num_docs} short hypothetical documents or paragraphs that would answer this query.

Query: "{query}"

Each document should:
- Be 1-2 paragraphs long
- Directly address the query
- Sound natural and informative
- Contain relevant keywords and concepts

Generate {num_docs} different documents, each starting with "[Doc N]":"""

        try:
            response = self.llm.generate_response(prompt)
            docs = self._extract_hypothetical_docs(response, num_docs)
            return docs if docs else [query]
        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            return [query]

    def _extract_hypothetical_docs(self, response: str, num_docs: int) -> list[str]:
        """Extract hypothetical documents from response"""
        docs = []
        pattern = r'\[Doc \d+\](.*?)(?=\[Doc \d+\]|$)'
        matches = re.findall(pattern, response, re.DOTALL)

        for match in matches[:num_docs]:
            doc = match.strip()
            if doc:
                docs.append(doc)

        return docs

# Global instances
_expander = None
_hyde_expander = None

def get_query_expander(llm_service) -> QueryExpander:
    """Get or create global query expander"""
    global _expander
    if _expander is None:
        _expander = QueryExpander(llm_service)
    return _expander

def get_hyde_expander(llm_service) -> HyDEExpander:
    """Get or create global HyDE expander"""
    global _hyde_expander
    if _hyde_expander is None:
        _hyde_expander = HyDEExpander(llm_service)
    return _hyde_expander

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test examples
    print("Query Expansion Examples:")
    print("\nExample 1: Simple query")
    print("  Original: 'How to implement caching?'")
    print("  Variants:")
    print("    - 'What are caching strategies?'")
    print("    - 'Best practices for cache implementation'")
    print("    - 'Cache optimization techniques'")

    print("\nExample 2: Complex query decomposition")
    print("  Original: 'How does machine learning improve search relevance?'")
    print("  Sub-questions:")
    print("    - 'What is machine learning in search?'")
    print("    - 'How does ranking work with ML?'")
    print("    - 'Benefits of ML for relevance?'")
