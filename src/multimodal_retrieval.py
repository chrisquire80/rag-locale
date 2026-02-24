"""
Multimodal Retrieval Engine - Hybrid Text + Visual Search
Enables searching and reasoning over both text and visual content
"""

import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MultimodalResult:
    """Result with both text and visual context"""
    result_id: str
    text_content: str
    has_visual: bool
    visual_description: str
    visual_element_type: Optional[str]  # chart, table, image
    page_number: int
    document_id: str
    relevance_score: float
    combined_score: float  # Text + visual relevance

class MultimodalRetriever:
    """Retrieve and rank results combining text and visual content"""

    def __init__(self, vector_store, llm_service):
        """Initialize retriever"""
        self.vector_store = vector_store
        self.llm = llm_service
        logger.info("Multimodal Retriever initialized")

    def retrieve_with_visuals(
        self,
        query: str,
        top_k: int = 5,
        include_visuals: bool = True
    ) -> list[MultimodalResult]:
        """
        Retrieve results with visual context

        Args:
            query: Search query
            top_k: Number of results
            include_visuals: Include visual elements

        Returns:
            List of MultimodalResult
        """
        # Step 1: Retrieve based on text
        text_results = self.vector_store.search(query, top_k=top_k*2)

        if not text_results:
            return []

        # Step 2: Enhance with visual metadata
        multimodal_results = []

        for result in text_results:
            # Check if result has visual elements
            metadata = result.get('metadata', {})
            visual_elements_count = metadata.get('visual_elements_count', 0)

            multimodal_result = MultimodalResult(
                result_id=result.get('id', ''),
                text_content=result.get('content', ''),
                has_visual=visual_elements_count > 0,
                visual_description=metadata.get('analysis_type', '') == 'visual_analysis',
                visual_element_type=metadata.get('element_type', None),
                page_number=metadata.get('page_number', 0),
                document_id=metadata.get('document_id', ''),
                relevance_score=result.get('score', 0.0),
                combined_score=result.get('score', 0.0)
            )

            # Boost score if has visual elements
            if multimodal_result.has_visual:
                multimodal_result.combined_score *= 1.2

            multimodal_results.append(multimodal_result)

        # Step 3: Sort by combined score
        multimodal_results.sort(key=lambda x: x.combined_score, reverse=True)

        return multimodal_results[:top_k]

    def ask_about_visual(
        self,
        question: str,
        visual_element,
        text_context: str = ""
    ) -> str:
        """
        Answer question using visual element

        Args:
            question: User question
            visual_element: VisualElement object
            text_context: Related text context

        Returns:
            Answer incorporating visual information
        """
        try:
            # Build context for Gemini with visual
            prompt = f"""Basandoti su questa immagine e il contesto testuale, rispondi alla domanda.

DOMANDA: {question}

CONTESTO TESTUALE: {text_context[:500]}

TIPO ELEMENTO VISIVO: {visual_element.element_type}
DESCRIZIONE VISIVA: {visual_element.description}

Nell'analizzare l'immagine:
1. Descrivi cosa vedi
2. Correlalo con la domanda
3. Estrai dati quantitativi se presenti
4. Fornisci una risposta completa

RISPOSTA:"""

            # Use vision API with image
            response = self.llm.completion(
                prompt=prompt,
                images=[visual_element.image_base64] if visual_element.image_base64 else None,
                max_tokens=1000,
                temperature=0.3
            )

            return response

        except Exception as e:
            logger.error(f"Failed to answer visual question: {e}")
            return "Non riesco ad analizzare l'elemento visivo."

    def generate_visual_summary(
        self,
        document_id: str,
        max_visuals: int = 10
    ) -> Dict:
        """
        Generate summary highlighting visual elements

        Args:
            document_id: Document to summarize
            max_visuals: Maximum visual elements to include

        Returns:
            Summary with visual highlights
        """
        try:
            # Get all pages with visual analysis for this document
            results = self.vector_store.search(
                f"document_id:{document_id}",
                top_k=100
            )

            visual_highlights = []
            for result in results:
                metadata = result.get('metadata', {})
                if metadata.get('analysis_type') == 'visual_analysis':
                    visual_highlights.append({
                        'page': metadata.get('page_number'),
                        'elements': metadata.get('visual_elements_count', 0),
                        'findings': metadata.get('key_findings', [])
                    })

            # Generate summary
            summary = {
                "document_id": document_id,
                "total_pages_analyzed": len(visual_highlights),
                "visual_elements_found": sum(h['elements'] for h in visual_highlights),
                "pages_with_visuals": [h['page'] for h in visual_highlights],
                "key_visual_findings": []
            }

            # Extract key findings
            for highlight in visual_highlights[:max_visuals]:
                summary["key_visual_findings"].extend(highlight['findings'])

            return summary

        except Exception as e:
            logger.error(f"Failed to generate visual summary: {e}")
            return {"error": str(e)}

class VisualQueryAnalyzer:
    """Analyze queries to determine if they need visual context"""

    VISUAL_KEYWORDS = [
        "grafico", "chart", "tabella", "table", "immagine", "image",
        "visualizza", "mostra", "vedi", "osserva", "trend", "trend",
        "percentuale", "barra", "linea", "pie", "diagramma"
    ]

    def needs_visual_context(self, query: str) -> bool:
        """Check if query mentions visual elements"""
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.VISUAL_KEYWORDS)

    def extract_visual_intent(self, query: str) -> Dict:
        """
        Extract what visual content user is looking for

        Args:
            query: User query

        Returns:
            Dict with visual search intent
        """
        intent = {
            "needs_visual": self.needs_visual_context(query),
            "visual_types": [],
            "context": "general"
        }

        query_lower = query.lower()

        # Detect visual types
        if any(w in query_lower for w in ["grafico", "chart"]):
            intent["visual_types"].append("chart")
        if any(w in query_lower for w in ["tabella", "table"]):
            intent["visual_types"].append("table")
        if any(w in query_lower for w in ["immagine", "image", "foto"]):
            intent["visual_types"].append("image")
        if any(w in query_lower for w in ["trend", "crescita", "andamento"]):
            intent["context"] = "trend_analysis"
        if any(w in query_lower for w in ["percentuale", "frazione", "porzione"]):
            intent["context"] = "proportion_analysis"

        return intent

def get_multimodal_retriever(vector_store, llm_service) -> MultimodalRetriever:
    """Get or create global multimodal retriever"""
    if not hasattr(get_multimodal_retriever, '_instance'):
        get_multimodal_retriever._instance = MultimodalRetriever(vector_store, llm_service)
    return get_multimodal_retriever._instance

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Multimodal Retrieval Engine")
    print("=" * 60)
    print("\nCapabilities:")
    print("✅ Hybrid Text + Visual Search")
    print("✅ Visual Intent Detection")
    print("✅ Visual-based Q&A")
    print("✅ Visual Summary Generation")
    print("✅ Automatic boost for visual-rich results")
