"""
Phase 3A: Structure Plugin

Extracts document heading hierarchy from raw Chunk text using regex patterns
identical to those already used in src/document_ingestion.py._process_markdown()
and src/document_hierarchy.py._identify_level().

No new dependencies. Pure regex + dataclass logic.

Storage: section rows written to SQLite via MetadataStore.upsert_sections().
Each Chunk's extra_metadata is NOT modified here; the section tree is stored
in the relational layer only, queryable by section_id or doc_id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

from src.logging_config import get_logger
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus

if TYPE_CHECKING:
    from src.document_ingestion import Chunk

logger = get_logger(__name__)


class HeadingLevel(Enum):
    """Maps to HierarchyLevel in document_hierarchy.py for consistency."""
    H1 = 1   # # Heading  or  CHAPTER X:
    H2 = 2   # ## Heading or  numbered 1.
    H3 = 3   # ### Heading or numbered 1.1
    H4 = 4   # #### Heading


@dataclass
class Section:
    """
    A single node in the extracted section hierarchy.

    Fields:
        section_id:    Unique string in format '{doc_id}_s{index}'.
        title:         Heading text stripped of markup.
        level:         HeadingLevel enum value.
        parent_id:     section_id of parent node, or None for top-level.
        chunk_indices: list[int] of Chunk.order values belonging to section.
        children:      Nested Section objects (populated post-parse).
        doc_id:        Document identifier.
    """
    section_id: str
    title: str
    level: HeadingLevel
    parent_id: Optional[str]
    chunk_indices: list[int] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)
    doc_id: str = ""


@dataclass
class DocumentStructure:
    """
    Complete section hierarchy for one document.

    Fields:
        doc_id:       Stable document identifier.
        sections:     Flat list of all Section objects (tree links via parent_id).
        root_sections: Top-level sections (parent_id is None).
        total_headings: Count of all detected headings.
        max_depth:    Deepest nesting level found (1-4).
    """
    doc_id: str
    sections: list[Section]
    root_sections: list[Section]
    total_headings: int
    max_depth: int


# Regex patterns matching document_ingestion._process_markdown and
# document_hierarchy._identify_level — kept identical for consistency.
_HEADING_PATTERNS: list[tuple[re.Pattern, HeadingLevel]] = [
    (re.compile(r'^(#{1})\s+(.+)$'),   HeadingLevel.H1),
    (re.compile(r'^(#{2})\s+(.+)$'),   HeadingLevel.H2),
    (re.compile(r'^(#{3})\s+(.+)$'),   HeadingLevel.H3),
    (re.compile(r'^(#{4,})\s+(.+)$'),  HeadingLevel.H4),
    # Numbered: "1." or "1.1" patterns
    (re.compile(r'^\d+\.\s+(.+)$'),    HeadingLevel.H2),
    (re.compile(r'^\d+\.\d+\s+(.+)$'), HeadingLevel.H3),
    # ALL CAPS title lines used in PDF-sourced documents
    (re.compile(r'^([A-Z][A-Z\s]{4,}):?\s*$'), HeadingLevel.H1),
]


def _detect_heading(line: str) -> Optional[tuple[HeadingLevel, str]]:
    """
    Return (level, title_text) if line matches a heading pattern, else None.
    Tries patterns in priority order; first match wins.
    """
    line = line.strip()
    if not line:
        return None
    for pattern, level in _HEADING_PATTERNS:
        m = pattern.match(line)
        if m:
            # Last group is always the title text
            title = m.group(m.lastindex).strip() if m.lastindex else line
            return level, title
    return None


class StructurePlugin(AnalysisPlugin):
    """
    Extracts document section hierarchy from chunk text.

    Algorithm:
    1. Iterate chunks in Chunk.order sequence.
    2. Scan each chunk's text line by line for heading patterns.
    3. Build Section nodes, linking parent_id via a level-indexed stack.
    4. Assign chunk.order indices to the current active section.
    5. Return DocumentStructure with flat sections list.

    Edge cases:
    - Documents with zero headings return a single implicit root section.
    - Heading text exceeding 200 chars is truncated (PDF artifacts).
    - Duplicate heading titles are disambiguated via section_id counter.
    """

    @property
    def plugin_name(self) -> str:
        return "structure"

    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """Extract heading hierarchy from chunk text."""
        try:
            structure = self._extract_structure(doc_id, chunks)
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.SUCCESS,
                payload=structure,
            )
        except Exception as exc:
            logger.error(f"StructurePlugin failed for '{doc_id}': {exc}")
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.FAILED,
                payload=None,
                error_message=str(exc),
            )

    def _extract_structure(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> DocumentStructure:
        """
        Core parsing logic. Returns DocumentStructure.

        Uses a stack indexed by HeadingLevel.value (1-4) to track
        the current ancestor at each depth level.
        """
        sections: list[Section] = []
        # Stack: index = level.value (1-4), value = current Section at that level
        level_stack: dict[int, Section] = {}
        section_counter = 0

        sorted_chunks = sorted(chunks, key=lambda c: c.order)

        # The active section for assigning chunk indices
        current_section: Optional[Section] = None

        for chunk in sorted_chunks:
            lines = chunk.text.splitlines()
            for line in lines:
                detection = _detect_heading(line)
                if detection:
                    level, raw_title = detection
                    title = raw_title[:200]  # truncate PDF artifacts
                    section_id = f"{doc_id}_s{section_counter}"
                    section_counter += 1

                    # Find parent: nearest section at a shallower level
                    parent_id: Optional[str] = None
                    for depth in range(level.value - 1, 0, -1):
                        if depth in level_stack:
                            parent_id = level_stack[depth].section_id
                            break

                    sec = Section(
                        section_id=section_id,
                        title=title,
                        level=level,
                        parent_id=parent_id,
                        doc_id=doc_id,
                    )
                    sections.append(sec)
                    level_stack[level.value] = sec
                    # Clear any deeper levels (new H2 invalidates H3 stack)
                    for deeper in range(level.value + 1, 5):
                        level_stack.pop(deeper, None)
                    current_section = sec

            # Assign this chunk to the active section
            if current_section is not None:
                current_section.chunk_indices.append(chunk.order)

        # Build children links from parent_id (single pass)
        sec_by_id: dict[str, Section] = {s.section_id: s for s in sections}
        root_sections: list[Section] = []
        for sec in sections:
            if sec.parent_id is None:
                root_sections.append(sec)
            else:
                parent = sec_by_id.get(sec.parent_id)
                if parent:
                    parent.children.append(sec)

        # If no headings found, create implicit root
        if not sections:
            implicit = Section(
                section_id=f"{doc_id}_s0",
                title=doc_id,
                level=HeadingLevel.H1,
                parent_id=None,
                chunk_indices=[c.order for c in sorted_chunks],
                doc_id=doc_id,
            )
            sections = [implicit]
            root_sections = [implicit]

        max_depth = max((s.level.value for s in sections), default=1)

        return DocumentStructure(
            doc_id=doc_id,
            sections=sections,
            root_sections=root_sections,
            total_headings=len(sections),
            max_depth=max_depth,
        )
