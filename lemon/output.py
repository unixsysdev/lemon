"""Output formatting — VIOLATION, GATE_FAILED, stats tables, summary lines."""

from __future__ import annotations

import math
from pathlib import Path

from .models import DuplicateCluster, GlobalMetrics, ShrinkViolation, Violation


# ---------------------------------------------------------------------------
# Violation formatting
# ---------------------------------------------------------------------------

def format_violation(v: Violation) -> str:
    """Format a violation in the canonical VIOLATION: format."""
    parts = [f"VIOLATION:{v.metric}:{v.file}:{v.line}:{v.unit_name}: {v.message}"]
    if v.suggestion:
        parts[0] += f" {v.suggestion}"
    return parts[0]


def format_duplication_violation(cluster: DuplicateCluster) -> str:
    """Format a duplication cluster as a VIOLATION line."""
    first = cluster.chunks[0]
    locations = ", ".join(
        f"{c.file}:{c.start_line}" for c in cluster.chunks
    )
    pct = int(cluster.similarity * 100)
    n = len(cluster.chunks)
    return (
        f"VIOLATION:duplication:{first.file}:{first.start_line}:{first.name}: "
        f"{pct}% similar, {n} copies: [{locations}]. "
        f"Factor out repeated patterns into shared functions."
    )


# ---------------------------------------------------------------------------
# Gate failure formatting
# ---------------------------------------------------------------------------

def format_coverage_gate_failure(
    total_defs: int,
    unreferenced_count: int,
    pct: int,
    threshold: int,
) -> str:
    """Format GATE_FAILED for test coverage."""
    return (
        f"GATE_FAILED:test_coverage: {pct}% (threshold: {threshold}%). "
        f"{unreferenced_count} of {total_defs} definitions lack test references."
    )


def format_shrink_violation(sv: ShrinkViolation) -> str:
    return str(sv)


# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------

def format_summary(metrics: GlobalMetrics) -> str:
    return (
        f"Analyzed: {metrics.files} files, {metrics.code_units} code_units, "
        f"{metrics.statements} statements, {metrics.graph_nodes} graph_nodes, "
        f"{metrics.graph_edges} graph_edges"
    )


# ---------------------------------------------------------------------------
# Stats table
# ---------------------------------------------------------------------------

def percentile(sorted_values: list[int], p: float) -> int:
    """Compute percentile matching Rust's rounding behavior.

    Uses the nearest-rank method: ceil(p/100 * N) - 1, clamped to valid range.
    """
    if not sorted_values:
        return 0
    n = len(sorted_values)
    rank = math.ceil(p / 100.0 * n) - 1
    rank = max(0, min(rank, n - 1))
    return sorted_values[rank]


def format_stats_table(summaries: list[tuple[str, list[int]]]) -> str:
    """Format a stats table with percentile distributions.

    Each entry in summaries is (metric_id, sorted_values).
    """
    header = f"{'metric_id':<40} {'N':>5} {'p50':>5} {'p90':>5} {'p95':>5} {'p99':>5} {'max':>5}"
    separator = "-" * len(header)
    lines = [header, separator]

    for metric_id, values in summaries:
        if not values:
            continue
        n = len(values)
        p50 = percentile(values, 50)
        p90 = percentile(values, 90)
        p95 = percentile(values, 95)
        p99 = percentile(values, 99)
        mx = values[-1] if values else 0
        lines.append(
            f"{metric_id:<40} {n:>5} {p50:>5} {p90:>5} {p95:>5} {p99:>5} {mx:>5}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Final status
# ---------------------------------------------------------------------------

def print_violations(violations: list[Violation]) -> None:
    for v in violations:
        print(format_violation(v))


def print_duplicates(clusters: list[DuplicateCluster]) -> None:
    for c in clusters:
        print(format_duplication_violation(c))


def print_final_status(violations: list[Violation],
                       clusters: list[DuplicateCluster]) -> bool:
    """Print final status and return True if no violations."""
    if not violations and not clusters:
        print("NO VIOLATIONS")
        return True
    return False


def format_candidate_list(candidates: list[str], max_display: int = 3) -> str:
    """Format a list of test candidates, truncating if needed."""
    if len(candidates) <= max_display:
        return ", ".join(candidates)
    shown = ", ".join(candidates[:max_display])
    return f"{shown}, +{len(candidates) - max_display} more"
