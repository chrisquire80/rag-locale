"""
Performance Benchmarking Suite for RAG LOCALE System
Measures execution time and memory usage across FASE 19-20
"""

import time
import tracemalloc
from typing import Dict, List, Callable
import statistics

from src.quality_metrics import get_quality_evaluator
from src.ux_enhancements import (
    get_response_enhancer,
    get_conversation_manager,
    ConversationTurn
)


class BenchmarkResult:
    """Store benchmark results"""

    def __init__(self, name: str):
        self.name = name
        self.times: List[float] = []
        self.memory_used: List[int] = []
        self.iterations = 0

    def add_result(self, execution_time: float, memory_bytes: int):
        """Add a single benchmark result"""
        self.times.append(execution_time)
        self.memory_used.append(memory_bytes)
        self.iterations += 1

    def get_stats(self) -> Dict:
        """Get statistics for results"""
        if not self.times:
            return {}

        return {
            'name': self.name,
            'iterations': self.iterations,
            'avg_time_ms': statistics.mean(self.times) * 1000,
            'min_time_ms': min(self.times) * 1000,
            'max_time_ms': max(self.times) * 1000,
            'stdev_ms': statistics.stdev(self.times) * 1000 if len(self.times) > 1 else 0,
            'avg_memory_kb': statistics.mean(self.memory_used) / 1024,
            'max_memory_kb': max(self.memory_used) / 1024,
        }

    def print_results(self):
        """Print formatted results"""
        stats = self.get_stats()
        if not stats:
            return

        print(f"\n{'='*60}")
        print(f"Benchmark: {stats['name']}")
        print(f"{'='*60}")
        print(f"  Iterations:     {stats['iterations']}")
        print(f"  Avg Time:       {stats['avg_time_ms']:.2f} ms")
        print(f"  Min Time:       {stats['min_time_ms']:.2f} ms")
        print(f"  Max Time:       {stats['max_time_ms']:.2f} ms")
        if stats['stdev_ms'] > 0:
            print(f"  Std Dev:        {stats['stdev_ms']:.2f} ms")
        print(f"  Avg Memory:     {stats['avg_memory_kb']:.2f} KB")
        print(f"  Max Memory:     {stats['max_memory_kb']:.2f} KB")


class PerformanceBenchmark:
    """Main benchmark orchestrator"""

    def __init__(self):
        self.results: Dict[str, BenchmarkResult] = {}

    def benchmark_function(self, name: str, func: Callable, *args, iterations: int = 5, **kwargs):
        """Benchmark a function multiple times"""
        result = BenchmarkResult(name)

        for _ in range(iterations):
            tracemalloc.start()
            start_time = time.perf_counter()

            # Execute function
            func(*args, **kwargs)

            end_time = time.perf_counter()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            execution_time = end_time - start_time
            result.add_result(execution_time, peak)

        self.results[name] = result
        return result

    def print_all_results(self):
        """Print all benchmark results"""
        print("\n" + "="*60)
        print("RAG LOCALE PERFORMANCE BENCHMARK RESULTS")
        print("="*60)

        for result in self.results.values():
            result.print_results()

        self.print_summary()

    def print_summary(self):
        """Print summary comparison"""
        print("\n" + "="*60)
        print("SUMMARY - Average Execution Times (Fastest to Slowest)")
        print("="*60)

        sorted_results = sorted(
            self.results.items(),
            key=lambda x: x[1].get_stats().get('avg_time_ms', 0)
        )

        for i, (name, result) in enumerate(sorted_results, 1):
            stats = result.get_stats()
            if stats:
                print(f"  {i}. {name:40} {stats['avg_time_ms']:8.2f} ms")


# ============================================================================
# FASE 19: Quality Metrics Benchmarks
# ============================================================================

class Fase19Benchmark:
    """Benchmark FASE 19 operations"""

    @staticmethod
    def benchmark_quality_evaluation(benchmark: PerformanceBenchmark):
        """Benchmark quality evaluation"""
        evaluator = get_quality_evaluator()

        test_docs = [
            {
                'id': 'doc_1',
                'text': 'This is test content about machine learning.',
                'metadata': {'source': 'Test Source'}
            }
        ]

        def evaluate_short():
            evaluator.evaluate_query(
                query_id="q1",
                query="What is ML?",
                answer="ML is learning.",
                retrieved_documents=test_docs
            )

        def evaluate_medium():
            evaluator.evaluate_query(
                query_id="q2",
                query="What is machine learning and how does it work?",
                answer="Machine learning is a subset of artificial intelligence that learns from data.",
                retrieved_documents=test_docs
            )

        def evaluate_long():
            evaluator.evaluate_query(
                query_id="q3",
                query="Explain machine learning, deep learning, and neural networks?",
                answer="Machine learning is a subset of AI. Deep learning uses neural networks. Neural networks are inspired by biological neurons.",
                retrieved_documents=test_docs * 3
            )

        benchmark.benchmark_function(
            "Quality Evaluation - Short Query",
            evaluate_short,
            iterations=10
        )
        benchmark.benchmark_function(
            "Quality Evaluation - Medium Query",
            evaluate_medium,
            iterations=10
        )
        benchmark.benchmark_function(
            "Quality Evaluation - Long Query",
            evaluate_long,
            iterations=5
        )


# ============================================================================
# FASE 20: UX Enhancement Benchmarks
# ============================================================================

class Fase20Benchmark:
    """Benchmark FASE 20 operations"""

    @staticmethod
    def benchmark_response_enhancement(benchmark: PerformanceBenchmark):
        """Benchmark response enhancement"""
        enhancer = get_response_enhancer()

        test_docs_1 = [
            {
                'id': 'doc_1',
                'text': 'Document content about the topic.',
                'metadata': {'source': 'Source'}
            }
        ]

        test_docs_3 = [
            {'id': f'doc_{i}', 'text': f'Content {i}.', 'metadata': {'source': f'Source {i}'}}
            for i in range(3)
        ]

        def enhance_single_doc():
            enhancer.enhance_response(
                query="What is the topic?",
                answer="The topic is important.",
                retrieved_documents=test_docs_1,
                quality_score=0.85
            )

        def enhance_multiple_docs():
            enhancer.enhance_response(
                query="What is the topic?",
                answer="The topic covers multiple aspects discussed in the sources.",
                retrieved_documents=test_docs_3,
                quality_score=0.85
            )

        benchmark.benchmark_function(
            "Response Enhancement - Single Document",
            enhance_single_doc,
            iterations=10
        )
        benchmark.benchmark_function(
            "Response Enhancement - Multiple Documents",
            enhance_multiple_docs,
            iterations=10
        )

    @staticmethod
    def benchmark_conversation_operations(benchmark: PerformanceBenchmark):
        """Benchmark conversation management"""
        conv_manager = get_conversation_manager()

        def create_and_add_5_turns():
            session_id = "session_5"
            conv_manager.create_conversation(session_id)

            for i in range(5):
                turn = ConversationTurn(
                    turn_id=f"turn_{i}",
                    query=f"Question {i}?",
                    answer=f"Answer {i}.",
                    quality_score=0.8
                )
                conv_manager.add_turn(session_id, turn)

        def create_and_add_10_turns():
            session_id = "session_10"
            conv_manager.create_conversation(session_id)

            for i in range(10):
                turn = ConversationTurn(
                    turn_id=f"turn_{i}",
                    query=f"Question {i}?",
                    answer=f"Answer {i}.",
                    quality_score=0.8
                )
                conv_manager.add_turn(session_id, turn)

        def conversation_context_extraction():
            session_id = "session_context"
            conv_manager.create_conversation(session_id)

            for i in range(5):
                turn = ConversationTurn(
                    turn_id=f"turn_{i}",
                    query=f"Q{i}?",
                    answer=f"A{i}.",
                    quality_score=0.8
                )
                conv_manager.add_turn(session_id, turn)

            # Extract context
            conv_manager.get_context(session_id, max_turns=3)
            conv_manager.summarize_conversation(session_id)

        benchmark.benchmark_function(
            "Conversation - Create and Add 5 Turns",
            create_and_add_5_turns,
            iterations=5
        )
        benchmark.benchmark_function(
            "Conversation - Create and Add 10 Turns",
            create_and_add_10_turns,
            iterations=5
        )
        benchmark.benchmark_function(
            "Conversation - Context & Summary (5 turns)",
            conversation_context_extraction,
            iterations=5
        )


# ============================================================================
# Integrated Pipeline Benchmarks
# ============================================================================

class IntegratedPipelineBenchmark:
    """Benchmark complete integrated pipelines"""

    @staticmethod
    def benchmark_quality_to_enhancement(benchmark: PerformanceBenchmark):
        """Benchmark quality evaluation to response enhancement"""
        evaluator = get_quality_evaluator()
        enhancer = get_response_enhancer()

        test_docs = [
            {
                'id': 'doc_1',
                'text': 'Content about topic.',
                'metadata': {'source': 'Source'}
            }
        ]

        def quality_and_enhancement():
            # Evaluate
            evaluation = evaluator.evaluate_query(
                query_id="test",
                query="What is the topic?",
                answer="The topic is important.",
                retrieved_documents=test_docs
            )

            # Enhance with quality score
            enhancer.enhance_response(
                query="What is the topic?",
                answer="The topic is important.",
                retrieved_documents=test_docs,
                quality_score=evaluation.get_overall_score()
            )

        benchmark.benchmark_function(
            "Pipeline - Quality + Enhancement Combined",
            quality_and_enhancement,
            iterations=10
        )

    @staticmethod
    def benchmark_full_conversation_turn(benchmark: PerformanceBenchmark):
        """Benchmark complete conversation turn processing"""
        evaluator = get_quality_evaluator()
        enhancer = get_response_enhancer()
        conv_manager = get_conversation_manager()

        test_docs = [
            {
                'id': 'doc_1',
                'text': 'Content for analysis.',
                'metadata': {'source': 'Source'}
            }
        ]

        def full_conversation_turn():
            session_id = "full_turn"
            conv_manager.create_conversation(session_id)

            # Evaluate
            evaluation = evaluator.evaluate_query(
                query_id="q1",
                query="What is the topic?",
                answer="The topic is important.",
                retrieved_documents=test_docs
            )

            # Enhance
            enhanced = enhancer.enhance_response(
                query="What is the topic?",
                answer="The topic is important.",
                retrieved_documents=test_docs,
                quality_score=evaluation.get_overall_score()
            )

            # Store
            turn = ConversationTurn(
                turn_id="turn_1",
                query="What is the topic?",
                answer=enhanced['answer'],
                quality_score=enhanced['quality_score']
            )
            conv_manager.add_turn(session_id, turn)

        benchmark.benchmark_function(
            "Pipeline - Complete Conversation Turn",
            full_conversation_turn,
            iterations=5
        )


# ============================================================================
# Main Benchmark Execution
# ============================================================================

def run_all_benchmarks():
    """Run all benchmarks"""
    benchmark = PerformanceBenchmark()

    print("\n" + "="*60)
    print("RAG LOCALE Performance Benchmarks")
    print("Testing FASE 19 (Quality Metrics) & FASE 20 (UX Enhancements)")
    print("="*60)

    # FASE 19 Benchmarks
    print("\nRunning FASE 19 Benchmarks (Quality Metrics)...")
    Fase19Benchmark.benchmark_quality_evaluation(benchmark)

    # FASE 20 Benchmarks
    print("Running FASE 20 Benchmarks (UX Enhancements)...")
    Fase20Benchmark.benchmark_response_enhancement(benchmark)
    Fase20Benchmark.benchmark_conversation_operations(benchmark)

    # Integrated Pipeline
    print("Running Integrated Pipeline Benchmarks...")
    IntegratedPipelineBenchmark.benchmark_quality_to_enhancement(benchmark)
    IntegratedPipelineBenchmark.benchmark_full_conversation_turn(benchmark)

    # Print results
    benchmark.print_all_results()

    return benchmark


if __name__ == "__main__":
    benchmark = run_all_benchmarks()
