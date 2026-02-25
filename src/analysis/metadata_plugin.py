"""
Phase 3A: Metadata Plugin

Auto-detects document-level metadata from chunks without any LLM call.
All detection is regex-based for zero API cost and deterministic results.

Storage strategy: writes one row to 'document_metadata' SQLite table
and also enriches the FIRST chunk's extra_metadata dict so the vector
store metadata index picks up the language and doc_type fields for
filtering in existing SearchFilter pipelines.

Fields detected:
  - title:        First H1 heading text, or filename stem if absent.
  - language:     'it' or 'en' via trigram frequency on first 1000 chars.
  - reading_level: 'technical', 'general', 'legal' from keyword density.
  - doc_type:     'policy', 'manual', 'reference', 'report', 'other'.
  - word_count:   Total words across all chunks.
  - chunk_count:  Number of input chunks.
  - keywords:     Top-10 frequency keywords (stopwords removed).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from src.logging_config import get_logger
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus

if TYPE_CHECKING:
    from src.document_ingestion import Chunk

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Detection tables
# ---------------------------------------------------------------------------

_IT_TRIGRAMS = {'che', 'del', 'della', 'per', 'con', 'una', 'non', 'sono'}
_EN_TRIGRAMS = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'are'}

_TECHNICAL_SIGNALS = {
    'api', 'function', 'class', 'module', 'parameter', 'return',
    'algoritmo', 'funzione', 'parametro', 'configurazione', 'deploy',
    'endpoint', 'schema', 'database', 'query', 'index',
}
_LEGAL_SIGNALS = {
    'pursuant', 'whereas', 'herein', 'liability', 'clause', 'provision',
    'contratto', 'accordo', 'normativa', 'regolamento', 'articolo',
}
_POLICY_SIGNALS = {
    'policy', 'procedure', 'compliance', 'must', 'shall', 'forbidden',
    'politica', 'procedura', 'obbligatorio', 'vietato', 'norma',
}
_REPORT_SIGNALS = {
    'summary', 'results', 'analysis', 'findings', 'conclusion',
    'sintesi', 'risultati', 'analisi', 'conclusioni', 'rapporto',
}

# Used by the frequency keyword extractor — mirrors entity_extractor.STOPWORDS
_STOPWORDS = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
    'has', 'in', 'is', 'it', 'of', 'on', 'or', 'that', 'the', 'to',
    'was', 'will', 'with', 'il', 'la', 'lo', 'le', 'un', 'una', 'e',
    'di', 'da', 'per', 'con', 'su', 'non', 'si', 'al', 'del', 'che',
}


@dataclass
class DocumentMetadata:
    """
    Document-level metadata extracted without LLM.

    All fields have fallback values so storage always receives
    a complete row even when detection is uncertain.
    """
    doc_id: str
    title: str                        # Best-effort title
    language: str                     # 'it' | 'en' | 'unknown'
    reading_level: str                # 'technical' | 'legal' | 'general'
    doc_type: str                     # 'policy' | 'manual' | 'reference' | 'report' | 'other'
    word_count: int
    chunk_count: int
    keywords: list[str] = field(default_factory=list)
    # Populated from PDF sidecar metadata when available via extra_metadata
    author: Optional[str] = None
    source_filename: str = ""


class MetadataPlugin(AnalysisPlugin):
    """
    Detects document-level metadata using regex and frequency analysis.

    No LLM calls. Designed to be fast (<10ms per document).
    The extra_metadata enrichment of the first chunk allows the
    existing vector store metadata index to participate in
    language/doc_type filtering without schema changes.
    """

    @property
    def plugin_name(self) -> str:
        return "metadata"

    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """Extract document metadata."""
        try:
            metadata = self._extract_metadata(doc_id, chunks)
            # Enrich first chunk's extra_metadata as side effect
            # so the vector store index picks up language/doc_type.
            if chunks:
                first_chunk = min(chunks, key=lambda c: c.order)
                if first_chunk.extra_metadata is None:
                    first_chunk.extra_metadata = {}
                first_chunk.extra_metadata.update({
                    "doc_language": metadata.language,
                    "doc_type":     metadata.doc_type,
                    "doc_title":    metadata.title,
                })
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.SUCCESS,
                payload=metadata,
            )
        except Exception as exc:
            logger.error(f"MetadataPlugin failed for '{doc_id}': {exc}")
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.FAILED,
                payload=None,
                error_message=str(exc),
            )

    def _extract_metadata(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> DocumentMetadata:
        """Internal extraction — never raises."""
        source_filename = chunks[0].source if chunks else doc_id
        full_text = " ".join(c.text for c in sorted(chunks, key=lambda c: c.order))
        sample = full_text[:2000]       # cheap sample for language/type detection

        title     = self._detect_title(doc_id, chunks)
        language  = self._detect_language(sample)
        reading_level = self._detect_reading_level(sample)
        doc_type  = self._detect_doc_type(source_filename, sample)
        word_count = len(full_text.split())
        keywords  = self._extract_keywords(full_text, top_n=10)
        author    = self._detect_author(chunks)

        return DocumentMetadata(
            doc_id=doc_id,
            title=title,
            language=language,
            reading_level=reading_level,
            doc_type=doc_type,
            word_count=word_count,
            chunk_count=len(chunks),
            keywords=keywords,
            author=author,
            source_filename=source_filename,
        )

    def _detect_title(self, doc_id: str, chunks: list["Chunk"]) -> str:
        """
        Tries in order:
        1. First H1 heading found in any chunk text.
        2. Filename stem formatted as title.
        """
        for chunk in sorted(chunks, key=lambda c: c.order):
            for line in chunk.text.splitlines():
                m = re.match(r'^#\s+(.+)$', line.strip())
                if m:
                    return m.group(1).strip()[:200]
        # Fallback: convert snake_case / hyphen filenames to title
        stem = Path(doc_id).stem if '.' in doc_id else doc_id
        return stem.replace('_', ' ').replace('-', ' ').title()

    def _detect_language(self, sample: str) -> str:
        """
        Compare Italian vs English trigram hits on a text sample.
        Returns 'it', 'en', or 'unknown'.
        """
        words = set(re.findall(r'\b\w{3,}\b', sample.lower()))
        it_score = len(words & _IT_TRIGRAMS)
        en_score = len(words & _EN_TRIGRAMS)
        if it_score > en_score:
            return 'it'
        if en_score > it_score:
            return 'en'
        return 'unknown'

    def _detect_reading_level(self, sample: str) -> str:
        """
        Classifies as 'technical', 'legal', or 'general' by keyword density.
        Highest density wins; ties resolve to 'general'.
        """
        words = set(re.findall(r'\b\w+\b', sample.lower()))
        scores = {
            'technical': len(words & _TECHNICAL_SIGNALS),
            'legal':     len(words & _LEGAL_SIGNALS),
        }
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] >= 2 else 'general'

    def _detect_doc_type(self, filename: str, sample: str) -> str:
        """
        Uses filename patterns first, falls back to content signals.
        """
        name_lower = filename.lower()
        if any(x in name_lower for x in ('policy', 'politica', 'procedura')):
            return 'policy'
        if any(x in name_lower for x in ('manual', 'manuale', 'guide', 'guida')):
            return 'manual'
        if any(x in name_lower for x in ('report', 'rapporto', 'summary')):
            return 'report'
        if any(x in name_lower for x in ('reference', 'spec', 'api', 'schema')):
            return 'reference'
        words = set(re.findall(r'\b\w+\b', sample.lower()))
        if len(words & _POLICY_SIGNALS) >= 3:
            return 'policy'
        if len(words & _REPORT_SIGNALS) >= 3:
            return 'report'
        return 'other'

    def _extract_keywords(self, text: str, top_n: int = 10) -> list[str]:
        """Frequency-based keywords excluding stopwords; mirrors entity_extractor."""
        tokens = re.findall(r'\b[a-zA-Z]\w{3,}\b', text.lower())
        filtered = [t for t in tokens if t not in _STOPWORDS]
        freq = Counter(filtered)
        return [word for word, _ in freq.most_common(top_n)]

    def _detect_author(self, chunks: list["Chunk"]) -> Optional[str]:
        """
        Reads author from PDF extra_metadata if the pdf_worker populated it,
        or searches first chunk text for 'Author: Name' pattern.
        """
        for chunk in sorted(chunks, key=lambda c: c.order)[:3]:
            # Check extra_metadata from pdf_worker output
            if chunk.extra_metadata and 'author' in chunk.extra_metadata:
                return str(chunk.extra_metadata['author'])
            # Regex scan first 3 chunks
            m = re.search(r'(?:Author|Autore)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                          chunk.text)
            if m:
                return m.group(1).strip()
        return None
