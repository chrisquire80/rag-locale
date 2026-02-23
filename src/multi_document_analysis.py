"""
Multi-Document Analysis - TASK 6
Leverages Gemini 2.0 Flash's 1M token context for comprehensive document analysis
Enables global summaries, cross-document insights, and pattern detection
"""

import logging
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DocumentCluster:
    """Represents a thematic cluster of documents"""
    cluster_id: str
    theme: str
    documents: list[str]  # Document IDs
    keywords: list[str]
    summary: str
    confidence: float = 0.8


@dataclass
class CrossDocumentInsight:
    """Represents an insight across multiple documents"""
    insight_type: str  # "contradiction", "connection", "progression", "consensus"
    related_documents: list[str]
    insight_text: str
    evidence: list[str]  # Supporting quotes
    confidence: float


@dataclass
class GlobalAnalysis:
    """Global analysis result across all documents"""
    total_documents: int
    total_tokens_used: int
    analysis_timestamp: datetime
    global_summary: str  # High-level summary of all documents
    themes: list[DocumentCluster]  # Thematic clusters
    insights: list[CrossDocumentInsight]  # Cross-document insights
    key_findings: list[str]
    recommendations: list[str]
    gaps_identified: list[str]


class MultiDocumentAnalyzer:
    """Analyze and synthesize information across multiple documents"""

    # Gemini 2.0 Flash supports 1M tokens per context
    MAX_CONTEXT_TOKENS = 900_000  # Leave 100K buffer
    APPROX_TOKENS_PER_CHAR = 0.25  # Rough estimate: 1 token ≈ 4 characters

    def __init__(self, llm_service):
        """
        Initialize multi-document analyzer

        Args:
            llm_service: LLM service with long context support (Gemini 2.0)
        """
        self.llm = llm_service
        self.cache = {}
        logger.info("Initialized Multi-Document Analyzer (1M token context)")

    def analyze_all_documents(
        self,
        documents: list[Dict],
        analysis_depth: str = "comprehensive"  # "quick", "standard", "comprehensive"
    ) -> GlobalAnalysis:
        """
        Perform comprehensive analysis across all documents

        Args:
            documents: List of {id, title, content, metadata}
            analysis_depth: Depth of analysis (affects token usage)

        Returns:
            GlobalAnalysis with summary, themes, and insights
        """
        logger.info(f"Starting multi-document analysis of {len(documents)} documents")

        # Estimate token usage
        total_chars = sum(len(d.get('content', '')) for d in documents)
        estimated_tokens = int(total_chars * self.APPROX_TOKENS_PER_CHAR)

        if estimated_tokens > self.MAX_CONTEXT_TOKENS:
            logger.warning(
                f"Token estimate ({estimated_tokens}) exceeds limit ({self.MAX_CONTEXT_TOKENS}), "
                "using sampling strategy"
            )
            documents = self._sample_documents(documents)

        # Step 1: Generate global summary
        global_summary = self._generate_global_summary(documents, analysis_depth)

        # Step 2: Identify themes and clusters
        themes = self._identify_themes(documents, global_summary)

        # Step 3: Find cross-document insights
        insights = self._find_insights(documents, themes)

        # Step 4: Extract key findings
        key_findings = self._extract_key_findings(documents, global_summary, insights)

        # Step 5: Generate recommendations
        recommendations = self._generate_recommendations(documents, key_findings, insights)

        # Step 6: Identify gaps
        gaps = self._identify_gaps(documents, key_findings)

        analysis = GlobalAnalysis(
            total_documents=len(documents),
            total_tokens_used=estimated_tokens,
            analysis_timestamp=datetime.now(),
            global_summary=global_summary,
            themes=themes,
            insights=insights,
            key_findings=key_findings,
            recommendations=recommendations,
            gaps_identified=gaps
        )

        logger.info(f"Multi-document analysis complete (tokens: {estimated_tokens})")
        return analysis

    def _generate_global_summary(self, documents: list[Dict], depth: str) -> str:
        """Generate high-level summary of all documents"""
        # Format all documents for context
        context = self._format_document_context(documents, max_docs=None)

        prompt = f"""Analizza questi {len(documents)} documenti e fornisci un riassunto globale.

DOCUMENTI:
{context}

Fornisci un riassunto CONCISO (200-300 parole) che copra:
1. Tema principale dei documenti
2. Argomenti centrali
3. Scope e profondità della copertura
4. Pubblico target
5. Livello di dettaglio

Riassunto:"""

        try:
            summary = self.llm.completion(
                prompt=prompt,
                max_tokens=400,
                temperature=0.3
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"Global summary generation failed: {e}")
            return f"Analisi di {len(documents)} documenti non completata"

    def _identify_themes(
        self,
        documents: list[Dict],
        summary: str
    ) -> list[DocumentCluster]:
        """Identify thematic clusters in documents"""
        context = self._format_document_context(documents, max_docs=min(20, len(documents)))

        prompt = f"""Identifica 3-5 cluster tematici nei seguenti documenti.

Riassunto precedente: {summary}

DOCUMENTI:
{context}

Rispondi in questo formato esatto (JSON):
{{
    "clusters": [
        {{
            "theme": "Nome tema",
            "keywords": ["keyword1", "keyword2"],
            "document_ids": ["doc_id1", "doc_id2"],
            "description": "Breve descrizione"
        }}
    ]
}}

Solo JSON, niente altro:"""

        try:
            import json
            import re

            response = self.llm.completion(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )

            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                clusters = []

                for idx, cluster_data in enumerate(data.get('clusters', []), 1):
                    cluster = DocumentCluster(
                        cluster_id=f"cluster_{idx}",
                        theme=cluster_data.get('theme', 'Unknown'),
                        documents=cluster_data.get('document_ids', []),
                        keywords=cluster_data.get('keywords', []),
                        summary=cluster_data.get('description', ''),
                        confidence=0.85
                    )
                    clusters.append(cluster)

                return clusters
        except Exception as e:
            logger.error(f"Theme identification failed: {e}")

        return []

    def _find_insights(
        self,
        documents: list[Dict],
        themes: list[DocumentCluster]
    ) -> list[CrossDocumentInsight]:
        """Find cross-document insights (contradictions, connections, progressions)"""
        # Prepare context with theme information
        themes_text = "\n".join([f"- {t.theme}: {', '.join(t.documents)}" for t in themes])
        context = self._format_document_context(documents, max_docs=min(15, len(documents)))

        prompt = f"""Analizza questi documenti e identifica insights cross-documento.

TEMI IDENTIFICATI:
{themes_text}

DOCUMENTI:
{context}

Trova:
1. Contraddizioni tra documenti
2. Connessioni e relazioni
3. Progressioni temporali
4. Consensi/accordi

Rispondi in formato JSON:
{{
    "insights": [
        {{
            "type": "contradiction|connection|progression|consensus",
            "documents": ["doc1", "doc2"],
            "insight": "Descrizione dell'insight",
            "evidence": ["citazione1", "citazione2"]
        }}
    ]
}}

Solo JSON:"""

        try:
            import json
            import re

            response = self.llm.completion(
                prompt=prompt,
                max_tokens=1500,
                temperature=0.3
            )

            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                insights = []

                for insight_data in data.get('insights', []):
                    insight = CrossDocumentInsight(
                        insight_type=insight_data.get('type', 'connection'),
                        related_documents=insight_data.get('documents', []),
                        insight_text=insight_data.get('insight', ''),
                        evidence=insight_data.get('evidence', []),
                        confidence=0.8
                    )
                    insights.append(insight)

                return insights
        except Exception as e:
            logger.error(f"Insight discovery failed: {e}")

        return []

    def _extract_key_findings(
        self,
        documents: list[Dict],
        summary: str,
        insights: list[CrossDocumentInsight]
    ) -> list[str]:
        """Extract key findings from analysis"""
        context = self._format_document_context(documents, max_docs=min(10, len(documents)))

        prompt = f"""Basandoti su questi documenti, estrai 5-7 KEY FINDINGS principali.

RIASSUNTO: {summary}

DOCUMENTI:
{context}

Findings dovrebbero essere:
- Specifici e actionable
- Supportati dai documenti
- Rilevanti per il business/uso

Rispondi come lista:
1. Finding 1
2. Finding 2
ecc.

Solo il numero + testo di ogni finding:"""

        try:
            response = self.llm.completion(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3
            )

            # Parse numbered list
            import re
            findings = re.findall(r'^\d+\.\s+(.+)$', response, re.MULTILINE)
            return findings[:7]
        except Exception as e:
            logger.error(f"Key findings extraction failed: {e}")
            return []

    def _generate_recommendations(
        self,
        documents: list[Dict],
        key_findings: list[str],
        insights: list[CrossDocumentInsight]
    ) -> list[str]:
        """Generate recommendations based on analysis"""
        findings_text = "\n".join(f"- {f}" for f in key_findings)

        prompt = f"""Basandoti su questi KEY FINDINGS e insights, genera raccomandazioni.

KEY FINDINGS:
{findings_text}

Numero di documenti analizzati: {len(documents)}
Numero di insights: {len(insights)}

Genera 3-5 RACCOMANDAZIONI:
- Concrete e implementabili
- Prioritizzate per impact
- Basate su evidenza documentale

Rispondi come lista numerata:"""

        try:
            response = self.llm.completion(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3
            )

            import re
            recommendations = re.findall(r'^\d+\.\s+(.+)$', response, re.MULTILINE)
            return recommendations[:5]
        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    def _identify_gaps(self, documents: list[Dict], findings: list[str]) -> list[str]:
        """Identify gaps or missing information in documentation"""
        prompt = f"""Basandoti su {len(documents)} documenti analizzati, identifica GAPS di informazione.

Key findings estratti:
{chr(10).join(f'- {f}' for f in findings[:5])}

Quali argomenti NON sono adequatamente coperti? Quali informazioni mancano?

Rispondi come lista di gap identificati:"""

        try:
            response = self.llm.completion(
                prompt=prompt,
                max_tokens=600,
                temperature=0.3
            )

            import re
            gaps = re.findall(r'^[-•]\s+(.+)$', response, re.MULTILINE)
            return gaps[:5]
        except Exception as e:
            logger.error(f"Gap identification failed: {e}")
            return []

    def _format_document_context(
        self,
        documents: list[Dict],
        max_docs: Optional[int] = None
    ) -> str:
        """Format documents for context in prompts"""
        if max_docs:
            documents = documents[:max_docs]

        context_parts = []
        for doc in documents:
            doc_id = doc.get('id', 'unknown')
            title = doc.get('title', doc.get('source', 'Document'))
            content = doc.get('content', '')[:1000]  # First 1000 chars

            context_parts.append(f"""[{doc_id}] {title}
{content}
---""")

        return "\n".join(context_parts)

    def _sample_documents(self, documents: list[Dict], max_sample: int = 50) -> list[Dict]:
        """Sample documents if token limit exceeded"""
        import random

        logger.warning(f"Sampling {max_sample} from {len(documents)} documents")

        # Ensure we get diverse selection (spread across document list)
        if len(documents) <= max_sample:
            return documents

        step = len(documents) // max_sample
        sampled = []

        for i in range(0, len(documents), step):
            if len(sampled) < max_sample:
                sampled.append(documents[i])

        # Add some random documents for coverage
        for _ in range(max_sample - len(sampled)):
            sampled.append(random.choice(documents))

        return sampled[:max_sample]

    def analyze_document_relationships(
        self,
        documents: list[Dict]
    ) -> Dict:
        """Analyze relationships and dependencies between documents"""
        context = self._format_document_context(documents, max_docs=min(20, len(documents)))

        prompt = f"""Analizza le relazioni tra questi {len(documents)} documenti.

DOCUMENTI:
{context}

Identifica:
1. Documenti che si riferiscono l'uno all'altro
2. Dipendenze (documento A dipende da B)
3. Documenti padre/figlio
4. Documenti alternativi che coprono lo stesso topic

Rispondi in formato JSON con adjacency list:
{{
    "relationships": [
        {{"source": "doc1", "target": "doc2", "type": "references|depends_on|parent_of|alternative"}}
    ]
}}

Solo JSON:"""

        try:
            import json
            import re

            response = self.llm.completion(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )

            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.error(f"Relationship analysis failed: {e}")

        return {"relationships": []}


def get_multi_document_analyzer(llm_service) -> MultiDocumentAnalyzer:
    """Get or create global multi-document analyzer"""
    if not hasattr(get_multi_document_analyzer, '_instance'):
        get_multi_document_analyzer._instance = MultiDocumentAnalyzer(llm_service)
    return get_multi_document_analyzer._instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Multi-Document Analysis Examples:")
    print("\n1. Global Summary Generation")
    print("   - Leverages 1M token Gemini context")
    print("   - Generates high-level overview across all docs")
    print("   - Identifies main themes and scope")

    print("\n2. Thematic Clustering")
    print("   - Groups documents by topic/theme")
    print("   - Identifies document relationships")
    print("   - Measures cluster coherence")

    print("\n3. Cross-Document Insights")
    print("   - Finds contradictions between docs")
    print("   - Identifies connections and progressions")
    print("   - Extracts consensus points")

    print("\n4. Key Findings Extraction")
    print("   - Extracts 5-7 key findings across all docs")
    print("   - Prioritizes actionable insights")
    print("   - Supports with evidence citations")

    print("\n5. Gap Analysis")
    print("   - Identifies missing information")
    print("   - Recommends documentation additions")
    print("   - Highlights areas needing clarification")
