"""
Document Hierarchy Manager - FASE 18
Organizes documents into hierarchical structures for efficient long-context retrieval
"""

import re
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from src.logging_config import get_logger

logger = get_logger(__name__)

class HierarchyLevel(Enum):
    """Document hierarchy levels"""
    CHAPTER = "chapter"
    SECTION = "section"
    SUBSECTION = "subsection"
    PARAGRAPH = "paragraph"

@dataclass
class HierarchyNode:
    """Node in document hierarchy tree"""
    level: HierarchyLevel
    title: str
    content: str
    node_id: str
    parent_id: Optional[str] = None
    children: list['HierarchyNode'] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    relevance_score: float = 0.0
    token_count: int = 0
    source_doc: str = ""

class DocumentHierarchy:
    """Manages hierarchical document organization"""

    def __init__(self):
        """Initialize hierarchy manager"""
        self.roots: dict[str, HierarchyNode] = {}  # doc_id -> root node
        self.node_map: dict[str, HierarchyNode] = {}  # node_id -> node
        self.doc_structures: dict[str, Dict] = {}  # doc_id -> structure metadata

    def organize_by_structure(self, documents: list[Dict]) -> dict[str, HierarchyNode]:
        """
        Parse documents and organize by hierarchical structure

        Expects document dict with:
        - id: document identifier
        - text: document content
        - metadata: optional metadata dict

        Args:
            documents: List of document dictionaries

        Returns:
            Mapping of doc_id -> root HierarchyNode
        """
        roots = {}

        for doc in documents:
            doc_id = doc.get("id", str(len(roots)))
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})

            # Parse document structure
            root = self._parse_document_structure(text, doc_id, metadata)
            roots[doc_id] = root
            self.roots[doc_id] = root
            self._index_hierarchy(root)

        logger.info(f"Organized {len(documents)} documents into hierarchy")
        return roots

    def get_context_window(
        self,
        doc_id: str,
        target_node_id: Optional[str] = None,
        window_size: int = 10000,
        include_siblings: bool = True
    ) -> str:
        """
        Extract context window around target node

        Args:
            doc_id: Document identifier
            target_node_id: Specific node to center window on
            window_size: Target size in tokens (approximate)
            include_siblings: Include sibling nodes

        Returns:
            Assembled context string
        """
        if doc_id not in self.roots:
            return ""

        root = self.roots[doc_id]

        # If no target, include all top-level content
        if not target_node_id:
            return self._serialize_node(root)

        # Find target node
        target = self.node_map.get(target_node_id)
        if not target:
            return ""

        # Build context around target
        context_parts = []

        # Add parent context (highest level)
        if target.parent_id:
            parent = self.node_map.get(target.parent_id)
            if parent and parent.parent_id is None:
                context_parts.append(f"# {parent.title}\n")

        # Add target and its children
        context_parts.append(self._serialize_node(target))

        # Add siblings if requested
        if include_siblings and target.parent_id:
            parent = self.node_map.get(target.parent_id)
            if parent:
                for sibling in parent.children:
                    if sibling.node_id != target.node_id:
                        # Add sibling header only
                        context_parts.append(f"\n## {sibling.title}\n")

        return "\n".join(context_parts)

    def traverse_hierarchy(
        self,
        query: str,
        top_k: int = 5
    ) -> list[str]:
        """
        Smart traversal: find most relevant nodes for query

        Returns node contents ordered by relevance

        Args:
            query: Query string
            top_k: Return top-k nodes

        Returns:
            List of node contents ordered by relevance
        """
        query_terms = set(query.lower().split())
        scored_nodes = []

        # Score all nodes
        for node_id, node in self.node_map.items():
            score = self._score_node_relevance(node, query_terms)
            scored_nodes.append((score, node))

        # Sort by score
        scored_nodes.sort(key=lambda x: x[0], reverse=True)

        # Return top-k node contents
        result = []
        seen_parents = set()

        for score, node in scored_nodes[:top_k * 2]:
            # Avoid redundancy: if we've included parent, skip child
            if node.parent_id and node.parent_id in seen_parents:
                continue

            result.append(self._serialize_node(node))
            seen_parents.add(node.node_id)

            if len(result) >= top_k:
                break

        return result

    def _parse_document_structure(
        self,
        text: str,
        doc_id: str,
        metadata: Dict
    ) -> HierarchyNode:
        """Parse document into hierarchy"""
        # Extract main title from metadata or text
        title = metadata.get("title", "Document")
        root = HierarchyNode(
            level=HierarchyLevel.CHAPTER,
            title=title,
            content="",
            node_id=f"{doc_id}_root",
            metadata=metadata,
            source_doc=doc_id
        )

        # Find hierarchical markers
        lines = text.split('\n')
        current_sections = {HierarchyLevel.CHAPTER: root}

        for line in lines:
            # Try to identify level
            level = self._identify_level(line)

            if level:
                # Create new node
                title = re.sub(r'^#+\s+', '', line).strip()
                node_id = f"{doc_id}_{len(self.node_map)}"

                new_node = HierarchyNode(
                    level=level,
                    title=title,
                    content=line,
                    node_id=node_id,
                    source_doc=doc_id
                )

                # Attach to hierarchy
                if level == HierarchyLevel.SECTION:
                    parent = current_sections[HierarchyLevel.CHAPTER]
                elif level == HierarchyLevel.SUBSECTION:
                    parent = current_sections.get(
                        HierarchyLevel.SECTION,
                        current_sections[HierarchyLevel.CHAPTER]
                    )
                else:
                    parent = current_sections.get(
                        HierarchyLevel.SUBSECTION,
                        current_sections.get(
                            HierarchyLevel.SECTION,
                            current_sections[HierarchyLevel.CHAPTER]
                        )
                    )

                new_node.parent_id = parent.node_id
                parent.children.append(new_node)
                current_sections[level] = new_node

            else:
                # Regular content line
                if current_sections.get(HierarchyLevel.PARAGRAPH):
                    current_sections[HierarchyLevel.PARAGRAPH].content += "\n" + line
                else:
                    # Add to lowest level section
                    for level in [HierarchyLevel.SUBSECTION, HierarchyLevel.SECTION]:
                        if level in current_sections:
                            current_sections[level].content += "\n" + line
                            break
                    else:
                        root.content += "\n" + line

        return root

    def _identify_level(self, line: str) -> Optional[HierarchyLevel]:
        """Identify hierarchy level from line"""
        line = line.strip()

        if re.match(r'^#\s+', line):
            return HierarchyLevel.CHAPTER
        elif re.match(r'^##\s+', line):
            return HierarchyLevel.SECTION
        elif re.match(r'^###\s+', line):
            return HierarchyLevel.SUBSECTION
        elif re.match(r'^[A-Z][^:]*:\s*$', line):
            return HierarchyLevel.SECTION
        elif re.match(r'^\d+\.\s+', line):
            return HierarchyLevel.SUBSECTION

        return None

    def _score_node_relevance(
        self,
        node: HierarchyNode,
        query_terms: set[str]
    ) -> float:
        """Score node relevance to query"""
        score = 0.0
        text = (node.title + " " + node.content).lower()

        # Title matches weighted higher
        title_matches = sum(1 for term in query_terms if term in node.title.lower())
        score += title_matches * 0.5

        # Content matches
        content_matches = sum(1 for term in query_terms if term in text)
        score += content_matches * 0.1

        # Boost for structural hierarchy level
        if node.level == HierarchyLevel.CHAPTER:
            score *= 1.3
        elif node.level == HierarchyLevel.SECTION:
            score *= 1.2

        return score

    def _serialize_node(self, node: HierarchyNode, depth: int = 0) -> str:
        """Serialize node and children to string"""
        lines = []

        # Add node title with appropriate level
        if node.level == HierarchyLevel.CHAPTER:
            lines.append(f"# {node.title}")
        elif node.level == HierarchyLevel.SECTION:
            lines.append(f"## {node.title}")
        elif node.level == HierarchyLevel.SUBSECTION:
            lines.append(f"### {node.title}")
        else:
            lines.append(f"#### {node.title}")

        # Add content
        if node.content.strip():
            lines.append(node.content.strip())

        # Add children
        for child in node.children:
            if depth < 3:  # Limit depth to avoid excessive recursion
                lines.append(self._serialize_node(child, depth + 1))

        return "\n\n".join(lines)

    def _index_hierarchy(self, node: HierarchyNode) -> None:
        """Index all nodes in hierarchy"""
        self.node_map[node.node_id] = node
        for child in node.children:
            self._index_hierarchy(child)

    def get_statistics(self) -> Dict:
        """Get hierarchy statistics"""
        total_nodes = len(self.node_map)
        total_docs = len(self.roots)

        depth_stats = {}
        for node_id, node in self.node_map.items():
            level = node.level.value
            depth_stats[level] = depth_stats.get(level, 0) + 1

        return {
            "total_documents": total_docs,
            "total_nodes": total_nodes,
            "avg_nodes_per_doc": total_nodes // max(total_docs, 1),
            "depth_distribution": depth_stats
        }
