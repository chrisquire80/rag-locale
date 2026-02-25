"""
PDF Image Extraction - FASE 17 Multimodal RAG
Extracts images from PDF documents and manages image metadata
"""

import tempfile
from pathlib import Path
import json
from src.logging_config import get_logger
from typing import Optional, Dict
from dataclasses import dataclass, asdict
from datetime import datetime

try:
    from PIL import Image
    import io
except ImportError:
    raise ImportError("PIL not found. Install with: pip install pillow")

try:
    from pypdf import PdfReader
except ImportError:
    raise ImportError("pypdf not found. Install with: pip install pypdf")

try:
    from pdf2image import convert_from_path
except ImportError:
    raise ImportError("pdf2image not found. Install with: pip install pdf2image")

logger = get_logger(__name__)

@dataclass
class ExtractedImage:
    """Represents an extracted image from PDF"""
    image_id: str
    page_number: int
    source_pdf: str
    extraction_date: str
    image_path: Optional[str] = None
    image_format: str = "RGB"
    width: Optional[int] = None
    height: Optional[int] = None
    file_size_bytes: Optional[int] = None
    extraction_method: str = "pypdf"  # or "pdf2image"
    analysis_text: Optional[str] = None
    analysis_embeddings: Optional[list[float]] = None
    relevance_score: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> "ExtractedImage":
        """Create from dictionary"""
        return ExtractedImage(**data)

class PDFImageExtractor:
    """Extract images from PDF documents with robust error handling"""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize PDF image extractor

        Args:
            output_dir: Directory to save extracted images (default: temp)
        """
        self.output_dir = output_dir or Path(tempfile.gettempdir()) / "pdf_images"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.image_counter = 0
        logger.info(f"PDFImageExtractor initialized, output_dir: {self.output_dir}")

    def extract_images_from_pdf(
        self,
        pdf_path: str,
        convert_to_images: bool = True
    ) -> tuple[list[ExtractedImage], dict[str, any]]:
        """
        Extract images from PDF using multiple strategies

        Args:
            pdf_path: Path to PDF file
            convert_to_images: If pypdf fails, use pdf2image to convert pages to images

        Returns:
            Tuple of (list of ExtractedImage, metadata dict)
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        extracted_images = []
        metadata = {
            "source_pdf": str(pdf_path),
            "total_pages": 0,
            "images_extracted": 0,
            "extraction_methods": [],
            "errors": [],
            "extraction_timestamp": datetime.now().isoformat()
        }

        try:
            # Method 1: Extract images directly from PDF using pypdf
            logger.info(f"Extracting images from {pdf_path.name} using pypdf...")
            extracted_images, stats = self._extract_with_pypdf(pdf_path)
            metadata["images_extracted"] += len(extracted_images)
            metadata["extraction_methods"].append("pypdf")
            metadata["total_pages"] = stats.get("total_pages", 0)

            # Method 2: If pypdf found few images, fallback to converting pages
            if convert_to_images and len(extracted_images) < 1:
                logger.info("Few images found with pypdf, trying pdf2image page conversion...")
                page_images, page_stats = self._extract_with_pdf2image(pdf_path)
                extracted_images.extend(page_images)
                metadata["images_extracted"] += len(page_images)
                metadata["extraction_methods"].append("pdf2image")
                metadata["total_pages"] = page_stats.get("total_pages", 0)

            logger.info(
                f"✓ Extraction complete: {len(extracted_images)} images from {metadata['total_pages']} pages"
            )

        except Exception as e:
            error_msg = f"Error extracting images: {str(e)}"
            logger.error(error_msg)
            metadata["errors"].append(error_msg)

        return extracted_images, metadata

    def _extract_with_pypdf(self, pdf_path: Path) -> tuple[list[ExtractedImage], Dict]:
        """Extract images directly from PDF using pypdf"""
        extracted_images = []
        stats = {"total_pages": 0, "images_found": 0}

        try:
            reader = PdfReader(str(pdf_path))
            stats["total_pages"] = len(reader.pages)

            for page_num, page in enumerate(reader.pages, 1):
                try:
                    if "/XObject" in page["/Resources"]:
                        xobject = page["/Resources"]["/XObject"].get_object()
                        for obj_name in xobject:
                            try:
                                obj = xobject[obj_name].get_object()
                                if obj["/Subtype"] == "/Image":
                                    image = self._extract_image_object(
                                        obj, page_num, pdf_path
                                    )
                                    if image:
                                        extracted_images.append(image)
                                        stats["images_found"] += 1
                            except Exception as e:
                                logger.debug(
                                    f"Could not extract image object from page {page_num}: {e}"
                                )
                except Exception as e:
                    logger.debug(f"Error processing page {page_num}: {e}")

        except Exception as e:
            logger.warning(f"pypdf extraction error: {e}")

        return extracted_images, stats

    def _extract_image_object(
        self,
        obj: any,
        page_num: int,
        pdf_path: Path
    ) -> Optional[ExtractedImage]:
        """Extract single image object from PDF"""
        try:
            if obj["/Subtype"] != "/Image":
                return None

            # Get image data
            data = obj.get_data()
            if not data:
                return None

            # Try to determine format
            filters = obj.get("/Filter", [])
            if isinstance(filters, list):
                filter_type = filters[0] if filters else None
            else:
                filter_type = filters

            # Create PIL Image
            try:
                if filter_type == "/DCTDecode":
                    # JPEG image
                    image = Image.open(io.BytesIO(data))
                    image_format = "JPEG"
                elif filter_type == "/FlateDecode":
                    # Flate-encoded image
                    width = int(obj["/Width"])
                    height = int(obj["/Height"])
                    colorspace = obj.get("/ColorSpace", "/DeviceRGB")

                    if colorspace == "/DeviceRGB":
                        image = Image.frombytes(
                            "RGB", (width, height), data, "raw"
                        )
                        image_format = "RGB"
                    else:
                        # Fallback
                        logger.debug(
                            f"Unsupported colorspace {colorspace} on page {page_num}"
                        )
                        return None
                else:
                    # Try generic approach
                    image = Image.open(io.BytesIO(data))
                    image_format = image.format or "Unknown"
            except Exception as e:
                logger.debug(f"Could not create PIL Image on page {page_num}: {e}")
                return None

            # Save image
            image_id = f"img_{page_num}_{self.image_counter}"
            self.image_counter += 1
            image_path = self.output_dir / f"{image_id}.png"

            # Convert to RGB if needed
            if image.mode != "RGB":
                image = image.convert("RGB")

            image.save(str(image_path), "PNG")

            # Get file size
            file_size = image_path.stat().st_size if image_path.exists() else 0

            return ExtractedImage(
                image_id=image_id,
                page_number=page_num,
                source_pdf=pdf_path.name,
                extraction_date=datetime.now().isoformat(),
                image_path=str(image_path),
                image_format=image_format,
                width=image.width,
                height=image.height,
                file_size_bytes=file_size,
                extraction_method="pypdf"
            )

        except Exception as e:
            logger.debug(f"Error extracting image object: {e}")
            return None

    def _extract_with_pdf2image(self, pdf_path: Path) -> tuple[list[ExtractedImage], Dict]:
        """Convert PDF pages to images using pdf2image"""
        extracted_images = []
        stats = {"total_pages": 0, "pages_converted": 0}

        try:
            # Convert first 50 pages (for large documents)
            max_pages = 50
            images = convert_from_path(
                str(pdf_path),
                first_page=1,
                last_page=max_pages,
                dpi=150
            )

            stats["total_pages"] = len(images)

            for page_num, image in enumerate(images, 1):
                try:
                    image_id = f"page_{page_num}_{self.image_counter}"
                    self.image_counter += 1
                    image_path = self.output_dir / f"{image_id}.png"

                    # Save converted image
                    image.save(str(image_path), "PNG")

                    # Get file size
                    file_size = image_path.stat().st_size if image_path.exists() else 0

                    extracted_images.append(
                        ExtractedImage(
                            image_id=image_id,
                            page_number=page_num,
                            source_pdf=pdf_path.name,
                            extraction_date=datetime.now().isoformat(),
                            image_path=str(image_path),
                            image_format="RGB",
                            width=image.width,
                            height=image.height,
                            file_size_bytes=file_size,
                            extraction_method="pdf2image"
                        )
                    )
                    stats["pages_converted"] += 1

                except Exception as e:
                    logger.warning(f"Error converting page {page_num}: {e}")

        except Exception as e:
            logger.warning(f"pdf2image conversion failed: {e}")

        return extracted_images, stats

    def get_image_text_with_ocr(self, image_path: str) -> str:
        """
        Extract text from image using OCR (placeholder for Gemini integration)
        This will be called by VisionService

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        # This is a placeholder - actual OCR will be done via Gemini Vision
        # In VisionService.extract_image_text()
        logger.debug(f"OCR requested for: {image_path}")
        return ""

    def save_extracted_images(
        self,
        images: list[ExtractedImage],
        output_dir: Optional[Path] = None
    ) -> Dict:
        """
        Save image metadata to JSON

        Args:
            images: List of extracted images
            output_dir: Output directory (default: self.output_dir)

        Returns:
            Metadata about saved files
        """
        output_dir = output_dir or self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = output_dir / "image_metadata.json"
        images_data = [img.to_dict() for img in images]

        try:
            with open(metadata_file, "w") as f:
                json.dump(images_data, f, indent=2)

            logger.info(f"✓ Saved metadata for {len(images)} images to {metadata_file}")

            return {
                "metadata_file": str(metadata_file),
                "images_count": len(images),
                "total_size_bytes": sum(
                    img.file_size_bytes or 0 for img in images
                )
            }

        except Exception as e:
            logger.error(f"Error saving image metadata: {e}")
            raise

    def load_image_metadata(self, metadata_file: Path) -> list[ExtractedImage]:
        """
        Load image metadata from JSON

        Args:
            metadata_file: Path to metadata JSON file

        Returns:
            List of ExtractedImage objects
        """
        try:
            with open(metadata_file, "r") as f:
                data = json.load(f)

            images = [ExtractedImage.from_dict(item) for item in data]
            logger.info(f"✓ Loaded metadata for {len(images)} images")
            return images

        except Exception as e:
            logger.error(f"Error loading image metadata: {e}")
            raise

    def get_extraction_statistics(
        self,
        images: list[ExtractedImage]
    ) -> Dict:
        """Get statistics about extracted images"""
        if not images:
            return {
                "total_images": 0,
                "total_size_bytes": 0,
                "avg_image_size": 0,
                "extraction_methods": []
            }

        total_size = sum(img.file_size_bytes or 0 for img in images)
        methods = list(set(img.extraction_method for img in images))

        return {
            "total_images": len(images),
            "total_size_bytes": total_size,
            "avg_image_size": total_size // len(images),
            "extraction_methods": methods,
            "min_dimensions": (
                min(img.width or 0 for img in images),
                min(img.height or 0 for img in images)
            ),
            "max_dimensions": (
                max(img.width or 0 for img in images),
                max(img.height or 0 for img in images)
            ),
            "pages_with_images": len(set(img.page_number for img in images))
        }

def get_pdf_image_extractor(output_dir: Optional[Path] = None) -> PDFImageExtractor:
    """Get or create PDF image extractor singleton"""
    if not hasattr(get_pdf_image_extractor, "_instance"):
        get_pdf_image_extractor._instance = PDFImageExtractor(output_dir)
    return get_pdf_image_extractor._instance

if __name__ == "__main__":

    # Test extraction
    extractor = PDFImageExtractor()
    # Add test code here
