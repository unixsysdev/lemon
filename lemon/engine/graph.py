"""Dependency graph analysis — matching graph.rs with networkx."""

from __future__ import annotations

import networkx as nx
from pathlib import Path

from ..models import Language, ParsedFile, Violation, ViolationBuilder
from ..config import Config


# ---------------------------------------------------------------------------
# Graph building
# ---------------------------------------------------------------------------

def build_dependency_graph(parsed_files: list[ParsedFile],
                            root: Path) -> nx.DiGraph:
    """Build a directed dependency graph from parsed source files.

    Nodes are qualified module names (e.g., 'pkg.module').
    Edges represent import/use/require dependencies.
    """
    g = nx.DiGraph()

    module_map: dict[str, Path] = {}  # module_name -> file path
    path_map: dict[Path, str] = {}  # file path -> module_name

    for pf in parsed_files:
        mod_name = _path_to_module(pf.path, root, pf.language)
        module_map[mod_name] = pf.path
        path_map[pf.path] = mod_name
        g.add_node(mod_name, path=str(pf.path), language=pf.language.name)

    for pf in parsed_files:
        src_mod = path_map[pf.path]
        imports = extract_imports(pf)
        for imp in imports:
            # Try to resolve import to a known module
            resolved = _resolve_import(imp, src_mod, set(module_map.keys()))
            if resolved and resolved != src_mod:
                g.add_edge(src_mod, resolved)

    return g


def _path_to_module(path: Path, root: Path, lang: Language) -> str:
    """Convert a file path to a qualified module name."""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path

    parts = list(rel.parts)

    # Handle __init__.py → parent module
    if parts and parts[-1] in ("__init__.py",):
        parts = parts[:-1]
    elif parts:
        # Strip extension
        stem = Path(parts[-1]).stem
        parts[-1] = stem

    return ".".join(parts)


def _resolve_import(import_name: str, src_module: str,
                     known_modules: set[str]) -> str | None:
    """Resolve an import name to a known module."""
    # Handle relative imports (.models, ..engine.graph)
    if import_name.startswith("."):
        stripped = import_name.lstrip(".")
        dot_count = len(import_name) - len(stripped)
        # .X from a.b.c => a.b.X  (drop last 1 = the module itself)
        # ..X from a.b.c => a.X   (drop last 2)
        src_parts = src_module.split(".")
        up = min(dot_count, len(src_parts))
        base_parts = src_parts[:-up] if up else src_parts
        if stripped:
            candidate = ".".join(base_parts + stripped.split("."))
        else:
            candidate = ".".join(base_parts)
        if candidate in known_modules:
            return candidate
        # Also try without the package prefix (flat layout)
        if stripped in known_modules:
            return stripped

    # Exact match
    if import_name in known_modules:
        return import_name

    # Relative resolve: try prepending parent packages
    parts = src_module.split(".")
    for i in range(len(parts)):
        candidate = ".".join(parts[:i] + [import_name])
        if candidate in known_modules:
            return candidate

    # Check suffix match
    for mod in known_modules:
        if mod.endswith("." + import_name) or mod == import_name:
            return mod

    return None


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

_IMPORT_DISPATCH = {
    "import_statement": "_extract_python_import",
    "import_from_statement": "_extract_python_from_import",
    "namespace_use_declaration": "_extract_php_use",
}

_JS_TS_IMPORT_TYPES = {"import_statement"}


def _get_import_handler(node_type, language):
    """Get the handler name for an import node type."""
    # Python and PHP use the dispatch table
    handler = _IMPORT_DISPATCH.get(node_type)
    if handler:
        return handler
    # JS/TS import_statement is the same node type as Python but different handler
    if node_type == "import_statement" and language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        return "_extract_js_import"
    return None


def extract_imports(parsed: ParsedFile) -> list[str]:
    """Extract import module names from a parsed file."""
    imports: list[str] = []
    _walk_imports(parsed.tree.root_node, parsed.source, parsed.language, imports)
    return imports


def _walk_imports(node, source, language, imports):
    """Recursively walk AST collecting imports (flat — no deep nesting)."""
    handler_name = _get_import_handler(node.type, language)
    if handler_name:
        globals()[handler_name](node, source, imports)
        return
    for child in _iter_node_children(node):
        _walk_imports(child, source, language, imports)


from .ast_helpers import iter_children as _iter_node_children


from .ast_helpers import node_text as _node_text


def _extract_python_import(node, source: str, imports: list[str]) -> None:
    for child in _iter_node_children(node):
        if child.type == "dotted_name":
            imports.append(_node_text(child, source))
        elif child.type == "aliased_import":
            name = child.child_by_field_name("name")
            if name:
                imports.append(_node_text(name, source))


def _extract_python_from_import(node, source: str, imports: list[str]) -> None:
    module = node.child_by_field_name("module_name")
    if module:
        imports.append(_node_text(module, source))


def _extract_php_use(node, source: str, imports: list[str]) -> None:
    for child in _iter_node_children(node):
        if child.type == "namespace_name":
            imports.append(_node_text(child, source))


def _extract_js_import(node, source: str, imports: list[str]) -> None:
    source_node = node.child_by_field_name("source")
    if source_node:
        txt = _node_text(source_node, source).strip("'\"")
        imports.append(txt)


# ---------------------------------------------------------------------------
# Graph metrics
# ---------------------------------------------------------------------------

def _graph_degree(g: nx.DiGraph, node: str, *, direction: str) -> int:
    """Get in-degree or out-degree for a node."""
    if node not in g:
        return 0
    return g.in_degree(node) if direction == "in" else g.out_degree(node)


def graph_fan_in(g: nx.DiGraph, node: str) -> int:
    return _graph_degree(g, node, direction="in")


def graph_fan_out(g: nx.DiGraph, node: str) -> int:
    return _graph_degree(g, node, direction="out")


def graph_indirect_dependencies(g: nx.DiGraph, node: str) -> int:
    """Total reachable modules minus direct fan-out."""
    if node not in g:
        return 0
    reachable = len(nx.descendants(g, node))
    return reachable - g.out_degree(node)


def graph_dependency_depth(g: nx.DiGraph, node: str) -> int:
    """Max longest path from this node."""
    if node not in g:
        return 0
    try:
        return max(
            (len(p) - 1 for p in nx.all_simple_paths(g, node, t)
             for t in nx.descendants(g, node)),
            default=0,
        )
    except nx.NetworkXError:
        return 0


def graph_max_depth(g: nx.DiGraph) -> int:
    """Maximum dependency depth in the graph."""
    if not g.nodes:
        return 0
    try:
        return nx.dag_longest_path_length(g) if nx.is_directed_acyclic_graph(g) else 0
    except nx.NetworkXError:
        return 0


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

def find_cycles(g: nx.DiGraph) -> list[list[str]]:
    """Find strongly connected components (cycles) in the graph.

    Returns list of SCCs with size > 1 (i.e., actual cycles).
    Uses Tarjan's algorithm (via networkx's kosaraju implementation).
    """
    return [list(scc) for scc in nx.strongly_connected_components(g) if len(scc) > 1]


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

_ENTRY_POINTS = {"__main__", "main", "cli", "app", "manage"}


def find_orphan_modules(g: nx.DiGraph) -> list[str]:
    """Find orphan modules — 0 fan-in + 0 fan-out, not an entry point."""
    orphans = []
    for node in g.nodes:
        if g.in_degree(node) == 0 and g.out_degree(node) == 0:
            basename = node.rsplit(".", 1)[-1] if "." in node else node
            if basename not in _ENTRY_POINTS:
                orphans.append(node)
    return orphans


# ---------------------------------------------------------------------------
# Graph violations
# ---------------------------------------------------------------------------

def check_graph_violations(g: nx.DiGraph, config: Config) -> list[Violation]:
    """Check dependency graph metrics against config thresholds."""
    violations: list[Violation] = []

    # Cycle violations
    cycles = find_cycles(g)
    for cycle in cycles:
        if len(cycle) > config.cycle_size:
            cycle_str = " -> ".join(sorted(cycle))
            violations.append(
                ViolationBuilder(Path("(graph)"))
                .line(0).unit_name(cycle_str)
                .metric("cycle_size")
                .value(len(cycle)).threshold(config.cycle_size)
                .message(f"Import cycle with {len(cycle)} modules: {cycle_str} (threshold: {config.cycle_size})")
                .suggestion("Break the cycle by introducing an interface or restructuring imports.")
                .build()
            )

    # Per-node violations
    for node in g.nodes:
        path_str = g.nodes[node].get("path", "(unknown)")
        file = Path(path_str)

        indirect = graph_indirect_dependencies(g, node)
        if indirect > config.indirect_dependencies:
            violations.append(
                ViolationBuilder(file)
                .line(0).unit_name(node)
                .metric("indirect_dependencies")
                .value(indirect).threshold(config.indirect_dependencies)
                .message(f"Module '{node}' has {indirect} indirect dependencies (threshold: {config.indirect_dependencies})")
                .suggestion("Reduce coupling by narrowing imports or introducing facades.")
                .build()
            )

    # Graph-wide depth
    try:
        if nx.is_directed_acyclic_graph(g):
            depth = nx.dag_longest_path_length(g)
            if depth > config.dependency_depth:
                violations.append(
                    ViolationBuilder(Path("(graph)"))
                    .line(0).unit_name("(dependency_graph)")
                    .metric("dependency_depth")
                    .value(depth).threshold(config.dependency_depth)
                    .message(f"Dependency depth is {depth} (threshold: {config.dependency_depth})")
                    .suggestion("Flatten the module hierarchy or reduce chained imports.")
                    .build()
                )
    except nx.NetworkXError:
        pass

    return violations
