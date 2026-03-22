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


def write_viz(g: nx.DiGraph, out_path: Path, *, zoom: float = 1.0) -> None:
    """Write graph visualization to a file (format inferred from extension).

    Args:
        zoom: 0.0 = maximally coarsened (top-level packages), 1.0 = full detail.
    """
    output_graph = coarsen_graph(g, zoom) if zoom < 1.0 else g
    ext = out_path.suffix.lower()
    if ext == ".dot":
        content = graph_to_dot(output_graph)
    elif ext in (".mmd", ".mermaid"):
        content = graph_to_mermaid(output_graph)
    elif ext in (".md", ".markdown"):
        content = "```mermaid\n" + graph_to_mermaid(output_graph) + "```\n"
    else:
        raise ValueError(
            f"Unsupported extension '{ext}'. Use .dot, .mmd/.mermaid, or .md"
        )
    out_path.write_text(content, encoding="utf-8")


def coarsen_graph(g: nx.DiGraph, zoom: float) -> nx.DiGraph:
    """Coarsen a module dependency graph by grouping nodes at a directory level.

    zoom=0.0 → top-level packages only (depth 1).
    zoom=1.0 → full detail (no coarsening).
    zoom=0.5 → halfway between min and max depth.
    """
    if not g.nodes:
        return g

    # Determine depth range
    depths = [n.count(".") + 1 for n in g.nodes]
    min_d, max_d = min(depths), max(depths)
    if min_d == max_d:
        return g

    # Target depth based on zoom
    target_depth = max(1, int(min_d + zoom * (max_d - min_d)))

    # Group nodes by truncated path
    def _truncate(name: str) -> str:
        parts = name.split(".")
        return ".".join(parts[:target_depth])

    coarse = nx.DiGraph()
    for node in g.nodes:
        group = _truncate(node)
        if group not in coarse:
            coarse.add_node(group)

    for u, v in g.edges:
        gu, gv = _truncate(u), _truncate(v)
        if gu != gv:
            coarse.add_edge(gu, gv)

    return coarse
