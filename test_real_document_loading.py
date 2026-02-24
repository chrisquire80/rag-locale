#!/usr/bin/env python3
"""
Test Script: Real Document Loading Configuration
Verifies that custom document folders can be loaded correctly
"""

import sys
import os
from pathlib import Path
from typing import Tuple, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from document_loader import DocumentLoaderManager


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title:^76}")
    print("="*80 + "\n")


def print_section(title: str):
    """Print section header"""
    print(f"\n--- {title} ---\n")


def test_default_folder():
    """Test loading from default 'documents' folder"""
    print_section("TEST 1: Default 'documents' Folder")

    try:
        manager = DocumentLoaderManager()
        docs = manager.load_all_sources("documents")

        if docs:
            print(f"[OK] Loaded {len(docs)} documents from default folder")
            summary = manager.get_document_summary()
            print(f"     Types: {', '.join(summary['types']) if summary['types'] else 'None'}")
            print(f"     Size: {summary['total_size_kb']:.1f} KB")
            return True, docs
        else:
            print("[WARNING] No documents found in 'documents' folder (expected for clean install)")
            return True, []

    except Exception as e:
        print(f"[ERROR] Failed to load from default folder: {e}")
        return False, []


def test_custom_folder(folder_path: str) -> Tuple[bool, List]:
    """Test loading from custom folder"""
    print_section(f"TEST 2: Custom Folder - {folder_path}")

    # Validate path exists
    if not Path(folder_path).exists():
        print(f"[ERROR] Path does not exist: {folder_path}")
        return False, []

    if not Path(folder_path).is_dir():
        print(f"[ERROR] Path is not a directory: {folder_path}")
        return False, []

    try:
        manager = DocumentLoaderManager()
        docs = manager.load_all_sources(folder_path)

        if docs:
            print(f"[OK] Loaded {len(docs)} documents from custom folder")
            summary = manager.get_document_summary()
            print(f"     Types: {', '.join(summary['types']) if summary['types'] else 'None'}")
            print(f"     Size: {summary['total_size_kb']:.1f} KB")
            print(f"     Sources: {', '.join(summary['sources'][:3] if len(summary['sources']) > 3 else summary['sources'])}")

            # Show sample documents
            if docs:
                print(f"\n     Sample documents:")
                for doc in docs[:3]:
                    text_preview = doc['text'][:60].replace('\n', ' ')
                    source = doc['metadata'].get('source', 'Unknown')
                    print(f"       - {source}: {text_preview}...")

            return True, docs
        else:
            print(f"[WARNING] No documents found in custom folder: {folder_path}")
            return True, []

    except Exception as e:
        print(f"[ERROR] Failed to load from custom folder: {e}")
        import traceback
        traceback.print_exc()
        return False, []


def test_folder_types(folder_path: str):
    """Analyze what file types are in the folder"""
    print_section(f"TEST 3: File Type Analysis - {folder_path}")

    if not Path(folder_path).exists():
        print(f"[ERROR] Path does not exist: {folder_path}")
        return

    folder = Path(folder_path)
    file_types = {}

    for file_path in folder.glob("*"):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext not in file_types:
                file_types[ext] = []
            file_types[ext].append(file_path.name)

    if not file_types:
        print(f"[WARNING] No files found in {folder_path}")
        return

    print(f"File types found:")
    for ext, files in sorted(file_types.items()):
        supported = ext in {".pdf", ".txt", ".md", ".docx", ".doc"}
        status = "[OK]" if supported else "[?]"
        print(f"  {status} {ext}: {len(files)} file(s)")

    # Show supported vs unsupported
    supported_extensions = {".pdf", ".txt", ".md", ".docx", ".doc"}
    total_supported = sum(
        len(files) for ext, files in file_types.items()
        if ext in supported_extensions
    )
    total_files = sum(len(files) for files in file_types.values())

    print(f"\n  Total: {total_supported}/{total_files} supported files")

    if total_supported == 0:
        print(f"\n  [WARNING] No supported documents found!")
        print(f"  Supported types: PDF, TXT, MD, DOCX, DOC")


def test_document_summary(docs: List):
    """Test document summary extraction"""
    print_section("TEST 4: Document Summary")

    if not docs:
        print("[SKIP] No documents to analyze")
        return

    manager = DocumentLoaderManager()
    manager.documents = docs
    summary = manager.get_document_summary()

    print(f"Total Documents: {summary['total_documents']}")
    print(f"Total Size: {summary['total_size_kb']:.1f} KB")
    print(f"Types: {', '.join(summary['types']) if summary['types'] else 'None'}")
    print(f"Sources: {len(summary['sources'])} unique sources")


def test_search_functionality(docs: List):
    """Test document search"""
    print_section("TEST 5: Document Search")

    if not docs:
        print("[SKIP] No documents to search")
        return

    manager = DocumentLoaderManager()
    manager.documents = docs

    # Test searches
    test_queries = ["machine", "learning", "data", "api", "integration"]

    for query in test_queries:
        results = manager.search_documents(query)
        if results:
            print(f"[OK] Query '{query}': {len(results)} results")
        else:
            print(f"[-] Query '{query}': 0 results")


def interactive_test():
    """Interactive test mode"""
    print_header("INTERACTIVE TEST MODE")

    print("Select test type:")
    print("1. Test default folder")
    print("2. Test custom folder (interactive)")
    print("3. Full test suite")
    print("4. Exit")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        success, docs = test_default_folder()
        if success and docs:
            test_document_summary(docs)
            test_search_functionality(docs)

    elif choice == "2":
        folder = input("Enter folder path: ").strip()
        if folder:
            folder = folder.strip('"\'')
            success, docs = test_custom_folder(folder)
            if success:
                test_folder_types(folder)
                if docs:
                    test_document_summary(docs)
                    test_search_functionality(docs)

    elif choice == "3":
        print_header("FULL TEST SUITE")
        success, default_docs = test_default_folder()
        if success:
            test_document_summary(default_docs)

        # Ask for custom folder
        print("\n")
        folder = input("Enter custom folder path (or press Enter to skip): ").strip()
        if folder:
            folder = folder.strip('"\'')
            success, custom_docs = test_custom_folder(folder)
            if success:
                test_folder_types(folder)
                if custom_docs:
                    test_document_summary(custom_docs)
                    test_search_functionality(custom_docs)

    elif choice == "4":
        print("\n[GOODBYE]")
        return

    # Ask to continue
    if input("\n\nRun another test? (y/n): ").lower() == "y":
        interactive_test()


def automated_tests(custom_folders: List[str] = None):
    """Run automated tests"""
    print_header("AUTOMATED TEST SUITE")

    results = {
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }

    # Test 1: Default folder
    success, docs = test_default_folder()
    if success:
        results["passed"] += 1
        if docs:
            test_document_summary(docs)
    else:
        results["failed"] += 1

    # Test 2-N: Custom folders
    if custom_folders:
        for folder in custom_folders:
            success, docs = test_custom_folder(folder)
            if success:
                results["passed"] += 1
                test_folder_types(folder)
                if docs:
                    test_document_summary(docs)
            else:
                results["failed"] += 1

    # Summary
    print_header("TEST SUMMARY")
    print(f"[PASSED] {results['passed']} tests")
    print(f"[FAILED] {results['failed']} tests")
    print(f"[WARNINGS] {results['warnings']} warnings")

    if results["failed"] == 0:
        print("\n[OK] All tests passed! Document loading is working correctly.")
    else:
        print("\n[ERROR] Some tests failed. Check the output above for details.")


def main():
    """Main entry point"""
    print_header("DOCUMENT LOADING TEST SUITE")

    if len(sys.argv) > 1:
        # Command line mode
        folders = sys.argv[1:]
        automated_tests(folders)
    else:
        # Interactive mode
        interactive_test()


if __name__ == "__main__":
    main()
