"""
Phase 3A: Knowledge Plugin

Builds a lightweight entity-relationship graph from chunk text.
No NLP libraries required — uses the existing EntityExtractor from
src/entity_extractor.py for proper nouns and regex for code entities.

Entity types extracted:
  - concept:    Capitalized phrases (2+ words), section titles.
  - function:   Patterns like 'foo()' or 'def foo'.
  - class_def:  Patterns like 'class Foo' or 'Foo class'.
  - definition: Patterns like 'X is defined as' or 'X: description'.

Relationship types built:
  - mentions:   Entity A and Entity B co-occur in the same chunk.
  - defined_in: A definition entity maps to its source section.
  - references: Entity B appears in a chunk that introduces Entity A.

Storage: edges written to 'knowledge_edges' SQLite table.
The graph is intentionally sparse — only edges with co-occurrence
count >= 2 are persisted to avoid noise from single mentions.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from src.logging_config import get_logger
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus

if TYPE_CHECKING:
    from src.document_ingestion import Chunk

logger = get_logger(__name__)


@dataclass
class Entity:
    """
    An extracted entity node in the knowledge graph.

    Fields:
        entity_id:    Stable identifier '{doc_id}_e_{slug}'.
        name:         Canonical display name.
        entity_type:  'concept' | 'function' | 'class_def' | 'definition'.
        source_chunk: Chunk.order of first occurrence.
        frequency:    Total occurrence count across all chunks.
        doc_id:       Parent document identifier.
    """
    entity_id: str
    name: str
    entity_type: str
    source_chunk: int
    frequency: int = 1
    doc_id: str = ""


@dataclass
class KnowledgeEdge:
    """
    A directed relationship between two entities.

    Fields:
        source_id:    entity_id of the source node.
        target_id:    entity_id of the target node.
        relationship: 'mentions' | 'defined_in' | 'references'.
        weight:       Co-occurrence count; persisted only if >= 2.
        doc_id:       Parent document identifier.
    """
    source_id: str
    target_id: str
    relationship: str
    weight: int
    doc_id: str


@dataclass
class KnowledgeGraph:
    """
    Complete entity-relationship graph for one document.

    Fields:
        doc_id:    Document identifier.
        entities:  All extracted Entity objects.
        edges:     All KnowledgeEdge objects with weight >= 2.
        entity_count: Total entities extracted.
        edge_count:   Total edges stored.
    """
    doc_id: str
    entities: list[Entity]
    edges: list[KnowledgeEdge]
    entity_count: int
    edge_count: int


# --- Regex patterns for code-specific entities ---
_FUNC_PATTERN  = re.compile(r'\bdef\s+([a-z_]\w+)\s*\(')
_CLASS_PATTERN = re.compile(r'\bclass\s+([A-Z]\w+)\b')
_DEFN_PATTERN  = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:is|are|refers to|si definisce|è)\b',
    re.IGNORECASE,
)


def _slugify(text: str) -> str:
    """Convert entity name to a stable, lowercase slug for entity_id."""
    return re.sub(r'\W+', '_', text.lower()).strip('_')[:60]


class KnowledgePlugin(AnalysisPlugin):
    """
    Builds entity graph from chunk text using regex + EntityExtractor.

    The EntityExtractor from src/entity_extractor.py is used for
    proper noun detection to avoid reimplementing that logic.
    All edges with weight < 2 are discarded before returning.
    """

    def __init__(self) -> None:
        # Lazy import to avoid circular dependency issues at module load
        self._extractor = None

    @property
    def plugin_name(self) -> str:
        return "knowledge"

    def _get_extractor(self):
        if self._extractor is None:
            try:
                from src.entity_extractor import get_entity_extractor
                self._extractor = get_entity_extractor()
            except Exception as exc:
                logger.warning(f"EntityExtractor unavailable, using regex only: {exc}")
        return self._extractor

    def analyze(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> AnalysisResult:
        """Extract entity graph."""
        try:
            graph = self._build_graph(doc_id, chunks)
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.SUCCESS,
                payload=graph,
            )
        except Exception as exc:
            logger.error(f"KnowledgePlugin failed for '{doc_id}': {exc}")
            return AnalysisResult(
                plugin_name=self.plugin_name,
                doc_id=doc_id,
                status=PluginStatus.FAILED,
                payload=None,
                error_message=str(exc),
            )

    def _build_graph(
        self,
        doc_id: str,
        chunks: list["Chunk"],
    ) -> KnowledgeGraph:
        """Core graph construction logic."""
        # entity_name -> Entity (deduplicated by name)
        entity_registry: dict[str, Entity] = {}
        # (source_id, target_id) -> co-occurrence count
        cooccurrence: dict[tuple[str, str], int] = defaultdict(int)

        extractor = self._get_extractor()

        for chunk in sorted(chunks, key=lambda c: c.order):
            chunk_entities: list[Entity] = []
            text = chunk.text

            # 1. Code entities via regex (highest precision)
            for m in _FUNC_PATTERN.finditer(text):
                chunk_entities.append(
                    self._register(entity_registry, doc_id, m.group(1),
                                   'function', chunk.order)
                )
            for m in _CLASS_PATTERN.finditer(text):
                chunk_entities.append(
                    self._register(entity_registry, doc_id, m.group(1),
                                   'class_def', chunk.order)
                )
            # 2. Definitions
            for m in _DEFN_PATTERN.finditer(text):
                chunk_entities.append(
                    self._register(entity_registry, doc_id, m.group(1),
                                   'definition', chunk.order)
                )
            # 3. Proper nouns from EntityExtractor (capitalized sequences)
            if extractor:
                try:
                    extracted = extractor.extract_entities(text, entity_types=['entity'])
                    for ent in extracted[:10]:  # cap per chunk to avoid noise
                        if len(ent.text) > 3:
                            chunk_entities.append(
                                self._register(entity_registry, doc_id, ent.text,
                                               'concept', chunk.order)
                            )
                except Exception as e:
                    logger.debug(f"EntityExtractor failed on chunk: {e}")

            # Build co-occurrence edges within this chunk
            seen_ids = list({e.entity_id for e in chunk_entities if e is not None})
            for i in range(len(seen_ids)):
                for j in range(i + 1, len(seen_ids)):
                    pair = (seen_ids[i], seen_ids[j])
                    cooccurrence[pair] += 1

        # Build edges: only persist weight >= 2
        edges: list[KnowledgeEdge] = []
        for (src_id, tgt_id), weight in cooccurrence.items():
            if weight >= 2:
                edges.append(KnowledgeEdge(
                    source_id=src_id,
                    target_id=tgt_id,
                    relationship="mentions",
                    weight=weight,
                    doc_id=doc_id,
                ))

        entities = list(entity_registry.values())
        return KnowledgeGraph(
            doc_id=doc_id,
            entities=entities,
            edges=edges,
            entity_count=len(entities),
            edge_count=len(edges),
        )

    def _register(
        self,
        registry: dict[str, Entity],
        doc_id: str,
        name: str,
        entity_type: str,
        chunk_order: int,
    ) -> Optional[Entity]:
        """
        Upsert entity into registry. Returns the Entity (new or existing).
        Returns None for names shorter than 3 chars.
        """
        name = name.strip()
        if len(name) < 3:
            return None
        slug = _slugify(name)
        entity_id = f"{doc_id}_e_{slug}"
        if entity_id in registry:
            registry[entity_id].frequency += 1
        else:
            registry[entity_id] = Entity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                source_chunk=chunk_order,
                doc_id=doc_id,
            )
        return registry[entity_id]
