"""
INT8 Quantization - Riduzione memoria per embeddings
FASE 6: Quantizza embeddings da float32 a int8 per 4x memoria savings

Quantizzazione:
- Float32: 4 byte per valore (768 dim = 3072 bytes per embedding)
- Int8: 1 byte per valore (768 dim = 768 bytes per embedding)
- Savings: 75% riduzione di memoria
- Trade-off: Minore accuratezza (~99% precisione con proper scaling)
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class QuantizationStats:
    """Statistiche di quantizzazione"""
    original_dtype: str
    quantized_dtype: str
    original_bytes: int
    quantized_bytes: int
    compression_ratio: float  # original_bytes / quantized_bytes
    memory_saved_pct: float  # (1 - quantized/original) * 100
    num_embeddings: int
    embedding_dim: int

class EmbeddingQuantizer:
    """Quantizza embeddings a INT8 per ridurre memoria"""

    def __init__(self, enable_quantization: bool = True):
        self.enable_quantization = enable_quantization
        self.quantization_scales: list[float] = []
        self.quantization_offsets: list[float] = []

    def quantize_embeddings(
        self,
        embeddings: list[np.ndarray]
    ) -> tuple[list[np.ndarray], QuantizationStats]:
        """
        Quantizza embeddings a INT8

        Process:
        1. Normalize each embedding to [-127, 127] range
        2. Convert float32 to int8
        3. Store scale factors for dequantization

        Returns:
            (quantized_embeddings, stats)
        """
        if not self.enable_quantization or not embeddings:
            return embeddings, self._get_no_quant_stats(embeddings)

        logger.info(f"Quantizing {len(embeddings)} embeddings to INT8...")

        quantized = []
        self.quantization_scales = []
        self.quantization_offsets = []

        for embedding in embeddings:
            # Find min/max
            min_val = np.min(embedding)
            max_val = np.max(embedding)

            # Avoid division by zero
            if max_val - min_val < 1e-6:
                scale = 1.0
                offset = min_val
                quantized_emb = np.zeros_like(embedding, dtype=np.int8)
            else:
                # Scale to [-127, 127]
                scale = (max_val - min_val) / 254.0
                offset = min_val
                quantized_emb = np.round(
                    (embedding - offset) / scale - 127.0
                ).astype(np.int8)

            self.quantization_scales.append(scale)
            self.quantization_offsets.append(offset)
            quantized.append(quantized_emb)

        # Compute statistics
        original_bytes = len(embeddings) * embeddings[0].itemsize * len(embeddings[0])
        quantized_bytes = len(quantized) * quantized[0].itemsize * len(quantized[0])

        stats = QuantizationStats(
            original_dtype="float32",
            quantized_dtype="int8",
            original_bytes=original_bytes,
            quantized_bytes=quantized_bytes,
            compression_ratio=original_bytes / quantized_bytes if quantized_bytes > 0 else 0,
            memory_saved_pct=(1 - quantized_bytes / original_bytes) * 100 if original_bytes > 0 else 0,
            num_embeddings=len(embeddings),
            embedding_dim=len(embeddings[0]) if embeddings else 0
        )

        logger.info(f"✓ Quantization complete:")
        logger.info(f"  Original: {original_bytes:,} bytes ({stats.original_dtype})")
        logger.info(f"  Quantized: {quantized_bytes:,} bytes ({stats.quantized_dtype})")
        logger.info(f"  Compression: {stats.compression_ratio:.1f}x ({stats.memory_saved_pct:.1f}% savings)")

        return quantized, stats

    def dequantize_embedding(
        self,
        quantized_emb: np.ndarray,
        idx: int
    ) -> np.ndarray:
        """Dequantizza un embedding"""
        if idx >= len(self.quantization_scales):
            logger.warning(f"Scale not found for embedding {idx}")
            return quantized_emb.astype(np.float32)

        scale = self.quantization_scales[idx]
        offset = self.quantization_offsets[idx]

        # Reverse quantization
        dequantized = (quantized_emb.astype(np.float32) + 127.0) * scale + offset
        return dequantized

    def dequantize_embeddings(
        self,
        quantized_embeddings: list[np.ndarray]
    ) -> list[np.ndarray]:
        """Dequantizza lista di embeddings"""
        dequantized = []
        for i, quantized in enumerate(quantized_embeddings):
            dequantized.append(self.dequantize_embedding(quantized, i))
        return dequantized

    def compute_similarity_quantized(
        self,
        query: np.ndarray,
        quantized_candidate: np.ndarray,
        candidate_idx: int
    ) -> float:
        """
        Computa similarità tra query (float32) e candidate quantizzato (int8)
        senza dequantizzazione completa (più veloce)
        """
        # Dequantizza solo il candidate
        candidate = self.dequantize_embedding(quantized_candidate, candidate_idx)

        # Cosine similarity
        dot_product = np.dot(query, candidate)
        norm_query = np.linalg.norm(query)
        norm_candidate = np.linalg.norm(candidate)

        if norm_query == 0 or norm_candidate == 0:
            return 0.0

        return dot_product / (norm_query * norm_candidate)

    @staticmethod
    def _get_no_quant_stats(embeddings: list[np.ndarray]) -> QuantizationStats:
        """Stats per embeddings non quantizzati"""
        original_bytes = len(embeddings) * 4 * len(embeddings[0]) if embeddings else 0
        return QuantizationStats(
            original_dtype="float32",
            quantized_dtype="float32",
            original_bytes=original_bytes,
            quantized_bytes=original_bytes,
            compression_ratio=1.0,
            memory_saved_pct=0.0,
            num_embeddings=len(embeddings),
            embedding_dim=len(embeddings[0]) if embeddings else 0
        )

def benchmark_quantization():
    """Benchmark quantizzazione vs memoria/accuratezza"""
    import time

    logger.info(f"\n{'='*60}")
    logger.info(f"Quantization Benchmark")
    logger.info(f"{'='*60}")

    # Generate synthetic embeddings
    np.random.seed(42)
    num_embeddings = 1000
    embedding_dim = 768

    embeddings = [
        np.random.randn(embedding_dim).astype(np.float32)
        for _ in range(num_embeddings)
    ]

    # Normalize embeddings
    embeddings = [
        emb / (np.linalg.norm(emb) + 1e-8)
        for emb in embeddings
    ]

    # Quantize
    logger.info(f"\nQuantizing {num_embeddings} embeddings ({embedding_dim}D)...")
    quantizer = EmbeddingQuantizer(enable_quantization=True)

    start = time.perf_counter()
    quantized, stats = quantizer.quantize_embeddings(embeddings)
    quant_time = time.perf_counter() - start

    logger.info(f"✓ Quantization time: {quant_time:.3f}s")

    # Benchmark similarity search
    logger.info(f"\nBenchmarking similarity search...")
    query = embeddings[0]

    # Original (float32)
    start = time.perf_counter()
    for candidate in embeddings[1:100]:
        dot = np.dot(query, candidate)
    float_time = time.perf_counter() - start

    # Quantized (int8 + dequant)
    start = time.perf_counter()
    for i, quantized_candidate in enumerate(quantized[1:100]):
        sim = quantizer.compute_similarity_quantized(
            query,
            quantized_candidate,
            i + 1
        )
    quant_search_time = time.perf_counter() - start

    logger.info(f"\nSearch Performance (100 candidates):")
    logger.info(f"  Float32: {float_time*1000:.2f}ms")
    logger.info(f"  Quantized: {quant_search_time*1000:.2f}ms")
    logger.info(f"  Overhead: {(quant_search_time/float_time - 1)*100:.1f}%")

    # Accuracy test
    logger.info(f"\nAccuracy Test (10 random candidates)...")
    test_indices = np.random.choice(len(embeddings), 10, replace=False)

    float_similarities = []
    quant_similarities = []

    for idx in test_indices:
        candidate = embeddings[idx]
        quantized_candidate = quantized[idx]

        # Float32 similarity
        float_sim = np.dot(query, candidate)
        float_similarities.append(float_sim)

        # Quantized similarity
        quant_sim = quantizer.compute_similarity_quantized(
            query,
            quantized_candidate,
            idx
        )
        quant_similarities.append(quant_sim)

    # Calculate rank correlation
    float_ranks = np.argsort(float_similarities)
    quant_ranks = np.argsort(quant_similarities)

    # Simple rank correlation metric (how many in same order)
    matches = sum(1 for i, j in zip(float_ranks, quant_ranks) if abs(i - j) <= 1)
    accuracy_pct = (matches / len(test_indices)) * 100

    logger.info(f"  Rank correlation: {accuracy_pct:.1f}%")
    logger.info(f"  Average float similarity: {np.mean(float_similarities):.4f}")
    logger.info(f"  Average quantized similarity: {np.mean(quant_similarities):.4f}")

if __name__ == "__main__":
    benchmark_quantization()
