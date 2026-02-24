"""
UX Enhancements - FASE 20
Advanced user experience features: citations, suggestions, memory, export
"""

import logging
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class CitationType(Enum):
    """Types of citations"""
    DIRECT = "direct"           # Direct quote from document
    PARAPHRASE = "paraphrase"   # Paraphrased from document
    SYNTHESIS = "synthesis"     # Synthesized from multiple documents

@dataclass
class Citation:
    """Citation reference in response"""
    citation_type: CitationType
    text: str                    # The cited text
    document_id: str            # Source document
    page: Optional[int] = None
    source_title: Optional[str] = None
    relevance_score: float = 0.9
    position_in_answer: int = 0  # Character position in answer

@dataclass
class QuerySuggestion:
    """Suggested follow-up query"""
    text: str
    category: str               # "clarification", "expansion", "related", "follow-up"
    confidence: float           # 0-1 confidence in suggestion
    reason: str                 # Why this suggestion?

@dataclass
class ConversationTurn:
    """Single turn in conversation history"""
    turn_id: str
    query: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    quality_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)

@dataclass
class ConversationMemory:
    """User conversation history and context"""
    conversation_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    context_summary: str = ""    # Summary of conversation so far
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def add_turn(self, turn: ConversationTurn):
        """Add a turn to conversation"""
        self.turns.append(turn)
        self.last_updated = datetime.now()

    def get_context(self, max_turns: int = 5) -> str:
        """Get recent conversation context"""
        recent = self.turns[-max_turns:] if len(self.turns) > max_turns else self.turns
        context_parts = []
        for turn in recent:
            context_parts.append(f"Q: {turn.query}\nA: {turn.answer}")
        return "\n\n".join(context_parts)

    def get_summary(self) -> Dict:
        """Get conversation summary"""
        return {
            'conversation_id': self.conversation_id,
            'turn_count': len(self.turns),
            'duration_seconds': (self.last_updated - self.created_at).total_seconds(),
            'average_quality': sum(t.quality_score for t in self.turns) / len(self.turns) if self.turns else 0,
            'topics': self._extract_topics(),
        }

    def _extract_topics(self) -> list[str]:
        """Extract main topics from conversation"""
        # Simple implementation: extract common words from queries
        all_words = []
        for turn in self.turns:
            words = turn.query.lower().split()
            all_words.extend([w for w in words if len(w) > 4])

        # Return top 5 most common words
        from collections import Counter
        word_counts = Counter(all_words)
        return [word for word, _ in word_counts.most_common(5)]

class CitationManager:
    """Manage citations in responses"""

    def __init__(self):
        """Initialize citation manager"""
        self.citations: list[Citation] = []
        logger.info("✓ CitationManager initialized")

    def extract_citations(self,
                         answer: str,
                         retrieved_documents: list[Dict],
                         relevance_scores: Optional[dict[str, float]] = None) -> list[Citation]:
        """
        Extract citations from answer and documents

        Args:
            answer: Generated answer
            retrieved_documents: Source documents
            relevance_scores: Relevance scores for documents

        Returns:
            List of citations
        """
        citations = []
        relevance_scores = relevance_scores or {}

        # Simple heuristic: find document sentences in answer
        for doc in retrieved_documents:
            doc_id = doc.get('id', 'unknown')
            doc_text = doc.get('text', '')
            source_title = doc.get('metadata', {}).get('source', 'Source')

            # Split into sentences
            sentences = doc_text.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and len(sentence) > 10:
                    # Check if sentence (or parts of it) appear in answer
                    if sentence[:30] in answer or sentence[-30:] in answer:
                        citation = Citation(
                            citation_type=CitationType.DIRECT,
                            text=sentence[:100],  # First 100 chars
                            document_id=doc_id,
                            source_title=source_title,
                            relevance_score=relevance_scores.get(doc_id, 0.8),
                            position_in_answer=answer.find(sentence[:30]) if sentence[:30] in answer else 0
                        )
                        citations.append(citation)

        self.citations = citations
        logger.debug(f"Extracted {len(citations)} citations")
        return citations

    def format_citations(self, answer: str, citations: list[Citation]) -> tuple[str, list[Citation]]:
        """
        Format answer with citation markers

        Args:
            answer: Original answer
            citations: List of citations

        Returns:
            Tuple of (formatted_answer, citations)
        """
        # Add [1], [2], etc. markers for citations
        formatted = answer
        for i, citation in enumerate(citations, 1):
            if citation.text[:20] in answer:
                # Simple replacement with marker
                marker = f"[{i}]"
                formatted = formatted.replace(citation.text[:20], f"{citation.text[:20]} {marker}", 1)

        return formatted, citations

    def get_citation_preview(self, citation: Citation) -> Dict:
        """Get preview of citation for UI display"""
        return {
            'citation_id': citation.document_id,
            'text_preview': citation.text[:100] + "..." if len(citation.text) > 100 else citation.text,
            'source': citation.source_title,
            'type': citation.citation_type.value,
            'confidence': citation.relevance_score,
        }

class QuerySuggestor:
    """Generate follow-up query suggestions"""

    def __init__(self):
        """Initialize query suggestor"""
        logger.info("✓ QuerySuggestor initialized")

    def generate_suggestions(self,
                            query: str,
                            answer: str,
                            retrieved_documents: list[Dict]) -> list[QuerySuggestion]:
        """
        Generate follow-up query suggestions

        Args:
            query: Original query
            answer: Generated answer
            retrieved_documents: Retrieved documents

        Returns:
            List of suggestions
        """
        suggestions = []

        # Suggestion 1: Clarification
        if "?" in query or "how" in query.lower():
            suggestion = QuerySuggestion(
                text=f"Can you provide more details about {self._extract_main_noun(query)}?",
                category="clarification",
                confidence=0.75,
                reason="User asked a question - likely wants more details"
            )
            suggestions.append(suggestion)

        # Suggestion 2: Related topic
        topic = self._extract_main_topic(answer)
        if topic:
            suggestion = QuerySuggestion(
                text=f"What about {topic}?",
                category="related",
                confidence=0.7,
                reason="Natural follow-up to expand on related topic"
            )
            suggestions.append(suggestion)

        # Suggestion 3: Expansion
        suggestion = QuerySuggestion(
            text=f"Can you explain {self._extract_main_noun(answer)} in more detail?",
            category="expansion",
            confidence=0.65,
            reason="User might want deeper understanding"
        )
        suggestions.append(suggestion)

        return suggestions

    @staticmethod
    def _extract_main_noun(text: str) -> str:
        """Extract main noun from text (simple heuristic)"""
        words = [w for w in text.split() if len(w) > 4]
        return words[0] if words else "this topic"

    @staticmethod
    def _extract_main_topic(text: str) -> str:
        """Extract main topic from text"""
        # Simple: take longest noun-like word
        words = text.split()
        longest = max(words, key=len) if words else "this"
        return longest.rstrip('.,!?')

class ConversationManager:
    """Manage conversation history and memory"""

    def __init__(self):
        """Initialize conversation manager"""
        self.conversations: dict[str, ConversationMemory] = {}
        logger.info("✓ ConversationManager initialized")

    def create_conversation(self, conversation_id: str) -> ConversationMemory:
        """Create new conversation"""
        conversation = ConversationMemory(conversation_id=conversation_id)
        self.conversations[conversation_id] = conversation
        logger.info(f"Created conversation {conversation_id}")
        return conversation

    def add_turn(self,
                 conversation_id: str,
                 turn: ConversationTurn):
        """Add turn to conversation"""
        if conversation_id not in self.conversations:
            self.create_conversation(conversation_id)

        self.conversations[conversation_id].add_turn(turn)

    def get_conversation(self, conversation_id: str) -> Optional[ConversationMemory]:
        """Get conversation by ID"""
        return self.conversations.get(conversation_id)

    def get_context(self, conversation_id: str, max_turns: int = 5) -> str:
        """Get conversation context for LLM"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return ""

        return conversation.get_context(max_turns)

    def summarize_conversation(self, conversation_id: str) -> Dict:
        """Get conversation summary"""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return {}

        return conversation.get_summary()

class ResponseEnhancer:
    """Enhance response with citations, suggestions, and formatting"""

    def __init__(self):
        """Initialize response enhancer"""
        self.citation_manager = CitationManager()
        self.query_suggestor = QuerySuggestor()
        logger.info("✓ ResponseEnhancer initialized")

    def enhance_response(self,
                        query: str,
                        answer: str,
                        retrieved_documents: list[Dict],
                        quality_score: float = 0.0) -> Dict:
        """
        Enhance response with all UX features

        Args:
            query: Original query
            answer: Generated answer
            retrieved_documents: Retrieved documents
            quality_score: Quality score from FASE 19

        Returns:
            Enhanced response dict
        """
        # Extract citations
        citations = self.citation_manager.extract_citations(answer, retrieved_documents)
        formatted_answer, _ = self.citation_manager.format_citations(answer, citations)

        # Generate suggestions
        suggestions = self.query_suggestor.generate_suggestions(query, answer, retrieved_documents)

        # Build enhanced response
        enhanced = {
            'query': query,
            'answer': formatted_answer,
            'base_answer': answer,
            'citations': [self.citation_manager.get_citation_preview(c) for c in citations],
            'suggestions': [
                {
                    'text': s.text,
                    'category': s.category,
                    'confidence': s.confidence,
                }
                for s in suggestions
            ],
            'quality_score': quality_score,
            'metadata': {
                'citation_count': len(citations),
                'suggestion_count': len(suggestions),
            }
        }

        return enhanced

def get_citation_manager() -> CitationManager:
    """Get singleton citation manager"""
    if not hasattr(get_citation_manager, '_instance'):
        get_citation_manager._instance = CitationManager()
    return get_citation_manager._instance

def get_query_suggestor() -> QuerySuggestor:
    """Get singleton query suggestor"""
    if not hasattr(get_query_suggestor, '_instance'):
        get_query_suggestor._instance = QuerySuggestor()
    return get_query_suggestor._instance

def get_conversation_manager() -> ConversationManager:
    """Get singleton conversation manager"""
    if not hasattr(get_conversation_manager, '_instance'):
        get_conversation_manager._instance = ConversationManager()
    return get_conversation_manager._instance

def get_response_enhancer() -> ResponseEnhancer:
    """Get singleton response enhancer"""
    if not hasattr(get_response_enhancer, '_instance'):
        get_response_enhancer._instance = ResponseEnhancer()
    return get_response_enhancer._instance
