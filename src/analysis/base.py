"""
Phase 3A: Analysis Plugin Base Classes

Defines the contract every analysis plugin must fulfill.
All plugins:
  - Accept list[Chunk] as sole input to analyze()
  - Return AnalysisResult containing a typed payload and storage instructions
  - Handle their own exceptions internally (never raise to orchestrator)
  - Are independently testable without touching SQLite
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.document_ingestion import Chunk

from src.logging_config import get_logger

logger = get_logger(__name__)


class PluginStatus(Enum):
    """Execution status of a plugin run"""
    SUCCESS = "success"
    PARTIAL = "partial"       # Some results produced despite errors
    FAILED  = "failed"        # No results produced; error logged


@dataclass
class AnalysisResult:
    """
    Universal return type from every AnalysisPlugin.analyze() call.

    The 'payload' field carries the plugin-specific typed result
    (DocumentStructure, DocumentMetadata, or KnowledgeGraph).
    The orchestrator inspects 'plugin_name' to route to correct storage.

    Fields:
        plugin_name:    Identifier matching the plugin class name.
        doc_id:         Stable identifier for the document (stem of filename).
        status:         Outcome of the analysis run.
        payload:        Typed result object; None only when status == FAILED.
        error_message:  Human-readable failure reason; None on SUCCESS.
        duration_ms:    Wall-clock time consumed by analyze().
        chunks_processed: Input chunk count for diagnostics.
    """
    plugin_name: str
    doc_id: str
    status: PluginStatus
    payload: Optional[Any]
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    chunks_processed: int = 0


class AnalysisPlugin(ABC):
    """
    Abstract base for all Phase 3A analysis plugins.

    Subclasses implement analyze() and store_result().
    The orchestrator calls them in order:
        result = plugin.analyze(doc_id, chunks)
        plugin.store_result(result, store)

    Timing and exception wrapping are handled by this base class
    in the run() method, which is what the orchestrator actually calls.
    """

    @property
    @abstractmethod
    def plugin_name(self) -> str:
        """Stable string identifier, used as storage key."""
        ...

    @abstractmethod
    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """
        Core analysis logic. Must NOT raise exceptions.
        Must return AnalysisResult with appropriate status.

        Args:
            doc_id:  Stable document identifier (typically Path.stem).
            chunks:  All Chunk objects for this document in order.

        Returns:
            AnalysisResult with typed payload.
        """
        ...

    def run(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """
        Timed, exception-safe wrapper around analyze().

        Orchestrator calls this, not analyze() directly.
        This ensures timing data is always captured and exceptions
        from buggy plugins are caught rather than aborting the pipeline.
        """
        start = time.perf_counter()
        try:
            result = self.analyze(doc_id, chunks)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                f"Plugin {self.plugin_name} raised unexpectedly for doc '{doc_id}': {exc}",
                exc_info=True,
            )
            result = AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.FAILED,
                payload=None,
                error_message=str(exc),
                duration_ms=duration_ms,
                chunks_processed=len(chunks),
            )
        else:
            result.duration_ms = (time.perf_counter() - start) * 1000
            result.chunks_processed = len(chunks)

        logger.info(
            f"Plugin {self.plugin_name} completed "
            f"doc='{doc_id}' status={result.status.value} "
            f"duration={result.duration_ms:.1f}ms"
        )
        return result
