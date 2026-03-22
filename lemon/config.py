"""Configuration system — .kissconfig TOML parsing with full Rust parity."""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import defaults
from .models import Language


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Per-language metric thresholds — matches Rust Config struct exactly."""
    statements_per_function: int = 0
    methods_per_class: int = 0
    statements_per_file: int = 0
    functions_per_file: int = 0
    arguments_per_function: int = 0
    arguments_positional: int = 0
    arguments_keyword_only: int = 0
    max_indentation_depth: int = 0
    interface_types_per_file: int = 0
    concrete_types_per_file: int = 0
    nested_function_depth: int = 0
    returns_per_function: int = 0
    return_values_per_function: int = 0
    branches_per_function: int = 0
    local_variables_per_function: int = 0
    imported_names_per_file: int = 0
    statements_per_try_block: int = 0
    boolean_parameters: int = 0
    annotations_per_function: int = 0
    calls_per_function: int = 0
    cycle_size: int = 0
    indirect_dependencies: int = 0
    dependency_depth: int = 0

    @classmethod
    def for_language(cls, lang: Language) -> "Config":
        d = defaults.LANGUAGE_DEFAULTS.get(lang.config_section, defaults.PYTHON)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def python_defaults(cls) -> "Config":
        return cls.for_language(Language.PYTHON)

    @classmethod
    def load(cls, lang: Language, config_path: Optional[Path] = None) -> "Config":
        config = cls.for_language(lang)
        # Chain: ~/.kissconfig -> ./.kissconfig -> explicit path
        home = Path.home() / ".kissconfig"
        if home.is_file():
            config._merge_from_file(home, lang)
        local = Path(".kissconfig")
        if local.is_file():
            config._merge_from_file(local, lang)
        if config_path and config_path.is_file():
            config._merge_from_file(config_path, lang)
        return config

    def _merge_from_file(self, path: Path, lang: Language) -> None:
        try:
            content = path.read_text()
            self._merge_from_toml(content, lang)
        except Exception as e:
            print(f"Warning: Failed to read config {path}: {e}", file=sys.stderr)

    def _merge_from_toml(self, content: str, lang: Language) -> None:
        try:
            table = tomllib.loads(content)
        except Exception as e:
            print(f"Warning: Failed to parse config: {e}", file=sys.stderr)
            return
        # Validate sections
        valid_sections = {"python", "rust", "php", "javascript", "typescript",
                          "shared", "thresholds", "gate"}
        for key in table:
            if key not in valid_sections:
                print(f"Error: Unknown config section '[{key}]'", file=sys.stderr)
                return
        # Apply shared section
        if "shared" in table and isinstance(table["shared"], dict):
            self._apply_section(table["shared"], _SHARED_KEYS)
        # Apply thresholds section (catch-all)
        if "thresholds" in table and isinstance(table["thresholds"], dict):
            self._apply_section(table["thresholds"], _THRESHOLD_KEYS)
        # Apply language-specific section
        section_name = lang.config_section
        if section_name in table and isinstance(table[section_name], dict):
            self._apply_language_section(table[section_name], lang)

    def _apply_section(self, section: dict, valid_keys: set[str]) -> None:
        for key, value in section.items():
            if key not in valid_keys:
                continue
            field_name = _KEY_TO_FIELD.get(key, key)
            if hasattr(self, field_name) and isinstance(value, int) and value >= 0:
                setattr(self, field_name, value)

    def _apply_language_section(self, section: dict, lang: Language) -> None:
        key_map = _LANGUAGE_KEY_MAPS.get(lang.config_section, {})
        for key, value in section.items():
            field_name = key_map.get(key, _KEY_TO_FIELD.get(key, key))
            if hasattr(self, field_name) and isinstance(value, int) and value >= 0:
                setattr(self, field_name, value)


# Key aliases matching Rust config exactly
_KEY_TO_FIELD: dict[str, str] = {
    "positional_args": "arguments_positional",
    "keyword_only_args": "arguments_keyword_only",
    "max_indentation": "max_indentation_depth",
    "local_variables": "local_variables_per_function",
    "decorators_per_function": "annotations_per_function",
    "attributes_per_function": "annotations_per_function",
    "arguments": "arguments_per_function",
    "classes_per_file": "concrete_types_per_file",
    "types_per_file": "concrete_types_per_file",
}

_SHARED_KEYS = {
    "statements_per_file", "functions_per_file", "interface_types_per_file",
    "concrete_types_per_file", "types_per_file", "imported_names_per_file",
    "cycle_size", "indirect_dependencies", "dependency_depth",
}

_THRESHOLD_KEYS = {
    "statements_per_function", "methods_per_class", "statements_per_file",
    "functions_per_file", "arguments_per_function", "arguments_positional",
    "arguments_keyword_only", "max_indentation_depth", "interface_types_per_file",
    "concrete_types_per_file", "classes_per_file", "nested_function_depth",
    "returns_per_function", "return_values_per_function", "branches_per_function",
    "local_variables_per_function", "imported_names_per_file",
    "statements_per_try_block", "boolean_parameters", "annotations_per_function",
    "calls_per_function", "cycle_size", "indirect_dependencies", "dependency_depth",
}

_PYTHON_KEYS: dict[str, str] = {
    "statements_per_function": "statements_per_function",
    "positional_args": "arguments_positional",
    "keyword_only_args": "arguments_keyword_only",
    "max_indentation": "max_indentation_depth",
    "branches_per_function": "branches_per_function",
    "local_variables": "local_variables_per_function",
    "methods_per_class": "methods_per_class",
    "returns_per_function": "returns_per_function",
    "return_values_per_function": "return_values_per_function",
    "nested_function_depth": "nested_function_depth",
    "statements_per_try_block": "statements_per_try_block",
    "boolean_parameters": "boolean_parameters",
    "decorators_per_function": "annotations_per_function",
    "calls_per_function": "calls_per_function",
    "imported_names_per_file": "imported_names_per_file",
    "statements_per_file": "statements_per_file",
    "functions_per_file": "functions_per_file",
    "interface_types_per_file": "interface_types_per_file",
    "concrete_types_per_file": "concrete_types_per_file",
    "types_per_file": "concrete_types_per_file",
    "cycle_size": "cycle_size",
    "indirect_dependencies": "indirect_dependencies",
    "dependency_depth": "dependency_depth",
}

# PHP, JS, TS use the same field names as their config keys
_GENERIC_KEYS: dict[str, str] = {
    k: k for k in Config.__dataclass_fields__
}
_GENERIC_KEYS.update(_KEY_TO_FIELD)

_LANGUAGE_KEY_MAPS: dict[str, dict[str, str]] = {
    "python": _PYTHON_KEYS,
    "php": _GENERIC_KEYS,
    "javascript": _GENERIC_KEYS,
    "typescript": _GENERIC_KEYS,
}


# ---------------------------------------------------------------------------
# GateConfig
# ---------------------------------------------------------------------------

@dataclass
class GateConfig:
    """Quality gate configuration."""
    test_coverage_threshold: int = defaults.GATE["test_coverage_threshold"]
    min_similarity: float = defaults.GATE["min_similarity"]
    duplication_enabled: bool = defaults.GATE["duplication_enabled"]
    orphan_module_enabled: bool = defaults.GATE["orphan_module_enabled"]

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "GateConfig":
        config = cls()
        home = Path.home() / ".kissconfig"
        if home.is_file():
            config._merge_from_file(home)
        local = Path(".kissconfig")
        if local.is_file():
            config._merge_from_file(local)
        if config_path and config_path.is_file():
            config._merge_from_file(config_path)
        return config

    def _merge_from_file(self, path: Path) -> None:
        try:
            content = path.read_text()
            self._merge_from_toml(content)
        except Exception as e:
            print(f"Warning: Failed to read config {path}: {e}", file=sys.stderr)

    def _merge_from_toml(self, content: str) -> None:
        try:
            table = tomllib.loads(content)
        except Exception:
            return
        gate = table.get("gate")
        if not isinstance(gate, dict):
            return
        if "test_coverage_threshold" in gate:
            v = gate["test_coverage_threshold"]
            if isinstance(v, int) and 0 <= v <= 100:
                self.test_coverage_threshold = v
        if "min_similarity" in gate:
            v = gate["min_similarity"]
            if isinstance(v, (int, float)) and 0.0 <= float(v) <= 1.0:
                self.min_similarity = float(v)
        if "duplication_enabled" in gate:
            v = gate["duplication_enabled"]
            if isinstance(v, bool):
                self.duplication_enabled = v
        if "orphan_module_enabled" in gate:
            v = gate["orphan_module_enabled"]
            if isinstance(v, bool):
                self.orphan_module_enabled = v
