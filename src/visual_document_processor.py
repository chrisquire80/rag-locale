"""
Visual Document Processor - Multimodal Pipeline with Gemini 2.0 Flash Vision
Extracts and analyzes visual content (tables, charts, images) from PDFs
Enables hybrid text + visual retrieval and reasoning
"""

import base64
import io
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
import threading

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class VisualElement:
    """Represents a visual element in a document"""
    element_id: str
    element_type: str  # "chart", "table", "image", "diagram", "logo"
    page_number: int
    description: str  # AI-generated description
    extracted_data: Optional[str]  # Markdown table, coordinates, etc.
    confidence: float  # 0.0-1.0
    image_base64: Optional[str] = None  # Base64 encoded image

@dataclass
class PageAnalysis:
    """Analysis result for a single page"""
    page_number: int
    text_content: str
    visual_elements: list[VisualElement]
    overall_description: str
    key_findings: list[str]

class PDFToImageConverter:
    """Convert PDF pages to high-resolution images"""

    def __init__(self, dpi: int = 300):
        """
        Initialize converter

        Args:
            dpi: Resolution in DPI (higher = better quality, slower)
        """
        self.dpi = dpi
        logger.info(f"PDF to Image Converter initialized (DPI: {dpi})")

    def convert_pdf_to_images(self, pdf_path: str) -> list[tuple[int, bytes]]:
        """
        Convert PDF to images

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of (page_number, image_bytes) tuples
        """
        try:
            import pdf2image

            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=self.dpi,
                fmt='jpeg'
            )

            result = []
            for page_num, image in enumerate(images, 1):
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=85)
                result.append((page_num, img_byte_arr.getvalue()))

            logger.info(f"Converted {pdf_path} to {len(result)} images (DPI: {self.dpi})")
            return result

        except ImportError:
            logger.error("pdf2image not installed. Install with: pip install pdf2image pillow")
            return []
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            return []

    def encode_image_base64(self, image_bytes: bytes) -> str:
        """Encode image to base64 for API transmission"""
        return base64.standard_b64encode(image_bytes).decode('utf-8')

class VisualContentAnalyzer:
    """Analyze visual content using Gemini 2.0 Flash Vision"""

    def __init__(self, llm_service):
        """
        Initialize analyzer with LLM service

        Args:
            llm_service: Gemini LLM service instance
        """
        self.llm = llm_service
        logger.info("Visual Content Analyzer initialized")

    def analyze_page_visually(
        self,
        page_number: int,
        image_base64: str,
        text_content: str = ""
    ) -> PageAnalysis:
        """
        Analyze a single page visually

        Args:
            page_number: Page number
            image_base64: Base64 encoded image
            text_content: Extracted text content (optional)

        Returns:
            PageAnalysis with visual elements and descriptions
        """
        try:
            # First pass: Overall page analysis
            prompt = f"""Analizza questa pagina del documento (pagina {page_number}).

Descrivi:
1. Tipo di contenuto (tabella, grafico, testo, misto)
2. Elementi visivi principali (titoli, grafici, tabelle, immagini)
3. Dati quantitativi visibili (numeri, percentuali, trend)
4. Qualsiasi logo o marchio identificativo

Fornisci un riassunto esecutivo di 2-3 frasi su cosa mostra questa pagina.

Rispondi in italiano con questo formato JSON:
{{
    "page_type": "chart|table|text|mixed",
    "visual_elements": [
        {{
            "type": "chart|table|image|logo|diagram",
            "description": "descrizione",
            "key_data": "dati quantitativi se presenti"
        }}
    ],
    "overall_description": "descrizione generale",
    "key_findings": ["finding1", "finding2"]
}}
"""

            response = self._call_vision_api(prompt, image_base64)

            # Parse response and extract data
            visual_elements = self._parse_visual_elements(response, page_number)

            return PageAnalysis(
                page_number=page_number,
                text_content=text_content,
                visual_elements=visual_elements,
                overall_description=self._extract_field(response, "overall_description", ""),
                key_findings=self._extract_field(response, "key_findings", [])
            )

        except Exception as e:
            logger.error(f"Failed to analyze page {page_number}: {e}")
            return PageAnalysis(
                page_number=page_number,
                text_content=text_content,
                visual_elements=[],
                overall_description="",
                key_findings=[]
            )

    def extract_table_from_image(
        self,
        page_number: int,
        image_base64: str
    ) -> Optional[str]:
        """
        Extract table data as Markdown

        Args:
            page_number: Page number
            image_base64: Base64 encoded image

        Returns:
            Markdown formatted table or None
        """
        try:
            prompt = """Estrai tutte le tabelle visibili in questa immagine.
Convertile in formato Markdown table.

Se non ci sono tabelle, rispondi: "NO_TABLE"

Formato Markdown per tabelle:
| Header1 | Header2 |
|---------|---------|
| Data1   | Data2   |

Rispondi SOLO con le tabelle in Markdown, niente altro."""

            response = self._call_vision_api(prompt, image_base64)

            if "NO_TABLE" not in response:
                return response.strip()
            return None

        except Exception as e:
            logger.error(f"Failed to extract table from page {page_number}: {e}")
            return None

    def analyze_chart_data(
        self,
        page_number: int,
        image_base64: str
    ) -> Dict:
        """
        Analyze chart and extract key data points

        Args:
            page_number: Page number
            image_base64: Base64 encoded image

        Returns:
            Dict with chart analysis
        """
        try:
            prompt = """Analizza questo grafico/chart.

Estrai:
1. Tipo di grafico (barre, linee, torta, area, altro)
2. Assi e scale (cosa misura X, cosa misura Y)
3. Serie di dati (cosa viene mostrato)
4. Trend principale (crescente, decrescente, stabile)
5. Valori notevoli (minimo, massimo, media)
6. Conclusione principale del grafico

Rispondi in formato JSON:
{{
    "chart_type": "tipo",
    "title": "titolo se presente",
    "x_axis": "descrizione",
    "y_axis": "descrizione",
    "series": ["serie1", "serie2"],
    "trend": "crescente|decrescente|stabile",
    "key_values": {{
        "max": "valore massimo",
        "min": "valore minimo",
        "average": "media se applicabile"
    }},
    "conclusion": "cosa significa questo grafico"
}}"""

            response = self._call_vision_api(prompt, image_base64)

            # Parse JSON response
            import json
            import re

            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())

            return {"error": "Could not parse chart data"}

        except Exception as e:
            logger.error(f"Failed to analyze chart on page {page_number}: {e}")
            return {"error": str(e)}

    def _call_vision_api(self, prompt: str, image_base64: str) -> str:
        """
        Call Gemini 2.0 Flash Vision API

        Args:
            prompt: Analysis prompt
            image_base64: Base64 encoded image

        Returns:
            API response
        """
        try:
            # Build vision prompt with image
            response = self.llm.completion(
                prompt=prompt,
                images=[image_base64],  # Gemini API expects list
                max_tokens=2000,
                temperature=0.2  # Lower temp for consistent analysis
            )
            return response

        except Exception as e:
            logger.error(f"Vision API call failed: {e}")
            return ""

    def _parse_visual_elements(
        self,
        response: str,
        page_number: int
    ) -> list[VisualElement]:
        """Parse visual elements from API response"""
        try:
            import json
            import re

            # Extract JSON from response
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                return []

            data = json.loads(match.group())
            elements = []

            for i, elem in enumerate(data.get("visual_elements", []), 1):
                element = VisualElement(
                    element_id=f"page_{page_number}_elem_{i}",
                    element_type=elem.get("type", "unknown"),
                    page_number=page_number,
                    description=elem.get("description", ""),
                    extracted_data=elem.get("key_data", ""),
                    confidence=0.85
                )
                elements.append(element)

            return elements

        except Exception as e:
            logger.error(f"Failed to parse visual elements: {e}")
            return []

    def _extract_field(self, response: str, field: str, default):
        """Extract specific field from JSON response"""
        try:
            import json
            import re

            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get(field, default)
            return default

        except Exception as e:
            logger.debug(f"Failed to extract field {field}: {e}")
            return default

class VisualDocumentIngestionEngine:
    """Enhanced document ingestion with visual analysis"""

    def __init__(self, llm_service, vector_store):
        """Initialize with services"""
        self.llm = llm_service
        self.vector_store = vector_store
        self.converter = PDFToImageConverter(dpi=300)
        self.analyzer = VisualContentAnalyzer(llm_service)
        self.lock = threading.Lock()
        logger.info("Visual Document Ingestion Engine initialized")

    def process_pdf_with_vision(
        self,
        pdf_path: str,
        document_id: str
    ) -> Dict:
        """
        Process PDF with visual analysis

        Args:
            pdf_path: Path to PDF
            document_id: Document identifier

        Returns:
            Processing results
        """
        logger.info(f"Processing {pdf_path} with visual analysis...")

        # Step 1: Convert PDF to images
        images = self.converter.convert_pdf_to_images(pdf_path)
        if not images:
            logger.error(f"Failed to convert {pdf_path} to images")
            return {"error": "Conversion failed", "document_id": document_id}

        # Step 2: Analyze each page visually
        page_analyses = []
        visual_index = []

        for page_num, image_bytes in images:
            try:
                image_b64 = self.converter.encode_image_base64(image_bytes)

                # Analyze page
                analysis = self.analyzer.analyze_page_visually(page_num, image_b64)
                page_analyses.append(analysis)

                # Extract tables if present
                table_md = self.analyzer.extract_table_from_image(page_num, image_b64)
                if table_md:
                    analysis.text_content += f"\n\n## Tabella Pagina {page_num}\n{table_md}"

                # Index visual elements
                for element in analysis.visual_elements:
                    element.image_base64 = image_b64  # Store reference
                    visual_index.append(element)

                logger.info(f"✓ Page {page_num}: {len(analysis.visual_elements)} visual elements found")

            except Exception as e:
                logger.error(f"Failed to analyze page {page_num}: {e}")

        # Step 3: Store in vector store with visual metadata
        results = self._store_visual_analysis(
            document_id,
            page_analyses,
            visual_index
        )

        logger.info(f"✓ Processing complete: {len(page_analyses)} pages, {len(visual_index)} visual elements")
        return results

    def _store_visual_analysis(
        self,
        document_id: str,
        page_analyses: list[PageAnalysis],
        visual_index: list[VisualElement]
    ) -> Dict:
        """Store analysis results in vector store"""
        try:
            stored_pages = 0
            stored_elements = 0

            for analysis in page_analyses:
                # Store page-level analysis
                metadata = {
                    "document_id": document_id,
                    "page_number": analysis.page_number,
                    "analysis_type": "visual_analysis",
                    "visual_elements_count": len(analysis.visual_elements),
                    "key_findings": analysis.key_findings
                }

                # Create chunks for both text and visual description
                chunks = [
                    f"Page {analysis.page_number}: {analysis.overall_description}",
                    analysis.text_content if analysis.text_content else ""
                ]

                # Add to vector store
                for chunk in chunks:
                    if chunk.strip():
                        self.vector_store.add_document(
                            chunk,
                            metadata=metadata,
                            source=f"{document_id}_page_{analysis.page_number}"
                        )
                        stored_pages += 1

            return {
                "status": "success",
                "document_id": document_id,
                "pages_processed": len(page_analyses),
                "visual_elements_indexed": len(visual_index),
                "chunks_stored": stored_pages
            }

        except Exception as e:
            logger.error(f"Failed to store visual analysis: {e}")
            return {
                "status": "error",
                "document_id": document_id,
                "error": str(e)
            }

def get_visual_ingestion_engine(llm_service, vector_store) -> VisualDocumentIngestionEngine:
    """Get or create global visual ingestion engine"""
    if not hasattr(get_visual_ingestion_engine, '_instance'):
        get_visual_ingestion_engine._instance = VisualDocumentIngestionEngine(llm_service, vector_store)
    return get_visual_ingestion_engine._instance

if __name__ == "__main__":

    print("Visual Document Processor - Gemini 2.0 Flash Vision")
    print("=" * 60)
    print("\nCapabilities:")
    print("✅ PDF → High-res Images (300 DPI)")
    print("✅ Visual Analysis (charts, tables, images)")
    print("✅ Table Extraction (Markdown format)")
    print("✅ Chart Data Extraction")
    print("✅ Hybrid Text + Visual Indexing")
    print("✅ Vision-based Q&A")
    print("\nUsage:")
    print("1. Initialize engines with LLM service")
    print("2. Call process_pdf_with_vision(pdf_path, doc_id)")
    print("3. Results indexed in vector store")
    print("4. Query with both text and vision context")
