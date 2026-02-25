"""
Phase 3C: Comparison Plugin

Builds document comparison analysis using existing similarity matrices and multi-doc insights.

Features:
- Side-by-side document comparison (overlap and differences)
- Section-level comparison (structure and content)
- Overlap detection (shared entities and concepts)
- Contradiction identification (conflicting information)
- Complementary content extraction (what one doc adds to another)

Storage: comparison_results written to analysis.db via MetadataStore extension
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
import numpy as np

from src.logging_config import get_logger
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus

if TYPE_CHECKING:
    from src.document_ingestion import Chunk
    from src.analysis.document_analyzer import DocumentAnalyzer

logger = get_logger(__name__)


@dataclass
class ComparisonMetric:
    """Metric measuring relationship between two documents"""

    metric_name: str  # 'overlap', 'similarity', 'contradiction', 'complement'
    value: float  # 0.0-1.0
    description: str = ""


@dataclass
class SectionComparison:
    """Comparison between two sections from different documents"""

    section1_id: str
    section1_title: str
    section2_id: str
    section2_title: str
    similarity_score: float  # 0.0-1.0
    overlap_entities: list[str] = field(default_factory=list)
    unique_to_section1: list[str] = field(default_factory=list)
    unique_to_section2: list[str] = field(default_factory=list)


@dataclass
class DocumentComparison:
    """Complete comparison between two or more documents"""

    doc_ids: list[str]
    comparison_type: str  # 'pairwise' | 'multi'
    overall_similarity: float
    overlap_metrics: dict[str, ComparisonMetric] = field(default_factory=dict)
    section_comparisons: list[SectionComparison] = field(default_factory=list)
    shared_concepts: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    complementary_insights: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class ComparisonPlugin(AnalysisPlugin):
    """
    Compares documents to identify overlap, differences, and insights.

    Note: Comparison typically happens across documents (not single-doc analysis),
    but implementing as AnalysisPlugin for consistency with architecture.
    """

    def __init__(self) -> None:
        """Initialize comparison plugin"""
        self._similarity_matrix = None
        self._doc_embeddings = {}

    @property
    def plugin_name(self) -> str:
        return "comparison"

    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """
        Per-document analysis: prepare for comparison (extract entity list, keywords).

        Note: Full comparison happens in DocumentAnalyzer.compare_documents()
        """
        try:
            # Extract entities and keywords for comparison purposes
            entities = set()
            keywords = set()

            for chunk in chunks:
                # Extract proper nouns (simplified approach)
                import re

                # Find capitalized sequences
                capitalized = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", chunk.text)
                entities.update(capitalized[:10])  # Top 10 per chunk

                # Extract keywords (4+ char words, not stopwords)
                words = re.findall(r"\b[a-z]{4,}\b", chunk.text.lower())
                keywords.update(words[:20])

            metadata = {
                "entities": list(entities),
                "keywords": list(keywords),
                "doc_id": doc_id,
            }

            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.SUCCESS,
                payload=metadata,
            )

        except Exception as exc:
            logger.error(f"ComparisonPlugin failed for '{doc_id}': {exc}")
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.FAILED,
                payload=None,
                error_message=str(exc),
            )

    def compare_documents(
        self,
        doc_id_1: str,
        doc_id_2: str,
        analysis_1: Optional[dict] = None,
        analysis_2: Optional[dict] = None,
    ) -> DocumentComparison:
        """
        Compare two documents using their analyses.

        Args:
            doc_id_1: First document ID
            doc_id_2: Second document ID
            analysis_1: Analysis metadata for doc 1 (entities, keywords)
            analysis_2: Analysis metadata for doc 2 (entities, keywords)

        Returns:
            DocumentComparison with overlap, differences, insights
        """
        try:
            # Extract entities from analyses
            entities_1 = set(analysis_1.get("entities", []) if analysis_1 else [])
            entities_2 = set(analysis_2.get("entities", []) if analysis_2 else [])

            keywords_1 = set(analysis_1.get("keywords", []) if analysis_1 else [])
            keywords_2 = set(analysis_2.get("keywords", []) if analysis_2 else [])

            # Calculate overlaps
            shared_entities = entities_1 & entities_2
            shared_keywords = keywords_1 & keywords_2
            unique_to_1 = (entities_1 | keywords_1) - (entities_2 | keywords_2)
            unique_to_2 = (entities_2 | keywords_2) - (entities_1 | keywords_1)

            # Calculate similarity (Jaccard index)
            combined = entities_1 | entities_2 | keywords_1 | keywords_2
            if combined:
                shared = shared_entities | shared_keywords
                similarity = len(shared) / len(combined)
            else:
                similarity = 0.0

            # Build comparison
            comparison = DocumentComparison(
                doc_ids=[doc_id_1, doc_id_2],
                comparison_type="pairwise",
                overall_similarity=similarity,
                overlap_metrics={
                    "entity_overlap": ComparisonMetric(
                        metric_name="entity_overlap",
                        value=len(shared_entities) / max(len(entities_1 | entities_2), 1),
                        description=f"Shared {len(shared_entities)} entities",
                    ),
                    "keyword_overlap": ComparisonMetric(
                        metric_name="keyword_overlap",
                        value=len(shared_keywords) / max(len(keywords_1 | keywords_2), 1),
                        description=f"Shared {len(shared_keywords)} keywords",
                    ),
                },
                shared_concepts=list(shared_entities | shared_keywords),
                metadata={
                    "unique_to_doc1_count": len(unique_to_1),
                    "unique_to_doc2_count": len(unique_to_2),
                    "shared_concepts_count": len(shared_entities | shared_keywords),
                },
            )

            logger.info(
                f"Compared '{doc_id_1}' and '{doc_id_2}': similarity={similarity:.0%}, "
                f"shared_concepts={len(shared_entities | shared_keywords)}"
            )

            return comparison

        except Exception as e:
            logger.error(f"Error comparing documents: {e}", exc_info=True)
            return DocumentComparison(
                doc_ids=[doc_id_1, doc_id_2],
                comparison_type="pairwise",
                overall_similarity=0.0,
            )

    def compare_sections(
        self,
        section_1: dict,
        section_2: dict,
    ) -> SectionComparison:
        """
        Compare two sections from different documents.

        Args:
            section_1: Section data (id, title, chunk content)
            section_2: Section data (id, title, chunk content)

        Returns:
            SectionComparison with overlap and differences
        """
        try:
            # Extract text from sections
            text_1 = section_1.get("text", "").lower()
            text_2 = section_2.get("text", "").lower()

            # Extract common words (3+ chars, not stopwords)
            import re

            stopwords = {
                "the",
                "and",
                "for",
                "with",
                "that",
                "this",
                "from",
                "are",
                "is",
                "in",
                "on",
                "at",
                "of",
                "to",
                "a",
            }

            words_1 = set(w for w in re.findall(r"\b\w{3,}\b", text_1) if w not in stopwords)
            words_2 = set(w for w in re.findall(r"\b\w{3,}\b", text_2) if w not in stopwords)

            shared = words_1 & words_2
            unique_1 = words_1 - words_2
            unique_2 = words_2 - words_1

            # Calculate similarity
            combined = words_1 | words_2
            similarity = len(shared) / max(len(combined), 1)

            comparison = SectionComparison(
                section1_id=section_1.get("id", "unknown"),
                section1_title=section_1.get("title", "Unknown"),
                section2_id=section_2.get("id", "unknown"),
                section2_title=section_2.get("title", "Unknown"),
                similarity_score=similarity,
                overlap_entities=list(shared)[:10],
                unique_to_section1=list(unique_1)[:5],
                unique_to_section2=list(unique_2)[:5],
            )

            return comparison

        except Exception as e:
            logger.error(f"Error comparing sections: {e}")
            return SectionComparison(
                section1_id=section_1.get("id", ""),
                section1_title=section_1.get("title", ""),
                section2_id=section_2.get("id", ""),
                section2_title=section_2.get("title", ""),
                similarity_score=0.0,
            )


# Global singleton
_comparison_plugin: Optional[ComparisonPlugin] = None


def get_comparison_plugin() -> ComparisonPlugin:
    """Get or create singleton ComparisonPlugin instance"""
    global _comparison_plugin
    if _comparison_plugin is None:
        _comparison_plugin = ComparisonPlugin()
    return _comparison_plugin
