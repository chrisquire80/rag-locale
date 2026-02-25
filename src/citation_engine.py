"""
Citation Engine - FASE 20
Generates proper citations and attribution for sources
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class Citation:
    """Represents a source citation"""
    id: str
    source_name: str
    source_url: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None
    excerpt: str = ""
    citation_format: str = "inline"  # inline, footnote, endnote, full
    access_date: Optional[str] = None
    relevance_score: float = 1.0

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "section": self.section,
            "excerpt": self.excerpt,
            "citation_format": self.citation_format,
            "access_date": self.access_date,
            "relevance_score": self.relevance_score
        }

@dataclass
class CitationLink:
    """Link between answer text and citations"""
    text_segment: str
    start_pos: int
    end_pos: int
    citation_ids: list[str] = field(default_factory=list)
    confidence: float = 1.0

class CitationEngine:
    """Manages citation generation and attribution"""

    def __init__(self):
        """Initialize citation engine"""
        self.citations: dict[str, Citation] = {}
        self.citation_links: list[CitationLink] = []
        self.citation_counter = 0

    def generate_citations(
        self,
        sources: list[Dict],
        answer: str = ""
    ) -> dict[str, Citation]:
        """
        Generate citations from sources

        Args:
            sources: List of source dictionaries with:
                - document: Document text
                - source: Source name/url
                - metadata: Optional metadata dict
            answer: Generated answer (for linking)

        Returns:
            Dictionary of citation_id -> Citation
        """
        citations = {}

        for source_idx, source in enumerate(sources):
            citation_id = f"cite_{source_idx + 1}"
            self.citation_counter += 1

            # Extract source information
            source_name = source.get("source", f"Source {source_idx + 1}")
            doc_text = source.get("document", "")
            metadata = source.get("metadata", {})

            # Create citation
            citation = Citation(
                id=citation_id,
                source_name=source_name,
                source_url=metadata.get("url"),
                document_id=metadata.get("doc_id"),
                page_number=metadata.get("page"),
                section=metadata.get("section"),
                excerpt=self._extract_excerpt(doc_text),
                access_date=datetime.now().isoformat()
            )

            citations[citation_id] = citation
            self.citations[citation_id] = citation

            logger.debug(f"Generated citation: {citation_id} -> {source_name}")

        return citations

    def create_citation_preview(self, citation: Citation) -> str:
        """
        Create human-readable citation preview

        Formats: [1] Source Name (Section). "Excerpt..."

        Args:
            citation: Citation object

        Returns:
            Formatted citation string
        """
        parts = []

        # Citation number
        parts.append(f"[{citation.id.split('_')[1]}]")

        # Source name
        parts.append(citation.source_name)

        # Section if available
        if citation.section:
            parts.append(f"({citation.section})")

        # Page if available
        if citation.page_number:
            parts.append(f"p. {citation.page_number}")

        # Excerpt
        if citation.excerpt:
            excerpt_clean = citation.excerpt[:80]
            if len(citation.excerpt) > 80:
                excerpt_clean += "..."
            parts.append(f'"{excerpt_clean}"')

        return " ".join(parts)

    def extract_citation_context(
        self,
        source: Dict,
        context_window: int = 50
    ) -> str:
        """
        Extract context around a citation point

        Args:
            source: Source dictionary
            context_window: Characters before/after to include

        Returns:
            Context string
        """
        doc_text = source.get("document", "")

        if not doc_text:
            return ""

        # Extract window
        if len(doc_text) > context_window * 2:
            # Get middle portion
            start = max(0, len(doc_text) // 2 - context_window)
            end = min(len(doc_text), len(doc_text) // 2 + context_window)
            context = "..." + doc_text[start:end] + "..."
        else:
            context = doc_text

        return context

    def link_citations_to_answer(
        self,
        answer: str,
        citations: dict[str, Citation]
    ) -> list[CitationLink]:
        """
        Create links between answer text and citations

        Identifies claim segments and associates them with citations

        Args:
            answer: Generated answer text
            citations: Citation objects

        Returns:
            List of CitationLink objects
        """
        links = []

        # Split answer into sentences/segments
        sentences = re.split(r'(?<=[.!?])\s+', answer)

        citation_idx = 0
        current_pos = 0

        for segment in sentences:
            if not segment.strip():
                continue

            # Find matching citations for this segment
            matching_citations = self._find_matching_citations(
                segment,
                citations
            )

            if matching_citations:
                link = CitationLink(
                    text_segment=segment,
                    start_pos=current_pos,
                    end_pos=current_pos + len(segment),
                    citation_ids=matching_citations
                )
                links.append(link)

            current_pos += len(segment) + 1  # +1 for space

        self.citation_links = links
        logger.debug(f"Linked {len(links)} text segments to citations")

        return links

    def format_answer_with_citations(
        self,
        answer: str,
        citations: dict[str, Citation],
        format_type: str = "inline"
    ) -> str:
        """
        Format answer with embedded citations

        Formats:
        - inline: Answer text [1] with citations at end
        - footnote: Answer text^1 with footnotes below
        - markdown: Answer text [source](url)

        Args:
            answer: Answer text
            citations: Citation objects
            format_type: Citation format type

        Returns:
            Formatted answer with citations
        """
        if format_type == "inline":
            return self._format_inline_citations(answer, citations)
        elif format_type == "footnote":
            return self._format_footnote_citations(answer, citations)
        elif format_type == "markdown":
            return self._format_markdown_citations(answer, citations)
        else:
            return answer

    def _extract_excerpt(self, text: str, length: int = 100) -> str:
        """Extract excerpt from text"""
        if not text:
            return ""

        # Clean text
        text_clean = re.sub(r'\s+', ' ', text).strip()

        # Get first sentence or length limit
        first_sentence = re.split(r'[.!?]', text_clean)[0]

        if len(first_sentence) <= length:
            excerpt = first_sentence
        else:
            excerpt = text_clean[:length]

        return excerpt

    def _find_matching_citations(
        self,
        segment: str,
        citations: dict[str, Citation]
    ) -> list[str]:
        """Find citations relevant to a text segment"""
        matching = []

        segment_lower = segment.lower()

        for citation_id, citation in citations.items():
            # Check if excerpt matches segment
            if citation.excerpt.lower() in segment_lower:
                matching.append(citation_id)
            # Check key terms from source
            elif self._segment_matches_source(segment_lower, citation.excerpt):
                matching.append(citation_id)

        return matching[:3]  # Max 3 citations per segment

    def _segment_matches_source(
        self,
        segment: str,
        source_excerpt: str,
        threshold: float = 0.5
    ) -> bool:
        """Check if segment matches source excerpt"""
        # Extract key terms (3+ chars)
        segment_terms = set(
            term for term in segment.split()
            if len(term) > 3
        )
        source_terms = set(
            term for term in source_excerpt.lower().split()
            if len(term) > 3
        )

        if not segment_terms or not source_terms:
            return False

        # Calculate overlap
        overlap = len(segment_terms & source_terms)
        overlap_ratio = overlap / len(segment_terms)

        return overlap_ratio >= threshold

    def _format_inline_citations(
        self,
        answer: str,
        citations: dict[str, Citation]
    ) -> str:
        """Format with inline citations [1][2]"""
        formatted = answer

        # Add citation numbers at strategic points
        # This is simplified; real implementation would be more sophisticated
        for idx, (citation_id, citation) in enumerate(citations.items()):
            # Find first mention of citation topic in answer
            topic_words = citation.source_name.split()[:2]
            for topic in topic_words:
                if topic.lower() in formatted.lower():
                    # Insert citation marker (simplified)
                    formatted = formatted.replace(
                        topic,
                        f"{topic} [{idx + 1}]",
                        1
                    )
                    break

        # Add bibliography at end
        formatted += "\n\nReferences:\n"
        for idx, (citation_id, citation) in enumerate(citations.items()):
            formatted += f"{idx + 1}. {self.create_citation_preview(citation)}\n"

        return formatted

    def _format_footnote_citations(
        self,
        answer: str,
        citations: dict[str, Citation]
    ) -> str:
        """Format with footnote citations^1"""
        # Simplified footnote format
        formatted = answer

        # Add superscript numbers
        for idx in range(1, len(citations) + 1):
            # Would typically use specific markers
            formatted += f"^{idx}"

        # Add footnotes at bottom
        formatted += "\n\n---\nFootnotes:\n"
        for idx, (citation_id, citation) in enumerate(citations.items()):
            formatted += f"{idx + 1}. {self.create_citation_preview(citation)}\n"

        return formatted

    def _format_markdown_citations(
        self,
        answer: str,
        citations: dict[str, Citation]
    ) -> str:
        """Format with Markdown links [text](url)"""
        formatted = answer

        for citation_id, citation in citations.items():
            if citation.source_url:
                # Create markdown link
                link = f"[{citation.source_name}]({citation.source_url})"
                # Replace first occurrence
                formatted = formatted.replace(
                    citation.source_name,
                    link,
                    1
                )

        return formatted

    def get_citation_statistics(self) -> Dict:
        """Get citation statistics"""
        return {
            "total_citations": len(self.citations),
            "linked_segments": len(self.citation_links),
            "citations_with_urls": sum(
                1 for c in self.citations.values() if c.source_url
            ),
            "citations_with_pages": sum(
                1 for c in self.citations.values() if c.page_number
            ),
            "avg_excerpt_length": sum(
                len(c.excerpt) for c in self.citations.values()
            ) / max(len(self.citations), 1)
        }

    def export_citations(self, format: str = "json") -> str:
        """
        Export citations in various formats

        Args:
            format: Export format (json, bibtex, apa, mla)

        Returns:
            Formatted citation export
        """
        if format == "json":
            return self._export_json()
        elif format == "bibtex":
            return self._export_bibtex()
        elif format == "apa":
            return self._export_apa()
        elif format == "mla":
            return self._export_mla()
        else:
            return str(self.citations)

    def _export_json(self) -> str:
        """Export as JSON"""
        import json
        citations_dict = {
            cid: citation.to_dict()
            for cid, citation in self.citations.items()
        }
        return json.dumps(citations_dict, indent=2)

    def _export_bibtex(self) -> str:
        """Export as BibTeX"""
        bibtex = []
        for idx, (cid, citation) in enumerate(self.citations.items()):
            entry = f"""@misc{{cite_{idx + 1},
  title = {{{citation.source_name}}},
  url = {{{citation.source_url or 'N/A'}}},
  accessed = {{{citation.access_date}}}
}}"""
            bibtex.append(entry)
        return "\n\n".join(bibtex)

    def _export_apa(self) -> str:
        """Export as APA format"""
        apa = []
        for idx, (cid, citation) in enumerate(self.citations.items()):
            entry = f"{idx + 1}. {citation.source_name}."
            if citation.source_url:
                entry += f" Retrieved from {citation.source_url}"
            if citation.access_date:
                entry += f" Accessed {citation.access_date}"
            apa.append(entry)
        return "\n".join(apa)

    def _export_mla(self) -> str:
        """Export as MLA format"""
        mla = []
        for idx, (cid, citation) in enumerate(self.citations.items()):
            entry = f"{idx + 1}. {citation.source_name}"
            if citation.source_url:
                entry += f". Web. {citation.source_url}"
            mla.append(entry)
        return "\n".join(mla)
