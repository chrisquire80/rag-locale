"""
Knowledge Graph Service (FASE 29)
Builds an entity-relationship graph from indexed documents and anomaly memory.
Used to visualize connections between documents, companies, and detected issues.
"""

import re
import json
import logging
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity Extraction
# ---------------------------------------------------------------------------

# Stopwords to ignore when extracting entities from filenames/text
_STOPWORDS = {
    "report", "analisi", "documento", "file", "data", "note", "notes",
    "briefing", "summary", "riepilogo", "integrazione", "piattaforma",
    "the", "and", "per", "con", "del", "dei", "delle", "alla", "alle",
    "pdf", "docx", "txt", "xlsx", "csv", "md", "tipo", "anno", "mese",
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
}

def _extract_entity_from_filename(filename: str) -> list[str]:
    """
    Extract meaningful entity tokens from a filename.
    E.g. '20250724 - Briefing Zucchetti Paghe.pdf' → ['Zucchetti', 'Paghe']
    """
    # Remove extension
    name = filename.rsplit(".", 1)[0]
    # Remove date prefix (YYYYMMDD or YYYY-MM-DD)
    name = re.sub(r"\b\d{6,8}\b", "", name)
    name = re.sub(r"\b\d{4}[-_]\d{2}[-_]\d{2}\b", "", name)
    # Split on separators
    tokens = re.split(r"[\s\-_\.\(\)]+", name)
    entities = []
    for tok in tokens:
        clean = tok.strip()
        if len(clean) > 3 and clean.lower() not in _STOPWORDS and not clean.isdigit():
            entities.append(clean)
    return entities

def build_entity_map(indexed_sources: set, anomalies: list[Dict] = None) -> dict[str, list[str]]:
    """
    Build a map of {document_filename: [entity1, entity2, ...]}
    Also attaches anomaly markers if the document was referenced in past anomalies.

    Args:
        indexed_sources: Set of filenames from VectorStore.list_indexed_files()
        anomalies: List of anomaly dicts from MemoryService.get_anomalies_history()

    Returns:
        Dict mapping each filename to its entity list
    """
    entity_map: dict[str, list[str]] = {}

    for source in indexed_sources:
        entities = _extract_entity_from_filename(source)
        if entities:
            entity_map[source] = entities

    # Attach anomaly tags to docs referenced in anomalies
    if anomalies:
        for anom in anomalies:
            # Anomaly references are stored as JSON list in referenced_docs
            try:
                refs = json.loads(anom.get("referenced_docs", "[]")) if isinstance(anom.get("referenced_docs"), str) else []
            except Exception:
                refs = []
            for ref in refs:
                # Match by partial filename
                for source in entity_map:
                    if ref in source or source in ref:
                        if "⚠️ Anomalia" not in entity_map[source]:
                            entity_map[source].append("⚠️ Anomalia")

    return entity_map

def get_graph_data(entity_map: dict[str, list[str]], risk_entities: list[str] = None, simulation_entities: list[str] = None) -> tuple[List, List]:
    """
    Convert entity_map to nodes and edges (plain Python objects).
    Enhanced: support for risk_entities (orange) and simulation_entities (purple).

    Returns:
        (nodes_list, edges_list) — each node has .id, .label, .size, .color, .title;
        each edge has .source, .target
    """
    from dataclasses import dataclass, field
    if risk_entities is None: risk_entities = []
    if simulation_entities is None: simulation_entities = []

    @dataclass
    class GraphNode:
        id: str
        label: str
        size: int = 20
        color: str = "#0d6efd"
        title: str = ""
        border_width: int = 1
        shadow_color: str = "rgba(0,0,0,0)"

    @dataclass
    class GraphEdge:
        source: str
        target: str

    nodes = []
    edges = []
    added_node_ids = set()

    for doc_name, entities in entity_map.items():
        if doc_name not in added_node_ids:
            is_anomalous = "⚠️ Anomalia" in entities
            has_risk_entity = any(e in risk_entities for e in entities)
            has_sim_entity = any(e in simulation_entities for e in entities)
            
            # Priority: Simulation (Purple) > Risk (Red/Orange) > Standard (Blue)
            if has_sim_entity:
                node_color = "#a855f7" # Purple for simulation
                size = 28
                border = 4
                shadow = "#d8b4fe"
            elif is_anomalous:
                node_color = "#dc3545" # Red
                size = 25
                border = 1
                shadow = "rgba(0,0,0,0)"
            elif has_risk_entity:
                node_color = "#0d6efd" # Blue doc, but will have orange entities
                size = 22
                border = 2
                shadow = "#f97316"
            else:
                node_color = "#0d6efd"
                size = 20
                border = 1
                shadow = "rgba(0,0,0,0)"

            short_label = doc_name[-40:] if len(doc_name) > 40 else doc_name
            nodes.append(GraphNode(
                id=doc_name, label=short_label, size=size, color=node_color,
                title=f"DOC: {doc_name}<br>Entità: {', '.join([e for e in entities if e != '⚠️ Anomalia'])}",
                border_width=border, shadow_color=shadow
            ))
            added_node_ids.add(doc_name)

        for entity in entities:
            if entity == "⚠️ Anomalia": continue

            if entity not in added_node_ids:
                is_risk = entity in risk_entities
                is_sim = entity in simulation_entities
                
                if is_sim:
                    node_color = "#a855f7" # Purple
                    size = 26
                    border = 5
                    shadow = "#d8b4fe"
                elif is_risk:
                    node_color = "#f97316" # Orange
                    size = 22
                    border = 4
                    shadow = "#fbbf24"
                else:
                    node_color = "#ffc107" # Yellow
                    size = 16
                    border = 1
                    shadow = "rgba(0,0,0,0)"

                nodes.append(GraphNode(
                    id=entity, label=entity, size=size, color=node_color,
                    title=f"ENTITÀ: {entity}{' (SIMULAZIONE)' if is_sim else (' (RISCHIO)' if is_risk else '')}",
                    border_width=border, shadow_color=shadow
                ))
                added_node_ids.add(entity)

            edges.append(GraphEdge(source=doc_name, target=entity))

    logger.info(f"[GRAPH] Built simulator-aware graph: {len(nodes)} nodes")
    return nodes, edges

def get_graph_stats(entity_map: dict[str, list[str]]) -> Dict:
    """Returns summary statistics about the knowledge graph."""
    all_entities = defaultdict(int)
    total_docs = len(entity_map)
    anomalous_docs = 0

    for doc, entities in entity_map.items():
        for e in entities:
            if e == "⚠️ Anomalia":
                anomalous_docs += 1
            else:
                all_entities[e] += 1

    # Top 5 most connected entities
    top_entities = sorted(all_entities.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_docs": total_docs,
        "total_entities": len(all_entities),
        "anomalous_docs": anomalous_docs,
        "top_entities": top_entities,
    }
