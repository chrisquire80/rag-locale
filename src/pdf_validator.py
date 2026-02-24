"""
PDF Validation Module
Detects corrupted/malformed PDFs before processing
Classifies errors for appropriate handling (retry vs blacklist)
"""

from pathlib import Path
from typing import Optional
from enum import Enum

from src.logging_config import get_logger

logger = get_logger(__name__)

class PDFErrorType(Enum):
    """Classification of PDF errors"""
    CORRUPTED = "corrupted"  # Invalid PDF structure
    UNSUPPORTED = "unsupported"  # Unsupported PDF version/features
    ENCRYPTED = "encrypted"  # Password-protected
    EMPTY = "empty"  # No pages/content
    INACCESSIBLE = "inaccessible"  # Permission denied
    TIMEOUT = "timeout"  # Processing took too long
    UNKNOWN = "unknown"  # Unknown error

class PDFValidationError(Exception):
    """Base exception for PDF validation errors"""

    def __init__(self, error_type: PDFErrorType, message: str):
        self.error_type = error_type
        self.message = message
        super().__init__(f"[{error_type.value}] {message}")

class PDFValidator:
    """Validates PDF files before processing"""

    # PDF magic bytes (file signature)
    PDF_MAGIC_BYTES = b"%PDF"

    # Maximum reasonable PDF file size (500 MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024

    # Minimum PDF file size (must have at least header + eof)
    # Real PDFs typically 300+ bytes, but allow smaller for edge cases
    MIN_FILE_SIZE = 50

    def __init__(self):
        self.logger = logger

    def validate(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Validate a PDF file.

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if file passes validation
            - error_message: None if valid, error message if invalid
        """
        try:
            file_path = Path(file_path)

            # Check 1: File exists
            if not file_path.exists():
                return False, "File does not exist"

            # Check 2: Is a file (not directory)
            if not file_path.is_file():
                return False, "Path is not a file"

            # Check 3: Has .pdf extension
            if file_path.suffix.lower() != ".pdf":
                return False, f"Not a PDF file (extension: {file_path.suffix})"

            # Check 4: File size is reasonable
            file_size = file_path.stat().st_size

            if file_size < self.MIN_FILE_SIZE:
                return False, f"File too small ({file_size} bytes, min {self.MIN_FILE_SIZE})"

            if file_size > self.MAX_FILE_SIZE:
                return False, f"File too large ({file_size / (1024*1024):.1f} MB, max 500 MB)"

            # Check 5: Has valid PDF magic bytes
            try:
                with open(file_path, "rb") as f:
                    magic = f.read(4)
                    if magic != self.PDF_MAGIC_BYTES:
                        return False, f"Invalid PDF signature (got {magic[:4]}, expected %PDF)"
            except IOError as e:
                return False, f"Cannot read file: {e}"

            # Check 6: Has PDF trailer
            if not self._has_pdf_trailer(file_path):
                return False, "Invalid PDF structure (missing %%EOF trailer)"

            # Check 7: Try basic PDF parsing
            error_msg = self._check_pdf_structure(file_path)
            if error_msg:
                return False, error_msg

            self.logger.debug(f"PDF validation passed: {file_path.name}")
            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def validate_strict(self, file_path: Path) -> tuple[bool, Optional[PDFValidationError]]:
        """
        Strict validation with error classification.

        Returns:
            Tuple of (is_valid, error)
            - is_valid: True if valid, False otherwise
            - error: None if valid, PDFValidationError if invalid
        """
        try:
            is_valid, error_msg = self.validate(file_path)

            if is_valid:
                return True, None

            # Classify the error
            error_type = self._classify_error(str(error_msg))
            return False, PDFValidationError(error_type, error_msg)

        except Exception as e:
            error = PDFValidationError(PDFErrorType.UNKNOWN, str(e))
            return False, error

    def should_retry(self, error: PDFValidationError) -> bool:
        """
        Determine if error warrants a retry.

        Returns:
            True if should retry (transient error)
            False if should blacklist (permanent error)
        """
        # Retry on transient errors
        retryable = {
            PDFErrorType.TIMEOUT,  # Network or processing timeout
            PDFErrorType.INACCESSIBLE,  # Temporary file lock
        }
        return error.error_type in retryable

    def should_blacklist(self, error: PDFValidationError) -> bool:
        """
        Determine if error warrants permanent blacklisting.

        Returns:
            True if should blacklist permanently
        """
        # Blacklist permanent errors
        blacklistable = {
            PDFErrorType.CORRUPTED,  # Corrupted file
            PDFErrorType.UNSUPPORTED,  # Unsupported format
            PDFErrorType.ENCRYPTED,  # Can't decrypt
            PDFErrorType.EMPTY,  # No content
        }
        return error.error_type in blacklistable

    def _has_pdf_trailer(self, file_path: Path) -> bool:
        """Check if file has PDF trailer marker"""
        try:
            # PDF files must end with %%EOF (possibly with whitespace)
            with open(file_path, "rb") as f:
                # Read last 1KB to find %%EOF
                f.seek(max(0, f.seek(0, 2) - 1024))
                content = f.read()
                return b"%%EOF" in content
        except Exception:
            return False

    def _check_pdf_structure(self, file_path: Path) -> Optional[str]:
        """
        Basic PDF structure validation.
        Returns error message if invalid, None if valid.
        """
        try:
            with open(file_path, "rb") as f:
                content = f.read()

                # Check for xref table or stream
                if b"xref" not in content and b"stream" not in content:
                    return "Missing PDF content structure (no xref/stream)"

                # Check for basic PDF objects
                if b"obj" not in content:
                    return "Missing PDF objects (no 'obj' markers)"

                # Check for common corruption patterns
                if b"%%EOF" in content and content.count(b"%%EOF") > 2:
                    return "Multiple %%EOF markers (possible corruption)"

                return None

        except Exception as e:
            return f"Cannot validate structure: {e}"

    def _classify_error(self, error_msg: str) -> PDFErrorType:
        """Classify error type from error message"""
        error_lower = error_msg.lower()

        # Pattern matching for error classification
        if "corrupted" in error_lower or "invalid" in error_lower or "structure" in error_lower:
            return PDFErrorType.CORRUPTED
        elif "unsupported" in error_lower or "version" in error_lower or "format" in error_lower:
            return PDFErrorType.UNSUPPORTED
        elif "encrypted" in error_lower or "password" in error_lower:
            return PDFErrorType.ENCRYPTED
        elif "empty" in error_lower or "no content" in error_lower or "no pages" in error_lower:
            return PDFErrorType.EMPTY
        elif "permission" in error_lower or "access" in error_lower or "denied" in error_lower:
            return PDFErrorType.INACCESSIBLE
        elif "timeout" in error_lower or "timed out" in error_lower:
            return PDFErrorType.TIMEOUT
        else:
            return PDFErrorType.UNKNOWN

# Global validator instance
_validator = None

def get_pdf_validator() -> PDFValidator:
    """Get or create global PDF validator"""
    global _validator
    if _validator is None:
        _validator = PDFValidator()
    return _validator

if __name__ == "__main__":
    # Test the validator
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_validator.py <pdf_file>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    validator = get_pdf_validator()

    print(f"\nValidating: {pdf_path.name}")
    print("=" * 70)

    is_valid, error_msg = validator.validate(pdf_path)

    if is_valid:
        print("✓ PDF is VALID")
    else:
        print(f"✗ PDF is INVALID: {error_msg}")

        # Try strict validation to get error type
        is_valid, error = validator.validate_strict(pdf_path)
        if error:
            print(f"\nError Classification:")
            print(f"  Type: {error.error_type.value}")
            print(f"  Message: {error.message}")
            print(f"  Should Retry: {validator.should_retry(error)}")
            print(f"  Should Blacklist: {validator.should_blacklist(error)}")

    print("=" * 70)
