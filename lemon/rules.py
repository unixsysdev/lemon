"""Rule definitions and machine-readable output — matching rules.rs + rule_defs.rs."""

from __future__ import annotations

from .config import Config, GateConfig
from .models import Language


# ---------------------------------------------------------------------------
# DEFINITION lines
# ---------------------------------------------------------------------------

DEFINITIONS = [
    "DEFINITION: [file] A source file included in analysis.",
    "DEFINITION: [code_unit] A named unit of code within a file (module, class/type, function, or method) that kiss can attach metrics/violations to.",
    "DEFINITION: [statement] A statement inside a function/method body (not an import or a class/function signature).",
    "DEFINITION: [graph_node] A module (file) in the dependency graph.",
    "DEFINITION: [graph_edge] A dependency between two modules (file A depends on file B via imports/uses/mod declarations).",
]


# ---------------------------------------------------------------------------
# Rule specs
# ---------------------------------------------------------------------------

class _RuleSpec:
    def __init__(self, metric: str, op: str, threshold_fn, description: str):
        self.metric = metric
        self.op = op
        self.threshold_fn = threshold_fn  # (Config, GateConfig) -> int|float
        self.description = description


def _shared_rules(lang_name: str) -> list[_RuleSpec]:
    """Rules common to all languages."""
    return [
        _RuleSpec("statements_per_function", "<",
                  lambda c, g: c.statements_per_function,
                  f"statements_per_function is the maximum number of statements in a {lang_name} function/method body."),
        _RuleSpec("max_indentation_depth", "<",
                  lambda c, g: c.max_indentation_depth,
                  f"max_indentation_depth is the maximum indentation depth within a {lang_name} function/method body."),
        _RuleSpec("branches_per_function", "<",
                  lambda c, g: c.branches_per_function,
                  f"branches_per_function is the number of branch statements in a {lang_name} function."),
        _RuleSpec("local_variables_per_function", "<",
                  lambda c, g: c.local_variables_per_function,
                  f"local_variables_per_function is the number of distinct local variables in a {lang_name} function."),
        _RuleSpec("returns_per_function", "<",
                  lambda c, g: c.returns_per_function,
                  f"returns_per_function is the number of return statements in a {lang_name} function."),
        _RuleSpec("nested_function_depth", "<",
                  lambda c, g: c.nested_function_depth,
                  f"nested_function_depth is the maximum nesting depth of function definitions inside a {lang_name} function."),
        _RuleSpec("boolean_parameters", "<",
                  lambda c, g: c.boolean_parameters,
                  f"boolean_parameters is the maximum number of boolean default parameters in a {lang_name} function."),
        _RuleSpec("calls_per_function", "<",
                  lambda c, g: c.calls_per_function,
                  f"calls_per_function is the maximum number of function/method calls in a {lang_name} function."),
        _RuleSpec("methods_per_class", "<",
                  lambda c, g: c.methods_per_class,
                  f"methods_per_class is the maximum number of methods defined on a {lang_name} class."),
        _RuleSpec("statements_per_file", "<",
                  lambda c, g: c.statements_per_file,
                  f"statements_per_file is the maximum number of statements inside function/method bodies in a {lang_name} file."),
        _RuleSpec("functions_per_file", "<",
                  lambda c, g: c.functions_per_file,
                  f"functions_per_file is the maximum number of functions/methods defined in a {lang_name} file."),
        _RuleSpec("interface_types_per_file", "<",
                  lambda c, g: c.interface_types_per_file,
                  f"interface_types_per_file is the maximum number of interface types defined in a {lang_name} file."),
        _RuleSpec("concrete_types_per_file", "<",
                  lambda c, g: c.concrete_types_per_file,
                  f"concrete_types_per_file is the maximum number of concrete types defined in a {lang_name} file."),
        _RuleSpec("imported_names_per_file", "<",
                  lambda c, g: c.imported_names_per_file,
                  f"imported_names_per_file is the maximum number of imported names in a {lang_name} file."),
        _RuleSpec("cycle_size", "<",
                  lambda c, g: c.cycle_size,
                  "cycle_size is the maximum allowed number of modules participating in an import cycle."),
        _RuleSpec("indirect_dependencies", "<",
                  lambda c, g: c.indirect_dependencies,
                  "indirect_dependencies is the number of modules reachable only through other modules."),
        _RuleSpec("dependency_depth", "<",
                  lambda c, g: c.dependency_depth,
                  "dependency_depth is the maximum length of an import chain in the dependency graph."),
        _RuleSpec("test_coverage_threshold", ">=",
                  lambda c, g: g.test_coverage_threshold,
                  "test_coverage_threshold is the minimum percent of code units whose names must appear in a test file."),
        _RuleSpec("min_similarity", ">=",
                  lambda c, g: g.min_similarity,
                  "min_similarity is the minimum similarity required to report duplicate code."),
    ]


def _python_extra_rules() -> list[_RuleSpec]:
    return [
        _RuleSpec("positional_args", "<",
                  lambda c, g: c.arguments_positional,
                  "positional_args is the maximum number of positional parameters in a Python function definition."),
        _RuleSpec("keyword_only_args", "<",
                  lambda c, g: c.arguments_keyword_only,
                  "keyword_only_args is the maximum number of keyword-only parameters in a Python function definition."),
        _RuleSpec("return_values_per_function", "<",
                  lambda c, g: c.return_values_per_function,
                  "return_values_per_function is the maximum number of values returned by a single return in a Python function."),
        _RuleSpec("statements_per_try_block", "<",
                  lambda c, g: c.statements_per_try_block,
                  "statements_per_try_block is the maximum number of statements inside any try block in a Python function."),
        _RuleSpec("decorators_per_function", "<",
                  lambda c, g: c.annotations_per_function,
                  "decorators_per_function is the maximum number of decorators applied to a Python function."),
    ]


def get_rules_for_language(lang: Language) -> list[_RuleSpec]:
    """Get all rules applicable to a language."""
    rules = _shared_rules(lang.name.capitalize())
    if lang == Language.PYTHON:
        # Insert Python-specific rules after statements_per_function
        py_extra = _python_extra_rules()
        rules = [rules[0]] + py_extra[:2] + rules[1:]  # Insert positional_args, keyword_only_args
        # Add remaining Python-specific rules
        rules.extend(py_extra[2:])
    elif lang in (Language.PHP, Language.TYPESCRIPT):
        # Add language-specific rules
        rules.insert(1, _RuleSpec(
            "arguments_per_function", "<",
            lambda c, g: c.arguments_per_function,
            f"arguments_per_function is the maximum number of parameters in a {lang.name.capitalize()} function."))
    elif lang == Language.JAVASCRIPT:
        rules.insert(1, _RuleSpec(
            "arguments_per_function", "<",
            lambda c, g: c.arguments_per_function,
            "arguments_per_function is the maximum number of parameters in a JavaScript function."))
    return rules


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_definitions() -> None:
    """Print DEFINITION: lines."""
    for d in DEFINITIONS:
        print(d)


def print_rules(lang: Language, config: Config, gate: GateConfig) -> None:
    """Print RULE: lines for a language."""
    lang_name = lang.name.capitalize()
    for spec in get_rules_for_language(lang):
        threshold_val = spec.threshold_fn(config, gate)
        if isinstance(threshold_val, float):
            formatted = f"{threshold_val:.2f}"
        else:
            formatted = str(threshold_val)
        print(f"RULE: [{lang_name}] [{spec.metric} {spec.op} {formatted}] {spec.description}")


def print_config(configs: dict[Language, Config], gate: GateConfig,
                 config_path: str | None = None, use_defaults: bool = False) -> None:
    """Print effective configuration."""
    print("# Effective configuration")
    if use_defaults:
        print("# Source: built-in defaults")
    elif config_path:
        print(f"# Source: {config_path}")
    else:
        print("# Source: .kissconfig or ~/.kissconfig (merged)")

    print("\n[gate]")
    print(f"test_coverage_threshold = {gate.test_coverage_threshold}")
    print(f"min_similarity = {gate.min_similarity:.2f}")
    print(f"duplication_enabled = {str(gate.duplication_enabled).lower()}")

    for lang, config in configs.items():
        print(f"\n[{lang.config_section}]")
        _print_lang_config(config, lang)


def _print_lang_config(c: Config, lang: Language) -> None:
    fields_to_print = [
        ("statements_per_function", c.statements_per_function),
        ("statements_per_file", c.statements_per_file),
        ("arguments_per_function", c.arguments_per_function),
        ("methods_per_class", c.methods_per_class),
        ("max_indentation_depth", c.max_indentation_depth),
        ("branches_per_function", c.branches_per_function),
        ("returns_per_function", c.returns_per_function),
        ("local_variables_per_function", c.local_variables_per_function),
        ("nested_function_depth", c.nested_function_depth),
        ("interface_types_per_file", c.interface_types_per_file),
        ("concrete_types_per_file", c.concrete_types_per_file),
        ("imported_names_per_file", c.imported_names_per_file),
        ("boolean_parameters", c.boolean_parameters),
        ("calls_per_function", c.calls_per_function),
        ("cycle_size", c.cycle_size),
        ("indirect_dependencies", c.indirect_dependencies),
        ("dependency_depth", c.dependency_depth),
    ]
    if lang == Language.PYTHON:
        fields_to_print.insert(2, ("positional_args", c.arguments_positional))
        fields_to_print.insert(3, ("keyword_only_args", c.arguments_keyword_only))
        fields_to_print.append(("statements_per_try_block", c.statements_per_try_block))
        fields_to_print.append(("decorators_per_function", c.annotations_per_function))

    import sys
    NOT_APPLICABLE = sys.maxsize
    for name, val in fields_to_print:
        if val < NOT_APPLICABLE:
            print(f"{name} = {val}")
