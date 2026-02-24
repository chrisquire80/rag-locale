
import sys
import gc
import json
from pathlib import Path

# Configure logging to stderr so it doesn't pollute stdout (if we used stdout for data)
from src.logging_config import get_logger

logger = get_logger(__name__)

try:
    import pypdf
except ImportError:
    pypdf = None

def extract_pdf_text(file_path: Path):
    if not pypdf:
        logger.error("pypdf not installed")
        sys.exit(1)

    result = {
        "text": "",
        "pages": []
    }

    try:
        reader = pypdf.PdfReader(str(file_path))
        num_pages = len(reader.pages)
        logger.info(f"Processing {file_path} ({num_pages} pages)")

        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                result["pages"].append({
                    "page_num": i + 1,
                    "text": page_text
                })

            # FIX FASE 5: Garbage collection dopo ogni page (memory leak fix)
            if (i + 1) % 10 == 0:
                gc.collect()
                logger.debug(f"GC: Memory cleanup dopo page {i+1}/{num_pages}")

        # Save result to a sidecar JSON file
        output_file = file_path.with_suffix(".json.temp")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)

        logger.info(f"Successfully extracted text to {output_file}")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Critical error processing PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pdf_worker.py <pdf_path>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"File not found: {input_file}")
        sys.exit(1)
        
    extract_pdf_text(input_file)
