"""CLI interface — all subcommands matching Rust kiss CLI."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click

from .config import Config, GateConfig
from .models import (
    CodeChunk,
    DuplicationConfig,
    GlobalMetrics,
    Language,
    Violation,
)


def _timing(label: str, start: float) -> None:
    elapsed = time.time() - start
    print(f"[TIMING] {label}: {elapsed:.3f}s", file=sys.stderr)


def _progress(msg: str) -> None:
    """Print a progress message to stderr."""
    click.echo(f"  ▸ {msg}", err=True)


def _load_configs(
    config_path: Path | None,
    lang_filter: Language | None,
    target_root: Path | None = None,
) -> dict[Language, Config]:
    langs = [lang_filter] if lang_filter else list(Language)
    return {lang: Config.load(lang, config_path, target_root=target_root) for lang in langs}


def _extract_chunks_for_duplication(parsed) -> list[CodeChunk]:
    from .engine.units import extract_code_units

    chunks: list[CodeChunk] = []
    for pf in parsed:
        for unit in extract_code_units(pf):
            if unit.kind.value in ("function", "method"):
                chunks.append(CodeChunk(
                    file=pf.path,
                    name=unit.name,
                    start_line=unit.start_line,
                    end_line=unit.end_line,
                    source=pf.source[unit.start_byte:unit.end_byte],
                ))
    return chunks


# ---------------------------------------------------------------------------
# Analysis pipeline (extracted from `check` to keep functions small)
# ---------------------------------------------------------------------------

def _run_metrics(parsed, configs, show_timing):
    """Run per-file metric analysis. Returns (total_stmts, total_units, violations)."""
    from .engine.metrics import analyze_file
    from .engine.units import count_code_units

    _progress("Running metrics …")
    t = time.time()
    violations: list[Violation] = []
    total_stmts = 0
    total_units = 0
    for pf in parsed:
        cfg = configs.get(pf.language) or Config.for_language(pf.language)
        stmts, viols = analyze_file(pf, cfg)
        total_stmts += stmts
        total_units += count_code_units(pf)
        violations.extend(viols)
    if show_timing:
        _timing("metrics", t)
    return total_stmts, total_units, violations


def _run_graph(parsed, root, configs, show_timing):
    """Build graph and check violations. Returns (graph, violations)."""
    from .engine.graph import build_dependency_graph, check_graph_violations

    _progress("Building dependency graph …")
    t = time.time()
    graph = build_dependency_graph(parsed, root)
    any_config = next(iter(configs.values()), Config.for_language(Language.PYTHON))
    viols = check_graph_violations(graph, any_config)
    if show_timing:
        _timing("graph", t)
    return graph, viols


def _run_duplication(parsed, gate, show_timing):
    """Run duplication analysis. Returns clusters."""
    from .engine.duplication import find_duplicates

    _progress("Checking duplication …")
    t = time.time()
    clusters = []
    if gate.duplication_enabled:
        chunks = _extract_chunks_for_duplication(parsed)
        dup_config = DuplicationConfig(min_similarity=gate.min_similarity)
        clusters = find_duplicates(chunks, dup_config)
    if show_timing:
        _timing("duplication", t)
    return clusters


def _run_test_coverage(parsed, graph, show_timing):
    """Run test coverage analysis. Returns (analysis, pct)."""
    from .engine.test_refs import analyze_test_refs, compute_coverage_pct

    _progress("Analyzing test coverage …")
    t = time.time()
    analysis = analyze_test_refs(parsed, graph)
    pct = compute_coverage_pct(analysis)
    if show_timing:
        _timing("test_coverage", t)
    return analysis, pct


def _emit_results(
    violations, clusters, *,
    test_analysis, coverage_pct,
    gate, metrics, check_all,
):
    """Print results and return True if failures exist."""
    from .output import (
        format_coverage_gate_failure,
        format_duplication_violation,
        format_summary,
        format_violation,
    )

    print(format_summary(metrics))
    has_failures = False
    for v in violations:
        print(format_violation(v))
        has_failures = True
    for cluster in clusters:
        print(format_duplication_violation(cluster))
        has_failures = True
    if not check_all and coverage_pct < gate.test_coverage_threshold:
        print(format_coverage_gate_failure(
            len(test_analysis.definitions),
            len(test_analysis.unreferenced),
            coverage_pct,
            gate.test_coverage_threshold,
        ))
        has_failures = True
    if not has_failures:
        print("NO VIOLATIONS")
    return has_failures


@click.group()
def main():
    """lemon: Language-agnostic code complexity analyzer."""
    pass


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

def _discover_and_parse(path, ignore_prefixes, lang_filter, show_timing):
    """Discover and parse source files. Returns (root, parsed) or exits."""
    from .engine.discovery import find_source_files
    from .engine.parser import parse_files

    root = Path(path).resolve()
    _progress(f"Scanning {root} …")
    t0 = time.time()
    files = find_source_files(root, list(ignore_prefixes), lang_filter)
    if show_timing:
        _timing("discovery", t0)
    if not files:
        print("No source files found.")
        sys.exit(0)
    _progress(f"Parsing {len(files)} files …")
    t1 = time.time()
    parsed = parse_files(files)
    if show_timing:
        _timing("parsing", t1)
    return root, parsed


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--focus", type=click.Path())
@click.option("--lang", type=click.Choice(["python", "php", "javascript", "typescript"]))
@click.option("--all", "check_all", is_flag=True)
@click.option("--ignore", "ignore_prefixes", multiple=True)
@click.option("--timing", "show_timing", is_flag=True)
@click.option("--config", "config_path", type=click.Path())
def check(path, focus, lang, check_all, ignore_prefixes, show_timing, config_path):
    """Run analysis and report violations."""
    lang_filter = Language[lang.upper()] if lang else None
    cfg_path = Path(config_path) if config_path else None
    root, parsed = _discover_and_parse(path, ignore_prefixes, lang_filter, show_timing)

    configs = _load_configs(cfg_path, lang_filter, target_root=root)
    gate = GateConfig.load(cfg_path, target_root=root)

    stmts, units, violations = _run_metrics(parsed, configs, show_timing)
    graph, graph_viols = _run_graph(parsed, root, configs, show_timing)
    violations.extend(graph_viols)
    clusters = _run_duplication(parsed, gate, show_timing)
    test_analysis, coverage_pct = _run_test_coverage(parsed, graph, show_timing)

    if focus:
        focus_path = Path(focus).resolve()
        violations = [v for v in violations if v.file.resolve().is_relative_to(focus_path)]

    metrics = GlobalMetrics(
        files=len(parsed), code_units=units, statements=stmts,
        graph_nodes=graph.number_of_nodes(), graph_edges=graph.number_of_edges(),
    )
    has_failures = _emit_results(
        violations, clusters,
        test_analysis=test_analysis, coverage_pct=coverage_pct,
        gate=gate, metrics=metrics, check_all=check_all,
    )
    sys.exit(1 if has_failures else 0)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

def _collect_func_class_metrics(node, source, lang, values):
    """Walk tree collecting function/class metrics into value lists."""
    from .engine.metrics import compute_class_metrics, compute_function_metrics

    _FUNC_KINDS = {
        "function_definition", "async_function_definition",
        "function_declaration", "generator_function_declaration",
        "method_definition", "method_declaration",
    }
    _CLASS_KINDS = {"class_definition", "class_declaration"}

    if node.type in _FUNC_KINDS:
        m = compute_function_metrics(node, source, lang)
        if not m.has_error:
            values["statements_per_function"].append(m.statements)
            values["arguments_per_function"].append(m.arguments)
            values["max_indentation_depth"].append(m.max_indentation)
            values["branches_per_function"].append(m.branches)
            values["local_variables_per_function"].append(m.local_variables)
            values["returns_per_function"].append(m.returns)
            values["nested_function_depth"].append(m.nested_function_depth)
            values["boolean_parameters"].append(m.boolean_parameters)
            values["calls_per_function"].append(m.calls)
        return

    if node.type in _CLASS_KINDS:
        cm = compute_class_metrics(node)
        values["methods_per_class"].append(cm.methods)
        body = node.child_by_field_name("body")
        if body:
            for child in _iter_children(body):
                _collect_func_class_metrics(child, source, lang, values)
        return

    for child in _iter_children(node):
        _collect_func_class_metrics(child, source, lang, values)


from .engine.ast_helpers import iter_children as _iter_children


_STATS_METRICS = [
    "statements_per_function", "arguments_per_function",
    "max_indentation_depth", "branches_per_function",
    "local_variables_per_function", "returns_per_function",
    "nested_function_depth", "boolean_parameters",
    "calls_per_function", "methods_per_class",
    "statements_per_file", "functions_per_file",
    "interface_types_per_file", "concrete_types_per_file",
    "imported_names_per_file",
]


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--lang", type=click.Choice(["python", "php", "javascript", "typescript"]))
@click.option("--ignore", "ignore_prefixes", multiple=True)
@click.option("--config", "config_path", type=click.Path())
@click.option("--all", "show_all", is_flag=True, help="Show top 10 outliers per metric.")
@click.option("--top", "top_n", type=int, default=None, help="Show top N outliers per metric.")
@click.option("--table", "show_table", is_flag=True, help="Per-unit wide-format table.")
def stats(path, lang, ignore_prefixes, config_path, show_all, top_n, show_table):
    """Show percentile distribution of metrics."""
    from .engine.discovery import find_source_files
    from .engine.metrics import compute_file_metrics
    from .engine.parser import parse_files
    from .output import format_stats_table

    root = Path(path).resolve()
    lang_filter = Language[lang.upper()] if lang else None
    files = find_source_files(root, list(ignore_prefixes), lang_filter)
    if not files:
        print("No source files found.")
        return

    parsed = parse_files(files)
    values: dict[str, list[int]] = {k: [] for k in _STATS_METRICS}

    for pf in parsed:
        fm = compute_file_metrics(pf)
        values["statements_per_file"].append(fm.statements)
        values["functions_per_file"].append(fm.functions)
        values["interface_types_per_file"].append(fm.interface_types)
        values["concrete_types_per_file"].append(fm.concrete_types)
        values["imported_names_per_file"].append(fm.imports)
        _collect_func_class_metrics(pf.tree.root_node, pf.source, pf.language, values)

    if show_table:
        _print_stats_table_wide(parsed, values)
    elif top_n is not None:
        _print_stats_top(values, top_n)
    elif show_all:
        _print_stats_top(values, 10)
    else:
        summaries = [(k, sorted(values[k])) for k in _STATS_METRICS]
        print(format_stats_table(summaries))


def _print_stats_top(values, n):
    """Print top-N outliers per metric (stats --all)."""
    for metric in _STATS_METRICS:
        vals = sorted(values[metric], reverse=True)
        if not vals:
            continue
        top = vals[:n]
        print(f"\n{metric}:")
        for i, v in enumerate(top, 1):
            print(f"  {i}. {v}")


def _print_stats_table_wide(parsed, values):
    """Print per-unit wide-format table (stats --table)."""
    from .engine.metrics import compute_file_metrics, compute_function_metrics
    from .engine.ast_helpers import iter_children

    _FUNC_KINDS = {
        "function_definition", "async_function_definition",
        "function_declaration", "generator_function_declaration",
        "method_definition", "method_declaration",
    }
    cols = ["file", "unit", "stmts", "args", "depth", "branches", "vars", "calls"]
    print("\t".join(cols))
    for pf in parsed:
        _print_units_from_node(pf.tree.root_node, pf, _FUNC_KINDS)


def _print_units_from_node(node, pf, func_kinds):
    """Recursively print per-unit metrics for stats --table."""
    from .engine.metrics import compute_function_metrics
    from .engine.ast_helpers import iter_children, node_text

    if node.type in func_kinds:
        m = compute_function_metrics(node, pf.source, pf.language)
        if not m.has_error:
            name_node = node.child_by_field_name("name")
            name = node_text(name_node, pf.source) if name_node else "<anon>"
            print(f"{pf.path.name}\t{name}\t{m.statements}\t{m.arguments}\t{m.max_indentation}\t{m.branches}\t{m.local_variables}\t{m.calls}")
        return
    for child in iter_children(node):
        _print_units_from_node(child, pf, func_kinds)


# ---------------------------------------------------------------------------
# dry
# ---------------------------------------------------------------------------

@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--filter", "filter_file", type=click.Path())
@click.option("--min-sim", type=float, default=0.7)
@click.option("--min-lines", type=int, default=5)
@click.option("--ignore", "ignore_prefixes", multiple=True)
def dry(path, filter_file, min_sim, min_lines, ignore_prefixes):
    """Show raw duplication pairs."""
    from .engine.discovery import find_source_files
    from .engine.duplication import find_duplicate_pairs
    from .engine.parser import parse_files

    root = Path(path).resolve()
    files = find_source_files(root, list(ignore_prefixes))
    parsed = parse_files(files)
    chunks = _extract_chunks_for_duplication(parsed)
    config = DuplicationConfig(min_similarity=min_sim, min_lines=min_lines)
    pairs = find_duplicate_pairs(chunks, config)

    if filter_file:
        fp = Path(filter_file).resolve()
        pairs = [p for p in pairs if p.chunk1.file.resolve() == fp or p.chunk2.file.resolve() == fp]

    for p in pairs:
        pct = int(p.similarity * 100)
        print(f"{p.chunk1.file}:{p.chunk1.start_line} <-> {p.chunk2.file}:{p.chunk2.start_line} ({pct}% similar)")
    if not pairs:
        print("No duplicates found.")


# ---------------------------------------------------------------------------
# clamp
# ---------------------------------------------------------------------------

@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--ignore", "ignore_prefixes", multiple=True)
def clamp(path, ignore_prefixes):
    """Generate .kissconfig from current codebase stats (p95 clamped)."""
    from .engine.discovery import find_source_files
    from .engine.metrics import compute_file_metrics
    from .engine.parser import parse_files
    from .output import percentile

    root = Path(path).resolve()
    files = find_source_files(root, list(ignore_prefixes))
    parsed = parse_files(files)
    values: dict[str, list[int]] = {k: [] for k in _STATS_METRICS}

    for pf in parsed:
        fm = compute_file_metrics(pf)
        values["statements_per_file"].append(fm.statements)
        values["functions_per_file"].append(fm.functions)
        values["interface_types_per_file"].append(fm.interface_types)
        values["concrete_types_per_file"].append(fm.concrete_types)
        values["imported_names_per_file"].append(fm.imports)
        _collect_func_class_metrics(pf.tree.root_node, pf.source, pf.language, values)

    print("# Generated by lemon clamp")
    print("[thresholds]")
    for key in _STATS_METRICS:
        vals = sorted(values.get(key, []))
        if vals:
            print(f"{key} = {max(percentile(vals, 95), 1)}")


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

@main.command()
@click.option("--lang", type=click.Choice(["python", "php", "javascript", "typescript"]))
@click.option("--defaults", "use_defaults", is_flag=True)
@click.option("--config", "config_path", type=click.Path())
def rules(lang, use_defaults, config_path):
    """Dump RULE: and DEFINITION: lines."""
    from .rules import print_definitions, print_rules

    cfg_path = Path(config_path) if config_path else None
    gate = GateConfig() if use_defaults else GateConfig.load(cfg_path)
    print_definitions()
    if lang:
        l = Language[lang.upper()]
        cfg = Config.for_language(l) if use_defaults else Config.load(l, cfg_path)
        print_rules(l, cfg, gate)
    else:
        for l in Language:
            cfg = Config.for_language(l) if use_defaults else Config.load(l, cfg_path)
            print_rules(l, cfg, gate)


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@main.command()
@click.option("--config", "config_path", type=click.Path())
@click.option("--defaults", "use_defaults", is_flag=True)
def config(config_path, use_defaults):
    """Show effective configuration."""
    from .rules import print_config

    cfg_path = Path(config_path) if config_path else None
    gate = GateConfig() if use_defaults else GateConfig.load(cfg_path)
    configs = {l: Config.for_language(l) if use_defaults else Config.load(l, cfg_path) for l in Language}
    print_config(configs, gate, config_path, use_defaults)


# ---------------------------------------------------------------------------
# shrink
# ---------------------------------------------------------------------------

@main.group()
def shrink():
    """Constrained metric minimization."""
    pass


main.add_command(shrink)


def _compute_current_metrics(path, ignore_prefixes):
    """Compute current GlobalMetrics for the codebase."""
    from .engine.discovery import find_source_files
    from .engine.graph import build_dependency_graph
    from .engine.metrics import compute_file_metrics
    from .engine.parser import parse_files
    from .engine.units import count_code_units

    root = Path(path).resolve()
    files = find_source_files(root, list(ignore_prefixes))
    parsed = parse_files(files)
    graph = build_dependency_graph(parsed, root)
    return GlobalMetrics(
        files=len(parsed),
        code_units=sum(count_code_units(pf) for pf in parsed),
        statements=sum(compute_file_metrics(pf).statements for pf in parsed),
        graph_nodes=graph.number_of_nodes(),
        graph_edges=graph.number_of_edges(),
    )


@shrink.command("start")
@click.argument("target")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--ignore", "ignore_prefixes", multiple=True)
def shrink_start(target, path, ignore_prefixes):
    """Start a shrink session: lemon shrink start statements=100."""
    from .engine.shrink import start_shrink

    current = _compute_current_metrics(path, ignore_prefixes)
    try:
        state = start_shrink(target, current)
        print(f"Shrink started. Target: {state.target.value}={state.target_value}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@shrink.command("check")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--ignore", "ignore_prefixes", multiple=True)
def shrink_check(path, ignore_prefixes):
    """Check shrink constraints."""
    from .engine.shrink import check_shrink, load_state

    state = load_state()
    if state is None:
        print("Error: No shrink session found.", file=sys.stderr)
        sys.exit(1)

    current = _compute_current_metrics(path, ignore_prefixes)
    violations = check_shrink(state, current)
    if violations:
        for sv in violations:
            print(str(sv))
        sys.exit(1)
    else:
        print("Shrink constraints satisfied.")


# ---------------------------------------------------------------------------
# viz
# ---------------------------------------------------------------------------

@main.command()
@click.argument("out", type=click.Path())
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--lang", type=click.Choice(["python", "php", "javascript", "typescript"]))
@click.option("--ignore", "ignore_prefixes", multiple=True)
def viz(out, path, lang, ignore_prefixes):
    """Generate dependency graph visualization (.dot, .mmd, .md)."""
    from .engine.graph import build_dependency_graph
    from .engine.viz import write_viz

    lang_filter = Language[lang.upper()] if lang else None
    root, parsed = _discover_and_parse(path, ignore_prefixes, lang_filter, False)
    _progress("Building dependency graph …")
    graph = build_dependency_graph(parsed, root)
    out_path = Path(out)
    _progress(f"Writing {out_path} …")
    write_viz(graph, out_path)
    print(f"Graph written to {out_path} ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges)")


# ---------------------------------------------------------------------------
# show-tests
# ---------------------------------------------------------------------------

@main.command("show-tests")
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--lang", type=click.Choice(["python", "php", "javascript", "typescript"]))
@click.option("--untested", is_flag=True, help="Also show untested definitions.")
@click.option("--ignore", "ignore_prefixes", multiple=True)
def show_tests(path, lang, untested, ignore_prefixes):
    """Show test coverage per definition."""
    from .engine.graph import build_dependency_graph
    from .engine.test_refs import analyze_test_refs

    lang_filter = Language[lang.upper()] if lang else None
    root, parsed = _discover_and_parse(path, ignore_prefixes, lang_filter, False)
    _progress("Building dependency graph …")
    graph = build_dependency_graph(parsed, root)
    _progress("Analyzing test references …")
    analysis = analyze_test_refs(parsed, graph)

    unreferenced_set = {(d.file, d.name, d.line) for d in analysis.unreferenced}

    for d in sorted(analysis.definitions, key=lambda x: (str(x.file), x.line)):
        key = (d.file, d.name, d.line)
        if key in unreferenced_set:
            if untested:
                print(f"UNTESTED:{d.file}:{d.line}:{d.name}")
        else:
            print(f"TEST:{d.file}:{d.name}")

