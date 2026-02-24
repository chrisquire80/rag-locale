import fitz  # PyMuPDF
import google.genai as genai
from PIL import Image
import io
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.config import config
from src.vision_service import get_vision_service

logger = logging.getLogger(__name__)

# Directory for saving cropped images
CROP_OUTPUT_DIR = Path("static/crops")
CROP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class MultimodalIngestion:
    """Handles PDF to Image conversion and Visual Element Extraction"""

    def __init__(self):
        self.vision_service = get_vision_service()

    def process_pdf_visuals(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Process a PDF to extract visual elements (charts, tables).
        
        Returns:
            List of dictionaries containing visual metadata and crop paths.
        """
        if not pdf_path.exists():
            logger.error(f"File not found: {pdf_path}")
            return []

        visual_elements = []
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Processing visuals for {pdf_path.name} ({len(doc)} pages)")

            for page_num in range(len(doc)):
                # 1. Render page to image (high resolution)
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))

                # 2. Detect objects using Gemini (via Vision Service)
                detections = self.detect_visual_elements(img)

                # 3. Crop and Save
                width, height = img.size
                for i, det in enumerate(detections):
                    try:
                        ymin, xmin, ymax, xmax = det['box_2d']
                        label = det.get('label', 'visual_element')
                        
                        # Convert normalized coordinates (0-1000) to pixels
                        left = xmin * width / 1000
                        top = ymin * height / 1000
                        right = xmax * width / 1000
                        bottom = ymax * height / 1000

                        # Crop
                        crop = img.crop((left, top, right, bottom))
                        
                        # Save
                        safe_filename = f"{pdf_path.stem}_p{page_num+1}_{i}.png"
                        crop_path = CROP_OUTPUT_DIR / safe_filename
                        crop.save(crop_path)

                        # Analyze the crop specifically to get a description
                        description = self.vision_service.analyze_image(str(crop_path))

                        visual_elements.append({
                            "source": pdf_path.name,
                            "page": page_num + 1,
                            "type": label,
                            "image_path": str(crop_path),
                            "description": description,
                            "text": f"Elemento Visivo ({label}): {description}" # For vector store text
                        })
                        logger.info(f"  ✓ Extracted {label} from page {page_num+1}")

                    except Exception as e:
                        logger.warning(f"Failed to crop/process element on page {page_num+1}: {e}")

            doc.close()
            return visual_elements

        except Exception as e:
            logger.error(f"Visual processing failed for {pdf_path}: {e}")
            return []

    def detect_visual_elements(self, image: Image.Image) -> List[Dict]:
        """
        Detects tables, charts, and diagrams in an image using Gemini.
        Returns a list of bounding boxes.
        """
        # Convert PIL Image back to bytes for API
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        prompt = """
        Trova tutti i GRAFICI, le TABELLE e i DIAGRAMMI in questa pagina.
        Ignora intestazioni, piè di pagina e testo normale.
        
        Per ogni elemento trovato, restituisci un oggetto JSON con:
        - "label": "grafico" | "tabella" | "diagramma"
        - "box_2d": [ymin, xmin, ymax, xmax] (coordinate normalizzate 0-1000)
        
        Rispondi ESCLUSIVAMENTE con una lista JSON valida, senza markdown o testo aggiuntivo.
        Esempio: [{"label": "grafico", "box_2d": [100, 100, 500, 500]}]
        Se non trovi nulla, rispondi con una lista vuota: []
        """

        try:
            # We use the client directly to avoid re-initializing or complex dependency loops,
            # but ideally we should expose a method in VisionService.
            # For now, let's use the VisionService instance's client if possible, or create a temporary one.
            # Better approach: Add a method to VisionService.
            # Since we haven't updated VisionService yet, we will mock this call or implement it 
            # by calling the VisionService generatively if we update it first.
            
            # PLAN ADJUSTMENT: We will assume VisionService has a method `generate_content` we can use, 
            # or we instantiate a client here as a fallback. 
            # Re-using logic from VisionService is cleaner.
            
            response_text = self.vision_service.detect_objects_in_image(img_bytes, prompt)
            
            # Parse JSON
            import json
            clean_json = response_text.replace("```json", "").replace("```", "").strip()
            if not clean_json:
                return []
            
            return json.loads(clean_json)

        except Exception as e:
            logger.warning(f"Object detection failed: {e}")
            return []
