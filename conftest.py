"""
Pytest configuration and fixtures for RAG LOCALE
Provides isolated test environments, mocking, and shared test utilities
"""

import pytest
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path


# ============================================================================
# EXTERNAL SERVICE MOCKS
# ============================================================================

@pytest.fixture
def mock_gemini_api():
    """
    Mock Gemini LLM API to avoid external service dependency in tests
    Provides consistent responses for deterministic test behavior
    """
    def mock_response(prompt: str, **kwargs) -> str:
        """Generate mock response based on prompt type"""
        prompt_lower = prompt.lower()

        if "summarize" in prompt_lower:
            return "This is a mock summary of the provided text."
        elif "extract" in prompt_lower:
            return "Mock extracted information"
        elif "expand" in prompt_lower:
            return "expanded query terms semantic variations"
        elif "rerank" in prompt_lower:
            return "[1, 3, 2]"  # Mock relevance ranking
        else:
            return "Mock response to your question based on the provided context."

    with patch('src.llm_service.LLMService.generate_response') as mock:
        mock.side_effect = mock_response
        yield mock


@pytest.fixture
def mock_vision_api():
    """
    Mock Vision API to avoid external service dependency
    Provides consistent image analysis results
    """
    with patch('src.vision_service.VisionService.analyze_image') as mock:
        mock.return_value = {
            'description': 'Mock image description',
            'text': 'Extracted text from image',
            'confidence': 0.85
        }
        yield mock


@pytest.fixture
def mock_embedding_service():
    """
    Mock embedding generation to avoid external service dependency
    Provides consistent embeddings for vector operations
    """
    import numpy as np

    def mock_embedding(text: str, **kwargs) -> list:
        """Generate deterministic embedding from text"""
        # Create a simple but deterministic embedding
        text_bytes = text.encode('utf-8')
        seed = sum(text_bytes) % (2**32)
        np.random.seed(seed)
        return np.random.randn(1536).tolist()  # Gemini embedding dimension

    with patch('src.vector_store.ChromaVectorStore._get_embedding') as mock:
        mock.side_effect = mock_embedding
        yield mock


# ============================================================================
# ISOLATED TEST FIXTURES
# ============================================================================

@pytest.fixture
def isolated_vector_store():
    """
    Provides isolated ChromaDB instance per test
    Prevents concurrent access issues and test pollution
    """
    from src.vector_store import ChromaVectorStore

    with tempfile.TemporaryDirectory() as tmpdir:
        store = ChromaVectorStore(persist_dir=tmpdir)
        yield store
        # Cleanup happens automatically when temp directory is deleted


@pytest.fixture
def isolated_memory_service():
    """
    Provides isolated memory service with temporary database
    Prevents test interference and ensures cleanup
    """
    from src.memory_service import MemoryService

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        service = MemoryService(db_path=str(db_path))
        yield service
        service.shutdown()


@pytest.fixture
def isolated_cache():
    """
    Provides isolated cache instance for testing
    """
    from src.cache import CacheManager

    cache = CacheManager(max_size=100)
    yield cache
    cache.clear()


# ============================================================================
# MOCK DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_documents():
    """
    Provides sample documents for ingestion testing
    """
    return [
        {
            'filename': 'sample1.txt',
            'content': '''
                Machine learning is a subset of artificial intelligence.
                It focuses on training algorithms with data.
                Deep learning uses neural networks with multiple layers.
            '''.strip()
        },
        {
            'filename': 'sample2.txt',
            'content': '''
                Python is a popular programming language.
                It has a simple syntax and rich ecosystem.
                NumPy and Pandas are essential data science libraries.
            '''.strip()
        },
        {
            'filename': 'sample3.txt',
            'content': '''
                Retrieval-augmented generation combines retrieval and generation.
                It improves answer quality by fetching relevant context.
                RAG systems excel at knowledge-grounded tasks.
            '''.strip()
        }
    ]


@pytest.fixture
def sample_queries():
    """
    Provides sample queries for testing search and retrieval
    """
    return [
        "What is machine learning?",
        "How does deep learning work?",
        "Explain neural networks",
        "What are Python libraries for data science?",
        "How does RAG improve answer quality?"
    ]


@pytest.fixture
def sample_retrieval_results():
    """
    Provides mock retrieval results for testing reranking and response generation
    """
    from src.rag_engine import RetrievalResult

    return [
        RetrievalResult(
            file_name='sample1.txt',
            content='Machine learning is a subset of artificial intelligence.',
            score=0.92,
            chunk_index=0
        ),
        RetrievalResult(
            file_name='sample1.txt',
            content='It focuses on training algorithms with data.',
            score=0.85,
            chunk_index=1
        ),
        RetrievalResult(
            file_name='sample1.txt',
            content='Deep learning uses neural networks with multiple layers.',
            score=0.88,
            chunk_index=2
        ),
    ]


# ============================================================================
# CONFIGURATION FIXTURES
# ============================================================================

@pytest.fixture
def test_config():
    """
    Provides test configuration with safe defaults
    """
    return {
        'top_k': 3,
        'similarity_threshold': 0.5,
        'max_context_tokens': 4000,
        'temperature': 0.7,
        'use_reranking': True,
        'cache_ttl_seconds': 3600,
        'embedding_model': 'models/embedding-001',
        'llm_model': 'gemini-pro'
    }


# ============================================================================
# PYTEST HOOKS & CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "external_service: marks tests requiring external services"
    )
    config.addinivalue_line(
        "markers", "requires_gemini: marks tests requiring Gemini API"
    )


@pytest.fixture(scope="function", autouse=True)
def reset_singletons():
    """
    Reset singleton instances between tests to prevent cross-test pollution
    """
    yield  # Run test

    # Cleanup after test
    try:
        from src.metrics import _metrics_collector_instance
        if hasattr(_metrics_collector_instance, 'clear'):
            _metrics_collector_instance.clear()
    except (ImportError, AttributeError):
        pass


@pytest.fixture(scope="function", autouse=True)
def setup_logging():
    """
    Setup logging for tests
    """
    import logging
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during tests
        format='%(name)s - %(levelname)s - %(message)s'
    )
    yield


# ============================================================================
# PARAMETRIZATION FIXTURES
# ============================================================================

def pytest_generate_tests(metafunc):
    """
    Dynamic test parametrization based on markers
    """
    if "chunk_size" in metafunc.fixturenames:
        metafunc.parametrize("chunk_size", [512, 1024, 2048])

    if "embedding_model" in metafunc.fixturenames:
        metafunc.parametrize("embedding_model", [
            'models/embedding-001',
            'models/embedding-004'
        ])
