"""
UX-Enhanced RAG Engine - FASE 20
Extends QualityAwareRAGEngine with user experience enhancements
"""

from typing import Any, Optional
from dataclasses import dataclass, field

try:
    from src.rag_engine_quality import (
        QualityAwareRAGEngine,
        RAGResponseWithMetrics
    )
except ImportError:
    from src.rag_engine_longcontext import LongContextRAGEngine as QualityAwareRAGEngine
    from src.rag_engine_longcontext import LongContextRAGResponse as RAGResponseWithMetrics

from src.citation_engine import CitationEngine, Citation
from src.query_suggestions import QuerySuggestionEngine, QuerySuggestion
from src.chat_memory import ConversationMemory, ConversationTurn
from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class EnhancedRAGResponse(RAGResponseWithMetrics):
    """RAG response with UX enhancements"""
    citations: dict[str, Citation] = field(default_factory=dict)
    formatted_answer: str = ""  # Answer with embedded citations
    followup_suggestions: list[str] = field(default_factory=list)
    related_queries: list[str] = field(default_factory=list)
    suggestion_objects: list[QuerySuggestion] = field(default_factory=list)
    conversation_summary: str = ""
    ui_metadata: dict[str, Any] = field(default_factory=dict)

class UIFormattedResponse:
    """Response formatted for UI display"""

    def __init__(self):
        self.main_answer: str = ""
        self.citations: list[Dict] = []
        self.sources: list[Dict] = []
        self.suggestions: list[Dict] = []
        self.metadata: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "main_answer": self.main_answer,
            "citations": self.citations,
            "sources": self.sources,
            "suggestions": self.suggestions,
            "metadata": self.metadata
        }

class UXEnhancedRAGEngine(QualityAwareRAGEngine):
    """RAG Engine with complete UX enhancements"""

    def __init__(self):
        """Initialize UX-enhanced RAG engine"""
        super().__init__()

        # Initialize UX components
        self.citation_engine = CitationEngine()
        self.suggestion_engine = QuerySuggestionEngine()
        self.conversation_memory = ConversationMemory()

        logger.info("✓ UXEnhancedRAGEngine initialized")

    def query_with_ux_enhancements(
        self,
        query: str,
        user_id: Optional[str] = None,
        include_citations: bool = True,
        include_suggestions: bool = True,
        include_conversation_context: bool = True
    ) -> EnhancedRAGResponse:
        """
        Complete query with all UX enhancements

        Pipeline:
        1. Get quality-aware response
        2. Generate citations
        3. Generate follow-up suggestions
        4. Format for UI
        5. Add to conversation memory

        Args:
            query: User query
            user_id: Optional user identifier
            include_citations: Include citation generation
            include_suggestions: Include query suggestions
            include_conversation_context: Use conversation history

        Returns:
            EnhancedRAGResponse with all enhancements
        """
        # Start with quality-aware query
        base_response = self.query_with_quality_feedback(query)

        # Create enhanced response
        response = EnhancedRAGResponse(
            answer=base_response.answer,
            sources=base_response.sources,
            quality_metrics=base_response.quality_metrics,
            approved=base_response.approved,
            hitl_required=base_response.hitl_required,
            model=base_response.model
        )

        # 1. Generate citations
        if include_citations:
            logger.debug("Generating citations...")
            response.citations = self._generate_citations_enhanced(
                base_response.sources,
                response.answer
            )
            response.formatted_answer = self.citation_engine.format_answer_with_citations(
                response.answer,
                response.citations,
                format_type="inline"
            )
        else:
            response.formatted_answer = response.answer

        # 2. Generate suggestions
        if include_suggestions:
            logger.debug("Generating query suggestions...")
            response.followup_suggestions = self.suggestion_engine.generate_followup_questions(
                query,
                response.answer,
                max_suggestions=3
            )
            response.related_queries = self.suggestion_engine.suggest_related_queries(
                query,
                max_suggestions=2
            )
            response.suggestion_objects = self.suggestion_engine.get_suggestion_objects(
                query,
                response.answer,
                max_suggestions=5
            )

        # 3. Prepare UI formatting
        logger.debug("Preparing UI response...")
        response.ui_metadata = self._prepare_response_for_ui(response)

        # 4. Add to conversation memory
        logger.debug("Adding to conversation memory...")
        self.conversation_memory.add_turn(
            query=query,
            response=response.answer,
            quality_score=response.quality_metrics.overall_score,
            sources=[s.source if hasattr(s, 'source') else str(s) for s in response.sources],
            metadata={"user_id": user_id}
        )

        # 5. Add conversation context to metadata if requested
        if include_conversation_context:
            response.conversation_summary = self.conversation_memory.get_conversation_context(
                max_turns=5
            )

        return response

    def _generate_citations_enhanced(
        self,
        sources: list[Any],
        answer: str
    ) -> dict[str, Citation]:
        """
        Generate enhanced citations

        Args:
            sources: Source objects
            answer: Answer text

        Returns:
            Dictionary of citations
        """
        # Convert sources to expected format
        source_dicts = []
        for source in sources:
            if hasattr(source, 'to_dict'):
                source_dicts.append(source.to_dict())
            elif isinstance(source, dict):
                source_dicts.append(source)
            else:
                source_dicts.append({"document": str(source), "source": "Unknown"})

        # Generate citations
        citations = self.citation_engine.generate_citations(source_dicts, answer)

        # Link to answer
        self.citation_engine.link_citations_to_answer(answer, citations)

        return citations

    def _prepare_response_for_ui(
        self,
        response: EnhancedRAGResponse
    ) -> dict[str, Any]:
        """
        Prepare response for UI display

        Args:
            response: Enhanced response

        Returns:
            UI metadata dictionary
        """
        metadata = {
            "response_type": "enhanced_rag",
            "has_citations": len(response.citations) > 0,
            "has_suggestions": len(response.followup_suggestions) > 0,
            "quality_badge": self._get_quality_badge(response.quality_metrics.overall_score),
            "confidence_level": self._get_confidence_level(response.quality_metrics),
            "readability_score": self._calculate_readability(response.answer),
            "estimated_reading_time_seconds": len(response.answer) // 150,  # ~150 chars/sec
            "has_sources": len(response.sources) > 0,
            "source_count": len(response.sources)
        }

        return metadata

    def get_formatted_ui_response(
        self,
        response: EnhancedRAGResponse
    ) -> UIFormattedResponse:
        """
        Get UI-formatted response ready for display

        Args:
            response: Enhanced response

        Returns:
            UIFormattedResponse object
        """
        ui_response = UIFormattedResponse()

        ui_response.main_answer = response.formatted_answer

        # Format citations
        for citation_id, citation in response.citations.items():
            ui_response.citations.append({
                "id": citation_id,
                "preview": self.citation_engine.create_citation_preview(citation),
                "full_citation": citation.to_dict()
            })

        # Format sources
        for source in response.sources:
            ui_response.sources.append({
                "name": source.source if hasattr(source, 'source') else "Unknown",
                "excerpt": source.document[:100] if hasattr(source, 'document') else ""
            })

        # Format suggestions
        for suggestion in response.suggestion_objects:
            ui_response.suggestions.append({
                "text": suggestion.text,
                "type": suggestion.type,
                "relevance": suggestion.relevance_score,
                "context": suggestion.context
            })

        # Add metadata
        ui_response.metadata = {
            "quality_score": response.quality_metrics.overall_score,
            "quality_badge": response.ui_metadata.get("quality_badge"),
            "reading_time": response.ui_metadata.get("estimated_reading_time_seconds"),
            "has_issues": len(response.quality_issues) > 0,
            "issues": response.quality_issues if len(response.quality_issues) > 0 else None
        }

        return ui_response

    def get_conversation_context(self) -> str:
        """Get current conversation context"""
        return self.conversation_memory.get_conversation_context()

    def get_conversation_stats(self) -> dict[str, Any]:
        """Get conversation statistics"""
        return self.conversation_memory.get_conversation_statistics()

    def export_conversation(self) -> dict[str, Any]:
        """Export conversation history"""
        return self.conversation_memory.export_conversation()

    def clear_conversation(self) -> None:
        """Clear conversation history"""
        self.conversation_memory.clear_conversation()

    def _get_quality_badge(self, score: float) -> str:
        """Get quality badge for score"""
        if score >= 0.80:
            return "excellent"
        elif score >= 0.70:
            return "good"
        elif score >= 0.60:
            return "acceptable"
        else:
            return "needs_improvement"

    def _get_confidence_level(self, metrics) -> str:
        """Get confidence level from metrics"""
        faith = metrics.faithfulness
        if faith >= 0.75:
            return "high"
        elif faith >= 0.60:
            return "medium"
        else:
            return "low"

    def _calculate_readability(self, text: str) -> float:
        """
        Simple readability score (0-100)

        Based on:
        - Average sentence length
        - Paragraph structure
        - Word length

        Returns:
            Score 0-100
        """
        import re

        if not text:
            return 0

        sentences = re.split(r'[.!?]+', text)
        paragraphs = text.split('\n\n')

        avg_sentence_length = len(text) / max(len(sentences), 1)
        num_paragraphs = len([p for p in paragraphs if p.strip()])

        # Simple scoring
        score = 100
        if avg_sentence_length > 50:
            score -= 20
        if num_paragraphs < 2:
            score -= 10

        return max(0, min(100, score))

    def create_shareable_response(
        self,
        response: EnhancedRAGResponse,
        format: str = "markdown"
    ) -> str:
        """
        Create shareable version of response

        Args:
            response: Response to share
            format: Format (markdown, html, plain)

        Returns:
            Formatted response string
        """
        if format == "markdown":
            return self._to_markdown(response)
        elif format == "html":
            return self._to_html(response)
        else:
            return response.formatted_answer

    def _to_markdown(self, response: EnhancedRAGResponse) -> str:
        """Convert response to Markdown"""
        lines = [
            "# Answer",
            "",
            response.formatted_answer,
            "",
            "## Sources",
        ]

        for citation_id, citation in response.citations.items():
            lines.append(f"- {self.citation_engine.create_citation_preview(citation)}")

        if response.followup_suggestions:
            lines.append("")
            lines.append("## Follow-up Questions")
            for suggestion in response.followup_suggestions:
                lines.append(f"- {suggestion}")

        return "\n".join(lines)

    def _to_html(self, response: EnhancedRAGResponse) -> str:
        """Convert response to HTML"""
        html_parts = [
            "<div class='rag-response'>",
            f"<div class='answer'>{response.formatted_answer}</div>"
        ]

        if response.citations:
            html_parts.append("<div class='citations'>")
            for citation_id, citation in response.citations.items():
                html_parts.append(
                    f"<div class='citation'>{self.citation_engine.create_citation_preview(citation)}</div>"
                )
            html_parts.append("</div>")

        html_parts.append("</div>")

        return "\n".join(html_parts)
