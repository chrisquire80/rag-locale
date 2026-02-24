"""
Hardware Optimization - Specifico per HP ProBook 440 G11
FASE 3: Ottimizzazione per CPU-only, 16GB RAM, Windows 11

HP ProBook 440 G11 Specs:
- CPU: Intel Core i5/i7 (12-13th gen, 4-8 cores)
- RAM: 16GB DDR4 (user reported)
- GPU: Intel Iris Xe (integrated, no CUDA)
- Storage: SSD
- OS: Windows 11 Pro
"""

import os
import psutil
import platform
from typing import Dict, Any
from dataclasses import dataclass

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class SystemProfile:
    """Profilo hardware del sistema"""
    cpu_count: int
    cpu_count_logical: int
    total_memory_gb: float
    available_memory_gb: float
    memory_percent: float
    python_version: str
    platform_name: str
    cpu_freq_ghz: float
    is_hp_probook: bool = False

class HardwareOptimizer:
    """Ottimizzazioni specifiche per HP ProBook"""

    # HP ProBook 440 G11 safe defaults
    HP_PROBOOK_DEFAULTS = {
        # Memory optimization
        "max_parallel_workers": 4,  # Safe per 16GB
        "chunk_cache_mb": 256,  # Conservative cache size
        "vector_batch_size": 25,  # Reduced from 50 for stability
        "embedding_cache_entries": 500,  # Reduced from 1000

        # CPU optimization
        "num_threads_vector_search": 2,  # Parallel search threads
        "pdf_worker_timeout_sec": 300,  # 5 min timeout
        "gc_frequency_docs": 10,  # Garbage collection every 10 pages

        # API optimization
        "api_batch_size": 25,  # Smaller batches for stability
        "api_retry_max": 5,
        "api_backoff_base_sec": 1.0,

        # Network optimization
        "request_timeout_sec": 300,
        "connection_pool_size": 4,
        "dns_cache_enabled": True,
    }

    # HP ProBook 440 G11 aggressive mode (if memory allows)
    HP_PROBOOK_AGGRESSIVE = {
        "max_parallel_workers": 6,
        "chunk_cache_mb": 512,
        "vector_batch_size": 50,
        "embedding_cache_entries": 1000,
        "num_threads_vector_search": 4,
    }

    def __init__(self):
        self.system_profile = self._detect_hardware()
        self.config = self._generate_config()

    def _detect_hardware(self) -> SystemProfile:
        """Rileva caratteristiche hardware"""
        try:
            cpu_count = os.cpu_count() or 4
            memory_bytes = psutil.virtual_memory().total
            total_memory_gb = memory_bytes / (1024**3)
            available_memory_gb = psutil.virtual_memory().available / (1024**3)
            memory_percent = psutil.virtual_memory().percent

            try:
                cpu_freq = psutil.cpu_freq()
                cpu_freq_ghz = cpu_freq.current / 1000 if cpu_freq else 2.5
            except (AttributeError, OSError, TypeError):
                cpu_freq_ghz = 2.5

            profile = SystemProfile(
                cpu_count=cpu_count,
                cpu_count_logical=os.cpu_count() or 4,
                total_memory_gb=total_memory_gb,
                available_memory_gb=available_memory_gb,
                memory_percent=memory_percent,
                python_version=platform.python_version(),
                platform_name=platform.system(),
                cpu_freq_ghz=cpu_freq_ghz,
                is_hp_probook=self._is_hp_probook()
            )

            logger.info(f"✓ System Profile Detected:")
            logger.info(f"  CPU: {profile.cpu_count} cores @ {profile.cpu_freq_ghz:.1f}GHz")
            logger.info(f"  RAM: {profile.total_memory_gb:.1f}GB (Available: {profile.available_memory_gb:.1f}GB)")
            logger.info(f"  Python: {profile.python_version}")
            logger.info(f"  Platform: {profile.platform_name}")

            return profile

        except Exception as e:
            logger.warning(f"Failed to detect hardware: {e}")
            # Default fallback
            return SystemProfile(
                cpu_count=4,
                cpu_count_logical=4,
                total_memory_gb=16.0,
                available_memory_gb=8.0,
                memory_percent=50,
                python_version=platform.python_version(),
                platform_name=platform.system(),
                cpu_freq_ghz=2.5,
                is_hp_probook=False
            )

    def _is_hp_probook(self) -> bool:
        """Rileva se è HP ProBook"""
        try:
            import subprocess
            result = subprocess.run(
                ["wmic", "computersystem", "get", "model"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return "ProBook" in result.stdout
        except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False

    def _generate_config(self) -> Dict[str, Any]:
        """Genera configurazione ottimale basata su hardware"""
        config = dict(self.HP_PROBOOK_DEFAULTS)

        # Adjust based on CPU count
        if self.system_profile.cpu_count >= 6:
            config["max_parallel_workers"] = min(8, self.system_profile.cpu_count)
            config["num_threads_vector_search"] = min(4, self.system_profile.cpu_count // 2)
        elif self.system_profile.cpu_count >= 4:
            config["max_parallel_workers"] = 4
            config["num_threads_vector_search"] = 2

        # Adjust based on available memory
        if self.system_profile.available_memory_gb > 12:
            logger.info("💾 Sufficient memory - enabling aggressive optimizations")
            config.update(self.HP_PROBOOK_AGGRESSIVE)
        elif self.system_profile.available_memory_gb < 6:
            logger.warning("⚠️  Low available memory - restricting workers")
            config["max_parallel_workers"] = 2
            config["chunk_cache_mb"] = 128
            config["embedding_cache_entries"] = 250

        return config

    def get_config(self) -> Dict[str, Any]:
        """Ritorna configurazione ottimale"""
        return self.config

    def get_optimal_workers(self) -> int:
        """Ritorna numero ottimale di worker threads"""
        return self.config["max_parallel_workers"]

    def get_optimal_batch_size(self) -> int:
        """Ritorna batch size ottimale per API calls"""
        return self.config["api_batch_size"]

    def get_optimal_vector_batch_size(self) -> int:
        """Ritorna vector batch size ottimale"""
        return self.config["vector_batch_size"]

    def get_memory_warning_threshold_pct(self) -> float:
        """Threshold per warning memoria"""
        # Se memoria totale < 12GB, warning a 70%
        # Se memoria totale >= 12GB, warning a 80%
        if self.system_profile.total_memory_gb < 12:
            return 70.0
        else:
            return 80.0

    def check_memory_health(self) -> bool:
        """Controlla salute memoria"""
        try:
            memory_percent = psutil.virtual_memory().percent
            threshold = self.get_memory_warning_threshold_pct()

            if memory_percent > threshold:
                logger.warning(
                    f"⚠️  Memory usage critical: {memory_percent:.1f}% "
                    f"(threshold: {threshold:.1f}%)"
                )
                return False
            elif memory_percent > 70:
                logger.info(
                    f"💾 Memory usage elevated: {memory_percent:.1f}%"
                )
            else:
                logger.debug(f"💾 Memory usage: {memory_percent:.1f}%")

            return True
        except Exception as e:
            logger.error(f"Failed to check memory: {e}")
            return True

    def get_performance_recommendations(self) -> str:
        """Ritorna raccomandazioni di performance"""
        recs = []

        if self.system_profile.cpu_count < 4:
            recs.append("⚠️  Low CPU count (<4 cores) - Consider upgrading for better performance")

        if self.system_profile.total_memory_gb < 12:
            recs.append("⚠️  Less than 12GB RAM - Recommend upgrading for optimal performance")

        if self.system_profile.memory_percent > 80:
            recs.append("⚠️  High memory usage (>80%) - Close unnecessary applications")

        if self.system_profile.available_memory_gb < 3:
            recs.append("🔴 CRITICAL: Very low available memory (<3GB) - System may freeze")

        if not recs:
            recs.append("✅ System is well-optimized for RAG LOCALE")

        return "\n".join(recs)

    def print_optimization_report(self) -> str:
        """Genera report di ottimizzazione"""
        report = f"\n{'='*80}\n"
        report += "HARDWARE OPTIMIZATION REPORT\n"
        report += f"{'='*80}\n\n"

        report += "SYSTEM PROFILE:\n"
        report += f"  CPU Cores:          {self.system_profile.cpu_count} physical (logical: {self.system_profile.cpu_count_logical})\n"
        report += f"  CPU Frequency:      {self.system_profile.cpu_freq_ghz:.1f} GHz\n"
        report += f"  Total Memory:       {self.system_profile.total_memory_gb:.1f} GB\n"
        report += f"  Available Memory:   {self.system_profile.available_memory_gb:.1f} GB ({100-self.system_profile.memory_percent:.1f}% free)\n"
        report += f"  Python Version:     {self.system_profile.python_version}\n"
        report += f"  Platform:           {self.system_profile.platform_name}\n"
        report += f"  HP ProBook:         {'Yes' if self.system_profile.is_hp_probook else 'No (assumed)'}\n"

        report += "\nOPTIMIZED CONFIGURATION:\n"
        for key, value in sorted(self.config.items()):
            report += f"  {key:<35} {value}\n"

        report += "\nPERFORMANCE RECOMMENDATIONS:\n"
        for rec in self.get_performance_recommendations().split("\n"):
            report += f"  {rec}\n"

        report += "\n" + "="*80 + "\n"
        return report

# Singleton optimizer
_optimizer_instance = None

def get_hardware_optimizer() -> HardwareOptimizer:
    """Factory per hardware optimizer"""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = HardwareOptimizer()
    return _optimizer_instance

if __name__ == "__main__":
    optimizer = get_hardware_optimizer()
    print(optimizer.print_optimization_report())
