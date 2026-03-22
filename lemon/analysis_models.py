"""Analysis-specific models — duplication, shrink, and test-ref types."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .models import CodeDefinition, CodeUnitKind


# ---------------------------------------------------------------------------
# Global metrics
# ---------------------------------------------------------------------------

@dataclass
class GlobalMetrics:
    files: int = 0
    code_units: int = 0
    statements: int = 0
    graph_nodes: int = 0
    graph_edges: int = 0


# ---------------------------------------------------------------------------
# Duplication
# ---------------------------------------------------------------------------

@dataclass
class CodeChunk:
    file: Path
    name: str
    start_line: int
    end_line: int
    source: str


@dataclass
class DuplicatePair:
    chunk1: CodeChunk
    chunk2: CodeChunk
    similarity: float


@dataclass
class DuplicateCluster:
    chunks: list[CodeChunk]
    similarity: float


@dataclass
class DuplicationConfig:
    min_lines: int = 5
    min_similarity: float = 0.7
    num_hashes: int = 128
    num_bands: int = 16


# ---------------------------------------------------------------------------
# Shrink
# ---------------------------------------------------------------------------

from enum import Enum


class ShrinkTarget(Enum):
    FILES = "files"
    CODE_UNITS = "code_units"
    STATEMENTS = "statements"
    GRAPH_NODES = "graph_nodes"
    GRAPH_EDGES = "graph_edges"

    def get(self, metrics: GlobalMetrics) -> int:
        return {
            ShrinkTarget.FILES: metrics.files,
            ShrinkTarget.CODE_UNITS: metrics.code_units,
            ShrinkTarget.STATEMENTS: metrics.statements,
            ShrinkTarget.GRAPH_NODES: metrics.graph_nodes,
            ShrinkTarget.GRAPH_EDGES: metrics.graph_edges,
        }[self]

    @staticmethod
    def from_str(s: str) -> "ShrinkTarget":
        try:
            return ShrinkTarget(s)
        except ValueError:
            valid = ", ".join(t.value for t in ShrinkTarget)
            raise ValueError(f"Unknown metric: '{s}'. Valid: {valid}") from None


@dataclass
class ShrinkState:
    baseline: GlobalMetrics
    target: ShrinkTarget
    target_value: int


@dataclass
class ShrinkViolation:
    metric: str
    current: int
    limit: int
    is_target: bool

    def __str__(self) -> str:
        reason = "(target not met)" if self.is_target else "(constraint exceeded baseline)"
        return f"GATE_FAILED:shrink: {self.metric} {self.current} > {self.limit} {reason}"


# ---------------------------------------------------------------------------
# Test refs
# ---------------------------------------------------------------------------

CoveringTest = tuple[Path, str]  # (test_file, test_function_name)


@dataclass
class TestRefAnalysis:
    definitions: list[CodeDefinition] = field(default_factory=list)
    test_references: set[str] = field(default_factory=set)
    unreferenced: list[CodeDefinition] = field(default_factory=list)
    coverage_map: dict[tuple[Path, str], list[CoveringTest]] = field(default_factory=dict)
