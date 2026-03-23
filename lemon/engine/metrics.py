"""Metric computation from Tree-Sitter parse trees — language-agnostic via query captures."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import Config
from ..models import (
    ClassMetrics,
    FileMetrics,
    FunctionMetrics,
    Language,
    ParsedFile,
    Violation,
    ViolationBuilder,
)


# ---------------------------------------------------------------------------
# Helpers — AST traversal utilities
# ---------------------------------------------------------------------------

# Cache to avoid re-encoding source strings on every call
_source_bytes_cache: dict[int, bytes] = {}


def _ensure_bytes(source: str) -> bytes:
    """Get or cache the UTF-8 bytes for a source string."""
    sid = id(source)
    if sid not in _source_bytes_cache:
        _source_bytes_cache[sid] = source.encode("utf-8")
    return _source_bytes_cache[sid]


def _node_text(node, source: str) -> str:
    """Extract text from a tree-sitter node using byte offsets."""
    b = _ensure_bytes(source)
    return b[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _child_by_field(node, field: str, source: str) -> str | None:
    child = node.child_by_field_name(field)
    if child is None:
        return None
    return _node_text(child, source)


def _count_children_of_kind(node, kinds: set[str]) -> int:
    count = 0
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            if cursor.node.type in kinds:
                count += 1
            if not cursor.goto_next_sibling():
                break
    return count


def _count_descendants_of_kind(node, kinds: set[str]) -> int:
    """Count all descendants (recursive) matching given node kinds."""
    count = 0
    cursor = node.walk()

    def _walk():
        nonlocal count
        if cursor.node.type in kinds:
            count += 1
        if cursor.goto_first_child():
            while True:
                _walk()
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()

    _walk()
    return count


def _max_depth(node, depth: int = 0) -> int:
    """Compute maximum indentation depth of a node tree."""
    # These node kinds increase indentation depth
    _DEPTH_NODES = {
        "if_statement", "elif_clause", "else_clause",
        "for_statement", "while_statement", "for_in_statement",
        "with_statement", "try_statement", "except_clause",
        "match_statement", "case_clause",
        # PHP
        "if_statement", "else_if_clause", "else_clause",
        "for_statement", "foreach_statement", "while_statement",
        "do_statement", "switch_statement", "case_statement",
        "try_statement", "catch_clause",
        # JS/TS
        "if_statement", "else_clause",
        "for_statement", "for_in_statement", "while_statement",
        "do_statement", "switch_case", "try_statement", "catch_clause",
    }
    max_d = depth
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            child = cursor.node
            child_depth = depth + 1 if child.type in _DEPTH_NODES else depth
            max_d = max(max_d, _max_depth(child, child_depth))
            if not cursor.goto_next_sibling():
                break
    return max_d


def _nested_func_depth(node, current: int = 0) -> int:
    """Compute maximum nested function/closure depth within a function."""
    _FUNC_KINDS = {
        "function_definition", "async_function_definition",  # Python
        "function_definition", "anonymous_function_creation_expression",  # PHP
        "function_declaration", "arrow_function",
        "generator_function_declaration",  # JS/TS
    }
    max_d = current
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            child = cursor.node
            if child.type in _FUNC_KINDS:
                max_d = max(max_d, _nested_func_depth(child, current + 1))
            else:
                max_d = max(max_d, _nested_func_depth(child, current))
            if not cursor.goto_next_sibling():
                break
    return max_d


def _count_statements(node) -> int:
    """Count statements in a block/body node."""
    _STMT_KINDS = {
        # Python
        "expression_statement", "return_statement", "delete_statement",
        "raise_statement", "pass_statement", "break_statement",
        "continue_statement", "assert_statement", "global_statement",
        "nonlocal_statement", "assignment", "augmented_assignment",
        # PHP
        "expression_statement", "return_statement", "echo_statement",
        "throw_expression", "break_statement", "continue_statement",
        "assignment_expression",
        # JS/TS
        "expression_statement", "return_statement", "throw_statement",
        "break_statement", "continue_statement", "variable_declaration",
    }
    count = 0
    cursor = node.walk()

    def _walk():
        nonlocal count
        if cursor.node.type in _STMT_KINDS:
            count += 1
        # Don't recurse into nested function/class definitions
        if cursor.node.type in {
            "function_definition", "async_function_definition",
            "class_definition", "function_declaration",
            "generator_function_declaration", "arrow_function",
            "class_declaration", "method_declaration", "method_definition",
        }:
            return
        if cursor.goto_first_child():
            while True:
                _walk()
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()

    _walk()
    return count


def _count_local_vars(body_node, source: str) -> int:
    """Count distinct local variable names assigned in a function body."""
    names: set[str] = set()
    _visit_for_assignments(body_node, source, names)
    return len(names)


def _visit_for_assignments(node, source: str, names: set[str]) -> None:
    """Recursively collect assignment target names, skipping nested functions."""
    _SKIP = {
        "function_definition", "async_function_definition",
        "function_declaration", "generator_function_declaration",
        "arrow_function", "class_definition", "class_declaration",
        "method_declaration", "method_definition",
    }
    if node.type in _SKIP:
        return
    _try_extract_assignment_name(node, source, names)
    for child in _node_children_iter(node):
        _visit_for_assignments(child, source, names)


# Maps (node_type) -> (field_name, expected_child_type)
_ASSIGN_PATTERNS: dict[str, tuple[str, str]] = {
    "assignment": ("left", "identifier"),
    "augmented_assignment": ("left", "identifier"),
    "assignment_expression": ("left", "identifier"),  # JS/TS + PHP variable_name
    "variable_declarator": ("name", "identifier"),
}


def _try_extract_assignment_name(node, source, names):
    """Extract assigned variable name if node is an assignment."""
    pattern = _ASSIGN_PATTERNS.get(node.type)
    if not pattern:
        return
    field_name, expected_type = pattern
    child = node.child_by_field_name(field_name)
    if not child:
        return
    # Accept both identifier and variable_name (PHP)
    if child.type in (expected_type, "variable_name"):
        names.add(_node_text(child, source))


def _count_return_values(node) -> int:
    """Max return values in any return statement (tuple returns in Python)."""
    max_vals = 0
    cursor = node.walk()

    def _walk():
        nonlocal max_vals
        n = cursor.node
        if n.type == "return_statement":
            # Check for tuple return (Python)
            ret_child = n.child_by_field_name("value") or (
                n.named_child(0) if n.named_child_count > 0 else None
            )
            if ret_child and ret_child.type in ("tuple", "expression_list"):
                max_vals = max(max_vals, ret_child.named_child_count)
            elif ret_child:
                max_vals = max(max_vals, 1)
            return
        # Don't recurse into nested functions
        if n.type in {
            "function_definition", "async_function_definition",
            "function_declaration", "arrow_function",
            "generator_function_declaration",
        }:
            return
        if cursor.goto_first_child():
            while True:
                _walk()
                if not cursor.goto_next_sibling():
                    break
            cursor.goto_parent()

    _walk()
    return max_vals


# Maps param node type -> field name that holds the default value
_BOOL_DEFAULT_FIELDS: dict[str, str] = {
    "default_parameter": "value",
    "typed_default_parameter": "value",
    "simple_parameter": "default_value",
    "required_parameter": "value",
    "optional_parameter": "value",
}


def _count_boolean_params(params_node, source: str, lang: Language) -> int:
    """Count parameters with boolean default values."""
    count = 0
    for child in _node_children_iter(params_node):
        field = _BOOL_DEFAULT_FIELDS.get(child.type)
        if not field:
            continue
        default = child.child_by_field_name(field)
        if default and _node_text(default, source).lower() in ("true", "false"):
            count += 1
    return count


_PYTHON_PARAM_KINDS = {
    "identifier", "typed_parameter", "default_parameter",
    "typed_default_parameter",
}
_PYTHON_SPLAT_KINDS = {"list_splat_pattern", "dictionary_splat_pattern"}
_OTHER_PARAM_KINDS = {
    "simple_parameter", "variadic_parameter",
    "required_parameter", "optional_parameter",
    "formal_parameter",
}


def _count_params(params_node, source: str, lang: Language) -> tuple[int, int, int]:
    """Count (total, positional, keyword_only) parameters."""
    if params_node is None:
        return 0, 0, 0

    total = 0
    positional = 0
    keyword_only = 0
    seen_star = False

    for n in _node_children_iter(params_node):
        kind = n.type
        if kind in _PYTHON_SPLAT_KINDS:
            if kind == "list_splat_pattern":
                seen_star = True
        elif kind == "*":
            seen_star = True
        elif kind in _PYTHON_PARAM_KINDS:
            if kind == "identifier" and _node_text(n, source) == "self":
                continue
            total, positional, keyword_only = _tally_param(
                total, positional, keyword_only, seen_star)
        elif kind in _OTHER_PARAM_KINDS:
            total += 1
            positional += 1

    return total, positional, keyword_only


def _tally_param(total, positional, keyword_only, seen_star):
    """Classify a parameter as positional or keyword-only."""
    total += 1
    if seen_star:
        keyword_only += 1
    else:
        positional += 1
    return total, positional, keyword_only


def _max_try_block_stmts(body_node) -> int:
    """Max statements in any try block body within this function."""
    max_stmts = 0
    _TRY_KINDS = {"try_statement"}

    def _walk(node):
        nonlocal max_stmts
        if node.type in _TRY_KINDS:
            body = node.child_by_field_name("body")
            if body:
                max_stmts = max(max_stmts, _count_statements(body))
        # Don't recurse into nested functions
        if node.type in {
            "function_definition", "async_function_definition",
            "function_declaration", "arrow_function",
            "generator_function_declaration",
            "method_declaration", "method_definition",
        }:
            return
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                _walk(cursor.node)
                if not cursor.goto_next_sibling():
                    break

    _walk(body_node)
    return max_stmts


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def compute_function_metrics(func_node, source: str, lang: Language) -> FunctionMetrics:
    """Compute all function-level metrics from a function AST node."""
    body = func_node.child_by_field_name("body")
    params = func_node.child_by_field_name("parameters")

    if body is None:
        return FunctionMetrics(has_error=True)

    total_args, pos_args, kw_args = _count_params(params, source, lang)
    bool_params = _count_boolean_params(params, source, lang) if params else 0

    # Count decorators/attributes
    decorators = 0
    parent = func_node.parent
    if parent and parent.type == "decorated_definition":
        # Python: decorators are siblings in the decorated_definition
        cursor = parent.walk()
        if cursor.goto_first_child():
            while True:
                if cursor.node.type == "decorator":
                    decorators += 1
                if not cursor.goto_next_sibling():
                    break
    elif parent and parent.type == "attribute_group":
        # PHP: attribute groups
        decorators = 1

    # Branch kinds per language
    _BRANCH_KINDS = {
        "if_statement", "elif_clause", "case_clause",  # Python
        "else_if_clause", "case_statement",  # PHP
        "switch_case",  # JS/TS
    }

    _RETURN_KINDS = {"return_statement"}
    _CALL_KINDS = {
        "call",  # Python
        "function_call_expression", "member_call_expression",
        "scoped_call_expression",  # PHP
        "call_expression", "new_expression",  # JS/TS
    }

    return FunctionMetrics(
        statements=_count_statements(body),
        arguments=total_args,
        arguments_positional=pos_args,
        arguments_keyword_only=kw_args,
        max_indentation=_max_depth(body),
        nested_function_depth=_nested_func_depth(body),
        returns=_count_descendants_of_kind(body, _RETURN_KINDS),
        branches=_count_descendants_of_kind(body, _BRANCH_KINDS),
        local_variables=_count_local_vars(body, source),
        max_try_block_statements=_max_try_block_stmts(body),
        boolean_parameters=bool_params,
        decorators=decorators,
        max_return_values=_count_return_values(body),
        calls=_count_descendants_of_kind(body, _CALL_KINDS),
        has_error=False,
    )


def compute_class_metrics(class_node) -> ClassMetrics:
    """Count methods in a class."""
    _METHOD_KINDS = {
        "function_definition", "async_function_definition",  # Python
        "method_declaration",  # PHP
        "method_definition",  # JS/TS
    }
    body = class_node.child_by_field_name("body")
    if body is None:
        return ClassMetrics(methods=0)
    return ClassMetrics(methods=_count_children_of_kind(body, _METHOD_KINDS))


def _is_python_interface(node, source: str, lang: Language) -> bool:
    """Check if a Python class is a Protocol or ABC."""
    if lang != Language.PYTHON:
        return False
    superclasses = node.child_by_field_name("superclasses")
    if not superclasses:
        return False
    sc_text = _node_text(superclasses, source)
    return "Protocol" in sc_text or "ABC" in sc_text


def compute_file_metrics(parsed: ParsedFile) -> FileMetrics:
    """Compute file-level metrics."""
    root = parsed.tree.root_node
    source = parsed.source
    lang = parsed.language
    counters = {"stmts": 0, "funcs": 0, "iface": 0, "concrete": 0, "imports": 0}

    _FUNC_KINDS = {
        "function_definition", "async_function_definition",
        "function_declaration", "generator_function_declaration",
        "method_declaration", "method_definition",
    }
    _CLASS_KINDS = {"class_definition", "class_declaration"}
    _INTERFACE_KINDS = {"interface_declaration"}
    _IMPORT_KINDS = {"import_statement", "import_from_statement", "namespace_use_declaration", "import_declaration"}

    def _walk_file(node):
        if node.type in _FUNC_KINDS:
            counters["funcs"] += 1
            body = node.child_by_field_name("body")
            if body:
                counters["stmts"] += _count_statements(body)
            return
        if node.type in _INTERFACE_KINDS:
            counters["iface"] += 1
            return
        if node.type in _IMPORT_KINDS:
            counters["imports"] += _count_import_names(node, source, lang)
            return
        # Go type_declaration: contains type_spec with struct_type or interface_type
        if node.type == "type_declaration":
            _walk_go_type_decl(node, counters)
            return
        if node.type in _CLASS_KINDS:
            _walk_class_for_file(node, source, lang, counters, walk_fn=_walk_file)
            return
        for child in _node_children_iter(node):
            _walk_file(child)

    _walk_file(root)
    return FileMetrics(
        statements=counters["stmts"],
        interface_types=counters["iface"],
        concrete_types=counters["concrete"],
        imports=counters["imports"],
        functions=counters["funcs"],
    )


def _walk_go_type_decl(node, counters):
    """Classify a Go type_declaration as interface or concrete (struct)."""
    for child in _node_children_iter(node):
        if child.type != "type_spec":
            continue
        for tc in _node_children_iter(child):
            if tc.type == "interface_type":
                counters["iface"] += 1
            elif tc.type == "struct_type":
                counters["concrete"] += 1


def _walk_class_for_file(node, source, lang, counters, *, walk_fn):
    """Process a class node during file metric computation."""
    if _is_python_interface(node, source, lang):
        counters["iface"] += 1
    else:
        counters["concrete"] += 1
    body = node.child_by_field_name("body")
    if body:
        for child in _node_children_iter(body):
            walk_fn(child)


def _count_import_names(node, source: str, lang: Language) -> int:
    """Count the number of imported names from an import statement."""
    if lang == Language.PYTHON:
        return _count_python_import_names(node)
    if lang == Language.PHP:
        return max(1, sum(1 for c in _node_children_iter(node)
                          if c.type in ("namespace_use_clause", "namespace_use_group_clause")))
    # JS/TS
    return max(1, sum(1 for c in _node_children_iter(node) if c.type == "import_specifier"))


def _count_python_import_names(node) -> int:
    """Count imported names from a Python import statement."""
    names = [c for c in _node_children_iter(node)
             if c.type in ("dotted_name", "aliased_import")]
    if node.type == "import_from_statement":
        return max(0, len(names) - 1)  # first dotted_name is the module
    return len(names)


def _node_children_iter(node):
    """Iterate over named children of a node."""
    cursor = node.walk()
    if cursor.goto_first_child():
        while True:
            yield cursor.node
            if not cursor.goto_next_sibling():
                break


# ---------------------------------------------------------------------------
# Violation checking — matches counts.rs logic exactly
# ---------------------------------------------------------------------------

def _viol(file: Path, line: int, name: str) -> ViolationBuilder:
    return ViolationBuilder(file).line(line).unit_name(name)


def analyze_file(parsed: ParsedFile, config: Config) -> tuple[int, list[Violation]]:
    """Analyze a parsed file and return (statement_count, violations)."""
    violations: list[Violation] = []
    file = parsed.path
    fname = file.name

    file_metrics = compute_file_metrics(parsed)
    _check_file_metrics(file_metrics, file, fname, config, violations)
    ctx = _AnalysisCtx(
        source=parsed.source, file=file,
        violations=violations, config=config, lang=parsed.language,
    )
    _analyze_node(parsed.tree.root_node, ctx)

    return file_metrics.statements, violations


def _check_file_metrics(m: FileMetrics, file: Path, fname: str,
                         cfg: Config, v: list[Violation]) -> None:
    if m.statements > cfg.statements_per_file:
        v.append(_viol(file, 1, fname).metric("statements_per_file")
                 .value(m.statements).threshold(cfg.statements_per_file)
                 .message(f"File has {m.statements} statements (threshold: {cfg.statements_per_file})")
                 .suggestion("Split into multiple modules with focused responsibilities.").build())
    if m.interface_types > cfg.interface_types_per_file:
        v.append(_viol(file, 1, fname).metric("interface_types_per_file")
                 .value(m.interface_types).threshold(cfg.interface_types_per_file)
                 .message(f"File has {m.interface_types} interface types (threshold: {cfg.interface_types_per_file})")
                 .suggestion("Move interfaces (Protocols/ABCs) into a dedicated module.").build())
    if m.concrete_types > cfg.concrete_types_per_file:
        v.append(_viol(file, 1, fname).metric("concrete_types_per_file")
                 .value(m.concrete_types).threshold(cfg.concrete_types_per_file)
                 .message(f"File has {m.concrete_types} concrete types (threshold: {cfg.concrete_types_per_file})")
                 .suggestion("Consider splitting types into separate modules by responsibility.").build())
    # Skip __init__.py for import check
    if m.imports > cfg.imported_names_per_file and fname != "__init__.py":
        v.append(_viol(file, 1, fname).metric("imported_names_per_file")
                 .value(m.imports).threshold(cfg.imported_names_per_file)
                 .message(f"File has {m.imports} imports (threshold: {cfg.imported_names_per_file})")
                 .suggestion("Consider reducing dependencies or splitting the module.").build())
    if m.functions > cfg.functions_per_file:
        v.append(_viol(file, 1, fname).metric("functions_per_file")
                 .value(m.functions).threshold(cfg.functions_per_file)
                 .message(f"File has {m.functions} functions (threshold: {cfg.functions_per_file})")
                 .suggestion("Split into multiple modules with focused responsibilities.").build())


_FUNC_NODE_KINDS = {
    "function_definition", "async_function_definition",
    "function_declaration", "generator_function_declaration",
    "method_definition", "method_declaration",
}
_CLASS_NODE_KINDS = {
    "class_definition", "class_declaration",
}


@dataclass
class _AnalysisCtx:
    """Bundles common args for recursive violation analysis."""
    source: str
    file: Path
    violations: list[Violation]
    config: Config
    lang: Language


def _analyze_node(node, ctx: _AnalysisCtx, *, inside_class: bool = False) -> None:
    if node.type in _FUNC_NODE_KINDS:
        name = _child_by_field(node, "name", ctx.source) or "<anonymous>"
        line = node.start_point[0] + 1
        m = compute_function_metrics(node, ctx.source, ctx.lang)
        if not m.has_error:
            _check_function_metrics(
                m, ctx, line=line, name=name, inside_class=inside_class)
        return

    if node.type in _CLASS_NODE_KINDS:
        _analyze_class_node(node, ctx)
        return

    for child in _node_children_iter(node):
        _analyze_node(child, ctx, inside_class=inside_class)


def _check_function_metrics(
    m: FunctionMetrics, ctx: _AnalysisCtx, *,
    line: int, name: str, inside_class: bool,
) -> None:
    ut = "Method" if inside_class else "Function"
    NOT_APPLICABLE = sys.maxsize

    def _chk(mval, cval, metric, label, sug):
        if cval < NOT_APPLICABLE and mval > cval:
            ctx.violations.append(
                _viol(ctx.file, line, name).metric(metric)
                .value(mval).threshold(cval)
                .message(f"{ut} '{name}' has {mval} {label} (threshold: {cval})")
                .suggestion(sug).build())

    cfg = ctx.config
    _chk(m.statements, cfg.statements_per_function, "statements_per_function",
         "statements", "Break into smaller, focused functions.")
    if not inside_class and cfg.arguments_positional < NOT_APPLICABLE:
        if m.arguments_positional > cfg.arguments_positional:
            ctx.violations.append(
                _viol(ctx.file, line, name).metric("positional_args")
                .value(m.arguments_positional).threshold(cfg.arguments_positional)
                .message(f"Function '{name}' has {m.arguments_positional} positional arguments (threshold: {cfg.arguments_positional})")
                .suggestion("Consider using keyword-only arguments, a config object, or the builder pattern.").build())
    _chk(m.arguments_keyword_only, cfg.arguments_keyword_only, "keyword_only_args",
         "keyword-only arguments", "Consider grouping related parameters into a config object.")
    _chk(m.max_indentation, cfg.max_indentation_depth, "max_indentation_depth",
         "indentation depth", "Extract nested logic into helper functions or use early returns.")
    _chk(m.nested_function_depth, cfg.nested_function_depth, "nested_function_depth",
         "nested functions", "Move nested functions to module level or use classes.")
    _chk(m.branches, cfg.branches_per_function, "branches_per_function",
         "branches", "Consider using polymorphism, lookup tables, or the strategy pattern.")
    _chk(m.local_variables, cfg.local_variables_per_function, "local_variables_per_function",
         "local variables", "Extract related variables into a data class or split the function.")
    _chk(m.max_try_block_statements, cfg.statements_per_try_block, "statements_per_try_block",
         "statements in try block", "Keep try blocks narrow: wrap only the code that can raise the specific exception.")
    _chk(m.boolean_parameters, cfg.boolean_parameters, "boolean_parameters",
         "boolean parameters", "Use keyword-only arguments, an enum, or separate functions instead of boolean flags.")
    _chk(m.decorators, cfg.annotations_per_function, "decorators_per_function",
         "decorators", "Consider consolidating decorators or simplifying the function's responsibilities.")
    if cfg.return_values_per_function < NOT_APPLICABLE and m.max_return_values > cfg.return_values_per_function:
        ctx.violations.append(
            _viol(ctx.file, line, name).metric("return_values_per_function")
            .value(m.max_return_values).threshold(cfg.return_values_per_function)
            .message(f"{ut} '{name}' has {m.max_return_values} return values (threshold: {cfg.return_values_per_function})")
            .suggestion("Consider returning a named tuple, dataclass, or structured object instead of multiple values.").build())
    _chk(m.calls, cfg.calls_per_function, "calls_per_function",
         "calls", "Extract some calls into helper functions to reduce coordination complexity.")


def _analyze_class_node(node, ctx: _AnalysisCtx) -> None:
    name = _child_by_field(node, "name", ctx.source) or "<anonymous>"
    line = node.start_point[0] + 1
    m = compute_class_metrics(node)

    if m.methods > ctx.config.methods_per_class:
        ctx.violations.append(
            _viol(ctx.file, line, name).metric("methods_per_class")
            .value(m.methods).threshold(ctx.config.methods_per_class)
            .message(f"Class '{name}' has {m.methods} methods (threshold: {ctx.config.methods_per_class})")
            .suggestion("Consider extracting groups of related methods into separate classes.").build()
        )

    body = node.child_by_field_name("body")
    if body:
        for child in _node_children_iter(body):
            _analyze_node(child, ctx, inside_class=True)
