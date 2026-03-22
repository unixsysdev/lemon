"""File discovery — matching discovery.rs behavior."""

from __future__ import annotations

import os
from pathlib import Path

from ..models import Language


# Directories always ignored (matching Rust ALWAYS_IGNORED)
ALWAYS_IGNORED = {"__pycache__", "node_modules", ".venv", "venv", "env"}


def find_source_files(root: Path,
                      ignore_prefixes: list[str] | None = None,
                      lang_filter: Language | None = None) -> list[Path]:
    """Walk root and return all source files, respecting ignore rules.

    Honors:
    - .gitignore (via checking if file is git-ignored)
    - .kissignore (gitignore-style patterns)
    - ALWAYS_IGNORED directories
    - --ignore prefix patterns (match against directory components, not filenames)
    """
    ignore_prefixes = ignore_prefixes or []
    kissignore_patterns = _load_kissignore(root)
    results: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        rel = dp.relative_to(root)

        # Filter out ignored directories in-place
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and d not in ALWAYS_IGNORED
            and not _has_prefix(d, ignore_prefixes)
        ]

        for filename in filenames:
            filepath = dp / filename
            rel_path = rel / filename

            # Check directory components against ignore prefixes
            if _should_ignore_path(rel_path, ignore_prefixes):
                continue

            # Check kissignore patterns
            if _matches_kissignore(str(rel_path), kissignore_patterns):
                continue

            # Check language
            lang = Language.from_path(filepath)
            if lang is None:
                continue
            if lang_filter is not None and lang != lang_filter:
                continue

            results.append(filepath.resolve())

    return results


def _has_prefix(name: str, prefixes: list[str]) -> bool:
    return any(name.startswith(p) for p in prefixes)


def _should_ignore_path(rel_path: Path, ignore_prefixes: list[str]) -> bool:
    """Check directory components (not filename) against ignore prefixes."""
    parts = rel_path.parts
    if len(parts) <= 1:
        return False
    # Only check directory components, not the filename
    for part in parts[:-1]:
        if _has_prefix(part, ignore_prefixes) or part in ALWAYS_IGNORED:
            return True
    return False


def _load_kissignore(root: Path) -> list[str]:
    """Load .kissignore patterns from root directory."""
    kissignore = root / ".kissignore"
    if not kissignore.is_file():
        return []
    patterns = []
    for line in kissignore.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def _matches_kissignore(rel_path: str, patterns: list[str]) -> bool:
    """Simple gitignore-style pattern matching."""
    for pattern in patterns:
        # Normalize pattern
        p = pattern.rstrip("/")
        if rel_path.startswith(p + "/") or rel_path.startswith(p + os.sep):
            return True
        if rel_path == p:
            return True
        # Simple glob: pattern ends with *
        if p.endswith("*") and rel_path.startswith(p[:-1]):
            return True
    return False


def is_test_file(path: Path) -> bool:
    """Check if a file is a test file by naming convention."""
    name = path.name
    stem = path.stem
    ext = path.suffix.lower()

    # Python test files
    if ext == ".py":
        if name.startswith("test_") or stem.endswith("_test") or name == "conftest.py":
            return True

    # PHP test files
    if ext == ".php":
        if name.endswith("Test.php") or name.startswith("Test"):
            return True

    # JS/TS test files
    if ext in (".js", ".jsx", ".ts", ".tsx", ".mjs"):
        if ".test." in name or ".spec." in name:
            return True
        if name.startswith("test_") or stem.endswith("_test"):
            return True

    return False


def is_in_test_directory(path: Path) -> bool:
    """Check if a file is inside a test/tests directory."""
    return any(p in ("test", "tests", "__tests__") for p in path.parts)
