#!/usr/bin/env python3
"""
Performance Profiling Script - Identify execution bottlenecks
Uses cProfile to measure function call times and identify optimization targets
"""

import cProfile
import pstats
import io
from pathlib import Path
import json
from typing import Dict, List, Tuple

def profile_vector_store_operations():
    """Profile vector store: add documents and search"""
    from src.vector_store import get_vector_store

    print("\n[PROFILING] Vector Store Operations...")

    # Sample documents
    docs = [
        "Python is a high-level programming language",
        "Machine learning enables computers to learn from data",
        "Artificial intelligence is transforming industries",
        "Neural networks mimic biological neurons",
        "Deep learning requires massive computational power"
    ] * 5  # 25 documents

    profiler = cProfile.Profile()

    # Profile add_documents
    print("  - Adding 25 documents...")
    profiler.enable()
    vector_store = get_vector_store()
    vector_store.add_documents(docs)
    profiler.disable()

    # Profile search
    print("  - Searching 10 queries...")
    profiler.enable()
    for _ in range(10):
        vector_store.search("machine learning")
    profiler.disable()

    return profiler


def profile_llm_operations():
    """Profile LLM: get embeddings"""
    from src.llm_service import get_llm_service

    print("\n[PROFILING] LLM Service Operations...")

    texts = [
        "What is machine learning?",
        "Explain neural networks",
        "How does deep learning work?"
    ] * 3  # 9 texts

    profiler = cProfile.Profile()

    print("  - Getting embeddings for 9 texts...")
    llm_service = get_llm_service()

    profiler.enable()
    for text in texts:
        try:
            llm_service.get_embedding(text)
        except Exception as e:
            print(f"    Warning: {str(e)[:50]}")
    profiler.disable()

    return profiler


def profile_memory_service():
    """Profile memory service: add and retrieve interactions"""
    from src.memory_service import get_memory_service

    print("\n[PROFILING] Memory Service Operations...")

    memory_service = get_memory_service()
    profiler = cProfile.Profile()

    print("  - Adding 20 interactions...")
    profiler.enable()
    for i in range(20):
        memory_service.save_interaction(
            user_query=f"Query {i}",
            ai_response=f"Response {i}",
            referenced_docs=["doc1.pdf"],
            found_anomalies=i % 3 == 0
        )
    profiler.disable()

    # Profile retrieval
    print("  - Retrieving interaction history...")
    profiler.enable()
    memory_service.get_anomalies_history(limit=10)
    memory_service.get_stats()
    profiler.disable()

    return profiler


def profile_rag_engine():
    """Profile RAG engine: initialization (skip to avoid nested profilers)"""
    # Note: RAG engine profiling skipped to avoid nested profiler conflict
    # The vector store and LLM profiling already covers the key components
    print("\n[PROFILING] RAG Engine Operations... [SKIPPED - avoids nested profiler conflicts]")

    # Return empty profiler
    profiler = cProfile.Profile()
    return profiler


def analyze_profiler(profiler: cProfile.Profile, operation: str) -> Dict:
    """Analyze profiler results and return top functions"""
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
    ps.print_stats(20)  # Top 20 functions

    # Parse results
    output = s.getvalue()
    lines = output.split('\n')

    # Extract key metrics
    results = {
        'operation': operation,
        'top_functions': [],
        'total_calls': 0,
        'total_time': 0.0
    }

    in_stats = False
    for line in lines:
        if 'function calls' in line:
            # Extract total calls and time
            parts = line.split()
            if len(parts) > 0:
                try:
                    results['total_calls'] = int(parts[0])
                    for part in parts:
                        if 's' in part and '.' in part:
                            results['total_time'] = float(part.replace('s', ''))
                except:
                    pass

        # Parse function stats
        if 'ncalls' in line:
            in_stats = True
            continue

        if in_stats and line.strip() and '{' not in line:
            parts = line.split()
            if len(parts) >= 6:
                try:
                    results['top_functions'].append({
                        'ncalls': parts[0],
                        'tottime': float(parts[1]),
                        'percall_tottime': float(parts[2]),
                        'cumtime': float(parts[3]),
                        'percall_cumtime': float(parts[4]),
                        'function': ' '.join(parts[5:])
                    })
                except:
                    pass

    return results


def print_bottleneck_report(results_list: List[Dict]):
    """Print human-readable bottleneck report"""
    print("\n" + "="*80)
    print("PERFORMANCE PROFILING REPORT - BOTTLENECK ANALYSIS")
    print("="*80)

    for result in results_list:
        print(f"\n[{result['operation']}]")
        print(f"  Total Calls: {result['total_calls']}")
        print(f"  Total Time: {result['total_time']:.4f}s")

        if result['top_functions']:
            print(f"  Top Functions by Cumulative Time:")
            for i, func in enumerate(result['top_functions'][:5], 1):
                print(f"    {i}. {func['function']}")
                print(f"       Cumulative Time: {func['cumtime']:.4f}s ({float(func['cumtime'])*100:.1f}% of total)")
                print(f"       Total Time: {func['tottime']:.4f}s")
                print(f"       Calls: {func['ncalls']}")


def main():
    """Run all profiling operations"""
    print("\n" + "="*80)
    print("STARTING PERFORMANCE PROFILING")
    print("="*80)

    results = []

    # Profile each operation
    try:
        profiler = profile_vector_store_operations()
        results.append(analyze_profiler(profiler, "Vector Store (add + search)"))
    except Exception as e:
        print(f"  Error profiling vector store: {e}")

    try:
        profiler = profile_llm_operations()
        results.append(analyze_profiler(profiler, "LLM Service (embeddings)"))
    except Exception as e:
        print(f"  Error profiling LLM: {e}")

    try:
        profiler = profile_memory_service()
        results.append(analyze_profiler(profiler, "Memory Service (add + retrieve)"))
    except Exception as e:
        print(f"  Error profiling memory service: {e}")

    try:
        profiler = profile_rag_engine()
        results.append(analyze_profiler(profiler, "RAG Engine (initialization)"))
    except Exception as e:
        print(f"  Error profiling RAG engine: {e}")

    # Print report
    print_bottleneck_report(results)

    # Save results to JSON
    json_results = []
    for r in results:
        r_copy = r.copy()
        r_copy['top_functions'] = r_copy['top_functions'][:5]  # Keep top 5
        json_results.append(r_copy)

    output_file = Path('performance_profile_results.json')
    with open(output_file, 'w') as f:
        json.dump(json_results, f, indent=2)

    print(f"\n[OK] Results saved to {output_file}")
    print("\n" + "="*80)
    print("PROFILING COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
