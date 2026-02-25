"""
Phase 3A: DocumentAnalyzer — Plugin Orchestrator

Main entry point for the analysis subsystem.
Called by DocumentIngestionPipeline after vector store insertion.

Responsibilities:
  1. Hold plugin instances in an ordered registry.
  2. Call plugin.run() for each plugin (error-safe, timed).
  3. Route results to MetadataStore based on plugin_name.
  4. Provide get_analysis(doc_id) for cached retrieval by RAGEngine and UI.

Design:
  - Single global instance via get_document_analyzer() factory.
  - Plugins run synchronously in registration order.
  - Failed plugins are logged; orchestrator always returns a
    DocumentAnalysis with partial or empty data rather than raising.
  - MetadataStore is injected; default path is data/analysis.db.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from src.config import DATA_DIR
from src.logging_config import get_logger
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus
from src.analysis.metadata_store import MetadataStore, DocumentMetadataRow, DocumentSectionRow, KnowledgeEdgeRow
from src.analysis.structure_plugin import StructurePlugin
from src.analysis.metadata_plugin import MetadataPlugin
from src.analysis.knowledge_plugin import KnowledgePlugin

if TYPE_CHECKING:
    from src.document_ingestion import Chunk

logger = get_logger(__name__)

_DEFAULT_DB_PATH = DATA_DIR / "analysis.db"


@dataclass
class DocumentAnalysis:
    """
    Aggregated result from all plugins for one document.

    Returned by get_analysis() and used directly by the UI and RAGEngine.
    Fields are Optional because individual plugins can fail independently.

    Fields:
        doc_id:     Stable document identifier.
        metadata:   Result from MetadataPlugin (DocumentMetadataRow).
        sections:   Result from StructurePlugin (list of DocumentSectionRow).
        edges:      Result from KnowledgePlugin (list of KnowledgeEdgeRow).
        plugin_statuses: dict mapping plugin_name -> PluginStatus value string.
        analysis_available: True if at least one plugin succeeded.
    """
    doc_id: str
    metadata: Optional[DocumentMetadataRow] = None
    sections: list[DocumentSectionRow] = field(default_factory=list)
    edges: list[KnowledgeEdgeRow] = field(default_factory=list)
    plugin_statuses: dict[str, str] = field(default_factory=dict)
    analysis_available: bool = False


class DocumentAnalyzer:
    """
    Orchestrates all analysis plugins for a document.

    Typical usage (called from DocumentIngestionPipeline):

        analyzer = get_document_analyzer()
        analysis = analyzer.analyze(doc_id="my_policy", chunks=chunks)
        # Results are now persisted; also returned for immediate use.

    Retrieval from cache (called from RAGEngine or UI):

        analyzer = get_document_analyzer()
        analysis = analyzer.get_analysis("my_policy")
    """

    def __init__(self, store: Optional[MetadataStore] = None) -> None:
        self._store = store or MetadataStore(_DEFAULT_DB_PATH)
        self._plugins: list[AnalysisPlugin] = [
            MetadataPlugin(),    # fastest, enriches Chunk.extra_metadata
            StructurePlugin(),   # heading hierarchy
            KnowledgePlugin(),   # entity graph (slowest, last)
        ]
        logger.info(
            f"DocumentAnalyzer initialized with {len(self._plugins)} plugins: "
            f"{[p.plugin_name for p in self._plugins]}"
        )

    def register_plugin(self, plugin: AnalysisPlugin) -> None:
        """
        Add a custom plugin at runtime.

        Plugins registered after initialization run after the built-in three.
        This is the extension point for Phase 3B additions (e.g., TablePlugin).

        Args:
            plugin: Any AnalysisPlugin subclass instance.
        """
        self._plugins.append(plugin)
        logger.info(f"Registered custom plugin: {plugin.plugin_name}")

    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> DocumentAnalysis:
        """
        Run all registered plugins on the provided chunks and persist results.

        This method is called from DocumentIngestionPipeline.ingest_single_file()
        immediately after vector store insertion succeeds. Failures in any plugin
        are caught and logged — they never abort ingestion.

        Args:
            doc_id: Stable document identifier (typically Path(filename).stem).
            chunks: All Chunk objects produced by DocumentProcessor for this file.

        Returns:
            DocumentAnalysis aggregating all plugin outputs.
        """
        if not chunks:
            logger.warning(f"DocumentAnalyzer.analyze() called with no chunks for '{doc_id}'")
            return DocumentAnalysis(doc_id=doc_id)

        logger.info(f"Starting analysis for '{doc_id}' ({len(chunks)} chunks)")

        results: list[AnalysisResult] = []
        for plugin in self._plugins:
            result = plugin.run(doc_id, chunks)
            results.append(result)
            self._store_result(result)

        return self._aggregate(doc_id, results)

    def get_analysis(self, doc_id: str) -> DocumentAnalysis:
        """
        Retrieve cached analysis from SQLite for a previously analyzed document.

        Returns DocumentAnalysis with analysis_available=False if the document
        has not been analyzed yet (graceful degradation for the UI).

        Args:
            doc_id: Stable document identifier.

        Returns:
            DocumentAnalysis with populated fields from the database.
        """
        try:
            metadata = self._store.get_document_metadata(doc_id)
            sections = self._store.get_sections(doc_id)
            edges    = self._store.get_edges(doc_id)
            available = metadata is not None

            return DocumentAnalysis(
                doc_id=doc_id,
                metadata=metadata,
                sections=sections,
                edges=edges,
                analysis_available=available,
            )
        except Exception as exc:
            logger.error(f"Failed to retrieve analysis for '{doc_id}': {exc}")
            return DocumentAnalysis(doc_id=doc_id, analysis_available=False)

    def get_all_analyzed_doc_ids(self) -> list[str]:
        """Return list of all doc_ids that have stored analysis."""
        try:
            return self._store.list_analyzed_documents()
        except Exception as exc:
            logger.error(f"Failed to list analyzed documents: {exc}")
            return []

    def delete_analysis(self, doc_id: str) -> None:
        """
        Remove all analysis data for a document.
        Call this when a document is deleted from the vector store.
        """
        try:
            self._store.delete_document(doc_id)
            logger.info(f"Deleted analysis data for '{doc_id}'")
        except Exception as exc:
            logger.error(f"Failed to delete analysis for '{doc_id}': {exc}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _store_result(self, result: AnalysisResult) -> None:
        """
        Route a plugin result to the appropriate MetadataStore method.
        Logs errors but never raises.
        """
        if result.status == PluginStatus.FAILED or result.payload is None:
            logger.warning(
                f"Skipping storage for failed plugin '{result.plugin_name}' "
                f"doc='{result.doc_id}': {result.error_message}"
            )
            return

        try:
            if result.plugin_name == "metadata":
                self._store.upsert_document_metadata(result.payload)
            elif result.plugin_name == "structure":
                self._store.upsert_sections(result.payload.sections)
            elif result.plugin_name == "knowledge":
                self._store.upsert_edges(result.payload.edges)
            else:
                # Future plugins: store payload in extracted_elements or custom table
                logger.debug(
                    f"No storage handler for plugin '{result.plugin_name}'; result not persisted."
                )
        except Exception as exc:
            logger.error(
                f"Storage failed for plugin '{result.plugin_name}' "
                f"doc='{result.doc_id}': {exc}",
                exc_info=True,
            )

    def _aggregate(
        self,
        doc_id: str,
        results: list[AnalysisResult],
    ) -> DocumentAnalysis:
        """Build DocumentAnalysis from list of AnalysisResult objects."""
        statuses = {r.plugin_name: r.status.value for r in results}
        any_success = any(r.status != PluginStatus.FAILED for r in results)

        # Re-read from store to return validated Pydantic rows
        return DocumentAnalysis(
            doc_id=doc_id,
            metadata=self._store.get_document_metadata(doc_id),
            sections=self._store.get_sections(doc_id),
            edges=self._store.get_edges(doc_id),
            plugin_statuses=statuses,
            analysis_available=any_success,
        )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_document_analyzer: Optional[DocumentAnalyzer] = None


def get_document_analyzer() -> DocumentAnalyzer:
    """
    Get or create the global DocumentAnalyzer singleton.
    Thread-safe via module-level lazy initialization (GIL-protected in CPython).
    """
    global _document_analyzer
    if _document_analyzer is None:
        _document_analyzer = DocumentAnalyzer()
    return _document_analyzer
