"""Constrained metric minimization — matching shrink.rs."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

from ..models import GlobalMetrics, ShrinkState, ShrinkTarget, ShrinkViolation

SHRINK_FILE = ".kiss_shrink"


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def save_state(state: ShrinkState, path: Path | None = None) -> None:
    """Save ShrinkState to a TOML file."""
    p = path or Path(SHRINK_FILE)
    content = f"""\
[baseline]
files = {state.baseline.files}
code_units = {state.baseline.code_units}
statements = {state.baseline.statements}
graph_nodes = {state.baseline.graph_nodes}
graph_edges = {state.baseline.graph_edges}

[target]
metric = "{state.target.value}"
value = {state.target_value}
"""
    p.write_text(content)


def load_state(path: Path | None = None) -> ShrinkState | None:
    """Load ShrinkState from a TOML file."""
    p = path or Path(SHRINK_FILE)
    if not p.is_file():
        return None
    try:
        data = tomllib.loads(p.read_text())
    except Exception as e:
        print(f"Error loading shrink state: {e}", file=sys.stderr)
        return None
    return _parse_shrink_data(data)


def _parse_shrink_data(data: dict) -> ShrinkState | None:
    """Parse validated TOML data into ShrinkState."""
    bl = data.get("baseline")
    tgt = data.get("target")
    if not bl or not tgt:
        return None
    baseline = GlobalMetrics(
        files=bl["files"],
        code_units=bl["code_units"],
        statements=bl["statements"],
        graph_nodes=bl["graph_nodes"],
        graph_edges=bl["graph_edges"],
    )
    return ShrinkState(
        baseline=baseline,
        target=ShrinkTarget.from_str(tgt["metric"]),
        target_value=tgt["value"],
    )


# ---------------------------------------------------------------------------
# Shrink check
# ---------------------------------------------------------------------------

def check_shrink(state: ShrinkState, current: GlobalMetrics) -> list[ShrinkViolation]:
    """Check current metrics against shrink constraints.

    Rules:
    - Target metric must be <= target_value
    - All other metrics must be <= their baseline values (no regression)
    """
    violations: list[ShrinkViolation] = []

    for metric in ShrinkTarget:
        current_val = metric.get(current)
        if metric == state.target:
            # Target must meet the target value
            if current_val > state.target_value:
                violations.append(ShrinkViolation(
                    metric=metric.value,
                    current=current_val,
                    limit=state.target_value,
                    is_target=True,
                ))
        else:
            # Other metrics must not regress past baseline
            baseline_val = metric.get(state.baseline)
            if current_val > baseline_val:
                violations.append(ShrinkViolation(
                    metric=metric.value,
                    current=current_val,
                    limit=baseline_val,
                    is_target=False,
                ))

    return violations


# ---------------------------------------------------------------------------
# CLI start command
# ---------------------------------------------------------------------------

def start_shrink(target_str: str, current: GlobalMetrics) -> ShrinkState:
    """Parse 'metric=value' and create a new ShrinkState.

    Validates that the target value is less than the current value.
    """
    parts = target_str.split("=", 1)
    if len(parts) != 2:
        raise ValueError(f"Expected 'metric=value', got '{target_str}'")

    metric_name = parts[0].strip()
    try:
        value = int(parts[1].strip())
    except ValueError:
        raise ValueError(f"Target value must be an integer, got '{parts[1].strip()}'")

    target = ShrinkTarget.from_str(metric_name)
    current_val = target.get(current)

    if value >= current_val:
        raise ValueError(
            f"Target {target.value}={value} must be less than current "
            f"value {current_val}"
        )

    state = ShrinkState(
        baseline=current,
        target=target,
        target_value=value,
    )
    save_state(state)
    return state
