"""
Phase 3B: Conversational Document Navigator

Enables intelligent document-aware multi-turn conversation with:
- Semantic document navigation (jump to sections)
- Automatic document context injection
- Multi-document comparison
- Related document discovery
- Intelligent conversation memory

Architecture:
- ChatContext: Tracks active document, conversation history, visited sections
- NavigationResponse: Extends RAGResponse with navigation metadata
- IntentClassifier: Pure functions detecting user intent (summary, section_jump, etc)
- DocumentNavigator: Routes intents to specialized handlers
- Singleton factory: get_document_navigator()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from io import StringIO
from typing import Optional, TYPE_CHECKING

from src.logging_config import get_logger

if TYPE_CHECKING:
    from src.rag_engine import RAGEngine, RAGResponse, RetrievalResult
    from src.analysis.document_analyzer import DocumentAnalyzer, DocumentAnalysis

logger = get_logger(__name__)

# Constants
MAX_CONTEXT_MESSAGES = 6
MAX_HISTORY_LENGTH = 100
CONTEXT_WINDOW_SIZE = 6


@dataclass
class ChatMessage:
    """Single message in conversation history"""
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    doc_id: Optional[str] = None  # Which document was active
    navigation_type: Optional[str] = None  # Type of navigation used


@dataclass
class ChatContext:
    """
    Maintains conversation state for document navigation.

    Tracks:
    - Active document being discussed
    - Conversation history (sliding window)
    - Visited sections in each document
    - Document-specific conversation memory
    """
    active_doc_id: Optional[str] = None
    messages: list[ChatMessage] = field(default_factory=list)
    visited_sections: dict[str, list[str]] = field(default_factory=dict)  # doc_id -> [section_ids]
    document_context_cache: dict[str, str] = field(default_factory=dict)  # doc_id -> cached context

    def add_message(
        self,
        role: str,
        content: str,
        doc_id: Optional[str] = None,
        nav_type: Optional[str] = None,
    ) -> None:
        """Add message to history with auto-trimming to MAX_HISTORY_LENGTH"""
        msg = ChatMessage(
            role=role,
            content=content,
            doc_id=doc_id or self.active_doc_id,
            navigation_type=nav_type,
        )
        self.messages.append(msg)

        # Auto-trim to max length
        if len(self.messages) > MAX_HISTORY_LENGTH:
            self.messages = self.messages[-MAX_HISTORY_LENGTH:]

    def get_context_window(self, n: int = MAX_CONTEXT_MESSAGES) -> list[ChatMessage]:
        """Return last N messages for LLM prompt injection"""
        return self.messages[-n:] if self.messages else []

    def switch_document(self, doc_id: str) -> None:
        """Switch active document and initialize section tracking if needed"""
        self.active_doc_id = doc_id
        if doc_id not in self.visited_sections:
            self.visited_sections[doc_id] = []

    def format_context_for_prompt(self) -> str:
        """Serialize context window as formatted string for LLM injection"""
        if not self.messages:
            return ""

        window = self.get_context_window(MAX_CONTEXT_MESSAGES)
        buf = StringIO()
        for i, msg in enumerate(window):
            if i > 0:
                buf.write("\n")
            prefix = "User:" if msg.role == "user" else "Assistant:"
            buf.write(f"{prefix} {msg.content}")

        return buf.getvalue()

    def mark_section_visited(self, doc_id: str, section_id: str) -> None:
        """Track visited sections for analytics"""
        if doc_id not in self.visited_sections:
            self.visited_sections[doc_id] = []
        if section_id not in self.visited_sections[doc_id]:
            self.visited_sections[doc_id].append(section_id)

    def to_dict(self) -> dict:
        """Serialize to dict for Streamlit session state"""
        return {
            "active_doc_id": self.active_doc_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "doc_id": msg.doc_id,
                    "navigation_type": msg.navigation_type,
                }
                for msg in self.messages
            ],
            "visited_sections": self.visited_sections,
            "document_context_cache": self.document_context_cache,
        }

    @staticmethod
    def from_dict(data: dict) -> ChatContext:
        """Deserialize from dict (Streamlit session state)"""
        ctx = ChatContext()
        ctx.active_doc_id = data.get("active_doc_id")
        ctx.visited_sections = data.get("visited_sections", {})
        ctx.document_context_cache = data.get("document_context_cache", {})

        for msg_data in data.get("messages", []):
            msg = ChatMessage(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.now().isoformat())),
                doc_id=msg_data.get("doc_id"),
                navigation_type=msg_data.get("navigation_type"),
            )
            ctx.messages.append(msg)

        return ctx


@dataclass
class NavigationResponse:
    """Extended response with navigation metadata"""
    answer: str
    navigation_type: str  # "direct_query" | "section_jump" | "summary" | "comparison" | "related_docs"
    active_document: Optional[str] = None
    referenced_sections: list[str] = field(default_factory=list)
    related_documents: list[str] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    confidence_score: float = 0.0
    source_chunks: list[str] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Whether response is successful (no error)"""
        return self.error is None


def _compile_combined(patterns: list[str]) -> re.Pattern:
    """Combine multiple pattern strings into a single compiled regex with alternation."""
    combined = "|".join(f"(?:{p})" for p in patterns)
    return re.compile(combined, re.IGNORECASE)


class IntentClassifier:
    """Pure functions for detecting user navigation intent.

    All regex patterns are pre-compiled at class definition time into
    single combined patterns per intent category, avoiding per-call
    recompilation overhead.
    """

    # Pre-compiled combined patterns (one regex per intent category)
    _SUMMARY_RE = _compile_combined([
        r"riassumi", r"summarizza",
        r"dammi un (?:rapido |breve )?riepilogo",
        r"cosa contiene", r"cosa tratta",
        r"summarize", r"summary",
        r"give me an? (?:quick |brief )?overview",
        r"what does", r"what treats",
    ])

    _SECTION_JUMP_RE = _compile_combined([
        r"vai (?:a|alla|al) (?:sezione |paragrafo |capitolo )?([^\.]+)",
        r"mostrami (?:la |la sezione )?([^\.]+)",
        r"vai a ([^\.]+)", r"salta a ([^\.]+)",
        r"go to (?:section |chapter |)?([^\.]+)",
        r"jump to ([^\.]+)",
        r"show me (?:the )?([^\.]+)",
        r"take me to ([^\.]+)",
    ])

    _COMPARISON_RE = _compile_combined([
        r"confronta", r"compara", r"differenza tra",
        r"quale è (?:la |il )?differenza", r"contrasta",
        r"compare", r"contrast", r"difference between",
        r"what'?s the difference", r"how do .* differ",
    ])

    _RELATED_DOCS_RE = _compile_combined([
        r"documenti simili", r"documenti correlati",
        r"cosa è collegato", r"trovami .* simile",
        r"altri documenti su",
        r"similar documents", r"related documents",
        r"what'?s related", r"find .* similar",
        r"other documents about",
    ])

    _SELF_REF_RE = _compile_combined([
        r"questo documento", r"questo file",
        r"il documento", r"il file", r"questo",
        r"this document", r"this file",
        r"the document", r"the file",
    ])

    _SECTION_REF_IT_RE = re.compile(
        r"(?:sezione|paragrafo|capitolo)\s+([\"']?)([^\"'\.]+)\1",
        re.IGNORECASE,
    )
    _SECTION_REF_EN_RE = re.compile(
        r"(?:section|chapter|paragraph)\s+([\"']?)([^\"'\.]+)\1",
        re.IGNORECASE,
    )

    # Ordered intent dispatch: (compiled_pattern, intent_name)
    _INTENT_ORDER = [
        (_SUMMARY_RE, "summary"),
        (_SECTION_JUMP_RE, "section_jump"),
        (_COMPARISON_RE, "comparison"),
        (_RELATED_DOCS_RE, "related_docs"),
    ]

    @staticmethod
    def classify_intent(text: str) -> str:
        """
        Classify user intent from text.
        Returns one of: "summary", "section_jump", "comparison", "related_docs", "direct_query"

        Priority order: summary > section_jump > comparison > related_docs > direct_query
        """
        text_lower = text.lower()

        for pattern, intent in IntentClassifier._INTENT_ORDER:
            if pattern.search(text_lower):
                return intent

        return "direct_query"

    @staticmethod
    def resolve_document_reference(
        text: str,
        active_doc_id: Optional[str],
        known_doc_ids: list[str],
    ) -> Optional[str]:
        """
        Resolve self-references ('questo documento', 'il file') to actual doc_id.
        Returns active_doc_id if reference is self-referential, or matched doc_id.
        """
        text_lower = text.lower()

        if IntentClassifier._SELF_REF_RE.search(text_lower):
            return active_doc_id

        # Try substring matching against known_doc_ids
        for doc_id in known_doc_ids:
            if doc_id.lower() in text_lower:
                return doc_id

        return None

    @staticmethod
    def extract_section_reference(text: str) -> Optional[str]:
        """
        Extract section title from text like 'vai alla sezione Introduzione'.
        Returns section title or None.
        """
        match = IntentClassifier._SECTION_REF_IT_RE.search(text)
        if match:
            return match.group(2).strip()

        match = IntentClassifier._SECTION_REF_EN_RE.search(text)
        if match:
            return match.group(2).strip()

        return None


class DocumentNavigator:
    """
    Routes user queries to specialized navigation handlers based on intent.

    Main entry point: query(text, ctx) -> NavigationResponse
    """

    def __init__(self, rag_engine: RAGEngine, analyzer: Optional[DocumentAnalyzer] = None) -> None:
        """
        Initialize navigator.

        Args:
            rag_engine: RAGEngine instance for document retrieval
            analyzer: DocumentAnalyzer for accessing document structure/metadata
        """
        self.rag_engine = rag_engine
        self.analyzer = analyzer
        logger.info("DocumentNavigator initialized")

    def query(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """
        Main entry point: classify intent and route to appropriate handler.

        Args:
            text: User query text
            ctx: ChatContext with conversation state

        Returns:
            NavigationResponse with answer and navigation metadata
        """
        try:
            # Classify intent
            intent = IntentClassifier.classify_intent(text)
            logger.info(f"Classified intent: {intent}")

            # Route to handler
            if intent == "summary":
                return self._handle_summary(text, ctx)
            elif intent == "section_jump":
                return self._handle_section_jump(text, ctx)
            elif intent == "comparison":
                return self._handle_comparison(text, ctx)
            elif intent == "related_docs":
                return self._handle_related_docs(text, ctx)
            else:  # direct_query
                return self._handle_direct_query(text, ctx)

        except Exception as e:
            logger.error(f"Navigator error: {e}", exc_info=True)
            return NavigationResponse(
                answer="Mi dispiace, si è verificato un errore nella navigazione.",
                navigation_type="error",
                error=str(e),
            )

    def _handle_direct_query(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """Route to RAGEngine with optional document scoping"""
        try:
            # Add context to prompt for multi-turn awareness
            context_window = ctx.format_context_for_prompt()
            scoped_query = text
            if ctx.active_doc_id and context_window:
                scoped_query = f"{context_window}\n\nNuova domanda su {ctx.active_doc_id}: {text}"

            # Query RAG engine
            response = self.rag_engine.query(
                scoped_query if context_window else text,
                metadata_filter={"doc_id": ctx.active_doc_id} if ctx.active_doc_id else None,
            )

            # Extract source information
            source_chunks = [f"{r.source}#{r.section}" for r in response.sources]
            related_docs = list({r.doc_id for r in response.sources if r.doc_id != ctx.active_doc_id})

            # Add to context
            ctx.add_message("user", text, nav_type="direct_query")
            ctx.add_message("assistant", response.answer, nav_type="direct_query")

            return NavigationResponse(
                answer=response.answer,
                navigation_type="direct_query",
                active_document=ctx.active_doc_id,
                source_chunks=source_chunks,
                related_documents=related_docs,
                confidence_score=response.confidence_score,
                suggested_questions=self._generate_suggestions(text),
            )

        except Exception as e:
            logger.error(f"Direct query handler error: {e}")
            return NavigationResponse(
                answer="Errore durante la query.",
                navigation_type="direct_query",
                error=str(e),
            )

    def _handle_summary(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """Generate summary of current document or specific section"""
        try:
            if not ctx.active_doc_id:
                return NavigationResponse(
                    answer="Per favore, seleziona un documento prima di richiede un riassunto.",
                    navigation_type="summary",
                    error="No active document",
                )

            if not self.analyzer:
                return NavigationResponse(
                    answer="L'analizzatore dei documenti non è disponibile.",
                    navigation_type="summary",
                    error="Analyzer not available",
                )

            # Get document analysis
            analysis = self.analyzer.get_analysis(ctx.active_doc_id)
            if not analysis or not analysis.analysis_available:
                return NavigationResponse(
                    answer=f"Non ho analisi disponibili per {ctx.active_doc_id}.",
                    navigation_type="summary",
                    error="No analysis available",
                )

            # Generate summary prompt
            metadata = analysis.metadata
            sections_text = "\n".join([s.title for s in analysis.sections[:10]])

            summary_prompt = f"""
Fornisci un breve riassunto di questo documento:

Titolo: {metadata.title if metadata else 'Sconosciuto'}
Tipo: {metadata.doc_type if metadata else 'Sconosciuto'}
Linguaggio: {metadata.language if metadata else 'Sconosciuto'}
Parole totali: {metadata.word_count if metadata else '?'}

Sezioni principali:
{sections_text}

Riassumi il documento in 3-4 frasi.
"""

            # Call LLM for summary
            response = self.rag_engine.llm.completion(summary_prompt)

            # Mark sections as visited
            for section in analysis.sections:
                ctx.mark_section_visited(ctx.active_doc_id, section.section_id)

            ctx.add_message("user", text, nav_type="summary")
            ctx.add_message("assistant", response, nav_type="summary")

            return NavigationResponse(
                answer=response,
                navigation_type="summary",
                active_document=ctx.active_doc_id,
                referenced_sections=[s.section_id for s in analysis.sections],
                suggested_questions=self._generate_suggestions(f"Tell me about {metadata.title if metadata else ctx.active_doc_id}"),
            )

        except Exception as e:
            logger.error(f"Summary handler error: {e}")
            return NavigationResponse(
                answer="Errore durante la generazione del riassunto.",
                navigation_type="summary",
                error=str(e),
            )

    def _handle_section_jump(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """Jump to specific section and provide context"""
        try:
            if not ctx.active_doc_id:
                return NavigationResponse(
                    answer="Per favore, seleziona un documento prima.",
                    navigation_type="section_jump",
                    error="No active document",
                )

            if not self.analyzer:
                return NavigationResponse(
                    answer="L'analizzatore non è disponibile.",
                    navigation_type="section_jump",
                    error="Analyzer not available",
                )

            # Extract section reference
            section_title = IntentClassifier.extract_section_reference(text)
            if not section_title:
                return NavigationResponse(
                    answer="Non ho capito quale sezione cerchi.",
                    navigation_type="section_jump",
                    error="Could not extract section reference",
                )

            # Find section
            analysis = self.analyzer.get_analysis(ctx.active_doc_id)
            if not analysis or not analysis.sections:
                return NavigationResponse(
                    answer=f"Nessuna sezione trovata in {ctx.active_doc_id}.",
                    navigation_type="section_jump",
                    error="No sections found",
                )

            section = self._find_section(analysis.sections, section_title)
            if not section:
                return NavigationResponse(
                    answer=f"Sezione '{section_title}' non trovata.",
                    navigation_type="section_jump",
                    error="Section not found",
                )

            # Mark as visited
            ctx.mark_section_visited(ctx.active_doc_id, section.section_id)

            # Generate section context
            answer = f"Ho trovato la sezione '{section.title}' nel documento {ctx.active_doc_id}.\n\n"
            answer += f"Questa sezione contiene {len(section.chunk_indices)} chunk di testo.\n\n"
            answer += "Come posso aiutarti con questa sezione?"

            ctx.add_message("user", text, nav_type="section_jump")
            ctx.add_message("assistant", answer, nav_type="section_jump")

            return NavigationResponse(
                answer=answer,
                navigation_type="section_jump",
                active_document=ctx.active_doc_id,
                referenced_sections=[section.section_id],
                suggested_questions=self._generate_suggestions(f"Tell me about {section.title}"),
            )

        except Exception as e:
            logger.error(f"Section jump handler error: {e}")
            return NavigationResponse(
                answer="Errore durante il salto di sezione.",
                navigation_type="section_jump",
                error=str(e),
            )

    def _handle_comparison(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """Compare concepts or documents"""
        try:
            # Extract comparison terms - supports both Italian and English patterns
            match = re.search(
                r"(?:confronta|compara|differenza tra|contrasta|compare|contrast|difference between)\s+([^\s]+)\s+(?:e|con|and)\s+([^\s\.]+)",
                text,
                re.IGNORECASE
            )
            if not match:
                return NavigationResponse(
                    answer="Per favore, specifica cosa confrontare: 'confronta A e B' oppure 'compare A and B'.",
                    navigation_type="comparison",
                    error="Could not parse comparison",
                )

            term_a, term_b = match.group(1), match.group(2)

            # Query for both terms
            response_a = self.rag_engine.query(f"Cos'è {term_a}?")
            response_b = self.rag_engine.query(f"Cos'è {term_b}?")

            # Generate comparison
            comparison_prompt = f"""
Confronta questi due concetti in modo conciso:

{term_a}: {response_a.answer}

{term_b}: {response_b.answer}

Quali sono le differenze principali? (max 5 punti)
"""

            answer = self.rag_engine.llm.completion(comparison_prompt)

            ctx.add_message("user", text, nav_type="comparison")
            ctx.add_message("assistant", answer, nav_type="comparison")

            return NavigationResponse(
                answer=answer,
                navigation_type="comparison",
                active_document=ctx.active_doc_id,
                source_chunks=[
                    f"{r.source}#{r.section}" for r in (response_a.sources + response_b.sources)
                ],
                suggested_questions=self._generate_suggestions(f"How do {term_a} and {term_b} relate?"),
            )

        except Exception as e:
            logger.error(f"Comparison handler error: {e}")
            return NavigationResponse(
                answer="Errore durante il confronto.",
                navigation_type="comparison",
                error=str(e),
            )

    def _handle_related_docs(self, text: str, ctx: ChatContext) -> NavigationResponse:
        """Find related documents"""
        try:
            if not ctx.active_doc_id:
                return NavigationResponse(
                    answer="Per favore, seleziona un documento prima.",
                    navigation_type="related_docs",
                    error="No active document",
                )

            if not self.analyzer:
                return NavigationResponse(
                    answer="L'analizzatore non è disponibile.",
                    navigation_type="related_docs",
                    error="Analyzer not available",
                )

            # Get active document analysis
            analysis = self.analyzer.get_analysis(ctx.active_doc_id)
            if not analysis:
                return NavigationResponse(
                    answer=f"Nessuna analisi disponibile per {ctx.active_doc_id}.",
                    navigation_type="related_docs",
                    error="No analysis available",
                )

            # Find related documents using keywords
            keywords = analysis.metadata.keywords if analysis.metadata else []
            related_docs = set()

            if keywords:
                for keyword in keywords[:5]:
                    response = self.rag_engine.query(f"Quale documento parla di {keyword}?")
                    for source in response.sources:
                        if source.doc_id != ctx.active_doc_id:
                            related_docs.add(source.doc_id)

            answer = f"Ho trovato {len(related_docs)} documenti correlati a {ctx.active_doc_id}:\n\n"
            for doc_id in list(related_docs)[:5]:
                answer += f"- {doc_id}\n"

            ctx.add_message("user", text, nav_type="related_docs")
            ctx.add_message("assistant", answer, nav_type="related_docs")

            return NavigationResponse(
                answer=answer,
                navigation_type="related_docs",
                active_document=ctx.active_doc_id,
                related_documents=list(related_docs)[:5],
                suggested_questions=self._generate_suggestions("Show me similar documents"),
            )

        except Exception as e:
            logger.error(f"Related docs handler error: {e}")
            return NavigationResponse(
                answer="Errore durante la ricerca di documenti correlati.",
                navigation_type="related_docs",
                error=str(e),
            )

    def _find_section(self, sections: list, section_title: str) -> Optional:
        """Find section by case-insensitive title matching"""
        title_lower = section_title.lower()
        for section in sections:
            if section.title.lower() == title_lower or title_lower in section.title.lower():
                return section
        return None

    def _generate_suggestions(self, context: str) -> list[str]:
        """Generate 3 suggested follow-up questions"""
        suggestions = [
            f"Puoi approfondire '{context}'?",
            f"Cosa è correlato a '{context}'?",
            f"Dammi un esempio di '{context}'.",
        ]
        return suggestions


# Global singleton
_document_navigator: Optional[DocumentNavigator] = None


def get_document_navigator(
    rag_engine: Optional[RAGEngine] = None,
    analyzer: Optional[DocumentAnalyzer] = None,
) -> DocumentNavigator:
    """
    Get or create the global DocumentNavigator singleton.
    Thread-safe via module-level lazy initialization.

    Args:
        rag_engine: RAGEngine instance (required for first call)
        analyzer: DocumentAnalyzer instance (optional)

    Returns:
        Singleton DocumentNavigator instance
    """
    global _document_navigator

    if _document_navigator is None:
        if rag_engine is None:
            from src.rag_engine import RAGEngine

            rag_engine = RAGEngine()
        _document_navigator = DocumentNavigator(rag_engine, analyzer)

    return _document_navigator
