"""
src/analysis — Phase 3A Document Analysis Engine

Public API:
    from src.analysis import get_document_analyzer, DocumentAnalysis
"""

from src.analysis.document_analyzer import (
    DocumentAnalyzer,
    DocumentAnalysis,
    get_document_analyzer,
)
from src.analysis.base import AnalysisPlugin, AnalysisResult, PluginStatus
from src.analysis.structure_plugin import StructurePlugin, DocumentStructure, Section, HeadingLevel
from src.analysis.metadata_plugin import MetadataPlugin, DocumentMetadata
from src.analysis.knowledge_plugin import KnowledgePlugin, KnowledgeGraph, Entity, KnowledgeEdge
from src.analysis.metadata_store import MetadataStore

__all__ = [
    "get_document_analyzer",
    "DocumentAnalyzer",
    "DocumentAnalysis",
    "AnalysisPlugin",
    "AnalysisResult",
    "PluginStatus",
    "StructurePlugin",
    "DocumentStructure",
    "Section",
    "HeadingLevel",
    "MetadataPlugin",
    "DocumentMetadata",
    "KnowledgePlugin",
    "KnowledgeGraph",
    "Entity",
    "KnowledgeEdge",
    "MetadataStore",
]
