#!/usr/bin/env python3
"""
Type Hints Standardization Script

Converts Python 3.8 typing module syntax to Python 3.9+ builtin generics:
- List[X] → list[X]
- Dict[X, Y] → dict[X, Y]
- Tuple[...] → tuple[...]
- Set[X] → set[X]

Removes unused typing imports and preserves Optional, Any, Callable, Literal.

Usage:
    python convert_type_hints.py src/file.py
    python convert_type_hints.py src/*.py
"""

import sys
import re
from pathlib import Path


def convert_file(file_path: str) -> bool:
    """Convert type hints in a single file. Returns True if changed."""
    path = Path(file_path)

    if not path.exists():
        print(f"[x] File not found: {path}")
        return False

    if not path.suffix == '.py':
        print(f"[o] Skipping non-Python file: {path}")
        return False

    content = path.read_text(encoding='utf-8')
    original = content

    # Convert List[...] → list[...]
    content = re.sub(r'\bList\[', 'list[', content)

    # Convert Dict[...] → dict[...]
    content = re.sub(r'\bDict\[', 'dict[', content)

    # Convert Tuple[...] → tuple[...]
    content = re.sub(r'\bTuple\[', 'tuple[', content)

    # Convert Set[...] → set[...]
    content = re.sub(r'\bSet\[', 'set[', content)

    # Simplify import lines
    # Pattern: from typing import X, Y, Z
    def simplify_typing_import(match):
        import_line = match.group(0)

        # Extract what's imported
        items = [item.strip() for item in import_line.split('import')[1].split(',')]

        # Keep only: Optional, Any, Callable, Literal, Union, TypeVar, Protocol
        keep_items = [
            item for item in items
            if item in ['Optional', 'Any', 'Callable', 'Literal', 'Union', 'TypeVar', 'Protocol']
        ]

        if not keep_items:
            # No items to keep - delete the entire line
            return ""
        else:
            # Reconstruct with only necessary items
            return f"from typing import {', '.join(sorted(set(keep_items)))}"

    # Find and replace typing imports
    # This regex matches the full import line
    content = re.sub(
        r'from typing import [^\n]+',
        simplify_typing_import,
        content
    )

    # Remove any blank lines created by deleted imports
    content = re.sub(r'\n\n\n+', '\n\n', content)

    # Check if changed
    if content == original:
        print(f"[o] No changes needed: {path.name}")
        return False

    # Write back
    path.write_text(content, encoding='utf-8')

    # Count changes
    list_count = len(re.findall(r'list\[', content)) - len(re.findall(r'list\[', original))
    dict_count = len(re.findall(r'dict\[', content)) - len(re.findall(r'dict\[', original))
    tuple_count = len(re.findall(r'tuple\[', content)) - len(re.findall(r'tuple\[', original))
    set_count = len(re.findall(r'set\[', content)) - len(re.findall(r'set\[', original))

    total_changes = abs(list_count) + abs(dict_count) + abs(tuple_count) + abs(set_count)

    print(f"[+] Converted: {path.name}")
    if total_changes > 0:
        print(f"   Changed {total_changes} type hints")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert_type_hints.py src/file.py [src/file2.py ...]")
        sys.exit(1)

    files = sys.argv[1:]

    print("[*] Type Hints Standardization")
    print("=" * 60)
    print()

    converted = 0
    for file_pattern in files:
        # Handle glob patterns
        if '*' in file_pattern:
            import glob
            matching_files = glob.glob(file_pattern)
            for f in matching_files:
                if convert_file(f):
                    converted += 1
        else:
            if convert_file(file_pattern):
                converted += 1

    print()
    print("=" * 60)
    print(f"[+] Converted {converted} file(s)")


if __name__ == '__main__':
    main()
