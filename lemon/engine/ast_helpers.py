"""Shared tree-sitter AST helpers used across the engine."""

from __future__ import annotations


def node_text(node, source: str) -> str:
    """Extract text from a tree-sitter node using byte offsets.

    Tree-sitter returns byte offsets, not character offsets,
    so we must encode→slice→decode to handle multi-byte UTF-8.
    """
    b = source.encode("utf-8")
    return b[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def iter_children(node):
    """Yield direct children of a tree-sitter node."""
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            yield cursor.node
            if not cursor.goto_next_sibling():
                break
