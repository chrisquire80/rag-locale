"""
Phase 3C: Export Engine

Handles document export to multiple formats (Markdown, PDF, JSON).
Preserves structure, metadata, and analysis results.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from src.logging_config import get_logger

if TYPE_CHECKING:
    from src.analysis.document_analyzer import DocumentAnalysis

logger = get_logger(__name__)


class ExportFormat(Enum):
    """Supported export formats"""

    MARKDOWN = "markdown"
    PDF = "pdf"
    JSON = "json"


@dataclass
class ExportOptions:
    """Options for document export"""

    include_metadata: bool = True
    include_structure: bool = True
    include_knowledge_graph: bool = False
    include_analysis: bool = True
    format_: ExportFormat = ExportFormat.MARKDOWN
    output_path: Optional[Path] = None


class ExportEngine:
    """
    Exports documents in multiple formats with full structure and metadata.
    """

    def __init__(self) -> None:
        """Initialize export engine"""
        logger.info("ExportEngine initialized")

    def export_document(
        self,
        doc_id: str,
        analysis: DocumentAnalysis,
        options: ExportOptions = None,
    ) -> Optional[str]:
        """
        Export a single document with all analysis results.

        Args:
            doc_id: Document identifier
            analysis: DocumentAnalysis result with metadata, sections, edges
            options: Export options (format, what to include)

        Returns:
            Export content (str) or None if failed
        """
        if options is None:
            options = ExportOptions()

        try:
            if options.format_ == ExportFormat.MARKDOWN:
                return self._export_markdown(doc_id, analysis, options)
            elif options.format_ == ExportFormat.JSON:
                return self._export_json(doc_id, analysis, options)
            elif options.format_ == ExportFormat.PDF:
                logger.info("PDF export requested (implementation deferred to Phase 6.1)")
                return self._export_pdf_stub(doc_id, analysis, options)
            else:
                logger.error(f"Unknown export format: {options.format_}")
                return None

        except Exception as e:
            logger.error(f"Export failed for '{doc_id}': {e}", exc_info=True)
            return None

    def _export_markdown(
        self,
        doc_id: str,
        analysis: DocumentAnalysis,
        options: ExportOptions,
    ) -> str:
        """
        Export document as Markdown with structure and metadata.

        Args:
            doc_id: Document ID
            analysis: Analysis results
            options: Export options

        Returns:
            Markdown-formatted string
        """
        buf = StringIO()
        now_iso = datetime.now().isoformat()

        # YAML frontmatter with metadata
        if options.include_metadata:
            buf.write("---\n")
            if analysis.metadata:
                m = analysis.metadata
                buf.write(f"title: {m.title}\n")
                buf.write(f"doc_id: {doc_id}\n")
                buf.write(f"language: {m.language}\n")
                buf.write(f"type: {m.doc_type}\n")
                buf.write(f"reading_level: {m.reading_level}\n")
                buf.write(f"word_count: {m.word_count}\n")
                buf.write(f"exported_at: {now_iso}\n")
            buf.write("---\n\n")

        # Document structure with sections
        if options.include_structure and analysis.sections:
            buf.write("# Document Structure\n\n")
            for section in analysis.sections:
                heading_prefix = "#" * min(section.level, 6)
                buf.write(f"{heading_prefix} {section.title}\n\n")

        # Metadata section
        if options.include_metadata and analysis.metadata:
            m = analysis.metadata
            buf.write("\n## Metadata\n\n")
            buf.write(f"- **Language**: {m.language}\n")
            buf.write(f"- **Type**: {m.doc_type}\n")
            buf.write(f"- **Reading Level**: {m.reading_level}\n")
            buf.write(f"- **Word Count**: {m.word_count:,}\n")
            buf.write(f"- **Sections**: {len(analysis.sections)}\n")

            if m.keywords:
                buf.write(f"- **Keywords**: {', '.join(m.keywords[:10])}\n")
            if m.author:
                buf.write(f"- **Author**: {m.author}\n\n")

        # Knowledge graph summary
        if options.include_knowledge_graph and analysis.edges:
            buf.write("\n## Knowledge Graph\n\n")
            buf.write(f"**Relationships**: {len(analysis.edges)} extracted\n\n")

            # Top relationships by weight
            top_edges = sorted(analysis.edges, key=lambda e: e.weight, reverse=True)[:20]
            for edge in top_edges:
                source = edge.source_entity_id.split("_e_")[-1].replace("_", " ")
                target = edge.target_entity_id.split("_e_")[-1].replace("_", " ")
                buf.write(
                    f"- **{source}** -> **{target}** (co-occurrences: {edge.weight})\n"
                )

        return buf.getvalue()

    def _export_json(
        self,
        doc_id: str,
        analysis: DocumentAnalysis,
        options: ExportOptions,
    ) -> str:
        """
        Export document as JSON with complete analysis.

        Args:
            doc_id: Document ID
            analysis: Analysis results
            options: Export options

        Returns:
            JSON-formatted string
        """
        export_data = {
            "doc_id": doc_id,
            "exported_at": datetime.now().isoformat(),
            "analysis_available": analysis.analysis_available,
        }

        # Include metadata
        if options.include_metadata and analysis.metadata:
            m = analysis.metadata
            export_data["metadata"] = {
                "title": m.title,
                "language": m.language,
                "type": m.doc_type,
                "reading_level": m.reading_level,
                "word_count": m.word_count,
                "chunk_count": m.chunk_count,
                "keywords": m.keywords,
                "author": m.author,
                "source_filename": m.source_filename,
            }

        # Include structure
        if options.include_structure and analysis.sections:
            export_data["sections"] = [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "level": s.level,
                    "parent_id": s.parent_id,
                    "chunk_count": len(s.chunk_indices),
                }
                for s in analysis.sections
            ]

        # Include knowledge graph
        if options.include_knowledge_graph and analysis.edges:
            export_data["knowledge_edges"] = [
                {
                    "source": e.source_entity_id,
                    "target": e.target_entity_id,
                    "relationship": e.relationship,
                    "weight": e.weight,
                }
                for e in analysis.edges
            ]

        # Include plugin statuses
        export_data["plugin_statuses"] = analysis.plugin_statuses

        return json.dumps(export_data, indent=2)

    def _export_pdf_stub(
        self,
        doc_id: str,
        analysis: DocumentAnalysis,
        options: ExportOptions,
    ) -> str:
        """
        Stub for PDF export (full implementation in Phase 6.1).

        For now, returns markdown representation with PDF export message.
        """
        lines = [
            f"# PDF Export - {doc_id}",
            "",
            "PDF export is scheduled for Phase 6.1",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "Content would include:",
            "- Title page with metadata",
            "- Section-by-section breakdown",
            "- Knowledge graph relationships",
            "- Formatted for printing",
        ]

        if analysis.metadata:
            lines.extend(
                [
                    "",
                    f"**{analysis.metadata.title}**",
                    f"Type: {analysis.metadata.doc_type}",
                    f"Language: {analysis.metadata.language}",
                ]
            )

        return "\n".join(lines)

    def export_comparison(
        self,
        doc_ids: list[str],
        comparison_data: dict,
        format_: ExportFormat = ExportFormat.MARKDOWN,
    ) -> Optional[str]:
        """
        Export document comparison results.

        Args:
            doc_ids: Documents being compared
            comparison_data: Comparison results
            format_: Export format

        Returns:
            Formatted comparison report or None
        """
        try:
            if format_ == ExportFormat.MARKDOWN:
                return self._export_comparison_markdown(doc_ids, comparison_data)
            elif format_ == ExportFormat.JSON:
                return json.dumps(comparison_data, indent=2)
            else:
                logger.warning(f"Comparison export format not supported: {format_}")
                return None

        except Exception as e:
            logger.error(f"Comparison export failed: {e}")
            return None

    def _export_comparison_markdown(
        self,
        doc_ids: list[str],
        comparison: dict,
    ) -> str:
        """
        Export comparison as markdown side-by-side format.

        Args:
            doc_ids: Documents being compared
            comparison: Comparison results

        Returns:
            Markdown-formatted comparison
        """
        buf = StringIO()
        buf.write("# Document Comparison Report\n\n")
        buf.write(f"**Comparing**: {', '.join(doc_ids)}\n")
        buf.write(f"**Generated**: {datetime.now().isoformat()}\n")
        buf.write(f"**Overall Similarity**: {comparison.get('overall_similarity', 0):.0%}\n\n")

        # Shared concepts
        shared = comparison.get("shared_concepts", [])
        if shared:
            buf.write("## Shared Concepts\n\n")
            buf.write("Topics and entities present in both documents:\n\n")
            for concept in shared[:20]:
                buf.write(f"- {concept}\n")
            buf.write("\n")

        # Overlap metrics
        metrics = comparison.get("overlap_metrics", {})
        if metrics:
            buf.write("## Overlap Metrics\n\n")
            for metric_name, metric_data in metrics.items():
                value = metric_data.get("value", 0)
                description = metric_data.get("description", "")
                buf.write(f"- **{metric_name}**: {value:.0%} ({description})\n")
            buf.write("\n")

        return buf.getvalue()

    def export_conversation(
        self,
        messages: list[dict],
        format_: ExportFormat = ExportFormat.MARKDOWN,
    ) -> Optional[str]:
        """
        Export conversation/chat history.

        Args:
            messages: Chat messages with roles and content
            format_: Export format

        Returns:
            Formatted conversation or None
        """
        try:
            if format_ == ExportFormat.MARKDOWN:
                return self._export_conversation_markdown(messages)
            elif format_ == ExportFormat.JSON:
                return json.dumps(messages, indent=2)
            else:
                return None

        except Exception as e:
            logger.error(f"Conversation export failed: {e}")
            return None

    def _export_conversation_markdown(self, messages: list[dict]) -> str:
        """Export conversation as readable markdown"""
        buf = StringIO()
        buf.write("# Conversation Export\n")
        buf.write(f"Generated: {datetime.now().isoformat()}\n")
        buf.write(f"Messages: {len(messages)}\n\n")

        for i, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            nav_type = msg.get("navigation_type", "")

            buf.write(f"## [{i}] {role}\n")
            if nav_type:
                buf.write(f"*Type: {nav_type}*\n")
            buf.write(f"\n{content}\n\n")

        return buf.getvalue()


# Global singleton
_export_engine: Optional[ExportEngine] = None


def get_export_engine() -> ExportEngine:
    """Get or create singleton ExportEngine instance"""
    global _export_engine
    if _export_engine is None:
        _export_engine = ExportEngine()
    return _export_engine
