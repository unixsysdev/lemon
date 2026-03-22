# Lemon — TODO

## Feature Gaps (vs Rust kiss)

- [ ] **`mimic` command** — write generated .kissconfig to a file (`--out` option), not just stdout like `clamp`
- [ ] **`viz --zoom`** — graph coarsening via Leiden community detection for large dependency graphs
- [ ] **`show-tests` coverage map** — list *which specific test functions* cover each definition (not just tested/untested)

## Performance

- [ ] **MinHash/LSH duplication** — replace SequenceMatcher (O(n²)) with MinHash+LSH for large codebases (>2000 files)
- [ ] **Incremental caching** — cache parse trees and metrics to avoid re-analyzing unchanged files

## Polish

- [ ] **`stats --all` without `=`** — `--all 5` eats the path argument; currently requires `--all=5`
- [ ] **Graph edges** — dependency graph shows 0 edges on lemon's own code (import resolution needs work)
- [ ] **Test coverage gate** — currently disabled in .kissconfig; add real tests to reach 90%
