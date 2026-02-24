"""
Performance Profiler - Misurazione dettagliata dei tempi di esecuzione
FASE 2: Profiling per identificare bottleneck
"""

import logging
import time
import statistics
from typing import Callable, Any, Dict, List
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TimingMetric:
    """Metrica di timing per un'operazione"""
    operation_name: str
    execution_time_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    call_count: int = 1
    tags: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """Profiler per timing dettagliato di operazioni RAG"""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.operation_count: Dict[str, int] = defaultdict(int)
        self.timestamps: Dict[str, List[datetime]] = defaultdict(list)
        self._active_timers = {}

    def start_timer(self, operation_name: str) -> str:
        """Inizia misurazione di un'operazione"""
        timer_id = f"{operation_name}_{time.time()}"
        self._active_timers[timer_id] = {
            "name": operation_name,
            "start": time.perf_counter()
        }
        return timer_id

    def end_timer(self, timer_id: str) -> float:
        """Termina misurazione e ritorna millisecondi"""
        if timer_id not in self._active_timers:
            logger.warning(f"Timer {timer_id} non trovato")
            return 0.0

        timer_info = self._active_timers.pop(timer_id)
        elapsed_ms = (time.perf_counter() - timer_info["start"]) * 1000

        operation_name = timer_info["name"]
        self.metrics[operation_name].append(elapsed_ms)
        self.operation_count[operation_name] += 1
        self.timestamps[operation_name].append(datetime.now())

        logger.debug(f"⏱️  {operation_name}: {elapsed_ms:.2f}ms")
        return elapsed_ms

    def record_operation(self, operation_name: str, execution_time_ms: float) -> None:
        """Registra direttamente un'operazione"""
        self.metrics[operation_name].append(execution_time_ms)
        self.operation_count[operation_name] += 1
        self.timestamps[operation_name].append(datetime.now())

    def get_stats(self, operation_name: str) -> Dict[str, float]:
        """Ritorna statistiche per un'operazione"""
        if operation_name not in self.metrics:
            return {}

        times = self.metrics[operation_name]
        if not times:
            return {}

        return {
            "count": len(times),
            "total_ms": sum(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "mean_ms": statistics.mean(times),
            "median_ms": statistics.median(times),
            "stdev_ms": statistics.stdev(times) if len(times) > 1 else 0,
            "per_operation_avg_ms": sum(times) / len(times)
        }

    def print_report(self, top_n: int = 10) -> str:
        """Genera report di performance"""
        report = f"\n{'='*80}\n"
        report += "PERFORMANCE PROFILING REPORT\n"
        report += f"{'='*80}\n\n"

        if not self.metrics:
            report += "No metrics recorded\n"
            return report

        # Ordina per tempo totale
        sorted_ops = sorted(
            self.metrics.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )[:top_n]

        report += f"{'Operation':<40} {'Count':>8} {'Total (ms)':>12} {'Mean (ms)':>12} {'Min (ms)':>12} {'Max (ms)':>12}\n"
        report += "-" * 100 + "\n"

        total_time = sum(sum(times) for times in self.metrics.values())

        for op_name, times in sorted_ops:
            count = len(times)
            total = sum(times)
            mean = total / count if count > 0 else 0
            min_time = min(times)
            max_time = max(times)
            pct = (total / total_time * 100) if total_time > 0 else 0

            report += f"{op_name:<40} {count:>8} {total:>12.2f} {mean:>12.2f} {min_time:>12.2f} {max_time:>12.2f}  ({pct:.1f}%)\n"

        report += "\n" + "="*80 + "\n"
        report += f"TOTAL EXECUTION TIME: {total_time:.2f}ms\n"
        report += f"TOTAL OPERATIONS: {sum(len(t) for t in self.metrics.values())}\n"
        report += "="*80 + "\n"

        return report

    def print_detailed_report(self) -> str:
        """Genera report dettagliato con statistiche"""
        report = f"\n{'='*80}\n"
        report += "DETAILED PERFORMANCE ANALYSIS\n"
        report += f"{'='*80}\n\n"

        if not self.metrics:
            report += "No metrics recorded\n"
            return report

        sorted_ops = sorted(
            self.metrics.items(),
            key=lambda x: sum(x[1]),
            reverse=True
        )

        for op_name, times in sorted_ops:
            stats = self.get_stats(op_name)

            report += f"\n📊 {op_name}\n"
            report += f"   Count:        {stats['count']}\n"
            report += f"   Total:        {stats['total_ms']:.2f}ms\n"
            report += f"   Mean:         {stats['mean_ms']:.2f}ms\n"
            report += f"   Median:       {stats['median_ms']:.2f}ms\n"
            report += f"   Min:          {stats['min_ms']:.2f}ms\n"
            report += f"   Max:          {stats['max_ms']:.2f}ms\n"
            report += f"   StdDev:       {stats['stdev_ms']:.2f}ms\n"

        report += "\n" + "="*80 + "\n"
        return report

    def reset(self) -> None:
        """Resetta tutti i metrics"""
        self.metrics.clear()
        self.operation_count.clear()
        self.timestamps.clear()
        self._active_timers.clear()


# Singleton profiler
_profiler_instance = None


def get_profiler() -> PerformanceProfiler:
    """Factory per performance profiler"""
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = PerformanceProfiler()
    return _profiler_instance


def profile_operation(operation_name: str):
    """Decorator per profiling automatico di funzioni"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            profiler = get_profiler()
            timer_id = profiler.start_timer(operation_name)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                profiler.end_timer(timer_id)
        return wrapper
    return decorator


# Decorator alternativo con nome dinamico
def profile_method(func: Callable) -> Callable:
    """Decorator che estrae il nome dal metodo"""
    operation_name = f"{func.__qualname__}"
    return profile_operation(operation_name)(func)


# Test suite per profiler
def test_profiler():
    """Test del profiler"""
    profiler = get_profiler()

    # Simula operazioni
    @profile_operation("vector_search")
    def mock_vector_search(n_docs: int):
        time.sleep(0.01 * (n_docs / 100))  # Simula delay proporzionale a docs

    @profile_operation("llm_completion")
    def mock_llm_completion():
        time.sleep(0.05)

    @profile_operation("embedding_generation")
    def mock_embedding():
        time.sleep(0.02)

    # Esegui operazioni multiple
    for _ in range(5):
        mock_vector_search(100)
        mock_llm_completion()
        mock_embedding()

    # Stampa report
    print(profiler.print_report())
    print(profiler.print_detailed_report())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_profiler()
