# 🍋 Lemon

**Language-agnostic code complexity analyzer.** Lemon statically analyzes your codebase and reports violations against configurable metric thresholds — helping teams enforce consistent code quality without runtime overhead.
## Supported Languages

| Language | Extensions | Parser |
|---|---|---|
| Python | `.py` | tree-sitter-python |
| PHP | `.php` | tree-sitter-php |
| JavaScript | `.js`, `.jsx`, `.mjs` | tree-sitter-javascript |
| TypeScript | `.ts`, `.tsx` | tree-sitter-typescript |

All languages receive **identical analysis depth** — the same 14 function-level metrics, 5 file-level metrics, 3 graph metrics, duplication detection, and test coverage analysis.

## Installation

```bash
cd kiss_py
pip install -e .
```

This installs the `lemon` CLI tool.

## Quick Start

```bash
# Analyze current directory
lemon check .

# Analyze only PHP files
lemon check --lang php /path/to/project

# Focus on a specific module
lemon check . --focus src/core/

# Show progress + timing
lemon check --timing .
```

## Commands

### `lemon check` — Run Analysis

The primary command. Discovers files, parses them, computes metrics, builds the dependency graph, detects duplication, and checks test coverage — all in one pass.

```bash
lemon check [PATH] [OPTIONS]

Options:
  --lang [python|php|javascript|typescript]   Filter by language
  --focus PATH          Only report violations in this subtree
  --all                 Skip the test coverage gate
  --ignore PREFIX       Ignore paths starting with PREFIX (repeatable)
  --timing              Show phase timing breakdown
  --config PATH         Use a specific .kissconfig file
```

**Output format:**
```
  ▸ Scanning /path/to/project …
  ▸ Parsing 1470 files …
  ▸ Running metrics …
  ▸ Building dependency graph …
  ▸ Checking duplication …
  ▸ Analyzing test coverage …
Analyzed: 1470 files, 7369 code_units, 29764 statements, 1470 graph_nodes, 0 graph_edges
VIOLATION:statements_per_function:path/to/file.py:42:my_func: Function 'my_func' has 50 statements (threshold: 35) Break into smaller, focused functions.
```

Exit code 0 = clean, 1 = violations found.

---

### `lemon stats` — Metric Distribution

Show percentile distribution (p50, p75, p90, p95, p99, max) for all metrics.

```bash
lemon stats .
lemon stats --all=10 .        # Top 10 outliers per metric
lemon stats --table .          # Per-unit wide-format table
```

---

### `lemon dry` — Duplication Report

Show raw duplication pairs with similarity percentages.

```bash
lemon dry .
lemon dry . --min-sim 0.8      # Only show ≥80% similar
lemon dry . --filter path/file.py  # Filter to specific file
```

---

### `lemon viz` — Dependency Graph

Generate a dependency graph visualization in Mermaid, DOT, or Markdown format.

```bash
lemon viz graph.mmd .          # Mermaid flowchart
lemon viz graph.dot .          # Graphviz DOT
lemon viz graph.md .           # Markdown with embedded Mermaid
```

---

### `lemon show-tests` — Test Coverage Map

Show which definitions are covered by tests.

```bash
lemon show-tests .
lemon show-tests . --untested  # Also show untested definitions
```

**Output format:**
```
TEST:path/to/module.py:my_function
UNTESTED:path/to/module.py:42:orphan_function
```

---

### `lemon clamp` — Generate Config

Generate a `.kissconfig` from current codebase stats (p95-clamped thresholds).

```bash
lemon clamp . > .kissconfig
```

---

### `lemon rules` — Show Rules

Dump all metric rules and definitions.

```bash
lemon rules
lemon rules --lang python
lemon rules --defaults        # Show built-in defaults
```

---

### `lemon config` — Show Config

Display the effective configuration after merging all config files.

```bash
lemon config
lemon config --defaults
```

---

### `lemon shrink` — Constrained Minimization

Start a shrink session to enforce that a metric only goes down.

```bash
lemon shrink start statements=1500 .
lemon shrink check .     # Fails if statements increased
```

## Metrics

### Function-Level (14 metrics)

| Metric | Description | Default Threshold |
|---|---|---|
| `statements_per_function` | Total statements in function body | 35 |
| `arguments_positional` | Positional parameters | 5 |
| `arguments_keyword_only` | Keyword-only parameters | 5 |
| `max_indentation_depth` | Deepest nesting level | 4 |
| `nested_function_depth` | Nested function/closure depth | 2 |
| `returns_per_function` | Number of return statements | 5 |
| `return_values_per_function` | Max values in a single return (tuple) | 3 |
| `branches_per_function` | If/elif/case branches | 10 |
| `local_variables_per_function` | Distinct local variable names | 10 |
| `statements_per_try_block` | Statements inside try blocks | 10 |
| `boolean_parameters` | Parameters with boolean defaults | 2 |
| `annotations_per_function` | Decorators/attributes | 3 |
| `calls_per_function` | Function/method calls | 15 |
| `methods_per_class` | Methods in a class | 10 |

### File-Level (5 metrics)

| Metric | Description | Default Threshold |
|---|---|---|
| `statements_per_file` | Total statements in file | 300 |
| `functions_per_file` | Total functions/methods | 20 |
| `imported_names_per_file` | Number of imported names | 15 |
| `interface_types_per_file` | Protocols/ABCs/interfaces | 5 |
| `concrete_types_per_file` | Concrete classes | 5 |

### Graph-Level (3 metrics)

| Metric | Description | Default Threshold |
|---|---|---|
| `cycle_size` | Modules in an import cycle | 3 |
| `indirect_dependencies` | Transitive (non-direct) deps | 20 |
| `dependency_depth` | Longest dependency chain | 6 |

### Quality Gates

| Gate | Description | Default |
|---|---|---|
| `test_coverage_threshold` | Minimum % of definitions with test references | 90% |
| `min_similarity` | Minimum similarity to flag as duplicate | 70% |
| `duplication_enabled` | Enable/disable duplication analysis | true |
| `orphan_module_enabled` | Detect modules with 0 fan-in and 0 fan-out | true |

## Configuration

Lemon reads `.kissconfig` files in TOML format, cascading in this order:

1. `~/.kissconfig` (global defaults)
2. `./.kissconfig` (project-level)
3. `--config PATH` (explicit override)

### Example `.kissconfig`

```toml
# Shared thresholds for all languages
[thresholds]
statements_per_function = 40
annotations_per_function = 9

# Language-specific overrides
[python]
max_indentation_depth = 5

[php]
statements_per_function = 50

# Quality gates
[gate]
test_coverage_threshold = 80
min_similarity = 0.85
duplication_enabled = true
```

## Architecture

```
lemon/
├── cli.py              # Click CLI — all subcommands
├── config.py           # .kissconfig TOML parsing (cascading)
├── defaults.py         # Built-in threshold defaults per language
├── models.py           # Data models (FunctionMetrics, Violation, etc.)
├── analysis_models.py  # Duplication, shrink, test coverage models
├── output.py           # Formatting (violations, stats tables, summaries)
├── rules.py            # Rule/definition dumping
└── engine/
    ├── ast_helpers.py   # Shared tree-sitter AST utilities
    ├── discovery.py     # File discovery + test file detection
    ├── duplication.py   # SequenceMatcher-based duplication detection
    ├── graph.py         # Dependency graph (networkx DiGraph)
    ├── metrics.py       # All metric computation from AST nodes
    ├── parser.py        # Tree-sitter parsing (4 language grammars)
    ├── shrink.py        # Constrained metric minimization
    ├── test_refs.py     # Static test reference coverage analysis
    ├── units.py         # Code unit extraction
    ├── viz.py           # Mermaid/DOT graph visualization
    └── queries/         # Tree-sitter SCM query files
        ├── python.scm
        ├── php.scm
        ├── javascript.scm
        └── typescript.scm
```

## Analysis Pipeline

```
Discovery → Parsing → Metrics → Graph → Duplication → Test Coverage → Report
```

1. **Discovery** — recursively finds source files, filters by language and ignore prefixes
2. **Parsing** — tree-sitter parses each file into an AST
3. **Metrics** — walks each AST computing function/file/class metrics, emitting violations
4. **Graph** — builds module dependency graph, checks for cycles, indirect deps, depth
5. **Duplication** — extracts function/method bodies, computes pairwise similarity, clusters duplicates
6. **Test Coverage** — identifies test files, collects referenced identifiers, checks definition coverage
7. **Report** — formats and prints violations, summary, and gate failures

## License

MIT
