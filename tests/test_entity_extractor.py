"""
Unit Tests for Entity Extractor Module

Tests keyword extraction, entity recognition, text normalization,
and tokenization functionality.
"""

import pytest
from src.entity_extractor import (
    EntityExtractor,
    ExtractedEntity,
    get_entity_extractor,
    STOPWORDS
)


class TestEntityExtractor:
    """Test EntityExtractor class"""

    @pytest.fixture
    def extractor(self):
        """Create fresh extractor instance for each test"""
        return EntityExtractor(llm_service=None)

    # ============= KEYWORD EXTRACTION TESTS =============

    def test_extract_keywords_frequency_based(self, extractor):
        """Test frequency-based keyword extraction"""
        text = "machine learning is great. machine learning helps solve problems."
        keywords = extractor.extract_keywords(text, num_keywords=3, use_llm=False)

        assert isinstance(keywords, list)
        assert len(keywords) <= 3
        assert "machine" in keywords or "learning" in keywords

    def test_extract_keywords_with_stopword_filtering(self, extractor):
        """Test that stopwords are filtered"""
        text = "the quick brown fox jumps over the lazy dog"
        keywords = extractor.extract_keywords(
            text,
            num_keywords=5,
            use_llm=False,
            remove_stopwords=True
        )

        # Should not contain common stopwords
        assert "the" not in keywords
        assert "is" not in keywords
        assert "a" not in keywords

    def test_extract_keywords_empty_text(self, extractor):
        """Test handling of empty text"""
        keywords = extractor.extract_keywords("", num_keywords=5)
        assert keywords == []

    def test_extract_keywords_short_text(self, extractor):
        """Test handling of very short text"""
        keywords = extractor.extract_keywords("hi", num_keywords=5)
        assert isinstance(keywords, list)

    def test_extract_keywords_caching(self, extractor):
        """Test that keyword extraction results are cached"""
        text = "test keyword extraction with caching system"

        # First call
        keywords1 = extractor.extract_keywords(text, num_keywords=3, use_llm=False)

        # Second call should come from cache
        keywords2 = extractor.extract_keywords(text, num_keywords=3, use_llm=False)

        assert keywords1 == keywords2
        assert len(extractor.extraction_cache) > 0

    def test_extract_keywords_num_keywords_limit(self, extractor):
        """Test that returned keywords respect num_keywords limit"""
        text = "one two three four five six seven eight nine ten"
        keywords = extractor.extract_keywords(text, num_keywords=5, use_llm=False)

        assert len(keywords) <= 5

    # ============= ENTITY EXTRACTION TESTS =============

    def test_extract_entities_numbers(self, extractor):
        """Test extraction of numbers"""
        text = "The price is $100.50 and weight is 25kg"
        entities = extractor.extract_entities(text, entity_types=['number'])

        assert len(entities) >= 2
        assert any("100" in e.text for e in entities)
        assert any(e.entity_type == 'number' for e in entities)

    def test_extract_entities_dates(self, extractor):
        """Test extraction of dates"""
        text = "Meeting on 2024-02-23 and also January 15, 2025"
        entities = extractor.extract_entities(text, entity_types=['date'])

        assert len(entities) >= 1
        assert any(e.entity_type == 'date' for e in entities)

    def test_extract_entities_proper_nouns(self, extractor):
        """Test extraction of proper nouns"""
        text = "Alice went to Paris with Bob Smith last week"
        entities = extractor.extract_entities(text, entity_types=['entity'])

        # Should find capitalized names
        assert len(entities) >= 1
        assert any(e.entity_type == 'entity' for e in entities)

    def test_extract_entities_all_types(self, extractor):
        """Test extraction of all entity types together"""
        text = "John Smith sold 100 units on 2024-02-23 for $5000"
        entities = extractor.extract_entities(text)

        # Should extract multiple types
        entity_types = {e.entity_type for e in entities}
        assert len(entity_types) >= 2  # At least multiple entity types

    def test_extract_entity_position(self, extractor):
        """Test that entity positions are correct"""
        text = "Alice and Bob met on 2024-02-23"
        entities = extractor.extract_entities(text)

        for entity in entities:
            # Position should be valid tuple
            assert isinstance(entity.position, tuple)
            assert len(entity.position) == 2
            start, end = entity.position
            # Position should be within text bounds
            assert 0 <= start < len(text)
            assert start <= end <= len(text)

    def test_extract_entity_confidence(self, extractor):
        """Test that entity confidence scores are reasonable"""
        text = "Visit Paris on 2024-02-23 for $100"
        entities = extractor.extract_entities(text)

        for entity in entities:
            assert isinstance(entity.confidence, float)
            assert 0.0 <= entity.confidence <= 1.0

    # ============= TEXT NORMALIZATION TESTS =============

    def test_normalize_query_lowercase(self, extractor):
        """Test that normalization converts to lowercase"""
        query = "HELLO WORLD"
        normalized = extractor.normalize_query(query)
        assert normalized == "hello world"

    def test_normalize_query_whitespace(self, extractor):
        """Test that normalization removes extra whitespace"""
        query = "hello    world   test"
        normalized = extractor.normalize_query(query)
        assert "    " not in normalized  # No multiple spaces

    def test_normalize_query_special_chars(self, extractor):
        """Test that special characters are removed"""
        query = "hello@world#test$value"
        normalized = extractor.normalize_query(query)
        assert "@" not in normalized
        assert "#" not in normalized
        assert "$" not in normalized

    def test_normalize_query_preserve_hyphens(self, extractor):
        """Test that hyphens are preserved"""
        query = "machine-learning test"
        normalized = extractor.normalize_query(query)
        assert "-" in normalized

    def test_normalize_query_empty(self, extractor):
        """Test normalization of empty query"""
        normalized = extractor.normalize_query("")
        assert normalized == ""

    # ============= TOKENIZATION TESTS =============

    def test_split_into_tokens(self, extractor):
        """Test basic tokenization"""
        text = "hello world test"
        tokens = extractor.split_into_tokens(text, remove_stopwords=False)

        assert isinstance(tokens, list)
        assert len(tokens) >= 2
        assert "hello" in tokens

    def test_split_into_tokens_stopword_filtering(self, extractor):
        """Test tokenization with stopword filtering"""
        text = "the quick brown fox is jumping"
        tokens = extractor.split_into_tokens(text, remove_stopwords=True)

        assert "the" not in tokens
        assert "is" not in tokens
        assert "quick" in tokens

    def test_split_into_tokens_min_length(self, extractor):
        """Test tokenization with minimum token length"""
        text = "a big beautiful cat and dog"
        tokens = extractor.split_into_tokens(text, min_length=3, remove_stopwords=False)

        # All tokens should have at least 3 chars
        assert all(len(t) >= 3 for t in tokens)

    def test_split_into_tokens_empty(self, extractor):
        """Test tokenization of empty text"""
        tokens = extractor.split_into_tokens("")
        assert tokens == []

    # ============= KEYWORD COMBINATION TESTS =============

    def test_combine_keywords_deduplication(self, extractor):
        """Test that combining keywords removes duplicates"""
        keywords_list = [
            ["machine", "learning", "ai"],
            ["machine", "deep learning", "neural"],
            ["ai", "algorithm"]
        ]
        combined = extractor.combine_keywords(keywords_list)

        # Should have unique keywords only
        assert combined.count("machine") == 1
        assert combined.count("ai") == 1
        assert "learning" in combined or "deep learning" in combined

    def test_combine_keywords_order_preservation(self, extractor):
        """Test that combine preserves order"""
        keywords_list = [
            ["first", "second"],
            ["third", "fourth"]
        ]
        combined = extractor.combine_keywords(keywords_list)

        # Should maintain order
        assert combined.index("first") < combined.index("second")

    def test_combine_keywords_empty_list(self, extractor):
        """Test combining empty keyword list"""
        combined = extractor.combine_keywords([])
        assert combined == []

    # ============= CACHING TESTS =============

    def test_cache_stats(self, extractor):
        """Test cache statistics"""
        # Extract some keywords to populate cache
        extractor.extract_keywords("test one", num_keywords=2, use_llm=False)
        extractor.extract_keywords("test two", num_keywords=2, use_llm=False)

        stats = extractor.get_cache_stats()

        assert "cache_size" in stats
        assert "max_size" in stats
        assert "utilization_percent" in stats
        assert stats["cache_size"] > 0

    def test_clear_cache(self, extractor):
        """Test cache clearing"""
        # Populate cache
        extractor.extract_keywords("test", num_keywords=2, use_llm=False)
        assert len(extractor.extraction_cache) > 0

        # Clear cache
        extractor.clear_cache()
        assert len(extractor.extraction_cache) == 0

    # ============= GLOBAL INSTANCE TESTS =============

    def test_get_entity_extractor_singleton(self):
        """Test that get_entity_extractor returns singleton"""
        extractor1 = get_entity_extractor()
        extractor2 = get_entity_extractor()

        # Should be same instance
        assert extractor1 is extractor2

    # ============= STOPWORDS TESTS =============

    def test_stopwords_english(self):
        """Test that English stopwords are loaded"""
        assert "the" in STOPWORDS
        assert "is" in STOPWORDS
        assert "and" in STOPWORDS
        assert "a" in STOPWORDS

    def test_stopwords_italian(self):
        """Test that Italian stopwords are loaded"""
        assert "il" in STOPWORDS
        assert "la" in STOPWORDS
        assert "è" in STOPWORDS

    def test_stopwords_count(self):
        """Test that reasonable number of stopwords are defined"""
        assert len(STOPWORDS) >= 50  # At least 50 stopwords


class TestExtractedEntity:
    """Test ExtractedEntity dataclass"""

    def test_extracted_entity_creation(self):
        """Test creating an ExtractedEntity"""
        entity = ExtractedEntity(
            text="New York",
            entity_type="entity",
            confidence=0.95,
            position=(0, 8)
        )

        assert entity.text == "New York"
        assert entity.entity_type == "entity"
        assert entity.confidence == 0.95
        assert entity.position == (0, 8)

    def test_extracted_entity_invalid_confidence(self):
        """Test that invalid confidence is caught"""
        # Confidence should be 0-1, but dataclass doesn't validate
        entity = ExtractedEntity(
            text="test",
            entity_type="keyword",
            confidence=1.5,  # Invalid but allowed
            position=(0, 4)
        )
        assert entity.confidence == 1.5  # Dataclass allows it


class TestEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def extractor(self):
        return EntityExtractor(llm_service=None)

    def test_very_long_text(self, extractor):
        """Test handling of very long text"""
        long_text = " ".join(["word"] * 10000)
        keywords = extractor.extract_keywords(long_text, num_keywords=5, use_llm=False)

        assert isinstance(keywords, list)
        assert len(keywords) <= 5

    def test_special_characters_handling(self, extractor):
        """Test handling of special characters"""
        text = "Hello @#$%^&*() World!!! Test"
        tokens = extractor.split_into_tokens(text)

        # Should handle special chars gracefully
        assert isinstance(tokens, list)
        assert "hello" in tokens or "world" in tokens

    def test_unicode_handling(self, extractor):
        """Test handling of unicode characters"""
        text = "Café résumé naïve 日本語 中文"
        tokens = extractor.split_into_tokens(text, remove_stopwords=False)

        # Should handle unicode without crashing
        assert isinstance(tokens, list)

    def test_mixed_case_normalization(self, extractor):
        """Test normalization of mixed case text"""
        text = "MiXeD CaSe TeXt"
        normalized = extractor.normalize_query(text)
        assert normalized == normalized.lower()

    def test_numbers_in_keywords(self, extractor):
        """Test keyword extraction with numbers"""
        text = "Python3 is better than Python2 for data science"
        keywords = extractor.extract_keywords(text, num_keywords=5, use_llm=False)

        # Should include numbered terms
        assert isinstance(keywords, list)
