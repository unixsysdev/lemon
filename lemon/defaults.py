"""Default thresholds per language — matching Rust kiss defaults exactly."""

from __future__ import annotations

import sys

NOT_APPLICABLE: int = sys.maxsize


# ---------------------------------------------------------------------------
# Python defaults (from defaults.rs python module)
# ---------------------------------------------------------------------------

PYTHON = {
    "imported_names_per_file": 20,
    "statements_per_file": 400,
    "functions_per_file": 30,
    "interface_types_per_file": 3,
    "concrete_types_per_file": 10,
    "statements_per_function": 35,
    "arguments_per_function": 7,
    "arguments_positional": 5,
    "arguments_keyword_only": 6,
    "max_indentation_depth": 4,
    "branches_per_function": 10,
    "local_variables_per_function": 20,
    "methods_per_class": 20,
    "returns_per_function": 5,
    "return_values_per_function": 3,
    "nested_function_depth": 2,
    "statements_per_try_block": 5,
    "boolean_parameters": 1,
    "annotations_per_function": 3,  # decorators
    "calls_per_function": 50,
    "cycle_size": 3,
    "indirect_dependencies": 100,
    "dependency_depth": 7,
}


# ---------------------------------------------------------------------------
# PHP defaults (new — tuned to PHP idioms)
# ---------------------------------------------------------------------------

PHP = {
    "imported_names_per_file": 20,
    "statements_per_file": 400,
    "functions_per_file": 30,
    "interface_types_per_file": 3,
    "concrete_types_per_file": 10,
    "statements_per_function": 35,
    "arguments_per_function": 7,
    "arguments_positional": NOT_APPLICABLE,
    "arguments_keyword_only": NOT_APPLICABLE,
    "max_indentation_depth": 4,
    "branches_per_function": 10,
    "local_variables_per_function": 20,
    "methods_per_class": 20,
    "returns_per_function": 5,
    "return_values_per_function": NOT_APPLICABLE,
    "nested_function_depth": 2,
    "statements_per_try_block": 5,
    "boolean_parameters": 2,
    "annotations_per_function": 4,  # PHP attributes
    "calls_per_function": 50,
    "cycle_size": 3,
    "indirect_dependencies": 100,
    "dependency_depth": 7,
}


# ---------------------------------------------------------------------------
# JavaScript defaults (new — tuned to JS/Node idioms)
# ---------------------------------------------------------------------------

JAVASCRIPT = {
    "imported_names_per_file": 20,
    "statements_per_file": 400,
    "functions_per_file": 30,
    "interface_types_per_file": 3,
    "concrete_types_per_file": 10,
    "statements_per_function": 35,
    "arguments_per_function": 7,
    "arguments_positional": NOT_APPLICABLE,
    "arguments_keyword_only": NOT_APPLICABLE,
    "max_indentation_depth": 4,
    "branches_per_function": 10,
    "local_variables_per_function": 20,
    "methods_per_class": 20,
    "returns_per_function": 5,
    "return_values_per_function": NOT_APPLICABLE,
    "nested_function_depth": 2,
    "statements_per_try_block": 5,
    "boolean_parameters": 2,
    "annotations_per_function": NOT_APPLICABLE,  # JS has no decorators in standard
    "calls_per_function": 50,
    "cycle_size": 3,
    "indirect_dependencies": 100,
    "dependency_depth": 7,
}


# ---------------------------------------------------------------------------
# TypeScript defaults (new — tuned to TS idioms)
# ---------------------------------------------------------------------------

TYPESCRIPT = {
    "imported_names_per_file": 20,
    "statements_per_file": 400,
    "functions_per_file": 30,
    "interface_types_per_file": 5,
    "concrete_types_per_file": 10,
    "statements_per_function": 35,
    "arguments_per_function": 7,
    "arguments_positional": NOT_APPLICABLE,
    "arguments_keyword_only": NOT_APPLICABLE,
    "max_indentation_depth": 4,
    "branches_per_function": 10,
    "local_variables_per_function": 20,
    "methods_per_class": 20,
    "returns_per_function": 5,
    "return_values_per_function": NOT_APPLICABLE,
    "nested_function_depth": 2,
    "statements_per_try_block": 5,
    "boolean_parameters": 2,
    "annotations_per_function": 4,  # TS decorators
    "calls_per_function": 50,
    "cycle_size": 3,
    "indirect_dependencies": 100,
    "dependency_depth": 7,
}


# ---------------------------------------------------------------------------
# Graph defaults
# ---------------------------------------------------------------------------

GRAPH = {
    "cycle_size": 3,
}


# ---------------------------------------------------------------------------
# Duplication defaults
# ---------------------------------------------------------------------------

DUPLICATION = {
    "min_similarity": 0.7,
}


# ---------------------------------------------------------------------------
# Gate defaults
# ---------------------------------------------------------------------------

GATE = {
    "test_coverage_threshold": 90,
    "min_similarity": 0.7,
    "duplication_enabled": True,
    "orphan_module_enabled": True,
}


# ---------------------------------------------------------------------------
# Language → defaults mapping
# ---------------------------------------------------------------------------

LANGUAGE_DEFAULTS: dict[str, dict] = {
    "python": PYTHON,
    "php": PHP,
    "javascript": JAVASCRIPT,
    "typescript": TYPESCRIPT,
}
