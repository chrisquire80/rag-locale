#!/usr/bin/env python3
"""
Helper script to find document folders on your PC
Helps users identify the correct path to their document collection
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple


def find_folders_with_documents(search_path: str = None, max_depth: int = 3) -> List[Tuple[str, int]]:
    """
    Search for folders containing documents (PDF, TXT, DOC, MD files)

    Args:
        search_path: Root path to search from (default: user's home directory)
        max_depth: Maximum folder depth to search (default: 3)

    Returns:
        List of tuples: (folder_path, document_count)
    """
    if search_path is None:
        search_path = str(Path.home())

    results = []

    try:
        print(f"\nSearching for document folders in: {search_path}")
        print("This may take a moment...\n")

        for root, dirs, files in os.walk(search_path):
            # Check depth
            depth = root.replace(search_path, "").count(os.sep)
            if depth > max_depth:
                # Skip subdirectories to avoid deep recursion
                dirs[:] = []
                continue

            # Look for document files
            doc_extensions = {".pdf", ".txt", ".md", ".docx", ".doc"}
            doc_files = [f for f in files if Path(f).suffix.lower() in doc_extensions]

            if doc_files:
                results.append((root, len(doc_files)))

    except PermissionError:
        print(f"[SKIP] Permission denied: {search_path}")
    except Exception as e:
        print(f"[ERROR] {e}")

    return sorted(results, key=lambda x: x[1], reverse=True)


def display_menu():
    """Display interactive menu for folder selection"""
    print("\n" + "="*80)
    print("RAG LOCALE - Document Folder Finder")
    print("="*80)

    print("\nOptions:")
    print("1. Search common document locations")
    print("2. Search specific folder")
    print("3. Enter folder path directly")
    print("4. Exit")

    choice = input("\nSelect option (1-4): ").strip()
    return choice


def search_common_locations():
    """Search in common document locations"""
    common_paths = [
        str(Path.home() / "Documents"),
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
        "C:\\Users",  # Windows common location
    ]

    all_results = []

    for base_path in common_paths:
        if Path(base_path).exists():
            print(f"\nSearching in: {base_path}")
            results = find_folders_with_documents(base_path, max_depth=2)
            all_results.extend(results)

    return all_results


def display_results(results: List[Tuple[str, int]]):
    """Display search results in formatted table"""
    if not results:
        print("\n[NO RESULTS] No folders with documents found.")
        return None

    print("\n" + "="*80)
    print("RESULTS - Folders with documents found:")
    print("="*80)

    # Display results
    for idx, (folder, count) in enumerate(results, 1):
        print(f"\n{idx}. Folder: {folder}")
        print(f"   Documents: {count}")

    # Let user select
    print("\n" + "-"*80)
    try:
        selection = int(input(f"\nSelect folder (1-{len(results)}), or 0 to cancel: "))
        if 1 <= selection <= len(results):
            selected_folder, _ = results[selection - 1]
            return selected_folder
    except ValueError:
        pass

    return None


def validate_and_test_folder(folder_path: str):
    """Validate folder and show what documents will be loaded"""
    folder = Path(folder_path)

    if not folder.exists():
        print(f"\n[ERROR] Folder does not exist: {folder_path}")
        return False

    if not folder.is_dir():
        print(f"\n[ERROR] Path is not a directory: {folder_path}")
        return False

    # Count document types
    doc_types = {
        ".pdf": [],
        ".txt": [],
        ".md": [],
        ".docx": [],
        ".doc": [],
    }

    for ext in doc_types.keys():
        doc_types[ext] = list(folder.glob(f"*{ext}"))

    total = sum(len(files) for files in doc_types.values())

    if total == 0:
        print(f"\n[WARNING] No documents found in: {folder_path}")
        return False

    # Display results
    print("\n" + "="*80)
    print("Folder Validation Results")
    print("="*80)
    print(f"\nFolder: {folder_path}")
    print(f"Absolute path: {folder.resolve()}")
    print(f"\nDocument types found:")
    for ext, files in doc_types.items():
        if files:
            print(f"  {ext}: {len(files)} files")
            # Show first 3 files
            for f in files[:3]:
                print(f"    - {f.name}")
            if len(files) > 3:
                print(f"    ... and {len(files) - 3} more")

    print(f"\nTotal documents: {total}")

    # Copy to clipboard message
    print("\n" + "-"*80)
    print("To use this folder in RAG LOCALE:")
    print("1. Open RAG LOCALE Streamlit app")
    print("2. In the sidebar, select 'Custom folder path'")
    print("3. Copy and paste this path:")
    print(f"\n   {folder.resolve()}\n")

    return True


def main():
    """Main interactive menu"""
    print("\nWelcome to RAG LOCALE Document Folder Finder!")

    while True:
        choice = display_menu()

        if choice == "1":
            print("\n[SEARCHING] Common locations (Documents, Downloads, Desktop)...")
            results = search_common_locations()
            selected = display_results(results)
            if selected:
                validate_and_test_folder(selected)

        elif choice == "2":
            folder = input("\nEnter folder path to search: ").strip()
            if folder:
                results = find_folders_with_documents(folder, max_depth=2)
                selected = display_results(results)
                if selected:
                    validate_and_test_folder(selected)

        elif choice == "3":
            folder = input("\nEnter the full folder path: ").strip()
            if folder:
                # Handle quoted paths
                folder = folder.strip('"\'')
                validate_and_test_folder(folder)

        elif choice == "4":
            print("\n[GOODBYE] Thank you for using RAG LOCALE Folder Finder!")
            sys.exit(0)

        else:
            print("[ERROR] Invalid option. Please select 1-4.")


if __name__ == "__main__":
    main()
