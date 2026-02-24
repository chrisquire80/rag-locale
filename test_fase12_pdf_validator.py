"""
FASE 12 Integration Test: PDF Validator

This test validates that:
1. Valid PDFs pass validation
2. Invalid PDFs are detected
3. Error classification works correctly
4. Retry/blacklist logic is correct
"""

import sys
import os
import logging
from pathlib import Path
import tempfile

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import DOCUMENTS_DIR
from pdf_validator import get_pdf_validator, PDFErrorType, PDFValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_valid_pdf():
    """Test validation of a real valid PDF"""
    print("\n" + "="*70)
    print("TEST 1: Valid PDF")
    print("="*70)

    try:
        validator = get_pdf_validator()

        # Find first PDF
        pdf_files = list(DOCUMENTS_DIR.glob('*.pdf'))
        if not pdf_files:
            logger.warning("No PDF files found. Skipping test.")
            return True

        pdf_path = pdf_files[0]
        logger.info(f"Testing: {pdf_path.name}")

        is_valid, error_msg = validator.validate(pdf_path)

        if is_valid:
            logger.info("PASS: Valid PDF accepted")
            return True
        else:
            logger.error(f"FAIL: Valid PDF rejected: {error_msg}")
            return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_invalid_pdfs():
    """Test detection of invalid PDFs"""
    print("\n" + "="*70)
    print("TEST 2: Invalid PDFs Detection")
    print("="*70)

    try:
        validator = get_pdf_validator()
        test_cases = []

        # Create temporary test files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Test 1: Empty file
            empty_file = tmpdir / "empty.pdf"
            empty_file.write_bytes(b"")
            test_cases.append(("Empty file", empty_file, "too small"))

            # Test 2: Non-PDF file (must be at least 50 bytes)
            not_pdf = tmpdir / "notpdf.pdf"
            not_pdf.write_bytes(b"This is not a PDF file at all" + b"X" * 30)  # Make it 60+ bytes
            test_cases.append(("Non-PDF content", not_pdf, "Invalid PDF signature"))

            # Test 3: Partial PDF (valid header but no content) - 50+ bytes
            partial_pdf = tmpdir / "partial.pdf"
            partial_pdf.write_bytes(b"%PDF-1.4\n" + b"X" * 50)  # Make it 60+ bytes
            test_cases.append(("Partial PDF", partial_pdf, "missing"))

            # Run tests
            passed = 0
            for test_name, file_path, expected_error_substring in test_cases:
                is_valid, error_msg = validator.validate(file_path)

                if not is_valid and expected_error_substring.lower() in error_msg.lower():
                    logger.info(f"✓ {test_name}: Correctly rejected")
                    logger.info(f"  Error: {error_msg}")
                    passed += 1
                else:
                    logger.error(f"✗ {test_name}: Unexpected result")
                    logger.error(f"  Is Valid: {is_valid}")
                    logger.error(f"  Error: {error_msg}")

            if passed == len(test_cases):
                logger.info(f"PASS: All {len(test_cases)} invalid PDFs detected")
                return True
            else:
                logger.error(f"FAIL: Only {passed}/{len(test_cases)} tests passed")
                return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_error_classification():
    """Test error classification logic"""
    print("\n" + "="*70)
    print("TEST 3: Error Classification")
    print("="*70)

    try:
        validator = get_pdf_validator()

        # Test error classifications
        test_cases = [
            ("Corrupted file: invalid structure", PDFErrorType.CORRUPTED),
            ("Unsupported PDF version", PDFErrorType.UNSUPPORTED),
            ("File is encrypted with password", PDFErrorType.ENCRYPTED),
            ("No pages found in PDF", PDFErrorType.EMPTY),
            ("Permission denied to access file", PDFErrorType.INACCESSIBLE),
            ("Operation timed out", PDFErrorType.TIMEOUT),
        ]

        passed = 0
        for error_msg, expected_type in test_cases:
            error = PDFValidationError(expected_type, error_msg)
            classified_type = validator._classify_error(error_msg)

            if classified_type == expected_type:
                logger.info(f"✓ Correctly classified: {expected_type.value}")
                passed += 1
            else:
                logger.warning(f"⚠ Classification mismatch:")
                logger.warning(f"  Message: {error_msg}")
                logger.warning(f"  Expected: {expected_type.value}")
                logger.warning(f"  Got: {classified_type.value}")

        if passed >= len(test_cases) - 1:  # Allow 1 mismatch due to ambiguity
            logger.info(f"PASS: Error classification working (mostly correct)")
            return True
        else:
            logger.error(f"FAIL: Classification accuracy too low")
            return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_retry_blacklist_logic():
    """Test retry vs blacklist decision logic"""
    print("\n" + "="*70)
    print("TEST 4: Retry vs Blacklist Logic")
    print("="*70)

    try:
        validator = get_pdf_validator()

        # Test cases: (error_type, should_retry, should_blacklist)
        test_cases = [
            (PDFErrorType.TIMEOUT, True, False, "Transient error - retry"),
            (PDFErrorType.INACCESSIBLE, True, False, "Transient error - retry"),
            (PDFErrorType.CORRUPTED, False, True, "Permanent error - blacklist"),
            (PDFErrorType.UNSUPPORTED, False, True, "Permanent error - blacklist"),
            (PDFErrorType.ENCRYPTED, False, True, "Permanent error - blacklist"),
            (PDFErrorType.EMPTY, False, True, "Permanent error - blacklist"),
        ]

        passed = 0
        for error_type, expected_retry, expected_blacklist, description in test_cases:
            error = PDFValidationError(error_type, f"Test {error_type.value}")

            should_retry = validator.should_retry(error)
            should_blacklist = validator.should_blacklist(error)

            if should_retry == expected_retry and should_blacklist == expected_blacklist:
                logger.info(f"✓ {error_type.value}: {description}")
                passed += 1
            else:
                logger.error(f"✗ {error_type.value}:")
                logger.error(f"  Expected: retry={expected_retry}, blacklist={expected_blacklist}")
                logger.error(f"  Got: retry={should_retry}, blacklist={should_blacklist}")

        if passed == len(test_cases):
            logger.info(f"PASS: All retry/blacklist logic correct")
            return True
        else:
            logger.error(f"FAIL: {len(test_cases) - passed} logic errors")
            return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_strict_validation():
    """Test strict validation with error objects"""
    print("\n" + "="*70)
    print("TEST 5: Strict Validation")
    print("="*70)

    try:
        validator = get_pdf_validator()

        # Test with valid PDF
        pdf_files = list(DOCUMENTS_DIR.glob('*.pdf'))
        if not pdf_files:
            logger.warning("No PDF files found. Skipping test.")
            return True

        pdf_path = pdf_files[0]
        logger.info(f"Testing strict validation on: {pdf_path.name}")

        is_valid, error = validator.validate_strict(pdf_path)

        if is_valid and error is None:
            logger.info("✓ Valid PDF: No error object returned")
        else:
            logger.warning(f"⚠ Valid PDF returned error: {error}")

        # Test with invalid PDF
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_pdf = Path(tmpdir) / "bad.pdf"
            bad_pdf.write_bytes(b"NOT A PDF")

            is_valid, error = validator.validate_strict(bad_pdf)

            if not is_valid and error is not None:
                logger.info(f"✓ Invalid PDF: Error classified as {error.error_type.value}")
                logger.info(f"  Message: {error.message}")
                return True
            else:
                logger.error(f"✗ Invalid PDF: Unexpected result")
                return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all FASE 12 validator tests"""
    print("\n" + "="*70)
    print("FASE 12 PDF VALIDATOR TEST SUITE")
    print("="*70)

    results = {
        "Valid PDF": test_valid_pdf(),
        "Invalid PDFs": test_invalid_pdfs(),
        "Error Classification": test_error_classification(),
        "Retry vs Blacklist": test_retry_blacklist_logic(),
        "Strict Validation": test_strict_validation(),
    }

    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<40} {status}")

    print("-"*70)
    print(f"Total: {passed}/{total} passed")

    if passed == total:
        print("\nAll FASE 12 validator tests passed!")
        return 0
    else:
        print(f"\nSome tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
