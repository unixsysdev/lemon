"""Tree-Sitter parser management — grammar loading and query compilation."""

from __future__ import annotations

import importlib.resources
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import tree_sitter

from ..models import Language, ParsedFile

# ---------------------------------------------------------------------------
# Grammar loading
# ---------------------------------------------------------------------------

# Lazily loaded grammars and languages
_LANGUAGES: dict[Language, tree_sitter.Language] = {}
_PARSERS: dict[Language, tree_sitter.Parser] = {}


def _get_ts_language(lang: Language) -> tree_sitter.Language:
    """Get or lazily load a Tree-Sitter language."""
    if lang not in _LANGUAGES:
        if lang == Language.PYTHON:
            import tree_sitter_python
            _LANGUAGES[lang] = tree_sitter.Language(tree_sitter_python.language())
        elif lang == Language.PHP:
            import tree_sitter_php
            # tree-sitter-php exposes language_php() for the PHP grammar
            _LANGUAGES[lang] = tree_sitter.Language(tree_sitter_php.language_php())
        elif lang == Language.JAVASCRIPT:
            import tree_sitter_javascript
            _LANGUAGES[lang] = tree_sitter.Language(tree_sitter_javascript.language())
        elif lang == Language.TYPESCRIPT:
            import tree_sitter_typescript
            _LANGUAGES[lang] = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        elif lang == Language.GO:
            import tree_sitter_go
            _LANGUAGES[lang] = tree_sitter.Language(tree_sitter_go.language())
        else:
            raise ValueError(f"Unsupported language: {lang}")
    return _LANGUAGES[lang]


def _get_parser(lang: Language) -> tree_sitter.Parser:
    """Get or lazily create a parser for a language."""
    if lang not in _PARSERS:
        parser = tree_sitter.Parser()
        parser.language = _get_ts_language(lang)
        _PARSERS[lang] = parser
    return _PARSERS[lang]


# ---------------------------------------------------------------------------
# Query loading
# ---------------------------------------------------------------------------

_QUERIES: dict[tuple[Language, str], tree_sitter.Query] = {}

_LANG_TO_QUERY_FILE: dict[Language, str] = {
    Language.PYTHON: "python.scm",
    Language.PHP: "php.scm",
    Language.JAVASCRIPT: "javascript.scm",
    Language.TYPESCRIPT: "typescript.scm",
    Language.GO: "go.scm",
}


def _load_query_source(lang: Language) -> str:
    """Load the .scm query file for a language from the queries package."""
    filename = _LANG_TO_QUERY_FILE[lang]
    queries_pkg = importlib.resources.files("lemon.engine.queries")
    query_file = queries_pkg / filename
    return query_file.read_text(encoding="utf-8")


def get_query(lang: Language, query_name: Optional[str] = None) -> tree_sitter.Query:
    """Get a compiled Tree-Sitter query for a language.

    Currently each language has a single combined .scm file;
    query_name is reserved for future per-metric query splitting.
    """
    cache_key = (lang, query_name or "__all__")
    if cache_key not in _QUERIES:
        ts_lang = _get_ts_language(lang)
        source = _load_query_source(lang)
        _QUERIES[cache_key] = ts_lang.query(source)
    return _QUERIES[cache_key]


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> ParsedFile:
    """Parse a single source file into a ParsedFile."""
    lang = Language.from_path(path)
    if lang is None:
        raise ValueError(f"Cannot determine language for: {path}")
    source = path.read_text(encoding="utf-8", errors="replace")
    source_bytes = source.encode("utf-8")
    parser = _get_parser(lang)
    tree = parser.parse(source_bytes)
    return ParsedFile(
        path=path,
        source=source,
        source_bytes=source_bytes,
        tree=tree,
        language=lang,
    )


def _parse_file_safe(path: Path) -> ParsedFile | str:
    """Parse a file, returning error string on failure."""
    try:
        return parse_file(path)
    except Exception as e:
        return f"Error parsing {path}: {e}"


def parse_files(paths: list[Path], max_workers: Optional[int] = None) -> list[ParsedFile]:
    """Parse multiple files. Returns list of successfully parsed files.

    Errors are logged to stderr.
    """
    import sys

    if not paths:
        return []

    results: list[ParsedFile] = []
    # Tree-sitter parsers aren't safely picklable for ProcessPoolExecutor,
    # so we use sequential parsing (still fast — tree-sitter is C-backed).
    for path in paths:
        result = _parse_file_safe(path)
        if isinstance(result, str):
            print(result, file=sys.stderr)
        else:
            results.append(result)
    return results
