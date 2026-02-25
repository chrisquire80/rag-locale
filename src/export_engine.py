"""
Phase 3C: Export Engine

Handles document export to multiple formats (Markdown, PDF, JSON).
Preserves structure, metadata, and analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import json
from datetime import datetime

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
        lines = []

        # YAML frontmatter with metadata
        if options.include_metadata:
            lines.append("---")
            if analysis.metadata:
                m = analysis.metadata
                lines.append(f"title: {m.title}")
                lines.append(f"doc_id: {doc_id}")
                lines.append(f"language: {m.language}")
                lines.append(f"type: {m.doc_type}")
                lines.append(f"reading_level: {m.reading_level}")
                lines.append(f"word_count: {m.word_count}")
                lines.append(f"exported_at: {datetime.now().isoformat()}")
            lines.append("---")
            lines.append("")

        # Document structure with sections
        if options.include_structure and analysis.sections:
            lines.append("# Document Structure\n")
            for section in analysis.sections:
                # Recreate heading hierarchy using level
                heading_prefix = "#" * min(section.level.value, 6)  # H6 max
                lines.append(f"{heading_prefix} {section.title}\n")

        # Metadata section
        if options.include_metadata and analysis.metadata:
            m = analysis.metadata
            lines.append("\n## Metadata\n")
            lines.append(f"- **Language**: {m.language}")
            lines.append(f"- **Type**: {m.doc_type}")
            lines.append(f"- **Reading Level**: {m.reading_level}")
            lines.append(f"- **Word Count**: {m.word_count:,}")
            lines.append(f"- **Sections**: {len(analysis.sections)}")

            if m.keywords:
                lines.append(f"- **Keywords**: {', '.join(m.keywords[:10])}")
            if m.author:
                lines.append(f"- **Author**: {m.author}\n")

        # Knowledge graph summary
        if options.include_knowledge_graph and analysis.edges:
            lines.append("\n## Knowledge Graph\n")
            lines.append(f"**Relationships**: {len(analysis.edges)} extracted\n")

            # Top relationships by weight
            top_edges = sorted(analysis.edges, key=lambda e: e.weight, reverse=True)[
                :20
            ]
            for edge in top_edges:
                source = edge.source_entity_id.split("_e_")[-1].replace("_", " ")
                target = edge.target_entity_id.split("_e_")[-1].replace("_", " ")
                lines.append(
                    f"- **{source}** → **{target}** (co-occurrences: {edge.weight})"
                )

        return "\n".join(lines)

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
                    "level": s.level.value,
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
        lines = [
            "# Document Comparison Report",
            "",
            f"**Comparing**: {', '.join(doc_ids)}",
            f"**Generated**: {datetime.now().isoformat()}",
            f"**Overall Similarity**: {comparison.get('overall_similarity', 0):.0%}",
            "",
        ]

        # Shared concepts
        shared = comparison.get("shared_concepts", [])
        if shared:
            lines.extend(
                [
                    "## Shared Concepts",
                    "",
                    "Topics and entities present in both documents:",
                    "",
                ]
            )
            for concept in shared[:20]:
                lines.append(f"- {concept}")
            lines.append("")

        # Overlap metrics
        metrics = comparison.get("overlap_metrics", {})
        if metrics:
            lines.extend(
                [
                    "## Overlap Metrics",
                    "",
                ]
            )
            for metric_name, metric_data in metrics.items():
                value = metric_data.get("value", 0)
                description = metric_data.get("description", "")
                lines.append(f"- **{metric_name}**: {value:.0%} ({description})")
            lines.append("")

        return "\n".join(lines)

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
        lines = [
            "# Conversation Export",
            f"Generated: {datetime.now().isoformat()}",
            f"Messages: {len(messages)}",
            "",
        ]

        for i, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            nav_type = msg.get("navigation_type", "")

            lines.append(f"## [{i}] {role}")
            if nav_type:
                lines.append(f"*Type: {nav_type}*")
            lines.append("")
            lines.append(content)
            lines.append("")

        return "\n".join(lines)


# Global singleton
_export_engine: Optional[ExportEngine] = None


def get_export_engine() -> ExportEngine:
    """Get or create singleton ExportEngine instance"""
    global _export_engine
    if _export_engine is None:
        _export_engine = ExportEngine()
    return _export_engine
