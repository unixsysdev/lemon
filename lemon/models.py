"""Data models for lemon — all dataclasses and enums."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

class Language(Enum):
    PYTHON = auto()
    PHP = auto()
    JAVASCRIPT = auto()
    TYPESCRIPT = auto()
    GO = auto()

    @staticmethod
    def from_path(path: Path) -> Optional["Language"]:
        ext = path.suffix.lower()
        return _EXT_MAP.get(ext)

    @property
    def extension(self) -> str:
        return {
            Language.PYTHON: ".py",
            Language.PHP: ".php",
            Language.JAVASCRIPT: ".js",
            Language.TYPESCRIPT: ".ts",
            Language.GO: ".go",
        }[self]

    @property
    def config_section(self) -> str:
        return self.name.lower()


_EXT_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".php": Language.PHP,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".go": Language.GO,
}


# ---------------------------------------------------------------------------
# Parsed file
# ---------------------------------------------------------------------------

@dataclass
class ParsedFile:
    path: Path
    source: str
    source_bytes: bytes  # UTF-8 encoded; tree-sitter offsets index into this
    tree: object  # tree_sitter.Tree
    language: Language


# ---------------------------------------------------------------------------
# Code units
# ---------------------------------------------------------------------------

class CodeUnitKind(Enum):
    MODULE = "module"
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"

    def __str__(self) -> str:
        return self.value


@dataclass
class CodeUnit:
    kind: CodeUnitKind
    name: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int


@dataclass
class CodeDefinition:
    """A code unit definition for test-coverage analysis."""
    name: str
    kind: CodeUnitKind
    file: Path
    line: int
    containing_class: Optional[str] = None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class FunctionMetrics:
    statements: int = 0
    arguments: int = 0
    arguments_positional: int = 0
    arguments_keyword_only: int = 0
    max_indentation: int = 0
    nested_function_depth: int = 0
    returns: int = 0
    branches: int = 0
    local_variables: int = 0
    max_try_block_statements: int = 0
    boolean_parameters: int = 0
    decorators: int = 0
    max_return_values: int = 0
    calls: int = 0
    has_error: bool = False


@dataclass
class ClassMetrics:
    methods: int = 0


@dataclass
class FileMetrics:
    statements: int = 0
    interface_types: int = 0
    concrete_types: int = 0
    imports: int = 0
    functions: int = 0



# ---------------------------------------------------------------------------
# Violation
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    file: Path
    line: int
    unit_name: str
    metric: str
    value: int
    threshold: int
    message: str
    suggestion: str = ""


class ViolationBuilder:
    """Builder pattern matching the Rust ViolationBuilder."""

    def __init__(self, file: Path) -> None:
        self._file = file
        self._line = 0
        self._unit_name = ""
        self._metric = ""
        self._value = 0
        self._threshold = 0
        self._message = ""
        self._suggestion = ""

    def line(self, line: int) -> "ViolationBuilder":
        self._line = line
        return self

    def unit_name(self, name: str) -> "ViolationBuilder":
        self._unit_name = name
        return self

    def metric(self, metric: str) -> "ViolationBuilder":
        self._metric = metric
        return self

    def value(self, value: int) -> "ViolationBuilder":
        self._value = value
        return self

    def threshold(self, threshold: int) -> "ViolationBuilder":
        self._threshold = threshold
        return self

    def message(self, message: str) -> "ViolationBuilder":
        self._message = message
        return self

    def suggestion(self, suggestion: str) -> "ViolationBuilder":
        self._suggestion = suggestion
        return self

    def build(self) -> Violation:
        return Violation(
            file=self._file,
            line=self._line,
            unit_name=self._unit_name,
            metric=self._metric,
            value=self._value,
            threshold=self._threshold,
            message=self._message,
            suggestion=self._suggestion,
        )


# ---------------------------------------------------------------------------
# Re-exports from analysis_models for backwards compatibility
# ---------------------------------------------------------------------------

from .analysis_models import (  # noqa: F401, E402
    CodeChunk,
    CoveringTest,
    DuplicateCluster,
    DuplicatePair,
    DuplicationConfig,
    GlobalMetrics,
    ShrinkState,
    ShrinkTarget,
    ShrinkViolation,
    TestRefAnalysis,
)

# ---------------------------------------------------------------------------
# Config constants
# ---------------------------------------------------------------------------

NOT_APPLICABLE: int = sys.maxsize
