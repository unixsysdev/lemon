"""Code unit extraction — matching units.rs exactly."""

from __future__ import annotations

from pathlib import Path

from ..models import CodeUnit, CodeUnitKind, ParsedFile


def extract_code_units(parsed: ParsedFile) -> list[CodeUnit]:
    """Extract all code units (module, functions, methods, classes) from a parsed file."""
    units: list[CodeUnit] = []
    root = parsed.tree.root_node

    # Synthetic module unit
    units.append(CodeUnit(
        kind=CodeUnitKind.MODULE,
        name=parsed.path.stem,
        start_line=1,
        end_line=root.end_point[0] + 1,
        start_byte=0,
        end_byte=len(parsed.source),
    ))

    _extract_from_node(root, parsed.source, units, inside_class=False)
    return units


def count_code_units(parsed: ParsedFile) -> int:
    """Fast-path count — matches extract_code_units(parsed).len()."""
    return 1 + _count_from_node(parsed.tree.root_node)


_FUNC_KINDS = {
    "function_definition", "async_function_definition",
    "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration",
}
_CLASS_KINDS = {
    "class_definition", "class_declaration",
}


def _extract_from_node(node, source: str, units: list[CodeUnit],
                       inside_class: bool) -> None:
    if node.type in _FUNC_KINDS:
        name = _get_name(node, source)
        if name:
            units.append(CodeUnit(
                kind=CodeUnitKind.METHOD if inside_class else CodeUnitKind.FUNCTION,
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
            ))
        # Recurse to find nested functions
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                _extract_from_node(cursor.node, source, units, inside_class=False)
                if not cursor.goto_next_sibling():
                    break
        return

    if node.type in _CLASS_KINDS:
        name = _get_name(node, source)
        if name:
            units.append(CodeUnit(
                kind=CodeUnitKind.CLASS,
                name=name,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
            ))
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                _extract_from_node(cursor.node, source, units, inside_class=True)
                if not cursor.goto_next_sibling():
                    break
        return

    # Default: recurse
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            _extract_from_node(cursor.node, source, units, inside_class)
            if not cursor.goto_next_sibling():
                break


def _count_from_node(node) -> int:
    if node.type in _FUNC_KINDS or node.type in _CLASS_KINDS:
        has_name = node.child_by_field_name("name") is not None
        count = 1 if has_name else 0
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                count += _count_from_node(cursor.node)
                if not cursor.goto_next_sibling():
                    break
        return count

    count = 0
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            count += _count_from_node(cursor.node)
            if not cursor.goto_next_sibling():
                break
    return count


def _get_name(node, source: str) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    b = source.encode("utf-8")
    return b[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
