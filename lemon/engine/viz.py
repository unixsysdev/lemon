"""Dependency graph visualization — Mermaid and DOT output."""

from __future__ import annotations

import re
from pathlib import Path

import networkx as nx


def _mermaid_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _mermaid_id(name: str) -> str:
    out = re.sub(r"[^a-z0-9]", "_", name.lower())
    if out and out[0].isdigit():
        out = "n" + out
    return out


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def graph_to_mermaid(g: nx.DiGraph) -> str:
    """Render a networkx DiGraph as a Mermaid flowchart."""
    lines = ["graph LR"]
    for node in sorted(g.nodes):
        nid = _mermaid_id(node)
        label = _mermaid_escape(node)
        lines.append(f'  {nid}["{label}"]')
    for u, v in sorted(g.edges):
        lines.append(f"  {_mermaid_id(u)} --> {_mermaid_id(v)}")
    return "\n".join(lines) + "\n"


def graph_to_dot(g: nx.DiGraph) -> str:
    """Render a networkx DiGraph as a Graphviz DOT string."""
    lines = [
        "digraph lemon {",
        "  rankdir=LR;",
        '  node [shape=box];',
    ]
    for node in sorted(g.nodes):
        lines.append(f'  "{_dot_escape(node)}";')
    for u, v in sorted(g.edges):
        lines.append(f'  "{_dot_escape(u)}" -> "{_dot_escape(v)}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_viz(g: nx.DiGraph, out_path: Path) -> None:
    """Write graph visualization to a file (format inferred from extension)."""
    ext = out_path.suffix.lower()
    if ext == ".dot":
        content = graph_to_dot(g)
    elif ext in (".mmd", ".mermaid"):
        content = graph_to_mermaid(g)
    elif ext in (".md", ".markdown"):
        content = "```mermaid\n" + graph_to_mermaid(g) + "```\n"
    else:
        raise ValueError(
            f"Unsupported extension '{ext}'. Use .dot, .mmd/.mermaid, or .md"
        )
    out_path.write_text(content, encoding="utf-8")
