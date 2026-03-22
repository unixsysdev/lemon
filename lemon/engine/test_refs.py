"""Static test reference coverage — matching test_refs.rs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import networkx as nx

from ..models import (
    CodeDefinition,
    CodeUnitKind,
    CoveringTest,
    Language,
    ParsedFile,
    TestRefAnalysis,
)
from .discovery import is_in_test_directory, is_test_file
from .ast_helpers import node_text as _node_text
from .ast_helpers import iter_children as _iter_children


# ---------------------------------------------------------------------------
# Test file detection (language-aware)
# ---------------------------------------------------------------------------

def _is_test_file_for_analysis(parsed: ParsedFile) -> bool:
    """Determine if a file should be treated as a test file."""
    if is_test_file(parsed.path) or is_in_test_directory(parsed.path):
        return True
    if parsed.language == Language.PYTHON:
        root = parsed.tree.root_node
        source = parsed.source
        return _has_test_framework_import(root, source) and _has_test_function(root, source)
    return False


def _has_test_framework_import(node, source: str) -> bool:
    for child in _iter_children(node):
        if child.type in ("import_statement", "import_from_statement"):
            if "pytest" in _node_text(child, source) or "unittest" in _node_text(child, source):
                return True
    return False


def _has_test_function(node, source: str) -> bool:
    cursor = node.walk()

    def _walk():
        n = cursor.node
        if n.type in ("function_definition", "async_function_definition"):
            name = n.child_by_field_name("name")
            if name and _node_text(name, source).startswith("test_"):
                return True
        if cursor.goto_first_child():
            while True:
                if _walk():
                    return True
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()
        return False

    return _walk()


# ---------------------------------------------------------------------------
# Definition collection
# ---------------------------------------------------------------------------

_FUNC_KINDS = {
    "function_definition", "async_function_definition",
    "function_declaration", "method_declaration",
    "method_definition",
}
_CLASS_KINDS = {"class_definition", "class_declaration"}


def _should_include_func(name: str) -> bool:
    """Check if a function name should be included in definitions."""
    if name.startswith("test_"):
        return False
    if name.startswith("_") and name != "__init__":
        return False
    return True


def _try_add_func_def(node, source, file, defs, *, inside_class, class_name):
    """Try to add a function/method definition, if it qualifies."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    if not _should_include_func(name):
        return
    if _is_abstract(node, source):
        return
    kind = CodeUnitKind.METHOD if inside_class else CodeUnitKind.FUNCTION
    defs.append(CodeDefinition(
        name=name, kind=kind, file=file,
        line=node.start_point[0] + 1,
        containing_class=class_name,
    ))


def _try_add_class_def(node, source, file, defs):
    """Try to add a class definition and recurse into its body."""
    name_node = node.child_by_field_name("name")
    if not name_node:
        return
    name = _node_text(name_node, source)
    if _is_protocol_or_abstract(node, source):
        return
    defs.append(CodeDefinition(
        name=name, kind=CodeUnitKind.CLASS,
        file=file, line=node.start_point[0] + 1,
    ))
    body = node.child_by_field_name("body")
    if body:
        for child in _iter_children(body):
            collect_definitions(child, source, file, defs,
                                inside_class=True, class_name=name)


def collect_definitions(
    node, source: str, file: Path,
    defs: list[CodeDefinition], *,
    inside_class: bool = False,
    class_name: str | None = None,
) -> None:
    """Collect function/class definitions from source code (non-test files)."""
    if node.type in _FUNC_KINDS:
        _try_add_func_def(node, source, file, defs,
                          inside_class=inside_class, class_name=class_name)
        return
    if node.type in _CLASS_KINDS:
        _try_add_class_def(node, source, file, defs)
        return
    for child in _iter_children(node):
        collect_definitions(child, source, file, defs,
                            inside_class=inside_class, class_name=class_name)


def _has_decorator_matching(node, source: str, pattern: str) -> bool:
    """Check if a decorated_definition parent has a decorator matching pattern."""
    parent = node.parent
    if not parent or parent.type != "decorated_definition":
        return False
    for child in _iter_children(parent):
        if child.type == "decorator" and pattern in _node_text(child, source):
            return True
    return False


def _is_abstract(node, source: str) -> bool:
    return _has_decorator_matching(node, source, "abstractmethod")


def _is_protocol_or_abstract(node, source: str) -> bool:
    superclasses = node.child_by_field_name("superclasses")
    if superclasses:
        text = _node_text(superclasses, source)
        if "Protocol" in text or "ABC" in text:
            return True
    return False


# ---------------------------------------------------------------------------
# Reference collection from test files
# ---------------------------------------------------------------------------

def collect_test_references(node, source: str, refs: set[str]) -> None:
    """Collect all identifiers referenced from test code."""
    if node.type == "identifier":
        refs.add(_node_text(node, source))
    elif node.type == "attribute":
        attr = node.child_by_field_name("attribute")
        if attr:
            refs.add(_node_text(attr, source))
        obj = node.child_by_field_name("object")
        if obj:
            collect_test_references(obj, source, refs)
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            collect_test_references(cursor.node, source, refs)
            if not cursor.goto_next_sibling():
                break


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def analyze_test_refs(
    parsed_files: list[ParsedFile],
    graph: nx.DiGraph | None = None,
) -> TestRefAnalysis:
    """Full test reference analysis — matching test_refs.rs::analyze_test_refs."""
    definitions: list[CodeDefinition] = []
    test_refs: set[str] = set()

    for pf in parsed_files:
        if _is_test_file_for_analysis(pf):
            collect_test_references(pf.tree.root_node, pf.source, test_refs)
        else:
            collect_definitions(pf.tree.root_node, pf.source, pf.path, definitions)

    # Build name→files map for disambiguation
    name_files: dict[str, set[Path]] = defaultdict(set)
    for d in definitions:
        name_files[d.name].add(d.file)

    # Find unreferenced definitions
    unreferenced: list[CodeDefinition] = []
    for d in definitions:
        if not _is_covered(d, name_files, test_refs):
            unreferenced.append(d)

    return TestRefAnalysis(
        definitions=definitions,
        test_references=test_refs,
        unreferenced=unreferenced,
    )


def _is_covered(d: CodeDefinition, name_files: dict[str, set[Path]],
                refs: set[str]) -> bool:
    """Check if a definition is covered by test references."""
    if d.name in refs:
        files = name_files.get(d.name, set())
        if len(files) <= 1:
            return True
        # Ambiguous: multiple files define same name, skip for now
        # (full disambiguation requires graph, not implemented yet)
        return True  # conservative: assume covered
    # Check containing class
    if d.containing_class and d.containing_class in refs:
        return True
    return False


def compute_coverage_pct(analysis: TestRefAnalysis) -> int:
    """Compute test coverage percentage."""
    total = len(analysis.definitions)
    if total == 0:
        return 100
    covered = total - len(analysis.unreferenced)
    return int(covered * 100 / total)
